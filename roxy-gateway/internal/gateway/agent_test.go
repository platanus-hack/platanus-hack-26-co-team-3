package gateway

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"

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

func TestAnthropicAgent_CallMCP_doesNotReturnInitializeHandshake(t *testing.T) {
	t.Parallel()
	handshake := `{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"MongoDB MCP Server"}}}`
	mcpSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Mcp-Session-Id", "sess-handshake")
		_, _ = w.Write([]byte(handshake))
	}))
	t.Cleanup(mcpSrv.Close)

	var rounds atomic.Int32
	anth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := rounds.Add(1)
		w.Header().Set("Content-Type", "application/json")
		if n == 1 {
			_, _ = w.Write([]byte(fmt.Sprintf(`{
				"stop_reason":"tool_use",
				"content":[{"type":"tool_use","id":"tu_1","name":"http_request","input":{"method":"POST","url":%q,"body":{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}}}]
			}`, mcpSrv.URL)))
			return
		}
		_, _ = w.Write([]byte(`{"stop_reason":"end_turn","content":[{"type":"text","text":"will not delete"}]}`))
	}))
	t.Cleanup(anth.Close)

	agent := NewAnthropicAgent(anth.URL, "test-key", "claude-sonnet-5", NewMCPClient())
	up, err := agent.CallMCP(context.Background(), &mcp.MCP{
		Server: mcp.Server{URL: mcpSrv.URL, Protocol: "mcp"},
	}, "delete", []byte(`{"intent":"delete invoices"}`))
	require.Error(t, err)
	require.NotContains(t, string(up.Body), "MongoDB MCP Server")
	require.ErrorIs(t, err, policy.ErrPlan)
}

func TestBodyForModel_stripsSSE(t *testing.T) {
	t.Parallel()
	got := bodyForModel(Upstream{
		ContentType: "text/event-stream",
		Body:        []byte("event: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{}}\n\n"),
	})
	require.JSONEq(t, `{"jsonrpc":"2.0","id":1,"result":{}}`, got)
}

func TestAgentSystem_targetsRoxyHostedMCP(t *testing.T) {
	t.Parallel()
	require.Contains(t, agentSystem, "https://roxygt.lat/mcp")
	require.NotContains(t, agentSystem, "mcp.mongodb.com")
}

type failCaller struct{ err error }

func (f failCaller) Invoke(context.Context, *mcp.MCP, PlannedCall) (Upstream, error) {
	return Upstream{}, f.err
}

func TestAnthropicAgent_CallMCP_surfacesInvokeError(t *testing.T) {
	t.Parallel()
	var calls atomic.Int32
	anth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := calls.Add(1)
		w.Header().Set("Content-Type", "application/json")
		if n == 1 {
			_, _ = w.Write([]byte(`{
				"stop_reason":"tool_use",
				"content":[{"type":"tool_use","id":"tu_1","name":"http_request","input":{"method":"POST","url":"https://roxygt.lat/mcp","body":{"jsonrpc":"2.0"}}}]
			}`))
			return
		}
		_, _ = w.Write([]byte(`{"stop_reason":"end_turn","content":[{"type":"text","text":"gave up"}]}`))
	}))
	t.Cleanup(anth.Close)

	agent := NewAnthropicAgent(anth.URL, "test-key", "claude-sonnet-5", failCaller{
		err: fmt.Errorf("%w: oauth token status 401", policy.ErrUpstream),
	})
	_, err := agent.CallMCP(context.Background(), &mcp.MCP{
		Server: mcp.Server{URL: "https://roxygt.lat/mcp", Protocol: "mcp"},
	}, "read", []byte(`{"intent":"find invoices"}`))
	require.ErrorIs(t, err, policy.ErrUpstream)
	require.NotContains(t, err.Error(), "model did not call the MCP")
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
	require.ErrorIs(t, err, policy.ErrPlan)
	require.Contains(t, err.Error(), "no tool")
}

func TestAnthropicAgent_firstRoundForcesToolChoice(t *testing.T) {
	t.Parallel()
	var saw atomic.Bool
	mcpSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Mcp-Session-Id", "sess-1")
		_, _ = w.Write([]byte(`{"jsonrpc":"2.0","id":1,"result":{}}`))
	}))
	t.Cleanup(mcpSrv.Close)
	anth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		if strings.Contains(string(raw), `"type":"any"`) && strings.Contains(string(raw), "tool_choice") {
			saw.Store(true)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"stop_reason":"tool_use",
			"content":[{"type":"tool_use","id":"tu_1","name":"http_request","input":{"method":"POST","url":"` + mcpSrv.URL + `","body":{"jsonrpc":"2.0"}}}]
		}`))
	}))
	t.Cleanup(anth.Close)
	agent := NewAnthropicAgent(anth.URL, "test-key", "claude-sonnet-5", NewMCPClient())
	_, err := agent.CallMCP(context.Background(), &mcp.MCP{
		Server: mcp.Server{URL: mcpSrv.URL, Protocol: "mcp"},
	}, "read", []byte(`{"intent":"find"}`))
	require.NoError(t, err)
	require.True(t, saw.Load(), "first Anthropic round must set tool_choice=any")
}
