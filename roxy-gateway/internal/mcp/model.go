package mcp

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

type Rule struct {
	Priority    int    `bson:"priority" json:"priority"`
	Instruction string `bson:"instruction" json:"instruction"`
}

type Server struct {
	URL      string `bson:"url" json:"url"`
	Protocol string `bson:"protocol,omitempty" json:"protocol,omitempty"`
}

type Authorization struct {
	Type           string `bson:"type" json:"type"`
	CredentialsRef string `bson:"credentialsRef,omitempty" json:"credentialsRef,omitempty"`
}

type MCP struct {
	ID            primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	Name          string             `bson:"name" json:"name"`
	Description   string             `bson:"description,omitempty" json:"description,omitempty"`
	Server        Server             `bson:"server" json:"server"`
	Authorization Authorization      `bson:"authorization" json:"authorization"`
	Rules         []Rule             `bson:"rules" json:"rules"`
	CreatedAt     time.Time          `bson:"createdAt,omitempty" json:"createdAt,omitempty"`
	UpdatedAt     time.Time          `bson:"updatedAt,omitempty" json:"updatedAt,omitempty"`
}
