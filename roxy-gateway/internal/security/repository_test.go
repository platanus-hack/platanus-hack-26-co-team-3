package security

import (
	"testing"

	"github.com/stretchr/testify/require"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

func TestInsertedIDHex(t *testing.T) {
	t.Parallel()
	oid := primitive.NewObjectID()
	tests := []struct {
		name string
		id   interface{}
		want string
	}{
		{name: "object id", id: oid, want: oid.Hex()},
		{name: "string id", id: "not-an-objectid", want: ""},
		{name: "nil", id: nil, want: ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			require.Equal(t, tt.want, insertedIDHex(tt.id))
		})
	}
}
