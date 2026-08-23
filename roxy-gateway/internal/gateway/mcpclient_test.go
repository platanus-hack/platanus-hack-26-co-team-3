package gateway

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"roxy-gateway/internal/mcp"

	"github.com/stretchr/testify/require"
)

func TestMCPClient_Invoke_sendsBearerAndReturnsRaw(t *testing.T) {
	t.Parallel()
	var gotAuth, gotPath string
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotPath = r.URL.Path
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"ok":true,"from":"mcp"}`))
	}))
	t.Cleanup(srv.Close)

	client := NewMCPClient()
	up, err := client.Invoke(context.Background(), &mcp.MCP{
		Server:        mcp.Server{URL: srv.URL},
		Authorization: mcp.Authorization{Type: "bearer", Credentials: "tok_catalog_demo"},
	}, PlannedCall{
		Method: http.MethodPost,
		URL:    srv.URL + "/tools/call",
		Body:   json.RawMessage(`{"name":"query"}`),
	})
	require.NoError(t, err)
	require.Equal(t, "Bearer tok_catalog_demo", gotAuth)
	require.Equal(t, "/tools/call", gotPath)
	require.Equal(t, "query", gotBody["name"])
	require.Equal(t, http.StatusCreated, up.StatusCode)
	require.JSONEq(t, `{"ok":true,"from":"mcp"}`, string(up.Body))
}

func TestMCPClient_Invoke_apiKeyHeader(t *testing.T) {
	t.Parallel()
	var gotKey string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotKey = r.Header.Get("X-API-Key")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"stock":1}`))
	}))
	t.Cleanup(srv.Close)

	client := NewMCPClient()
	_, err := client.Invoke(context.Background(), &mcp.MCP{
		Server:        mcp.Server{URL: srv.URL},
		Authorization: mcp.Authorization{Type: "apiKey", Credentials: "inv_key_demo"},
	}, PlannedCall{Method: http.MethodGet, URL: srv.URL})
	require.NoError(t, err)
	require.Equal(t, "inv_key_demo", gotKey)
}
