package gateway

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
)

const mcpProtocolVersion = "2025-06-18"

type MCPCaller interface {
	Invoke(ctx context.Context, doc *mcp.MCP, plan PlannedCall) (Upstream, error)
}

type Upstream struct {
	StatusCode  int
	ContentType string
	Header      http.Header
	Body        []byte
}

type MCPClient struct {
	httpClient *http.Client
	mu         sync.Mutex
	cachedKey  string
	cachedTok  string
	cachedExp  time.Time
}

func NewMCPClient() *MCPClient {
	return &MCPClient{httpClient: &http.Client{Timeout: 45 * time.Second}}
}

func (c *MCPClient) Invoke(ctx context.Context, doc *mcp.MCP, plan PlannedCall) (Upstream, error) {
	if plan.URL == "" {
		return Upstream{}, fmt.Errorf("%w: missing planned url", policy.ErrUpstream)
	}
	var body io.Reader
	if planHasBody(plan.Body) {
		body = bytes.NewReader(plan.Body)
	}
	req, err := http.NewRequestWithContext(ctx, plan.Method, plan.URL, body)
	if err != nil {
		return Upstream{}, fmt.Errorf("%w: %v", policy.ErrUpstream, err)
	}
	if planHasBody(plan.Body) {
		req.Header.Set("Content-Type", "application/json")
	}
	req.Header.Set("Accept", "application/json, text/event-stream")
	req.Header.Set("MCP-Protocol-Version", mcpProtocolVersion)
	if sid := strings.TrimSpace(plan.SessionID); sid != "" {
		req.Header.Set("Mcp-Session-Id", sid)
	}
	if err := c.setAuth(ctx, req, doc.Authorization); err != nil {
		return Upstream{}, err
	}

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
		Header:      res.Header.Clone(),
		Body:        raw,
	}, nil
}

func headerValue(up Upstream, key string) string {
	if up.Header == nil {
		return ""
	}
	return up.Header.Get(key)
}

func (c *MCPClient) setAuth(ctx context.Context, req *http.Request, auth mcp.Authorization) error {
	if strings.EqualFold(auth.Type, "apikey") {
		if auth.Credentials != "" {
			req.Header.Set("X-API-Key", auth.Credentials)
		}
		return nil
	}
	bearer, err := c.resolveBearer(ctx, auth)
	if err != nil {
		return err
	}
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	return nil
}
