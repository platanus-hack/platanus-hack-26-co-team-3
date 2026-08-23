package gateway

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"roxy-gateway/internal/dashboard"
	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
	"roxy-gateway/internal/security"

	"github.com/stretchr/testify/require"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

type fakeFinder struct {
	doc *mcp.MCP
	err error
}

func (f fakeFinder) GetByName(context.Context, string) (*mcp.MCP, error) {
	return f.doc, f.err
}

type fakeLogs struct {
	mu      sync.Mutex
	entries []security.Log
	err     error
}

func (f *fakeLogs) Insert(_ context.Context, entry security.Log) (string, error) {
	if f.err != nil {
		return "", f.err
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	f.entries = append(f.entries, entry)
	return "log-1", nil
}

type fakeEvaluator struct {
	result policy.Result
	err    error
}

func (f fakeEvaluator) Evaluate(context.Context, policy.Input) (policy.Result, error) {
	return f.result, f.err
}

type fakeNotifier struct {
	mu    sync.Mutex
	calls []dashboard.Notification
	err   error
}

func (f *fakeNotifier) Notify(_ context.Context, n dashboard.Notification) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, n)
	return f.err
}

type fakeCaller struct {
	up    Upstream
	err   error
	calls int
	last  PlannedCall
}

func (f *fakeCaller) Invoke(_ context.Context, _ *mcp.MCP, plan PlannedCall) (Upstream, error) {
	f.calls++
	f.last = plan
	return f.up, f.err
}

type fakePlanner struct {
	plan  PlannedCall
	err   error
	calls int
}

func (f *fakePlanner) Plan(context.Context, *mcp.MCP, string, []byte) (PlannedCall, error) {
	f.calls++
	return f.plan, f.err
}

func catalogMCP() *mcp.MCP {
	return &mcp.MCP{
		ID:   primitive.NewObjectID(),
		Name: "mongo-catalog-mcp",
		Server: mcp.Server{
			URL:      "https://mcp.internal/mongo-catalog",
			Protocol: "mcp",
		},
		Authorization: mcp.Authorization{
			Type:           "bearer",
			CredentialsRef: "vault://roxy/mcp/mongo-catalog",
			Credentials:    "tok_catalog_demo",
		},
		Rules: []mcp.Rule{
			{Priority: 1, Instruction: "deny any write operation outside working hours"},
		},
	}
}

func TestService_Evaluate(t *testing.T) {
	fixed := time.Date(2026, 8, 22, 12, 0, 0, 0, time.UTC)
	rule := mcp.Rule{Priority: 1, Instruction: "deny any write operation outside working hours"}

	tests := []struct {
		name       string
		finder     MCPFinder
		eval       fakeEvaluator
		notifyErr  error
		wantErr    error
		wantDec    string
		wantLogs   int
		wantStatus string
		wantNotes  int
		wantRule   bool
	}{
		{
			name:       "approve writes log and notifies",
			finder:     fakeFinder{doc: catalogMCP()},
			eval:       fakeEvaluator{result: policy.Result{Allowed: true, Reason: "read ok"}},
			wantDec:    "approved",
			wantLogs:   1,
			wantStatus: security.StatusApproved,
			wantNotes:  1,
		},
		{
			name:   "deny drop table writes log and notifies with rule",
			finder: fakeFinder{doc: catalogMCP()},
			eval: fakeEvaluator{result: policy.Result{
				Allowed:      false,
				ViolatedRule: &rule,
				Reason:       "drop table violates write rule",
			}},
			wantDec:    "denied",
			wantLogs:   1,
			wantStatus: security.StatusDenied,
			wantNotes:  1,
			wantRule:   true,
		},
		{
			name:      "mcp missing",
			finder:    fakeFinder{err: mcp.ErrNotFound},
			eval:      fakeEvaluator{result: policy.Result{Allowed: true}},
			wantErr:   mcp.ErrNotFound,
			wantLogs:  0,
			wantNotes: 0,
		},
		{
			name:      "evaluator down",
			finder:    fakeFinder{doc: catalogMCP()},
			eval:      fakeEvaluator{err: policy.ErrUnavailable},
			wantErr:   policy.ErrUnavailable,
			wantLogs:  0,
			wantNotes: 0,
		},
		{
			name:       "dashboard down still succeeds",
			finder:     fakeFinder{doc: catalogMCP()},
			eval:       fakeEvaluator{result: policy.Result{Allowed: true, Reason: "ok"}},
			notifyErr:  errors.New("dashboard down"),
			wantDec:    "approved",
			wantLogs:   1,
			wantStatus: security.StatusApproved,
			wantNotes:  1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			logs := &fakeLogs{}
			notes := &fakeNotifier{err: tt.notifyErr}
			caller := &fakeCaller{up: Upstream{StatusCode: 200, Body: []byte(`{"ok":true}`)}}
			planner := &fakePlanner{plan: PlannedCall{Method: "POST", URL: "https://mcp.internal/mongo-catalog/tools/call"}}
			svc := New(tt.finder, logs, tt.eval, notes, planner, caller)
			svc.now = func() time.Time { return fixed }

			got, err := svc.Evaluate(context.Background(), EvaluateRequest{
				MCPName:    "mongo-catalog-mcp",
				AccessedBy: "agent-subtask-07",
				Action:     "drop_table",
				Payload:    []byte(`{"intent":"DROP TABLE orders"}`),
			})
			if tt.wantErr != nil {
				require.ErrorIs(t, err, tt.wantErr)
				require.Len(t, logs.entries, tt.wantLogs)
				require.Len(t, notes.calls, tt.wantNotes)
				return
			}
			require.NoError(t, err)
			require.Equal(t, tt.wantDec, got.Decision)
			require.Equal(t, "mongo-catalog-mcp", got.MCPName)
			require.Equal(t, "log-1", got.LogID)
			require.Len(t, logs.entries, tt.wantLogs)
			require.Equal(t, tt.wantStatus, logs.entries[0].Status)
			require.Len(t, notes.calls, tt.wantNotes)
			require.Equal(t, tt.wantStatus, notes.calls[0].Status)
			if tt.wantDec == "approved" {
				require.True(t, got.Allowed)
				require.Equal(t, 1, planner.calls)
				require.Equal(t, 1, caller.calls)
				require.Equal(t, "https://mcp.internal/mongo-catalog/tools/call", caller.last.URL)
				require.NotNil(t, got.Upstream)
				require.JSONEq(t, `{"ok":true}`, string(got.Upstream.Body))
			} else {
				require.False(t, got.Allowed)
				require.Equal(t, 0, planner.calls)
				require.Equal(t, 0, caller.calls)
				require.Nil(t, got.Upstream)
			}
			if tt.wantRule {
				require.NotNil(t, got.ViolatedRule)
				require.Equal(t, 1, got.ViolatedRule.Priority)
				require.NotNil(t, notes.calls[0].ViolatedRule)
			}
		})
	}
}
