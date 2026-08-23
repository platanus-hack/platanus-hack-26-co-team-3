#!/usr/bin/env bash
set -euo pipefail

# Non-interactive wrapper around deploy.sh: reads MONGO_URI, VPC_ID, SUBNET_ID,
# EVALUATOR_URL, and (optionally) ACM_CERTIFICATE_ARN/DOMAIN_ALIASES/DASHBOARD_URL from an
# .env file and exports them, so deploy.sh finds them already set and skips its interactive
# prompts entirely. Useful for CI or repeatable local deploys. Any arguments passed to this
# script forward straight to deploy.sh (the do_infra/do_api/do_app/do_demo_api/do_roxy_gateway
# flags).
#
# Usage: ./scripts/deploy-from-env.sh [do_infra] [do_api] [do_app] [do_demo_api] [do_roxy_gateway]
# Env:   ENV_FILE — path to the .env file (default: infra/.env)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/.."
ENV_FILE="${ENV_FILE:-$INFRA_DIR/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example to .env and fill it in, or set ENV_FILE to point elsewhere."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

for var in MONGO_URI VPC_ID SUBNET_ID EVALUATOR_URL; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set in $ENV_FILE."
    exit 1
  fi
done

exec "$SCRIPT_DIR/deploy.sh" "$@"
