package policy

import (
	"context"
	"errors"

	"roxy-gateway/internal/mcp"
)

var ErrUnavailable = errors.New("evaluator unavailable")

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
