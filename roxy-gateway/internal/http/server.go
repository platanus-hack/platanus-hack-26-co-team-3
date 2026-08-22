package httpapi

import (
	"context"
	"net/http"

	"roxy-gateway/internal/gateway"

	"github.com/gin-gonic/gin"
)

type EvaluatorService interface {
	Evaluate(ctx context.Context, req gateway.EvaluateRequest) (gateway.EvaluateResponse, error)
}

func NewRouter(svc EvaluatorService) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "roxy"})
	})
	r.POST("/v1/evaluate", handleEvaluate(svc))
	return r
}
