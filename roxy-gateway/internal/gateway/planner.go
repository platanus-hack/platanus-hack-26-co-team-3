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
	plannerTimeout   = 45 * time.Second
	plannerMaxTokens = 1024
)

const plannerSystem = `You plan a single HTTP call to an MCP server. You do not call it yourself.
Given the MCP base URL, protocol, description, and the agent's action+payload, decide method, url, and body.
Return a single JSON object only:
{"method":"GET|POST|PUT|PATCH|DELETE","url":"<absolute url or path>","body":<object or null>}
Rules:
- url must stay on the same host as the MCP base URL
- do not invent another host
- do not include Authorization, API keys, or credentials
- prefer the MCP's own HTTP/JSON-RPC style implied by protocol and description
- if unsure, POST to the base URL with a JSON body that represents the action`

type AnthropicPlanner struct {
	httpClient *http.Client
	baseURL    string
	apiKey     string
	model      string
}

func NewAnthropicPlanner(baseURL, apiKey, model string) *AnthropicPlanner {
	if model == "" {
		model = "claude-sonnet-5"
	}
	return &AnthropicPlanner{
		httpClient: &http.Client{Timeout: plannerTimeout},
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		model:      model,
	}
}

func (p *AnthropicPlanner) Plan(ctx context.Context, doc *mcp.MCP, action string, payload []byte) (PlannedCall, error) {
	user := fmt.Sprintf(
		"MCP name: %s\nDescription: %s\nProtocol: %s\nBase URL: %s\nAgent action: %s\nAgent payload: %s\n",
		doc.Name,
		doc.Description,
		doc.Server.Protocol,
		doc.Server.URL,
		action,
		string(payload),
	)
	body, err := json.Marshal(map[string]any{
		"model":      p.model,
		"max_tokens": plannerMaxTokens,
		"system":     plannerSystem,
		"output_config": map[string]string{
			"effort": "low",
		},
		"messages": []map[string]string{
			{"role": "user", "content": user},
		},
	})
	if err != nil {
		return PlannedCall{}, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.baseURL+"/v1/messages", bytes.NewReader(body))
	if err != nil {
		return PlannedCall{}, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	req.Header.Set("x-api-key", p.apiKey)
	req.Header.Set("anthropic-version", anthropicVersion)
	req.Header.Set("Content-Type", "application/json")

	res, err := p.httpClient.Do(req)
	if err != nil {
		return PlannedCall{}, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(res.Body)
	if err != nil {
		return PlannedCall{}, fmt.Errorf("%w: %v", policy.ErrPlan, err)
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return PlannedCall{}, fmt.Errorf("%w: anthropic status %d", policy.ErrPlan, res.StatusCode)
	}

	text := anthropicText(raw)
	if strings.TrimSpace(text) == "" {
		return PlannedCall{}, fmt.Errorf("%w: empty planner content", policy.ErrPlan)
	}
	return normalizePlan(doc.Server.URL, []byte(text))
}

func anthropicText(raw []byte) string {
	var parsed struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return ""
	}
	var b strings.Builder
	for _, block := range parsed.Content {
		if block.Type == "text" {
			b.WriteString(block.Text)
		}
	}
	return b.String()
}
