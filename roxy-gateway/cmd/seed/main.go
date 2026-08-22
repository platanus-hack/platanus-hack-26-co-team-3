package main

import (
	"context"
	"log"
	"os"
	"time"

	"roxy-gateway/internal/mcp"

	"github.com/joho/godotenv"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

func main() {
	_ = godotenv.Load(".env", "roxy-gateway/.env", ".env.production")

	uri := os.Getenv("MONGO_URI")
	if uri == "" {
		log.Fatal("MONGO_URI is required")
	}
	dbName := os.Getenv("MONGO_DB_NAME")
	if dbName == "" {
		dbName = "roxy"
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	client, err := mongo.Connect(ctx, options.Client().ApplyURI(uri))
	if err != nil {
		log.Fatal(err)
	}
	defer func() { _ = client.Disconnect(context.Background()) }()
	if err := client.Ping(ctx, nil); err != nil {
		log.Fatal(err)
	}

	col := client.Database(dbName).Collection("mcps")
	now := time.Now().UTC()
	docs := mockMCPs(now)

	inserted := 0
	for _, doc := range docs {
		res, err := col.UpdateOne(
			ctx,
			bson.M{"name": doc.Name},
			bson.M{"$setOnInsert": doc},
			options.Update().SetUpsert(true),
		)
		if err != nil {
			log.Fatal(err)
		}
		if res.UpsertedCount > 0 {
			inserted++
		}
	}
	log.Printf("seed complete: %d new MCP docs (existing names left unchanged)", inserted)
}

func mockMCPs(now time.Time) []mcp.MCP {
	return []mcp.MCP{
		{
			Name:        "mongo-catalog-mcp",
			Description: "MCP exposing read/write access to the product catalog database",
			Server:      mcp.Server{URL: "https://mcp.internal/mongo-catalog", Protocol: "mcp"},
			Authorization: mcp.Authorization{
				Type:           "bearer",
				CredentialsRef: "vault://roxy/mcp/mongo-catalog",
			},
			Rules: []mcp.Rule{
				{Priority: 1, Instruction: "deny any write operation outside working hours"},
				{Priority: 2, Instruction: "allow read-only queries on the 'orders' collection"},
			},
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			Name:        "payments-mcp",
			Description: "MCP exposing payment processing and transaction records",
			Server:      mcp.Server{URL: "https://mcp.internal/payments", Protocol: "mcp"},
			Authorization: mcp.Authorization{
				Type:           "oauth2",
				CredentialsRef: "vault://roxy/mcp/payments",
			},
			Rules: []mcp.Rule{
				{Priority: 1, Instruction: "deny writes to 'transactions' from non-orchestrator agents"},
				{Priority: 2, Instruction: "require explicit intent confirmation for refunds"},
			},
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			Name:        "inventory-mcp",
			Description: "MCP exposing warehouse inventory levels and stock adjustments",
			Server:      mcp.Server{URL: "https://mcp.internal/inventory", Protocol: "sse"},
			Authorization: mcp.Authorization{
				Type:           "apiKey",
				CredentialsRef: "vault://roxy/mcp/inventory",
			},
			Rules: []mcp.Rule{
				{Priority: 1, Instruction: "allow stock read for all delegated agents"},
				{Priority: 2, Instruction: "deny bulk stock adjustments above 1000 units"},
			},
			CreatedAt: now,
			UpdatedAt: now,
		},
	}
}
