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
)

const anthropicVersion = "2023-06-01"

type AnthropicClient struct {
	httpClient *http.Client
	baseURL    string
	apiKey     string
	model      string
}

func NewAnthropicClient(baseURL, apiKey, model string) *AnthropicClient {
	return &AnthropicClient{
		httpClient: &http.Client{Timeout: openRouterTimeout},
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		model:      model,
	}
}

type anthropicRequest struct {
	Model        string             `json:"model"`
	MaxTokens    int                `json:"max_tokens"`
	System       string             `json:"system"`
	OutputConfig anthropicEffort    `json:"output_config"`
	Messages     []anthropicMessage `json:"messages"`
}

type anthropicEffort struct {
	Effort string `json:"effort"`
}

type anthropicMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type anthropicResponse struct {
	Content []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error"`
}

func (c *AnthropicClient) Evaluate(ctx context.Context, in Input) (Result, error) {
	body, err := json.Marshal(anthropicRequest{
		Model:     c.model,
		MaxTokens: maxCompletionTokens,
		System:    systemPrompt,
		OutputConfig: anthropicEffort{
			Effort: "low",
		},
		Messages: []anthropicMessage{
			{Role: "user", Content: userPrompt(in)},
		},
	})
	if err != nil {
		return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
	}

	var lastErr error
	for attempt := 1; attempt <= maxEvaluateAttempts; attempt++ {
		raw, status, retryAfter, err := c.complete(ctx, body)
		if err != nil {
			return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
		}
		if status == http.StatusTooManyRequests {
			lastErr = fmt.Errorf("%w: anthropic status %d: %s", ErrUnavailable, status, anthropicErrorMessage(raw))
			if attempt == maxEvaluateAttempts {
				break
			}
			if err := sleepRetry(ctx, retryAfter); err != nil {
				return Result{}, fmt.Errorf("%w: %v", ErrUnavailable, err)
			}
			continue
		}
		if status < 200 || status >= 300 {
			return Result{}, fmt.Errorf("%w: anthropic status %d: %s", ErrUnavailable, status, anthropicErrorMessage(raw))
		}

		text := anthropicText(raw)
		if strings.TrimSpace(text) == "" {
			return Result{}, fmt.Errorf("%w: empty content", ErrUnavailable)
		}

		var decision modelDecision
		if err := json.Unmarshal([]byte(extractJSONObject(text)), &decision); err != nil {
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
	return Result{}, lastErr
}

func (c *AnthropicClient) complete(ctx context.Context, body []byte) (raw []byte, status int, retryAfter time.Duration, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/messages", bytes.NewReader(body))
	if err != nil {
		return nil, 0, 0, err
	}
	req.Header.Set("x-api-key", c.apiKey)
	req.Header.Set("anthropic-version", anthropicVersion)
	req.Header.Set("Content-Type", "application/json")

	res, err := c.httpClient.Do(req)
	if err != nil {
		return nil, 0, 0, err
	}
	defer res.Body.Close()

	raw, err = io.ReadAll(res.Body)
	if err != nil {
		return nil, res.StatusCode, 0, err
	}
	return raw, res.StatusCode, parseRetryAfter(res.Header.Get("Retry-After")), nil
}

func anthropicText(raw []byte) string {
	var parsed anthropicResponse
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

func anthropicErrorMessage(raw []byte) string {
	var payload struct {
		Error struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := json.Unmarshal(raw, &payload); err == nil && payload.Error.Message != "" {
		return payload.Error.Message
	}
	msg := strings.TrimSpace(string(raw))
	if len(msg) > 240 {
		msg = msg[:240]
	}
	if msg == "" {
		return "empty body"
	}
	return msg
}

func extractJSONObject(text string) string {
	start := strings.Index(text, "{")
	end := strings.LastIndex(text, "}")
	if start >= 0 && end > start {
		return text[start : end+1]
	}
	return text
}
