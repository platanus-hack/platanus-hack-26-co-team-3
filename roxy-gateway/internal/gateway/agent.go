package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
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
	agentMaxRounds   = 4
)

const agentSystem = `You fulfill an already-approved agent request against an MCP server.
You MUST use the http_request tool to talk to the MCP. Do not only describe the call.
Auth headers are added automatically; do not send credentials.
url must stay on the MCP base URL host.
Choose method, path/url, and body from the MCP description, protocol, and the agent's action+payload.`

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
	messages := []map[string]any{
		{"role": "user", "content": user},
	}

	var last *Upstream
	for round := 0; round < agentMaxRounds; round++ {
		stop, content, err := a.round(ctx, messages)
		if err != nil {
			return Upstream{}, err
		}
		toolUses := toolUseBlocks(content)
		if len(toolUses) == 0 {
			if last != nil {
				return *last, nil
			}
			return Upstream{}, fmt.Errorf("%w: model did not call the MCP", policy.ErrPlan)
		}

		messages = append(messages, map[string]any{
			"role":    "assistant",
			"content": content,
		})
		var toolResults []map[string]any
		for _, tu := range toolUses {
			up, callErr := a.execTool(ctx, doc, tu.Input)
			if callErr != nil {
				toolResults = append(toolResults, map[string]any{
					"type":        "tool_result",
					"tool_use_id": tu.ID,
					"is_error":    true,
					"content":     callErr.Error(),
				})
				continue
			}
			cp := up
			last = &cp
			toolResults = append(toolResults, map[string]any{
				"type":        "tool_result",
				"tool_use_id": tu.ID,
				"content":     string(up.Body),
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

func (a *AnthropicAgent) round(ctx context.Context, messages []map[string]any) (stop string, content []any, err error) {
	body, err := json.Marshal(map[string]any{
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
						"method": map[string]any{"type": "string", "enum": []string{"GET", "POST", "PUT", "PATCH", "DELETE"}},
						"url":    map[string]any{"type": "string"},
						"body":   map[string]any{"type": "object"},
					},
					"required": []string{"method", "url"},
				},
			},
		},
		"messages": messages,
	})
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
		return "", nil, fmt.Errorf("%w: anthropic status %d", policy.ErrPlan, res.StatusCode)
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
