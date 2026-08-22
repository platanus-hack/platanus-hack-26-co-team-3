package policy

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"roxy-gateway/internal/mcp"

	"github.com/stretchr/testify/require"
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

func completionBody(content string) string {
	payload, _ := json.Marshal(map[string]any{
		"choices": []map[string]any{
			{"message": map[string]any{"content": content}},
		},
	})
	return string(payload)
}

func TestClient_Evaluate(t *testing.T) {
	tests := []struct {
		name       string
		status     int
		body       string
		wantErr    error
		wantAllow  bool
		wantPrio   *int
		wantReason string
	}{
		{
			name:       "allow",
			status:     http.StatusOK,
			body:       completionBody(`{"allowed":true,"violatedPriority":null,"reason":"read is permitted"}`),
			wantAllow:  true,
			wantReason: "read is permitted",
		},
		{
			name:       "deny first rule",
			status:     http.StatusOK,
			body:       completionBody(`{"allowed":false,"violatedPriority":1,"reason":"drop table is a write"}`),
			wantAllow:  false,
			wantPrio:   intPtr(1),
			wantReason: "drop table is a write",
		},
		{
			name:    "non-2xx",
			status:  http.StatusInternalServerError,
			body:    `{"error":"boom"}`,
			wantErr: ErrUnavailable,
		},
		{
			name:    "malformed json content",
			status:  http.StatusOK,
			body:    completionBody("not-json"),
			wantErr: ErrUnavailable,
		},
		{
			name:    "empty choices",
			status:  http.StatusOK,
			body:    `{"choices":[]}`,
			wantErr: ErrUnavailable,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				require.Equal(t, http.MethodPost, r.Method)
				require.Equal(t, "/chat/completions", r.URL.Path)
				require.Equal(t, "Bearer test-key", r.Header.Get("Authorization"))
				w.WriteHeader(tt.status)
				_, _ = w.Write([]byte(tt.body))
			}))
			t.Cleanup(srv.Close)

			client := NewClient(srv.URL, "test-key", "openai/gpt-4o-mini")
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
			require.Equal(t, tt.wantReason, got.Reason)
			if tt.wantPrio == nil {
				require.Nil(t, got.ViolatedRule)
				return
			}
			require.NotNil(t, got.ViolatedRule)
			require.Equal(t, *tt.wantPrio, got.ViolatedRule.Priority)
		})
	}
}

func TestClient_Evaluate_retries429ThenSucceeds(t *testing.T) {
	t.Parallel()
	var hits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		if hits == 1 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte(`{"error":{"message":"temporarily rate-limited upstream"}}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(completionBody(`{"allowed":true,"violatedPriority":null,"reason":"ok"}`)))
	}))
	t.Cleanup(srv.Close)

	client := NewClient(srv.URL, "test-key", "z-ai/glm-5.2:free")
	got, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.NoError(t, err)
	require.True(t, got.Allowed)
	require.Equal(t, 2, hits)
}

func TestClient_Evaluate_exhausted429IncludesBody(t *testing.T) {
	t.Parallel()
	var hits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		w.Header().Set("Retry-After", "0")
		w.WriteHeader(http.StatusTooManyRequests)
		_, _ = w.Write([]byte(`{"error":{"message":"temporarily rate-limited upstream"}}`))
	}))
	t.Cleanup(srv.Close)

	client := NewClient(srv.URL, "test-key", "z-ai/glm-5.2:free")
	_, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.ErrorIs(t, err, ErrUnavailable)
	require.Contains(t, err.Error(), "429")
	require.Contains(t, err.Error(), "rate-limited")
	require.Equal(t, maxEvaluateAttempts, hits)
}

func TestClient_Evaluate_doesNotRetry500(t *testing.T) {
	t.Parallel()
	var hits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":{"message":"boom"}}`))
	}))
	t.Cleanup(srv.Close)

	client := NewClient(srv.URL, "test-key", "openai/gpt-4o-mini")
	_, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.ErrorIs(t, err, ErrUnavailable)
	require.Equal(t, 1, hits)
}

func TestClient_Evaluate_clientTimeout(t *testing.T) {
	t.Parallel()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(80 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(completionBody(`{"allowed":true,"violatedPriority":null,"reason":"ok"}`)))
	}))
	t.Cleanup(srv.Close)

	client := NewClient(srv.URL, "test-key", "poolside/laguna-xs-2.1:free")
	client.httpClient.Timeout = 20 * time.Millisecond
	_, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.ErrorIs(t, err, ErrUnavailable)
}

func TestClient_Evaluate_wrapsTransportError(t *testing.T) {
	t.Parallel()
	client := NewClient("http://127.0.0.1:1", "test-key", "openai/gpt-4o-mini")
	_, err := client.Evaluate(context.Background(), Input{MCP: fixtureMCP(), Action: "read"})
	require.Error(t, err)
	require.True(t, errors.Is(err, ErrUnavailable))
}

func intPtr(v int) *int { return &v }
