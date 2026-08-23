package config

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	HTTPAddr         string
	MongoURI         string
	MongoDBName      string
	EvaluatorURL     string
	AnthropicAPIKey  string
	AnthropicModel   string
	AnthropicBaseURL string
	DashboardURL     string
}

func Load() (Config, error) {
	cfg := Config{
		HTTPAddr:         getenv("HTTP_ADDR", ":8080"),
		MongoURI:         os.Getenv("MONGO_URI"),
		MongoDBName:      getenv("MONGO_DB_NAME", "roxy"),
		EvaluatorURL:     os.Getenv("EVALUATOR_URL"),
		AnthropicAPIKey:  os.Getenv("ANTHROPIC_API_KEY"),
		AnthropicModel:   getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
		AnthropicBaseURL: strings.TrimRight(getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), "/"),
		DashboardURL:     os.Getenv("DASHBOARD_URL"),
	}
	if port := os.Getenv("PORT"); port != "" {
		if !strings.HasPrefix(port, ":") {
			port = ":" + port
		}
		cfg.HTTPAddr = port
	}
	var missing []string
	if cfg.MongoURI == "" {
		missing = append(missing, "MONGO_URI")
	}
	if cfg.EvaluatorURL == "" {
		missing = append(missing, "EVALUATOR_URL")
	}
	if cfg.AnthropicAPIKey == "" {
		missing = append(missing, "ANTHROPIC_API_KEY")
	}
	if len(missing) > 0 {
		return Config{}, fmt.Errorf("missing required env: %s", strings.Join(missing, ", "))
	}
	return cfg, nil
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
