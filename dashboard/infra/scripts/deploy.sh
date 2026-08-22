#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/.."
API_DIR="$INFRA_DIR/../api"
APP_DIR="$INFRA_DIR/../app"
TFVARS_FILE="terraform.tfvars"

info() { echo ""; echo "==> $*"; }

DO_INFRA="${1:-true}"
DO_API="${2:-true}"
DO_APP="${3:-true}"

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
if [[ -f "$TFVARS_FILE" ]]; then
  EXISTING_VPC_ID=$(sed -n -E 's/^vpc_id *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_SUBNET_ID=$(sed -n -E 's/^subnet_id *= *"(.*)"$/\1/p' "$TFVARS_FILE")
  EXISTING_ACM_ARN=$(sed -n -E 's/^acm_certificate_arn *= *"(.*)"$/\1/p' "$TFVARS_FILE")
fi

info "Configuration"

read -r -s -p "MongoDB connection string (mongo_uri, input hidden): " MONGO_URI
echo ""
[[ -n "$MONGO_URI" ]] || { echo "ERROR: mongo_uri is required."; exit 1; }

read -r -p "VPC id (vpc_id)${EXISTING_VPC_ID:+ [$EXISTING_VPC_ID]}: " VPC_ID
VPC_ID="${VPC_ID:-$EXISTING_VPC_ID}"
[[ -n "$VPC_ID" ]] || { echo "ERROR: vpc_id is required."; exit 1; }

read -r -p "Subnet id (subnet_id)${EXISTING_SUBNET_ID:+ [$EXISTING_SUBNET_ID]}: " SUBNET_ID
SUBNET_ID="${SUBNET_ID:-$EXISTING_SUBNET_ID}"
[[ -n "$SUBNET_ID" ]] || { echo "ERROR: subnet_id is required."; exit 1; }

read -r -p "ACM certificate ARN (acm_certificate_arn, optional — blank uses the CloudFront default cert)${EXISTING_ACM_ARN:+ [$EXISTING_ACM_ARN]}: " ACM_ARN
ACM_ARN="${ACM_ARN:-$EXISTING_ACM_ARN}"

info "Writing $TFVARS_FILE..."
{
  echo "vpc_id    = \"$VPC_ID\""
  echo "subnet_id = \"$SUBNET_ID\""
  if [[ -n "$ACM_ARN" ]]; then
    echo "acm_certificate_arn = \"$ACM_ARN\""
  fi
} > "$TFVARS_FILE"

info "terraform init..."
terraform init -input=false

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
CLOUDFRONT_DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)
SITE_URL=$(terraform output -raw site_url)

if [[ "$DO_API" == "true" ]]; then
  info "Logging in to ECR ($ECR_REGISTRY)..."
  aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

  info "Building API image..."
  docker build -t "$ECR_REPO_URL:latest" "$API_DIR"

  info "Pushing API image..."
  docker push "$ECR_REPO_URL:latest"

  info "Forcing new ECS deployment ($ECS_CLUSTER/$ECS_SERVICE)..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --force-new-deployment \
    --region "$AWS_REGION" >/dev/null
else
  info "Skipping API build/deploy (do_api=false)"
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
