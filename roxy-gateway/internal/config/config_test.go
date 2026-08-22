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
				"MONGO_URI":     "mongodb://localhost:27017",
				"EVALUATOR_URL": "http://127.0.0.1:8080/evaluate",
				"HTTP_ADDR":     "",
				"MONGO_DB_NAME": "",
				"PORT":          "",
				"DASHBOARD_URL": "",
			},
			check: func(t *testing.T, cfg Config) {
				require.Equal(t, ":8080", cfg.HTTPAddr)
				require.Equal(t, "roxy", cfg.MongoDBName)
				require.Equal(t, "mongodb://localhost:27017", cfg.MongoURI)
				require.Equal(t, "http://127.0.0.1:8080/evaluate", cfg.EvaluatorURL)
			},
		},
		{
			name: "missing mongo",
			env: map[string]string{
				"MONGO_URI":     "",
				"EVALUATOR_URL": "http://127.0.0.1:8080/evaluate",
			},
			wantErr: "MONGO_URI",
		},
		{
			name: "missing evaluator url",
			env: map[string]string{
				"MONGO_URI":     "mongodb://localhost:27017",
				"EVALUATOR_URL": "",
			},
			wantErr: "EVALUATOR_URL",
		},
		{
			name: "render PORT overrides HTTP_ADDR",
			env: map[string]string{
				"MONGO_URI":     "mongodb://localhost:27017",
				"EVALUATOR_URL": "http://127.0.0.1:8080/evaluate",
				"HTTP_ADDR":     ":8080",
				"PORT":          "10000",
			},
			check: func(t *testing.T, cfg Config) {
				require.Equal(t, ":10000", cfg.HTTPAddr)
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
