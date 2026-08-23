package gateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"

	"roxy-gateway/internal/mcp"

	"github.com/stretchr/testify/require"
)

func TestAnthropicAgent_CallMCP_usesToolThenReturnsRaw(t *testing.T) {
	t.Parallel()
	mcpSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, http.MethodPost, r.Method)
		require.Equal(t, "/query", r.URL.Path)
		require.Equal(t, "Bearer tok_catalog_demo", r.Header.Get("Authorization"))
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"rows":[]}`))
	}))
	t.Cleanup(mcpSrv.Close)

	var calls atomic.Int32
	anth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := calls.Add(1)
		raw, _ := io.ReadAll(r.Body)
		require.NotContains(t, string(raw), "tok_catalog_demo")
		w.Header().Set("Content-Type", "application/json")
		if n == 1 {
			_, _ = w.Write([]byte(`{
				"stop_reason":"tool_use",
				"content":[{"type":"tool_use","id":"tu_1","name":"http_request","input":{"method":"POST","url":"/query","body":{"q":"orders"}}}]
			}`))
			return
		}
		_, _ = w.Write([]byte(`{"stop_reason":"end_turn","content":[{"type":"text","text":"done"}]}`))
	}))
	t.Cleanup(anth.Close)

	agent := NewAnthropicAgent(anth.URL, "test-key", "claude-sonnet-5", NewMCPClient())
	up, err := agent.CallMCP(context.Background(), &mcp.MCP{
		Name:   "mongo-catalog-mcp",
		Server: mcp.Server{URL: mcpSrv.URL, Protocol: "mcp"},
		Authorization: mcp.Authorization{
			Type:        "bearer",
			Credentials: "tok_catalog_demo",
		},
	}, "read", []byte(`{"intent":"read orders"}`))
	require.NoError(t, err)
	require.JSONEq(t, `{"rows":[]}`, string(up.Body))
	require.GreaterOrEqual(t, calls.Load(), int32(1))
}

func TestAnthropicAgent_CallMCP_requiresTool(t *testing.T) {
	t.Parallel()
	anth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"stop_reason":"end_turn","content":[{"type":"text","text":"no tool"}]}`))
	}))
	t.Cleanup(anth.Close)

	agent := NewAnthropicAgent(anth.URL, "test-key", "claude-sonnet-5", NewMCPClient())
	_, err := agent.CallMCP(context.Background(), &mcp.MCP{
		Server: mcp.Server{URL: "https://mcp.internal/x", Protocol: "mcp"},
	}, "read", nil)
	require.Error(t, err)
}
