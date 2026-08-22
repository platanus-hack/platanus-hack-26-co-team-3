package mcp

import (
	"context"
	"errors"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

var ErrNotFound = errors.New("mcp not found")

type Repository struct {
	col *mongo.Collection
}

func NewRepository(db *mongo.Database) *Repository {
	return &Repository{col: db.Collection("mcps")}
}

func mapFindError(err error) error {
	if err == nil {
		return nil
	}
	if errors.Is(err, mongo.ErrNoDocuments) {
		return ErrNotFound
	}
	return err
}

func (r *Repository) GetByName(ctx context.Context, name string) (*MCP, error) {
	var doc MCP
	err := r.col.FindOne(ctx, bson.M{"name": name}).Decode(&doc)
	if err != nil {
		return nil, mapFindError(err)
	}
	return &doc, nil
}
