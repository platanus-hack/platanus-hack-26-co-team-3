package httpapi_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"roxy-gateway/internal/gateway"
	httpapi "roxy-gateway/internal/http"
	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"

	"github.com/stretchr/testify/require"
)

type stubService struct {
	resp gateway.EvaluateResponse
	err  error
}

func (s stubService) Evaluate(context.Context, gateway.EvaluateRequest) (gateway.EvaluateResponse, error) {
	return s.resp, s.err
}

func TestEvaluateHandler(t *testing.T) {
	validBody := map[string]any{
		"mcpName":    "mongo-catalog-mcp",
		"accessedBy": "agent-subtask-07",
		"action":     "drop_table",
		"payload":    map[string]any{"intent": "DROP TABLE orders"},
	}
	rule := mcp.Rule{Priority: 1, Instruction: "deny any write operation outside working hours"}

	tests := []struct {
		name       string
		body       any
		svc        stubService
		wantStatus int
		wantSubstr string
	}{
		{
			name:       "400 missing action",
			body:       map[string]any{"mcpName": "mongo-catalog-mcp", "accessedBy": "agent-1"},
			wantStatus: http.StatusBadRequest,
			wantSubstr: `"error":"invalid request"`,
		},
		{
			name:       "404 unknown mcp",
			body:       validBody,
			svc:        stubService{err: mcp.ErrNotFound},
			wantStatus: http.StatusNotFound,
			wantSubstr: `"error":"mcp not found"`,
		},
		{
			name:       "503 evaluator",
			body:       validBody,
			svc:        stubService{err: policy.ErrUnavailable},
			wantStatus: http.StatusServiceUnavailable,
			wantSubstr: `"error":"evaluator unavailable"`,
		},
		{
			name: "200 denied",
			body: validBody,
			svc: stubService{resp: gateway.EvaluateResponse{
				Decision:     "denied",
				MCPName:      "mongo-catalog-mcp",
				AccessedBy:   "agent-subtask-07",
				ViolatedRule: &rule,
				Reason:       "drop table violates write rule",
				LogID:        "abc",
			}},
			wantStatus: http.StatusOK,
			wantSubstr: `"decision":"denied"`,
		},
		{
			name: "200 approved",
			body: map[string]any{
				"mcpName":    "inventory-mcp",
				"accessedBy": "agent-orchestrator-01",
				"action":     "read",
				"payload":    map[string]any{"intent": "read stock"},
			},
			svc: stubService{resp: gateway.EvaluateResponse{
				Decision:   "approved",
				MCPName:    "inventory-mcp",
				AccessedBy: "agent-orchestrator-01",
				Reason:     "stock read allowed",
				LogID:      "def",
			}},
			wantStatus: http.StatusOK,
			wantSubstr: `"decision":"approved"`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			raw, err := json.Marshal(tt.body)
			require.NoError(t, err)
			r := httpapi.NewRouter(tt.svc)
			req := httptest.NewRequest(http.MethodPost, "/v1/evaluate", bytes.NewReader(raw))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			r.ServeHTTP(w, req)
			require.Equal(t, tt.wantStatus, w.Code)
			require.Contains(t, w.Body.String(), tt.wantSubstr)
		})
	}
}
