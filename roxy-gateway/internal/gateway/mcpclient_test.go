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

func TestMCPClient_Invoke_oauth2MintsBearer(t *testing.T) {
	t.Parallel()
	var gotAuth, gotProto string
	tokenSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, http.MethodPost, r.Method)
		user, pass, ok := r.BasicAuth()
		require.True(t, ok)
		require.Equal(t, "mdb_sa_id_abc", user)
		require.Equal(t, "mdb_sa_sk_secret", pass)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"access_token":"minted-token","expires_in":3600,"token_type":"Bearer"}`))
	}))
	t.Cleanup(tokenSrv.Close)
	mcpSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotProto = r.Header.Get("MCP-Protocol-Version")
		w.Header().Set("Mcp-Session-Id", "sess-1")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"jsonrpc":"2.0","id":1,"result":{}}`))
	}))
	t.Cleanup(mcpSrv.Close)

	creds, err := json.Marshal(map[string]string{
		"clientId":     "mdb_sa_id_abc",
		"clientSecret": "mdb_sa_sk_secret",
		"tokenURL":     tokenSrv.URL,
	})
	require.NoError(t, err)
	client := NewMCPClient()
	up, err := client.Invoke(context.Background(), &mcp.MCP{
		Server: mcp.Server{URL: mcpSrv.URL, Protocol: "mcp"},
		Authorization: mcp.Authorization{
			Type:        "oauth2",
			Credentials: string(creds),
		},
	}, PlannedCall{Method: http.MethodPost, URL: mcpSrv.URL, Body: json.RawMessage(`{"jsonrpc":"2.0"}`)})
	require.NoError(t, err)
	require.Equal(t, "Bearer minted-token", gotAuth)
	require.Equal(t, "2025-06-18", gotProto)
	require.Equal(t, "sess-1", up.Header.Get("Mcp-Session-Id"))
}

func TestParseOAuthCreds_colonPair(t *testing.T) {
	t.Parallel()
	got, err := parseOAuthCreds("mdb_sa_id_abc:mdb_sa_sk_secret")
	require.NoError(t, err)
	require.Equal(t, "mdb_sa_id_abc", got.ClientID)
	require.Equal(t, "mdb_sa_sk_secret", got.ClientSecret)
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
