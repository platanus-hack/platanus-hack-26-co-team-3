package gateway

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
)

type MCPCaller interface {
	Invoke(ctx context.Context, doc *mcp.MCP, plan PlannedCall) (Upstream, error)
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
