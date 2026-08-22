#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q -r requirements.txt

# The API seeds the "invoices" collection automatically on startup if it's
# empty (see app/seed.py:seed_if_empty), so nothing else to do here.
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
