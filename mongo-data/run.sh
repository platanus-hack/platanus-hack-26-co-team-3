#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting local MongoDB container..."
docker compose up -d

echo "Waiting for MongoDB to be ready..."
until docker compose exec -T mongo mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
  sleep 1
done
echo "MongoDB is ready."

if [ ! -f population/.env ]; then
  echo "population/.env not found, creating it from .env-example"
  cp population/.env-example population/.env
fi

if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -q -r population/requirements.txt

echo "Populating database..."
python3 population/populate.py

echo "Done. MongoDB is running at mongodb://localhost:27017 (database: roxy)."
