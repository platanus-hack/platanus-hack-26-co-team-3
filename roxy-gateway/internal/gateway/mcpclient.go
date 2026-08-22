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

type MCPCaller interface {
	Invoke(ctx context.Context, doc *mcp.MCP, action string, payload []byte) (Upstream, error)
}

type Upstream struct {
	StatusCode  int
	ContentType string
	Body        []byte
}

type MCPClient struct {
	httpClient *http.Client
}

func NewMCPClient() *MCPClient {
	return &MCPClient{httpClient: &http.Client{Timeout: 15 * time.Second}}
}

func (c *MCPClient) Invoke(ctx context.Context, doc *mcp.MCP, action string, payload []byte) (Upstream, error) {
	if doc.Server.URL == "" {
		return Upstream{}, fmt.Errorf("%w: missing server url", policy.ErrUpstream)
	}
	bodyPayload := json.RawMessage(payload)
	if len(bytes.TrimSpace(bodyPayload)) == 0 {
		bodyPayload = json.RawMessage("null")
	}
	body, err := json.Marshal(map[string]any{
		"action":  action,
		"payload": bodyPayload,
	})
	if err != nil {
		return Upstream{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, doc.Server.URL, bytes.NewReader(body))
	if err != nil {
		return Upstream{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}
	req.Header.Set("Content-Type", "application/json")
	setAuth(req, doc.Authorization)

	res, err := c.httpClient.Do(req)
	if err != nil {
		return Upstream{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(res.Body)
	if err != nil {
		return Upstream{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}
	return Upstream{
		StatusCode:  res.StatusCode,
		ContentType: res.Header.Get("Content-Type"),
		Body:        raw,
	}, nil
}

func setAuth(req *http.Request, auth mcp.Authorization) {
	secret := auth.Credentials
	if secret == "" {
		return
	}
	switch strings.ToLower(auth.Type) {
	case "apikey":
		req.Header.Set("X-API-Key", secret)
	default:
		req.Header.Set("Authorization", "Bearer "+secret)
	}
}
