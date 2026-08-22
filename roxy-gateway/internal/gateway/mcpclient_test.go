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
	var gotAuth, gotCT string
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotCT = r.Header.Get("Content-Type")
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
	}, "read", []byte(`{"intent":"read stock"}`))
	require.NoError(t, err)
	require.Equal(t, "Bearer tok_catalog_demo", gotAuth)
	require.Equal(t, "application/json", gotCT)
	require.Equal(t, "read", gotBody["action"])
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
	}, "read", nil)
	require.NoError(t, err)
	require.Equal(t, "inv_key_demo", gotKey)
}
