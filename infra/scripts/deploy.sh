#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/.."
API_DIR="$INFRA_DIR/../dashboard/api"
APP_DIR="$INFRA_DIR/../dashboard/app"
DEMO_API_DIR="$INFRA_DIR/../demo-api"
ROXY_GATEWAY_DIR="$INFRA_DIR/../roxy-gateway"
TFVARS_FILE="terraform.tfvars"

info() { echo ""; echo "==> $*"; }

DO_INFRA="${1:-true}"
DO_API="${2:-true}"
DO_APP="${3:-true}"
DO_DEMO_API="${4:-true}"
DO_ROXY_GATEWAY="${5:-true}"

for cmd in terraform docker aws npm; do
  command -v "$cmd" &>/dev/null || { echo "ERROR: $cmd is required but not installed."; exit 1; }
done

cd "$INFRA_DIR"

# Non-secret values persist to terraform.tfvars (gitignored) and are offered back as
# defaults on the next run. mongo_uri is never written to disk — it's re-entered each
# run (hidden input) and passed only via -var to terraform apply.
EXISTING_VPC_ID=""
EXISTING_SUBNET_ID=""
EXISTING_ACM_ARN=""
EXISTING_DOMAIN_ALIASES=""
EXISTING_EVALUATOR_URL=""
EXISTING_DASHBOARD_URL=""
if [[ -f "$TFVARS_FILE" ]]; then
  EXISTING_VPC_ID=$(sed -n -E 's/^vpc_id *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_SUBNET_ID=$(sed -n -E 's/^subnet_id *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_ACM_ARN=$(sed -n -E 's/^acm_certificate_arn *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_DOMAIN_ALIASES=$(sed -n -E 's/^domain_aliases *= *\[(.*)\]$/\1/p' "$TFVARS_FILE" | sed -E 's/"//g; s/, */,/g')
  EXISTING_EVALUATOR_URL=$(sed -n -E 's/^evaluator_url *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_DASHBOARD_URL=$(sed -n -E 's/^dashboard_url *= *"(.*)"$/\1/p' "$TFVARS_FILE")
fi

info "Configuration"

# Each value is taken from the environment if already set (e.g. by deploy-from-env.sh) —
# only prompts interactively for whatever's missing.
MONGO_URI="${MONGO_URI:-}"
if [[ -z "$MONGO_URI" ]]; then
  read -r -s -p "MongoDB connection string (mongo_uri, input hidden): " MONGO_URI
  echo ""
fi
[[ -n "$MONGO_URI" ]] || { echo "ERROR: mongo_uri is required."; exit 1; }

VPC_ID="${VPC_ID:-}"
if [[ -z "$VPC_ID" ]]; then
  read -r -p "VPC id (vpc_id)${EXISTING_VPC_ID:+ [$EXISTING_VPC_ID]}: " VPC_ID
  VPC_ID="${VPC_ID:-$EXISTING_VPC_ID}"
fi
[[ -n "$VPC_ID" ]] || { echo "ERROR: vpc_id is required."; exit 1; }

SUBNET_ID="${SUBNET_ID:-}"
if [[ -z "$SUBNET_ID" ]]; then
  read -r -p "Subnet id (subnet_id)${EXISTING_SUBNET_ID:+ [$EXISTING_SUBNET_ID]}: " SUBNET_ID
  SUBNET_ID="${SUBNET_ID:-$EXISTING_SUBNET_ID}"
fi
[[ -n "$SUBNET_ID" ]] || { echo "ERROR: subnet_id is required."; exit 1; }

ACM_CERTIFICATE_ARN="${ACM_CERTIFICATE_ARN:-}"
if [[ -z "$ACM_CERTIFICATE_ARN" ]]; then
  read -r -p "ACM certificate ARN (acm_certificate_arn, optional — blank uses the CloudFront default cert)${EXISTING_ACM_ARN:+ [$EXISTING_ACM_ARN]}: " ACM_CERTIFICATE_ARN
  ACM_CERTIFICATE_ARN="${ACM_CERTIFICATE_ARN:-$EXISTING_ACM_ARN}"
fi

DOMAIN_ALIASES="${DOMAIN_ALIASES:-}"
if [[ -z "$DOMAIN_ALIASES" ]]; then
  read -r -p "Domain aliases (domain_aliases, optional, comma-separated — blank for none)${EXISTING_DOMAIN_ALIASES:+ [$EXISTING_DOMAIN_ALIASES]}: " DOMAIN_ALIASES
  DOMAIN_ALIASES="${DOMAIN_ALIASES:-$EXISTING_DOMAIN_ALIASES}"
fi

EVALUATOR_URL="${EVALUATOR_URL:-}"
if [[ -z "$EVALUATOR_URL" ]]; then
  read -r -p "Evaluator URL (evaluator_url, roxy-gateway's policy/verification service)${EXISTING_EVALUATOR_URL:+ [$EXISTING_EVALUATOR_URL]}: " EVALUATOR_URL
  EVALUATOR_URL="${EVALUATOR_URL:-$EXISTING_EVALUATOR_URL}"
fi
[[ -n "$EVALUATOR_URL" ]] || { echo "ERROR: evaluator_url is required (roxy-gateway refuses to start without it)."; exit 1; }

DASHBOARD_URL="${DASHBOARD_URL:-}"
if [[ -z "$DASHBOARD_URL" ]]; then
  read -r -p "Dashboard URL (dashboard_url, optional — blank uses the default, http://localhost:8000/log)${EXISTING_DASHBOARD_URL:+ [$EXISTING_DASHBOARD_URL]}: " DASHBOARD_URL
  DASHBOARD_URL="${DASHBOARD_URL:-$EXISTING_DASHBOARD_URL}"
fi

info "Writing $TFVARS_FILE..."
{
  echo "vpc_id = \"$VPC_ID\""
  echo "subnet_id = \"$SUBNET_ID\""
  echo "evaluator_url = \"$EVALUATOR_URL\""
  if [[ -n "$DASHBOARD_URL" ]]; then
    echo "dashboard_url = \"$DASHBOARD_URL\""
  fi
  if [[ -n "$ACM_CERTIFICATE_ARN" ]]; then
    echo "acm_certificate_arn = \"$ACM_CERTIFICATE_ARN\""
  fi
  if [[ -n "$DOMAIN_ALIASES" ]]; then
    IFS=',' read -ra _domain_alias_items <<< "$DOMAIN_ALIASES"
    _hcl_aliases=()
    for _alias in "${_domain_alias_items[@]}"; do
      _alias="$(echo "$_alias" | xargs)"
      [[ -n "$_alias" ]] && _hcl_aliases+=("\"$_alias\"")
    done
    if [[ ${#_hcl_aliases[@]} -gt 0 ]]; then
      _joined_aliases=$(IFS=,; echo "${_hcl_aliases[*]}")
      echo "domain_aliases = [$_joined_aliases]"
    fi
  fi
} > "$TFVARS_FILE"
terraform fmt "$TFVARS_FILE" >/dev/null

info "terraform init..."
terraform init -input=false

info "terraform fmt -check..."
if ! terraform fmt -check -recursive; then
  echo "ERROR: files are not gofmt'd — run 'terraform fmt -recursive' and re-run this script."
  exit 1
fi

info "terraform validate..."
terraform validate

if [[ "$DO_INFRA" == "true" ]]; then
  info "terraform apply..."
  terraform apply -auto-approve \
    -var-file="$TFVARS_FILE" \
    -var="mongo_uri=$MONGO_URI"
else
  info "Skipping infra (do_infra=false)"
fi

ECR_REPO_URL=$(terraform output -raw ecr_repository_url)
ECR_REGISTRY="${ECR_REPO_URL%%/*}"
AWS_REGION=$(terraform output -raw aws_region)
S3_BUCKET=$(terraform output -raw s3_bucket_name)
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
ECS_SERVICE=$(terraform output -raw ecs_service_name)
DEMO_API_ECR_REPO_URL=$(terraform output -raw demo_api_ecr_repository_url)
DEMO_API_ECS_SERVICE=$(terraform output -raw demo_api_ecs_service_name)
ROXY_GATEWAY_ECR_REPO_URL=$(terraform output -raw roxy_gateway_ecr_repository_url)
ROXY_GATEWAY_ECS_SERVICE=$(terraform output -raw roxy_gateway_ecs_service_name)
CLOUDFRONT_DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)
SITE_URL=$(terraform output -raw site_url)

if [[ "$DO_API" == "true" || "$DO_DEMO_API" == "true" || "$DO_ROXY_GATEWAY" == "true" ]]; then
  info "Logging in to ECR ($ECR_REGISTRY)..."
  aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
fi

if [[ "$DO_API" == "true" ]]; then
  # --platform linux/amd64: the EC2 instance (t3a.micro) is x86_64. Building without an
  # explicit platform on an Apple Silicon Mac produces an arm64-only image that ECS can't
  # pull (CannotPullContainerError: no matching manifest for linux/amd64).
  info "Building and pushing API image (linux/amd64)..."
  docker buildx build --platform linux/amd64 -t "$ECR_REPO_URL:latest" --push "$API_DIR"

  info "Forcing new ECS deployment ($ECS_CLUSTER/$ECS_SERVICE)..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --force-new-deployment \
    --region "$AWS_REGION" >/dev/null
else
  info "Skipping API build/deploy (do_api=false)"
fi

if [[ "$DO_DEMO_API" == "true" ]]; then
  info "Building and pushing demo-api image (linux/amd64)..."
  docker buildx build --platform linux/amd64 -t "$DEMO_API_ECR_REPO_URL:latest" --push "$DEMO_API_DIR"

  info "Forcing new ECS deployment ($ECS_CLUSTER/$DEMO_API_ECS_SERVICE)..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$DEMO_API_ECS_SERVICE" \
    --force-new-deployment \
    --region "$AWS_REGION" >/dev/null
else
  info "Skipping demo-api build/deploy (do_demo_api=false)"
fi

if [[ "$DO_ROXY_GATEWAY" == "true" ]]; then
  info "Building and pushing roxy-gateway image (linux/amd64)..."
  docker buildx build --platform linux/amd64 -t "$ROXY_GATEWAY_ECR_REPO_URL:latest" --push "$ROXY_GATEWAY_DIR"

  info "Forcing new ECS deployment ($ECS_CLUSTER/$ROXY_GATEWAY_ECS_SERVICE)..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ROXY_GATEWAY_ECS_SERVICE" \
    --force-new-deployment \
    --region "$AWS_REGION" >/dev/null
else
  info "Skipping roxy-gateway build/deploy (do_roxy_gateway=false)"
fi

if [[ "$DO_APP" == "true" ]]; then
  info "Installing frontend dependencies..."
  (cd "$APP_DIR" && npm ci)

  info "Building frontend..."
  (cd "$APP_DIR" && VITE_API_URL=/api npm run build)

  info "Syncing frontend to s3://$S3_BUCKET/app..."
  aws s3 sync "$APP_DIR/dist/" "s3://$S3_BUCKET/app/" --delete

  info "Invalidating CloudFront distribution ($CLOUDFRONT_DISTRIBUTION_ID)..."
  aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
    --paths "/*" \
    --region "$AWS_REGION" >/dev/null
else
  info "Skipping frontend build/deploy (do_app=false)"
fi

info "Deploy complete: $SITE_URL"
