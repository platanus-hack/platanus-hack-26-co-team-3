package config

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	HTTPAddr          string
	MongoURI          string
	MongoDBName       string
	OpenRouterAPIKey  string
	OpenRouterModel   string
	OpenRouterBaseURL string
	AnthropicAPIKey   string
	AnthropicModel    string
	AnthropicBaseURL  string
	DashboardURL      string
}

func Load() (Config, error) {
	cfg := Config{
		HTTPAddr:          getenv("HTTP_ADDR", ":8080"),
		MongoURI:          os.Getenv("MONGO_URI"),
		MongoDBName:       getenv("MONGO_DB_NAME", "roxy"),
		OpenRouterAPIKey:  os.Getenv("OPENROUTER_API_KEY"),
		OpenRouterModel:   getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
		OpenRouterBaseURL: strings.TrimRight(getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), "/"),
		AnthropicAPIKey:   os.Getenv("ANTHROPIC_API_KEY"),
		AnthropicModel:    getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
		AnthropicBaseURL:  strings.TrimRight(getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), "/"),
		DashboardURL:      os.Getenv("DASHBOARD_URL"),
	}
	var missing []string
	if cfg.MongoURI == "" {
		missing = append(missing, "MONGO_URI")
	}
	if cfg.AnthropicAPIKey == "" && cfg.OpenRouterAPIKey == "" {
		missing = append(missing, "ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
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
