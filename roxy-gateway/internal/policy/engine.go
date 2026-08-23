package policy

import (
	"context"
	"errors"

	"roxy-gateway/internal/mcp"
)

var (
	ErrUnavailable = errors.New("evaluator unavailable")
	ErrPlan        = errors.New("mcp request planner unavailable")
	ErrUpstream    = errors.New("mcp upstream unavailable")
)

type Input struct {
	MCP        mcp.MCP
	AccessedBy string
	Action     string
	Payload    []byte
}

type Result struct {
	Allowed      bool
	ViolatedRule *mcp.Rule
	Reason       string
}

type Evaluator interface {
	Evaluate(ctx context.Context, in Input) (Result, error)
}

func ruleByPriority(rules []mcp.Rule, priority int) *mcp.Rule {
	for i := range rules {
		if rules[i].Priority == priority {
			rule := rules[i]
			return &rule
		}
	}
	return nil
}
