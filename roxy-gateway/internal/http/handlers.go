package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"

	"roxy-gateway/internal/gateway"
	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"

	"github.com/gin-gonic/gin"
)

type evaluateRequest struct {
	MCPName    string          `json:"mcpName" binding:"required"`
	AccessedBy string          `json:"accessedBy" binding:"required"`
	Action     string          `json:"action" binding:"required"`
	Payload    json.RawMessage `json:"payload"`
}

type evaluateResponse struct {
	Decision     string              `json:"decision"`
	MCPName      string              `json:"mcpName"`
	AccessedBy   string              `json:"accessedBy"`
	ViolatedRule *mcp.Rule           `json:"violatedRule"`
	Reason       string              `json:"reason"`
	LogID        string              `json:"logId"`
	Connection   *gateway.Connection `json:"connection"`
}

func handleEvaluate(svc EvaluatorService) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req evaluateRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
			return
		}

		result, err := svc.Evaluate(c.Request.Context(), gateway.EvaluateRequest{
			MCPName:    req.MCPName,
			AccessedBy: req.AccessedBy,
			Action:     req.Action,
			Payload:    req.Payload,
		})
		if err != nil {
			switch {
			case errors.Is(err, mcp.ErrNotFound):
				c.JSON(http.StatusNotFound, gin.H{"error": "mcp not found"})
			case errors.Is(err, policy.ErrUnavailable):
				c.JSON(http.StatusServiceUnavailable, gin.H{
					"error":  "evaluator unavailable",
					"detail": err.Error(),
				})
			default:
				c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			}
			return
		}

		c.JSON(http.StatusOK, evaluateResponse{
			Decision:     result.Decision,
			MCPName:      result.MCPName,
			AccessedBy:   result.AccessedBy,
			ViolatedRule: result.ViolatedRule,
			Reason:       result.Reason,
			LogID:        result.LogID,
			Connection:   result.Connection,
		})
	}
}
