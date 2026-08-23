package policy

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"roxy-gateway/internal/mcp"

	"github.com/stretchr/testify/require"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

func fixtureMCP() mcp.MCP {
	return mcp.MCP{
		Name:        "mongo-catalog-mcp",
		Description: "catalog database",
		Rules: []mcp.Rule{
			{Priority: 1, Instruction: "deny any write operation outside working hours"},
			{Priority: 2, Instruction: "allow read-only queries on the 'orders' collection"},
		},
	}
}

func TestRemoteClient_Evaluate_sendsRulesAndPromptWithoutCredentials(t *testing.T) {
	t.Parallel()
	id := primitive.NewObjectID()
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, http.MethodPost, r.Method)
		require.Equal(t, "/evaluate", r.URL.Path)
		raw, err := io.ReadAll(r.Body)
		require.NoError(t, err)
		require.NoError(t, json.Unmarshal(raw, &gotBody))
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"allowed":false,"violatedPriority":1,"reason":"denied by rule 1"}`))
	}))
	t.Cleanup(srv.Close)

	client := NewRemoteClient(srv.URL + "/evaluate")
	in := Input{
		MCP: mcp.MCP{
			ID:          id,
			Name:        "mongo-catalog-mcp",
			Description: "catalog database",
			Authorization: mcp.Authorization{
				Type:        "bearer",
				Credentials: "secret-must-not-leak",
			},
			Rules: []mcp.Rule{
				{Priority: 1, Instruction: "deny any write operation outside working hours"},
				{Priority: 2, Instruction: "allow read-only queries on the 'orders' collection"},
			},
		},
		AccessedBy: "agent-subtask-07",
		Action:     "drop_table",
		Payload:    []byte(`{"intent":"DROP TABLE orders"}`),
	}
	got, err := client.Evaluate(context.Background(), in)
	require.NoError(t, err)
	require.False(t, got.Allowed)
	require.NotNil(t, got.ViolatedRule)
	require.Equal(t, 1, got.ViolatedRule.Priority)

	raw, _ := json.Marshal(gotBody)
	require.NotContains(t, string(raw), "secret-must-not-leak")
	require.NotContains(t, string(raw), "priority")
	require.NotContains(t, string(raw), id.Hex())
	require.Equal(t, []any{
		"deny any write operation outside working hours",
		"allow read-only queries on the 'orders' collection",
	}, gotBody["rules"])
	require.Equal(t, "drop_table: DROP TABLE orders", gotBody["prompt"])
	_, hasMCP := gotBody["mcp"]
	require.False(t, hasMCP)
	_, hasRequest := gotBody["request"]
	require.False(t, hasRequest)
}

func TestRemoteClient_Evaluate_allow(t *testing.T) {
	t.Parallel()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"allowed":true,"violatedPriority":null,"reason":"read ok"}`))
	}))
	t.Cleanup(srv.Close)

	client := NewRemoteClient(srv.URL)
	got, err := client.Evaluate(context.Background(), Input{
		MCP:        fixtureMCP(),
		AccessedBy: "agent-orchestrator-01",
		Action:     "read",
		Payload:    []byte(`{"intent":"read stock"}`),
	})
	require.NoError(t, err)
	require.True(t, got.Allowed)
	require.Nil(t, got.ViolatedRule)
}

func TestRemoteClient_Evaluate_non2xx(t *testing.T) {
	t.Parallel()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	t.Cleanup(srv.Close)

	client := NewRemoteClient(srv.URL)
	_, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.ErrorIs(t, err, ErrUnavailable)
}

func TestAgentPrompt(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name    string
		action  string
		payload string
		want    string
	}{
		{name: "intent with action", action: "drop_table", payload: `{"intent":"DROP TABLE orders"}`, want: "drop_table: DROP TABLE orders"},
		{name: "payload prompt wins", action: "read", payload: `{"prompt":"list orders","intent":"ignored"}`, want: "list orders"},
		{name: "json string payload", action: "read", payload: `"show me paid orders"`, want: "read: show me paid orders"},
		{name: "action only", action: "read", payload: "", want: "read"},
		{name: "null payload", action: "read", payload: "null", want: "read"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := agentPrompt(tt.action, []byte(tt.payload))
			require.Equal(t, tt.want, got)
		})
	}
}
