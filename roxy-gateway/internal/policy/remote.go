package policy

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
)

const evaluatorTimeout = 15 * time.Second

type RemoteClient struct {
	httpClient *http.Client
	url        string
}

func NewRemoteClient(url string) *RemoteClient {
	return &RemoteClient{
		httpClient: &http.Client{Timeout: evaluatorTimeout},
		url:        url,
	}
}

type remoteRequest struct {
	Rules  []string `json:"rules"`
	Prompt string   `json:"prompt"`
}

type remoteResponse struct {
	Allowed          bool   `json:"allowed"`
	ViolatedPriority *int   `json:"violatedPriority"`
	Reason           string `json:"reason"`
}

func (c *RemoteClient) Evaluate(ctx context.Context, in Input) (Result, error) {
	body, err := json.Marshal(remoteRequest{
		Rules:  ruleInstructions(in.MCP.Rules),
		Prompt: agentPrompt(in.Action, in.Payload),
	})
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url, bytes.NewReader(body))
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	req.Header.Set("Content-Type", "application/json")

	res, err := c.httpClient.Do(req)
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(res.Body)
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return Result{}, fmt.Errorf("%w: evaluator status %d", ErrUnavailable, res.StatusCode)
	}

	var parsed remoteResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}

	out := Result{
		Allowed: parsed.Allowed,
		Reason:  parsed.Reason,
	}
	if !parsed.Allowed && parsed.ViolatedPriority != nil {
		out.ViolatedRule = ruleFromEvaluator(in.MCP.Rules, *parsed.ViolatedPriority)
	}
	return out, nil
}

func ruleInstructions(rules []mcp.Rule) []string {
	out := make([]string, 0, len(rules))
	for _, r := range rules {
		if r.Instruction == "" {
			continue
		}
		out = append(out, r.Instruction)
	}
	return out
}

func agentPrompt(action string, payload []byte) string {
	action = strings.TrimSpace(action)
	raw := bytes.TrimSpace(payload)
	if len(raw) == 0 || bytes.Equal(raw, []byte("null")) {
		return action
	}

	var asString string
	if err := json.Unmarshal(raw, &asString); err == nil {
		return joinPrompt(action, strings.TrimSpace(asString))
	}

	var obj map[string]any
	if err := json.Unmarshal(raw, &obj); err == nil {
		if p, ok := obj["prompt"].(string); ok {
			if p = strings.TrimSpace(p); p != "" {
				return p
			}
		}
		if p, ok := obj["intent"].(string); ok {
			if p = strings.TrimSpace(p); p != "" {
				return joinPrompt(action, p)
			}
		}
	}

	return joinPrompt(action, string(raw))
}

func joinPrompt(action, detail string) string {
	switch {
	case action == "":
		return detail
	case detail == "" || detail == action:
		return action
	default:
		return action + ": " + detail
	}
}
