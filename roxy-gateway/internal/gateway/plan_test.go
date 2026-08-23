package gateway

import (
	"testing"

	"roxy-gateway/internal/policy"

	"github.com/stretchr/testify/require"
)

func TestNormalizePlan_rejectsOtherHost(t *testing.T) {
	t.Parallel()
	_, err := normalizePlan("https://mcp.internal/catalog", []byte(`{"method":"GET","url":"https://evil.example/x"}`))
	require.ErrorIs(t, err, policy.ErrPlan)
}

func TestNormalizePlan_joinsPathToBase(t *testing.T) {
	t.Parallel()
	got, err := normalizePlan("https://mcp.internal/mongo-catalog", []byte(`{"method":"POST","url":"/query","body":{"q":1}}`))
	require.NoError(t, err)
	require.Equal(t, "https://mcp.internal/mongo-catalog/query", got.URL)
}
