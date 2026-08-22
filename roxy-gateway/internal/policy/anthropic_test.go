package policy

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
)

func anthropicBody(text string) string {
	payload, _ := json.Marshal(map[string]any{
		"content": []map[string]any{
			{"type": "text", "text": text},
		},
	})
	return string(payload)
}

func TestAnthropicClient_Evaluate(t *testing.T) {
	tests := []struct {
		name      string
		status    int
		body      string
		wantErr   error
		wantAllow bool
		wantPrio  *int
	}{
		{
			name:      "allow",
			status:    http.StatusOK,
			body:      anthropicBody(`{"allowed":true,"violatedPriority":null,"reason":"read is permitted"}`),
			wantAllow: true,
		},
		{
			name:      "deny first rule",
			status:    http.StatusOK,
			body:      anthropicBody(`{"allowed":false,"violatedPriority":1,"reason":"drop table is a write"}`),
			wantAllow: false,
			wantPrio:  intPtr(1),
		},
		{
			name:    "non-2xx",
			status:  http.StatusInternalServerError,
			body:    `{"error":{"message":"boom"}}`,
			wantErr: ErrUnavailable,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				require.Equal(t, http.MethodPost, r.Method)
				require.Equal(t, "/v1/messages", r.URL.Path)
				require.Equal(t, "test-key", r.Header.Get("x-api-key"))
				require.Equal(t, anthropicVersion, r.Header.Get("anthropic-version"))
				w.WriteHeader(tt.status)
				_, _ = w.Write([]byte(tt.body))
			}))
			t.Cleanup(srv.Close)

			client := NewAnthropicClient(srv.URL, "test-key", "claude-sonnet-5")
			got, err := client.Evaluate(context.Background(), Input{
				MCP:        fixtureMCP(),
				AccessedBy: "agent-subtask-07",
				Action:     "drop_table",
				Payload:    []byte(`{"intent":"DROP TABLE orders"}`),
			})
			if tt.wantErr != nil {
				require.ErrorIs(t, err, tt.wantErr)
				return
			}
			require.NoError(t, err)
			require.Equal(t, tt.wantAllow, got.Allowed)
			if tt.wantPrio == nil {
				require.Nil(t, got.ViolatedRule)
				return
			}
			require.NotNil(t, got.ViolatedRule)
			require.Equal(t, *tt.wantPrio, got.ViolatedRule.Priority)
		})
	}
}
