package policy

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
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
	MCP     remoteMCP     `json:"mcp"`
	Request remoteAttempt `json:"request"`
	Time    time.Time     `json:"time"`
}

type remoteMCP struct {
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Description string     `json:"description"`
	Rules       []mcp.Rule `json:"rules"`
}

type remoteAttempt struct {
	AccessedBy string          `json:"accessedBy"`
	Action     string          `json:"action"`
	Payload    json.RawMessage `json:"payload"`
}

type remoteResponse struct {
	Allowed          bool   `json:"allowed"`
	ViolatedPriority *int   `json:"violatedPriority"`
	Reason           string `json:"reason"`
}

func (c *RemoteClient) Evaluate(ctx context.Context, in Input) (Result, error) {
	payload := json.RawMessage(in.Payload)
	if len(bytes.TrimSpace(payload)) == 0 {
		payload = json.RawMessage("null")
	}
	body, err := json.Marshal(remoteRequest{
		MCP: remoteMCP{
			ID:          in.MCP.ID.Hex(),
			Name:        in.MCP.Name,
			Description: in.MCP.Description,
			Rules:       in.MCP.Rules,
		},
		Request: remoteAttempt{
			AccessedBy: in.AccessedBy,
			Action:     in.Action,
			Payload:    payload,
		},
		Time: time.Now().UTC(),
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
		out.ViolatedRule = ruleByPriority(in.MCP.Rules, *parsed.ViolatedPriority)
	}
	return out, nil
}
