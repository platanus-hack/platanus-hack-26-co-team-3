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

const systemPrompt = `You are Roxy, a security gateway that decides whether an agent may call an MCP.
Compare the agent's action and payload against the MCP rules (priority order, lower number first).
A rule is violated when the agent's intended operation would break the rule's instruction.
Respond with a single JSON object only:
{"allowed": true or false, "violatedPriority": <int or null>, "reason": "<short explanation>"}
If allowed is true, violatedPriority must be null.
If allowed is false, violatedPriority must be the priority of the first matching rule, or null if you must deny but cannot map a rule.`

type Client struct {
	httpClient *http.Client
	baseURL    string
	apiKey     string
	model      string
}

func NewClient(baseURL, apiKey, model string) *Client {
	return &Client{
		httpClient: &http.Client{Timeout: 15 * time.Second},
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		model:      model,
	}
}

type chatRequest struct {
	Model          string            `json:"model"`
	Temperature    float64           `json:"temperature"`
	ResponseFormat map[string]string `json:"response_format"`
	Messages       []chatMessage     `json:"messages"`
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

type modelDecision struct {
	Allowed          bool   `json:"allowed"`
	ViolatedPriority *int   `json:"violatedPriority"`
	Reason           string `json:"reason"`
}

func (c *Client) Evaluate(ctx context.Context, in Input) (Result, error) {
	body, err := json.Marshal(chatRequest{
		Model:       c.model,
		Temperature: 0,
		ResponseFormat: map[string]string{
			"type": "json_object",
		},
		Messages: []chatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: userPrompt(in)},
		},
	})
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/chat/completions", bytes.NewReader(body))
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("HTTP-Referer", "http://localhost")

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
		return Result{}, fmt.Errorf("%w: openrouter status %d", ErrUnavailable, res.StatusCode)
	}

	var parsed chatResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}
	if len(parsed.Choices) == 0 || strings.TrimSpace(parsed.Choices[0].Message.Content) == "" {
		return Result{}, fmt.Errorf("%w: empty choices", ErrUnavailable)
	}

	var decision modelDecision
	if err := json.Unmarshal([]byte(parsed.Choices[0].Message.Content), &decision); err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}

	out := Result{
		Allowed: decision.Allowed,
		Reason:  decision.Reason,
	}
	if !decision.Allowed && decision.ViolatedPriority != nil {
		out.ViolatedRule = ruleByPriority(in.MCP.Rules, *decision.ViolatedPriority)
	}
	return out, nil
}

func userPrompt(in Input) string {
	var b strings.Builder
	fmt.Fprintf(&b, "MCP name: %s\n", in.MCP.Name)
	fmt.Fprintf(&b, "MCP description: %s\n", in.MCP.Description)
	b.WriteString("Rules (lower priority number is evaluated first):\n")
	if len(in.MCP.Rules) == 0 {
		b.WriteString("- (none)\n")
	}
	for _, rule := range in.MCP.Rules {
		fmt.Fprintf(&b, "- priority %d: %s\n", rule.Priority, rule.Instruction)
	}
	fmt.Fprintf(&b, "Agent: %s\n", in.AccessedBy)
	fmt.Fprintf(&b, "Action: %s\n", in.Action)
	fmt.Fprintf(&b, "Payload: %s\n", string(in.Payload))
	return b.String()
}

func ruleByPriority(rules []mcp.Rule, priority int) *mcp.Rule {
	for i := range rules {
		if rules[i].Priority == priority {
			rule := rules[i]
			return &rule
		}
	}
	return nil
}
