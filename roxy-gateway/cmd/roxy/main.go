package main

import (
	"context"
	"log"
	"time"

	"roxy-gateway/internal/config"
	"roxy-gateway/internal/dashboard"
	"roxy-gateway/internal/gateway"
	httpapi "roxy-gateway/internal/http"
	"roxy-gateway/internal/mcp"
	"roxy-gateway/internal/policy"
	"roxy-gateway/internal/security"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

func main() {
	_ = godotenv.Load(".env", "roxy-gateway/.env")

	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	client, err := mongo.Connect(ctx, options.Client().ApplyURI(cfg.MongoURI))
	if err != nil {
		log.Fatal(err)
	}
	defer func() { _ = client.Disconnect(context.Background()) }()
	if err := client.Ping(ctx, nil); err != nil {
		log.Fatal(err)
	}

	db := client.Database(cfg.MongoDBName)
	var evaluator policy.Evaluator
	if cfg.AnthropicAPIKey != "" {
		log.Printf("evaluator: anthropic model=%s", cfg.AnthropicModel)
		evaluator = policy.NewAnthropicClient(cfg.AnthropicBaseURL, cfg.AnthropicAPIKey, cfg.AnthropicModel)
	} else {
		log.Printf("evaluator: openrouter model=%s", cfg.OpenRouterModel)
		evaluator = policy.NewClient(cfg.OpenRouterBaseURL, cfg.OpenRouterAPIKey, cfg.OpenRouterModel)
	}
	svc := gateway.New(
		mcp.NewRepository(db),
		security.NewRepository(db),
		evaluator,
		dashboard.NewClient(cfg.DashboardURL),
	)

	gin.SetMode(gin.ReleaseMode)
	r := httpapi.NewRouter(svc)
	log.Printf("roxy listening on %s", cfg.HTTPAddr)
	if err := r.Run(cfg.HTTPAddr); err != nil {
		log.Fatal(err)
	}
}
