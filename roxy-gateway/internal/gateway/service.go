package gateway

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"roxy-gateway/internal/dashboard"
	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
	"roxy-gateway/internal/security"
)

type MCPFinder interface {
	GetByName(ctx context.Context, name string) (*mcp.MCP, error)
}

type LogWriter interface {
	Insert(ctx context.Context, entry security.Log) (string, error)
}

type Service struct {
	mcps      MCPFinder
	logs      LogWriter
	evaluator policy.Evaluator
	notifier  dashboard.Notifier
	agent     MCPAgent
	now       func() time.Time
}

func New(mcps MCPFinder, logs LogWriter, evaluator policy.Evaluator, notifier dashboard.Notifier, agent MCPAgent) *Service {
	return &Service{
		mcps:      mcps,
		logs:      logs,
		evaluator: evaluator,
		notifier:  notifier,
		agent:     agent,
		now:       func() time.Time { return time.Now().UTC() },
	}
}

type EvaluateRequest struct {
	MCPName    string
	AccessedBy string
	Action     string
	Payload    []byte
}

type EvaluateResponse struct {
	Decision     string
	MCPName      string
	AccessedBy   string
	ViolatedRule *mcp.Rule
	Reason       string
	LogID        string
	Allowed      bool
	Upstream     *Upstream
}

func (s *Service) Evaluate(ctx context.Context, req EvaluateRequest) (EvaluateResponse, error) {
	doc, err := s.mcps.GetByName(ctx, req.MCPName)
	if err != nil {
		return EvaluateResponse{}, err
	}

	result, err := s.evaluator.Evaluate(ctx, policy.Input{
		MCP:        *doc,
		AccessedBy: req.AccessedBy,
		Action:     req.Action,
		Payload:    req.Payload,
	})
	if err != nil {
		if errors.Is(err, policy.ErrUnavailable) {
			return EvaluateResponse{}, err
		}
		return EvaluateResponse{}, fmt.Errorf("%w: %v", policy.ErrUnavailable, err)
	}

	status := security.StatusApproved
	decision := "approved"
	if !result.Allowed {
		status = security.StatusDenied
		decision = "denied"
	}

	ts := s.now()
	description := result.Reason
	if description == "" {
		description = fmt.Sprintf("action %q evaluated as %s", req.Action, decision)
	}

	logID, err := s.logs.Insert(ctx, security.Log{
		Status:      status,
		MCPID:       doc.ID,
		MCPName:     doc.Name,
		Time:        ts,
		AccessedBy:  req.AccessedBy,
		Description: description,
	})
	if err != nil {
		return EvaluateResponse{}, err
	}

	if err := s.notifier.Notify(ctx, dashboard.Notification{
		Status:       status,
		MCPName:      doc.Name,
		MCPID:        doc.ID.Hex(),
		AccessedBy:   req.AccessedBy,
		Action:       req.Action,
		ViolatedRule: result.ViolatedRule,
		Description:  description,
		Time:         ts,
	}); err != nil {
		log.Printf("dashboard notify failed: %v", err)
	}

	resp := EvaluateResponse{
		Decision:     decision,
		MCPName:      doc.Name,
		AccessedBy:   req.AccessedBy,
		ViolatedRule: result.ViolatedRule,
		Reason:       description,
		LogID:        logID,
		Allowed:      result.Allowed,
	}
	if !result.Allowed {
		log.Printf("evaluate denied mcp=%s action=%s", doc.Name, req.Action)
		return resp, nil
	}

	log.Printf("evaluate allowed mcp=%s url=%s action=%s → CallMCP", doc.Name, doc.Server.URL, req.Action)
	up, err := s.agent.CallMCP(ctx, doc, req.Action, req.Payload)
	if err != nil {
		return EvaluateResponse{}, fmt.Errorf("CallMCP name=%s url=%s auth=%s: %w",
			doc.Name, doc.Server.URL, doc.Authorization.Type, err)
	}
	resp.Upstream = &up
	return resp, nil
}
