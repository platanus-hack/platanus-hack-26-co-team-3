package config

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestLoad(t *testing.T) {
	tests := []struct {
		name    string
		env     map[string]string
		wantErr string
		check   func(t *testing.T, cfg Config)
	}{
		{
			name: "defaults",
			env: map[string]string{
				"MONGO_URI":           "mongodb://localhost:27017",
				"OPENROUTER_API_KEY":  "sk-test",
				"ANTHROPIC_API_KEY":   "",
				"HTTP_ADDR":           "",
				"MONGO_DB_NAME":       "",
				"OPENROUTER_MODEL":    "",
				"OPENROUTER_BASE_URL": "",
				"ANTHROPIC_MODEL":     "",
				"ANTHROPIC_BASE_URL":  "",
				"DASHBOARD_URL":       "",
			},
			check: func(t *testing.T, cfg Config) {
				require.Equal(t, ":8080", cfg.HTTPAddr)
				require.Equal(t, "roxy", cfg.MongoDBName)
				require.Equal(t, "openai/gpt-4o-mini", cfg.OpenRouterModel)
				require.Equal(t, "https://openrouter.ai/api/v1", cfg.OpenRouterBaseURL)
				require.Equal(t, "mongodb://localhost:27017", cfg.MongoURI)
				require.Equal(t, "sk-test", cfg.OpenRouterAPIKey)
			},
		},
		{
			name: "missing mongo",
			env: map[string]string{
				"MONGO_URI":          "",
				"OPENROUTER_API_KEY": "sk-test",
			},
			wantErr: "MONGO_URI",
		},
		{
			name: "missing llm key",
			env: map[string]string{
				"MONGO_URI":          "mongodb://localhost:27017",
				"OPENROUTER_API_KEY": "",
				"ANTHROPIC_API_KEY":  "",
			},
			wantErr: "ANTHROPIC_API_KEY or OPENROUTER_API_KEY",
		},
		{
			name: "anthropic key is enough",
			env: map[string]string{
				"MONGO_URI":          "mongodb://localhost:27017",
				"OPENROUTER_API_KEY": "",
				"ANTHROPIC_API_KEY":  "sk-ant-test",
			},
			check: func(t *testing.T, cfg Config) {
				require.Equal(t, "sk-ant-test", cfg.AnthropicAPIKey)
				require.Equal(t, "claude-sonnet-5", cfg.AnthropicModel)
			},
		},
		{
			name: "trims openrouter base url",
			env: map[string]string{
				"MONGO_URI":           "mongodb://localhost:27017",
				"OPENROUTER_API_KEY":  "sk-test",
				"OPENROUTER_BASE_URL": "https://example.com/v1/",
			},
			check: func(t *testing.T, cfg Config) {
				require.Equal(t, "https://example.com/v1", cfg.OpenRouterBaseURL)
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			for k, v := range tt.env {
				t.Setenv(k, v)
			}
			cfg, err := Load()
			if tt.wantErr != "" {
				require.Error(t, err)
				require.True(t, strings.Contains(err.Error(), tt.wantErr))
				return
			}
			require.NoError(t, err)
			tt.check(t, cfg)
		})
	}
}
