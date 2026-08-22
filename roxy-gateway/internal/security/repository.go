package security

import (
	"context"
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
)

type Repository struct {
	col *mongo.Collection
}

func NewRepository(db *mongo.Database) *Repository {
	return &Repository{col: db.Collection("security")}
}

func insertedIDHex(id interface{}) string {
	oid, ok := id.(primitive.ObjectID)
	if !ok {
		return ""
	}
	return oid.Hex()
}

func (r *Repository) Insert(ctx context.Context, entry Log) (string, error) {
	if entry.Time.IsZero() {
		entry.Time = time.Now().UTC()
	}
	res, err := r.col.InsertOne(ctx, entry)
	if err != nil {
		return "", err
	}
	return insertedIDHex(res.InsertedID), nil
}
