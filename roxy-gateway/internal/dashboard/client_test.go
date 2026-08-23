package dashboard

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"roxy-gateway/internal/mcp"

	"github.com/stretchr/testify/require"
)

func TestClient_Notify_emptyURLIsNoop(t *testing.T) {
	t.Parallel()
	c := NewClient("")
	err := c.Notify(context.Background(), Notification{Status: "denied", MCPName: "payments-mcp"})
	require.NoError(t, err)
}

func TestLogEndpoint(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name string
		in   string
		want string
	}{
		{name: "empty is noop", in: "", want: ""},
		{name: "api base", in: "https://roxygt.lat/api", want: "https://roxygt.lat/api/log"},
		{name: "api base slash", in: "https://roxygt.lat/api/", want: "https://roxygt.lat/api/log"},
		{name: "already log", in: "https://roxygt.lat/api/log", want: "https://roxygt.lat/api/log"},
		{name: "already log slash", in: "https://roxygt.lat/api/log/", want: "https://roxygt.lat/api/log"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			require.Equal(t, tt.want, logEndpoint(tt.in))
		})
	}
}

func TestClient_Notify_postsDenyJSONToLog(t *testing.T) {
	t.Parallel()
	var gotMethod, gotPath, gotCT, gotBody string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotPath = r.URL.Path
		gotCT = r.Header.Get("Content-Type")
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL + "/api")
	rule := mcp.Rule{Priority: 1, Instruction: "deny any write operation outside working hours"}
	err := c.Notify(context.Background(), Notification{
		Status:       "denied",
		MCPName:      "mongo-catalog-mcp",
		MCPID:        "6a89974fe413c1e675df5b82",
		AccessedBy:   "agent-subtask-07",
		Action:       "drop_table",
		ViolatedRule: &rule,
		Description:  "Dropping a table is a write/destructive operation, denied by priority 1 rule.",
		Time:         time.Date(2026, 8, 22, 12, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)
	require.Equal(t, http.MethodPost, gotMethod)
	require.Equal(t, "/api/log", gotPath)
	require.Equal(t, "application/json", gotCT)
	require.JSONEq(t, `{
		"status": "denied",
		"mcpName": "mongo-catalog-mcp",
		"mcpId": "6a89974fe413c1e675df5b82",
		"accessedBy": "agent-subtask-07",
		"action": "drop_table",
		"violatedRule": {
			"priority": 1,
			"instruction": "deny any write operation outside working hours"
		},
		"description": "Dropping a table is a write/destructive operation, denied by priority 1 rule.",
		"time": "2026-08-22T12:00:00Z"
	}`, gotBody)
}

func TestClient_Notify_allowOmitsViolatedRule(t *testing.T) {
	t.Parallel()
	var gotBody string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL + "/api")
	err := c.Notify(context.Background(), Notification{
		Status:      "approved",
		MCPName:     "mongo-catalog-mcp",
		MCPID:       "6a89974fe413c1e675df5b82",
		AccessedBy:  "agent-subtask-07",
		Action:      "read",
		Description: "read ok",
		Time:        time.Date(2026, 8, 22, 12, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)
	require.NotContains(t, gotBody, "violatedRule")
	var parsed map[string]any
	require.NoError(t, json.Unmarshal([]byte(gotBody), &parsed))
	_, present := parsed["violatedRule"]
	require.False(t, present)
	require.JSONEq(t, `{
		"status": "approved",
		"mcpName": "mongo-catalog-mcp",
		"mcpId": "6a89974fe413c1e675df5b82",
		"accessedBy": "agent-subtask-07",
		"action": "read",
		"description": "read ok",
		"time": "2026-08-22T12:00:00Z"
	}`, gotBody)
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
