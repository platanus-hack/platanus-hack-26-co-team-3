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

	tests := []struct {
		name       string
		body       any
		svc        stubService
		wantStatus int
		wantBody   string
	}{
		{
			name:       "400 missing action",
			body:       map[string]any{"mcpName": "mongo-catalog-mcp", "accessedBy": "agent-1"},
			wantStatus: http.StatusBadRequest,
			wantBody:   `"error":"invalid request"`,
		},
		{
			name:       "404 unknown mcp",
			body:       validBody,
			svc:        stubService{err: mcp.ErrNotFound},
			wantStatus: http.StatusNotFound,
			wantBody:   `"error":"mcp not found"`,
		},
		{
			name:       "503 evaluator",
			body:       validBody,
			svc:        stubService{err: policy.ErrUnavailable},
			wantStatus: http.StatusServiceUnavailable,
			wantBody:   `"error":"evaluator unavailable"`,
		},
		{
			name:       "503 planner",
			body:       validBody,
			svc:        stubService{err: policy.ErrPlan},
			wantStatus: http.StatusServiceUnavailable,
			wantBody:   `"error":"planner unavailable"`,
		},
		{
			name: "403 denied has empty body",
			body: validBody,
			svc: stubService{resp: gateway.EvaluateResponse{
				Decision: "denied",
				Allowed:  false,
			}},
			wantStatus: http.StatusForbidden,
			wantBody:   "",
		},
		{
			name: "200 allowed returns raw mcp body",
			body: map[string]any{
				"mcpName":    "inventory-mcp",
				"accessedBy": "agent-orchestrator-01",
				"action":     "read",
				"payload":    map[string]any{"intent": "read stock"},
			},
			svc: stubService{resp: gateway.EvaluateResponse{
				Decision: "approved",
				Allowed:  true,
				Upstream: &gateway.Upstream{
					StatusCode:  http.StatusOK,
					ContentType: "application/json",
					Body:        []byte(`{"stock":42}`),
				},
			}},
			wantStatus: http.StatusOK,
			wantBody:   `{"stock":42}`,
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
			if tt.wantBody == "" {
				require.Empty(t, w.Body.String())
				return
			}
			require.Contains(t, w.Body.String(), tt.wantBody)
		})
	}
}
