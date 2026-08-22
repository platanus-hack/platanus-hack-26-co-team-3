package mcp

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/require"
	"go.mongodb.org/mongo-driver/mongo"
)

func TestMapFindError(t *testing.T) {
	t.Parallel()
	other := errors.New("connection refused")
	tests := []struct {
		name string
		in   error
		want error
	}{
		{name: "nil", in: nil, want: nil},
		{name: "no documents", in: mongo.ErrNoDocuments, want: ErrNotFound},
		{name: "other error unchanged", in: other, want: other},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := mapFindError(tt.in)
			if tt.want == nil {
				require.NoError(t, got)
				return
			}
			require.ErrorIs(t, got, tt.want)
		})
	}
}
