package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
)

const (
	anthropicVersion = "2023-06-01"
	agentTimeout     = 60 * time.Second
	agentMaxTokens   = 2048
	agentMaxRounds   = 6
)

const agentSystem = `You fulfill an already-approved agent request against an MCP server.
You MUST use the http_request tool. Do not only describe the call.
Auth headers are added automatically; do not send credentials.
url must stay on the MCP base URL host.

If protocol is "mcp", speak Streamable HTTP / JSON-RPC against the base URL (hosted MCP is POST https://roxygt.lat/mcp — that MCP talks to Atlas; do not append another /mcp):
1) POST initialize: {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"roxy","version":"1.0"}}}
2) Read mcp-session-id from the tool result headers and pass it as sessionId on later calls
3) POST notifications/initialized: {"jsonrpc":"2.0","method":"notifications/initialized"} with that sessionId
4) Then tools/list or tools/call. find requires connectionId "preconfigured", plus database/collection/filter
5) Stop after you have the data that answers the agent

Choose method, url/path, body, and sessionId from the MCP description, protocol, and the agent's action+payload.`

type MCPAgent interface {
	CallMCP(ctx context.Context, doc *mcp.MCP, action string, payload []byte) (Upstream, error)
}

type AnthropicAgent struct {
	httpClient *http.Client
	baseURL    string
	apiKey     string
	model      string
	caller     MCPCaller
}

func NewAnthropicAgent(baseURL, apiKey, model string, caller MCPCaller) *AnthropicAgent {
	if model == "" {
		model = "claude-sonnet-5"
	}
	return &AnthropicAgent{
		httpClient: &http.Client{Timeout: agentTimeout},
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		model:      model,
		caller:     caller,
	}
}

func (a *AnthropicAgent) CallMCP(ctx context.Context, doc *mcp.MCP, action string, payload []byte) (Upstream, error) {
	user := fmt.Sprintf(
		"MCP name: %s\nDescription: %s\nProtocol: %s\nBase URL: %s\nAgent action: %s\nAgent payload: %s\n",
		doc.Name, doc.Description, doc.Server.Protocol, doc.Server.URL, action, string(payload),
	)
	log.Printf("mcp agent start name=%s protocol=%s url=%s action=%s auth=%s",
		doc.Name, doc.Server.Protocol, doc.Server.URL, action, doc.Authorization.Type)
	messages := []map[string]any{
		{"role": "user", "content": user},
	}

	var last *Upstream
	var lastErr error
	for round := 0; round < agentMaxRounds; round++ {
		stop, content, err := a.round(ctx, messages, last == nil)
		if err != nil {
			log.Printf("mcp agent round=%d anthropic_err=%v", round, err)
			return Upstream{}, err
		}
		toolUses := toolUseBlocks(content)
		log.Printf("mcp agent round=%d stop=%s tools=%d text=%q", round, stop, len(toolUses), trimLog(contentText(content), 240))
		if len(toolUses) == 0 {
			if last != nil {
				return *last, nil
			}
			if lastErr != nil {
				return Upstream{}, lastErr
			}
			txt := contentText(content)
			if txt == "" {
				txt = "(empty model content)"
			}
			return Upstream{}, fmt.Errorf("%w: model did not complete the MCP request stop=%s url=%s: %s", policy.ErrPlan, stop, doc.Server.URL, trimLog(txt, 300))
		}

		messages = append(messages, map[string]any{
			"role":    "assistant",
			"content": content,
		})
		var toolResults []map[string]any
		for _, tu := range toolUses {
			up, callErr := a.execTool(ctx, doc, tu.Input)
			if callErr != nil {
				log.Printf("mcp agent round=%d invoke_err=%v input=%s", round, callErr, trimLog(string(tu.Input), 240))
				lastErr = callErr
				toolResults = append(toolResults, map[string]any{
					"type":        "tool_result",
					"tool_use_id": tu.ID,
					"is_error":    true,
					"content":     callErr.Error(),
				})
				continue
			}
			log.Printf("mcp agent round=%d invoke_ok status=%d ct=%s bytes=%d handshake=%v", round, up.StatusCode, up.ContentType, len(up.Body), isMCPHandshake(tu.Input))
			if !isMCPHandshake(tu.Input) {
				cp := up
				last = &cp
			}
			resultPayload, _ := json.Marshal(map[string]any{
				"status":  up.StatusCode,
				"headers": map[string]string{"mcp-session-id": headerValue(up, "Mcp-Session-Id")},
				"body":    bodyForModel(up),
			})
			toolResults = append(toolResults, map[string]any{
				"type":        "tool_result",
				"tool_use_id": tu.ID,
				"content":     string(resultPayload),
			})
		}
		messages = append(messages, map[string]any{
			"role":    "user",
			"content": toolResults,
		})
		if stop != "tool_use" && last != nil {
			return *last, nil
		}
	}
	if last != nil {
		return *last, nil
	}
	if lastErr != nil {
		return Upstream{}, lastErr
	}
	return Upstream{}, fmt.Errorf("%w: no MCP response", policy.ErrPlan)
}

func (a *AnthropicAgent) execTool(ctx context.Context, doc *mcp.MCP, input json.RawMessage) (Upstream, error) {
	plan, err := normalizePlan(doc.Server.URL, input)
	if err != nil {
		return Upstream{}, err
	}
	return a.caller.Invoke(ctx, doc, plan)
}

type toolUse struct {
	ID    string
	Input json.RawMessage
}

func toolUseBlocks(content []any) []toolUse {
	var out []toolUse
	for _, raw := range content {
		block, ok := raw.(map[string]any)
		if !ok || block["type"] != "tool_use" {
			continue
		}
		id, _ := block["id"].(string)
		input, _ := json.Marshal(block["input"])
		out = append(out, toolUse{ID: id, Input: input})
	}
	return out
}

func isMCPHandshake(input json.RawMessage) bool {
	var parsed struct {
		Body struct {
			Method string `json:"method"`
		} `json:"body"`
	}
	if err := json.Unmarshal(input, &parsed); err != nil {
		return false
	}
	switch parsed.Body.Method {
	case "initialize", "notifications/initialized", "tools/list", "ping":
		return true
	default:
		return false
	}
}

func contentText(content []any) string {
	var parts []string
	for _, raw := range content {
		block, ok := raw.(map[string]any)
		if !ok || block["type"] != "text" {
			continue
		}
		if s, ok := block["text"].(string); ok && strings.TrimSpace(s) != "" {
			parts = append(parts, s)
		}
	}
	return strings.Join(parts, " ")
}

func trimLog(s string, n int) string {
	s = strings.ReplaceAll(s, "\n", " ")
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

func bodyForModel(up Upstream) string {
	raw := strings.TrimSpace(string(up.Body))
	if i := strings.Index(raw, "data:"); i >= 0 {
		line := strings.TrimSpace(raw[i+len("data:"):])
		if j := strings.Index(line, "\n"); j >= 0 {
			line = strings.TrimSpace(line[:j])
		}
		if json.Valid([]byte(line)) {
			return line
		}
	}
	return string(up.Body)
}

func (a *AnthropicAgent) round(ctx context.Context, messages []map[string]any, forceTool bool) (stop string, content []any, err error) {
	payload := map[string]any{
		"model":      a.model,
		"max_tokens": agentMaxTokens,
		"system":     agentSystem,
		"output_config": map[string]string{
			"effort": "low",
		},
		"tools": []map[string]any{
			{
				"name":        "http_request",
				"description": "HTTP call to the MCP. Auth is injected. Stay on the MCP host.",
				"input_schema": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"method":    map[string]any{"type": "string", "enum": []string{"GET", "POST", "PUT", "PATCH", "DELETE"}},
						"url":       map[string]any{"type": "string"},
						"body":      map[string]any{"type": "object"},
						"sessionId": map[string]any{"type": "string", "description": "Mcp-Session-Id from initialize"},
					},
					"required": []string{"method", "url"},
				},
			},
		},
		"messages": messages,
	}
	if forceTool {
		payload["tool_choice"] = map[string]string{"type": "any"}
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", nil, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.baseURL+"/v1/messages", bytes.NewReader(body))
	if err != nil {
		return "", nil, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	req.Header.Set("x-api-key", a.apiKey)
	req.Header.Set("anthropic-version", anthropicVersion)
	req.Header.Set("Content-Type", "application/json")

	res, err := a.httpClient.Do(req)
	if err != nil {
		return "", nil, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(res.Body)
	if err != nil {
		return "", nil, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return "", nil, fmt.Errorf("%w: anthropic status %d: %s", policy.ErrPlan, res.StatusCode, trimLog(string(raw), 400))
	}
	var parsed struct {
		StopReason string `json:"stop_reason"`
		Content    []any  `json:"content"`
	}
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return "", nil, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	return parsed.StopReason, parsed.Content, nil
}
