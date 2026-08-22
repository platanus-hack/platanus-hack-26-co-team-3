package dashboard

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestClient_Notify_emptyURLIsNoop(t *testing.T) {
	t.Parallel()
	c := NewClient("")
	err := c.Notify(context.Background(), Notification{Status: "denied", MCPName: "payments-mcp"})
	require.NoError(t, err)
}

func TestClient_Notify_postsJSON(t *testing.T) {
	t.Parallel()
	var gotMethod, gotCT, gotBody string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotCT = r.Header.Get("Content-Type")
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL)
	err := c.Notify(context.Background(), Notification{
		Status:      "denied",
		MCPName:     "payments-mcp",
		MCPID:       "abc",
		AccessedBy:  "agent-subtask-07",
		Action:      "write_transactions",
		Description: "rule priority 1 violation",
		Time:        time.Date(2026, 8, 20, 9, 17, 32, 0, time.UTC),
	})
	require.NoError(t, err)
	require.Equal(t, http.MethodPost, gotMethod)
	require.Equal(t, "application/json", gotCT)
	require.Contains(t, gotBody, `"status":"denied"`)
	require.Contains(t, gotBody, `"mcpName":"payments-mcp"`)
}

func TestClient_Notify_non2xxReturnsError(t *testing.T) {
	t.Parallel()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL)
	err := c.Notify(context.Background(), Notification{Status: "approved"})
	require.Error(t, err)
	require.Contains(t, err.Error(), "500")
}
