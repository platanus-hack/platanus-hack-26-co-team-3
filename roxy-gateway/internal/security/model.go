package security

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

const (
	StatusApproved = "approved"
	StatusDenied   = "denied"
)

type Log struct {
	ID          primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	Status      string             `bson:"status" json:"status"`
	MCPID       primitive.ObjectID `bson:"mcpId" json:"mcpId"`
	MCPName     string             `bson:"mcpName" json:"mcpName"`
	Time        time.Time          `bson:"time" json:"time"`
	AccessedBy  string             `bson:"accessedBy" json:"accessedBy"`
	Description string             `bson:"description" json:"description"`
}
