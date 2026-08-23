package gateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"

	"github.com/stretchr/testify/require"
)

func TestAnthropicPlanner_Plan(t *testing.T) {
	t.Parallel()
	var gotBody []byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "/v1/messages", r.URL.Path)
		require.Equal(t, "test-key", r.Header.Get("x-api-key"))
		gotBody, _ = io.ReadAll(r.Body)
		_, _ = w.Write([]byte(`{"content":[{"type":"text","text":"{\"method\":\"POST\",\"url\":\"/tools/call\",\"body\":{\"name\":\"query\"}}"}]}`))
	}))
	t.Cleanup(srv.Close)

	p := NewAnthropicPlanner(srv.URL, "test-key", "claude-sonnet-5")
	doc := &mcp.MCP{
		Name:        "mongo-catalog-mcp",
		Description: "catalog",
		Server:      mcp.Server{URL: "https://mcp.internal/mongo-catalog", Protocol: "mcp"},
		Authorization: mcp.Authorization{
			Credentials: "secret-must-not-leak",
		},
	}
	plan, err := p.Plan(context.Background(), doc, "read", []byte(`{"intent":"read orders"}`))
	require.NoError(t, err)
	require.Equal(t, http.MethodPost, plan.Method)
	require.Equal(t, "https://mcp.internal/mongo-catalog/tools/call", plan.URL)
	require.JSONEq(t, `{"name":"query"}`, string(plan.Body))
	require.NotContains(t, string(gotBody), "secret-must-not-leak")
}

func TestNormalizePlan_rejectsOtherHost(t *testing.T) {
	t.Parallel()
	_, err := normalizePlan("https://mcp.internal/catalog", []byte(`{"method":"GET","url":"https://evil.example/x"}`))
	require.ErrorIs(t, err, policy.ErrPlan)
}
