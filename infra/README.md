# infra

Terraform for deploying `dashboard/api` (FastAPI backend), `dashboard/app` (React frontend),
`demo-api` (block 4's demo billing API), `roxy-gateway` (block 2), and a self-hosted MongoDB MCP
server to AWS, within the AWS Free Tier for a low-traffic project.

## What this creates

- **S3 bucket** (named `var.project_name`) — hosts the built frontend (`app/dist`) under the
  `app/` prefix, private, only reachable through CloudFront.
- **CloudFront distribution** — one HTTPS domain for everything. `/*` → S3 (frontend), `/api/*` →
  the dashboard API, `/gateway/*` → roxy-gateway, `/mcp*` → mcp-server, `/demo-api/*` → demo-api
  (all four on the EC2 instance). Routing everything through the same domain avoids CORS and avoids
  the browser blocking mixed HTTP/HTTPS content, since the EC2 instance itself has no TLS
  certificate. The `/api/*`, `/gateway/*`, and `/demo-api/*` behaviors each have a CloudFront
  Function that strips their path prefix before forwarding to the origin (`strip_api_prefix.js`,
  `strip_gateway_prefix.js`, `strip_demo_api_prefix.js`) — so `/gateway/v1/evaluate` reaches
  roxy-gateway as `/v1/evaluate`, and `/demo-api/invoices` reaches demo-api as `/invoices`. `/mcp*`
  has no such function: mongodb-mcp-server's HTTP endpoint is a single fixed path, `/mcp` (not a
  prefix scheme), so the CDN path already matches the origin path 1:1 with no rewrite needed.
- **CloudFront Origin Access Control (OAC)** — used only on the S3 origin. The bucket policy grants
  `s3:GetObject` on `app/*` to `cloudfront.amazonaws.com`, scoped by an `AWS:SourceArn` condition to
  this specific distribution, so nothing else (not even other CloudFront distributions) can read
  the bucket.
- **ECS cluster running on a single EC2 instance** (`t3a.small`) — **four** ECS services share this
  one instance/cluster, each an EC2-launch-type task with host networking (a hand-installed process
  each, essentially, but ECS-managed):
  - **dashboard API** — port 8000, its own ECR repo, connects to the `roxy` database.
  - **demo-api** — port 8001, its own ECR repo, connects to the `demo_billing` database (same
    `mongo_uri`/cluster, different database — see `demo_api_db_name`).
  - **roxy-gateway** — port 8002, its own ECR repo, connects to the same `roxy` database as the
    dashboard API (it writes what the dashboard reads). Also needs `evaluator_url`: the URL of the
    policy/verification service it calls per request (block 10, "verifier" — not deployed by this
    Terraform; point it at wherever that service actually runs). It also POSTs a notification to
    `dashboard_url` (dashboard API's `POST /log`) on every decision — defaults to
    `http://localhost:8000/log`, since all four containers share this one instance (host
    networking), so it never needs to leave the box. Also needs `anthropic_api_key`: it calls
    Claude (`anthropic_model`, default `claude-sonnet-5`) to decide how to invoke the MCP
    tool. Passed as a plain environment variable, not SSM (same as `mongo_uri` for this
    service).
  - **mcp-server** — port 8003, running the official `mongodb/mongodb-mcp-server` image straight
    from Docker Hub (no ECR repo, no build step — it's not built from source in this repo, unlike
    the other three). Talks directly to `mongo_uri` — no OAuth, no Atlas Service Account,
    sidestepping the hosted Atlas Managed MCP Server entirely. Reachable two ways: internally at
    `mcp_server_url` (`http://localhost:8003/mcp`, what roxy-gateway or anything else on this
    instance should use — no CloudFront round-trip needed), and publicly at `mcp_server_public_url`
    (`/mcp`, through the CDN, for callers outside the instance).

  All four ports only accept traffic from CloudFront's IP ranges (the security group, one rule
  covering 8000-8003), and all four are wired into the CloudFront distribution (`/api/*`,
  `/gateway/*`, `/mcp*`, `/demo-api/*`).

  Four tasks share one `t3a.small` (2GiB RAM total): hard memory limits total 700MB + 300MB + 250MB
  + 200MB = 1450MB, comfortably under the ~1.75-1.85GB actually usable after OS/Docker/ECS-agent
  overhead, with some headroom for traffic spikes. (This was a `t3a.micro`, 1GiB, until the fourth
  service — mcp-server — pushed the combined hard limits past what 1GiB could hold at all.)

## Prerequisites

- Terraform >= 1.5
- Docker, for building the images
- AWS credentials configured (`aws configure`, or env vars) with permission to create the resources above
- A MongoDB connection string reachable from the EC2 instance (Atlas, or your own), with `roxy` and
  `demo_billing` databases
- A reachable URL for `evaluator_url` (roxy-gateway refuses to start without one)
- An Anthropic API key for `anthropic_api_key` (roxy-gateway refuses to start without one)

## Remote state (one-time bootstrap)

State is stored remotely in S3 (with DynamoDB locking) so it persists across machines and CI runs
— a backend can't create its own storage, so this bucket/table must exist *before* `terraform
init` will work. Run once, ever, per AWS account this is deployed into:

```bash
aws s3api create-bucket \
  --bucket roxy-dashboard-terraform-state \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket roxy-dashboard-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket roxy-dashboard-terraform-state \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket roxy-dashboard-terraform-state \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --table-name roxy-dashboard-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Deploy

The easiest path is `./scripts/deploy.sh`, which prompts interactively for `mongo_uri`,
`anthropic_api_key`, `vpc_id`, `subnet_id`, `evaluator_url`, `dashboard_url`, `anthropic_model`,
`anthropic_base_url`, `acm_certificate_arn`, and `domain_aliases` (the last five blank to
skip/use defaults), then runs `terraform apply` and builds/pushes/deploys the dashboard API,
demo-api, and roxy-gateway in one shot. `mongo_uri` and `anthropic_api_key` are entered with hidden
input and passed straight to `terraform apply -var` — neither is ever written to disk. The other
eight are non-secret and get saved to `terraform.tfvars` (gitignored), so the next run offers them
back as defaults instead of asking from scratch. Any of the ten can also come from the environment
instead of a prompt (see `./scripts/deploy-from-env.sh` below) — whichever are already set are used
as-is, only what's missing gets prompted for. Pass positional flags to skip steps: `./scripts/deploy.sh
<do_infra> <do_api> <do_app> <do_demo_api> <do_roxy_gateway>` (each `true`/`false`, all default
`true`).

```bash
cd infra
./scripts/deploy.sh
```

For a non-interactive run (CI, or just avoiding retyping things), `./scripts/deploy-from-env.sh`
reads `mongo_uri`/`anthropic_api_key`/`vpc_id`/`subnet_id`/`evaluator_url`/`dashboard_url`/
`anthropic_model`/`anthropic_base_url`/`acm_certificate_arn`/`domain_aliases` from an `.env` file
and exports them, so `deploy.sh` finds them already set and skips every prompt. `mongo_uri`,
`vpc_id`, `subnet_id`, `evaluator_url`, and `anthropic_api_key` are required in `.env`; the rest
stay optional:

```bash
cd infra
cp .env.example .env   # fill in MONGO_URI, VPC_ID, SUBNET_ID, EVALUATOR_URL, ANTHROPIC_API_KEY (others optional)
./scripts/deploy-from-env.sh
```

To run Terraform yourself instead:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set vpc_id, subnet_id, evaluator_url (and optionally dashboard_url, anthropic_model, anthropic_base_url, acm_certificate_arn, domain_aliases)

terraform init
terraform apply -var="mongo_uri=mongodb://user:password@host:27017" -var="anthropic_api_key=sk-ant-xxxxxxxx"
```

This provisions the bucket, CloudFront distribution, all three ECR repos, and the ECS
cluster/instance. All three ECS services will fail to start tasks until images actually exist in
their ECR repos — push them next (same ECR login covers all repos, same registry). **Build with
`--platform linux/amd64` explicitly** — the EC2 instance (`t3a.small`) is x86_64, and building
without a platform flag on an Apple Silicon Mac produces an arm64-only image that ECS can't pull
(`CannotPullContainerError: no matching manifest for linux/amd64`):

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$(terraform -chdir=infra output -raw ecr_repository_url | cut -d/ -f1)"

cd dashboard/api
docker buildx build --platform linux/amd64 -t "$(terraform -chdir=../../infra output -raw ecr_repository_url):latest" --push .

cd ../../demo-api
docker buildx build --platform linux/amd64 -t "$(terraform -chdir=../infra output -raw demo_api_ecr_repository_url):latest" --push .

cd ../roxy-gateway
docker buildx build --platform linux/amd64 -t "$(terraform -chdir=../infra output -raw roxy_gateway_ecr_repository_url):latest" --push .
```

ECS will pick up new images on the next deployment. To force it immediately:

```bash
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-api --force-new-deployment --region us-east-1
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-demo-api --force-new-deployment --region us-east-1
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-roxy-gateway --force-new-deployment --region us-east-1
```

Then build and deploy the frontend against this deployment:

```bash
cd ../dashboard/app
VITE_API_URL=/api npm run build
aws s3 sync dist/ "s3://$(terraform -chdir=../../infra output -raw s3_bucket_name)/app/" --delete
```

`terraform output site_url` is the URL to open.

## Redeploying an API after a code change

Rebuild and push a new image (as above), then force a new ECS deployment for that service — no
Terraform apply needed for a plain code change. Bump `api_image_tag`, `demo_api_image_tag`, or
`roxy_gateway_image_tag` (e.g. to a git SHA) and `terraform apply` only if you want the exact
deployed tag tracked in Terraform state.

## Changing `instance_type`

ECS refuses to re-register a container instance under a different instance type than it
originally registered with (`ClientException: Container instance type changes are not
supported`) — an in-place resize (what Terraform does by default for `instance_type`, via
stop/modify/start) leaves the ECS agent permanently crash-looping, and every service's
`runningCount` silently drops to 0. If you change `instance_type`, force a clean
destroy+recreate of the instance instead: set `REPLACE_INSTANCE=true` (env var — see
`.env.example`) when running `deploy.sh`/`deploy-from-env.sh`, or run
`terraform apply -replace=aws_instance.api` yourself. The Elastic IP re-associates to the new
instance automatically; expect a few minutes of downtime across all four services while it
boots and the tasks get placed.

## Notes and caveats

- **Image architecture**: both `deploy.sh` and the manual instructions above build with
  `docker buildx build --platform linux/amd64`. Don't drop that flag — a plain `docker build` on
  an Apple Silicon Mac (or any arm64 machine) produces an arm64-only image, and the `t3a.small`
  instance is x86_64, so ECS fails every task with `CannotPullContainerError: no matching manifest
  for linux/amd64` — a silent crash loop, not an application bug.
- **Cost**: ~$17.37/month minimum, running 24/7, with no free-tier path — the two components that
  can't be free:
  - **EC2 t3a.small**: ~$13.72/mo. Not free-tier eligible (the free tier only covers t2.micro/t3.micro,
    or t3.small/t4g.micro/etc. for accounts created after July 2025) — t3a is a different instance
    family and isn't on either list, and t3a.small isn't `.micro`-sized regardless. Needed for the
    combined memory of four ECS services (see above) — t3a.micro (1GiB) isn't enough anymore.
  - **Elastic IP**: ~$3.65/mo. AWS made all public IPv4 addresses billable in Feb 2024, attached or
    not — there's no free allowance for this regardless of account age.

  Everything else is free at this project's scale: the 30GB EBS volume is covered by the EBS free
  tier in an account's first 12 months (small charge after); S3 and ECR usage here (a few MB) is
  negligible either way; CloudWatch Logs, SSM (standard parameters), and CloudFront (1TB / 10M
  requests per month, no 12-month expiry — it's part of AWS's perpetual "Always Free" tier) round to
  $0 at this traffic level.
- **Secrets**: `mongo_uri` is stored in SSM Parameter Store (`SecureString`, free) and injected into
  the dashboard API and demo-api containers via the task definition's `secrets` field, so the
  plaintext value never sits in their task definitions — only in SSM, access-controlled separately.
  roxy-gateway's container gets both `mongo_uri` and `anthropic_api_key` as plain `environment`
  values instead (by request) — simpler, but that means the plaintext values sit in every revision
  of that one task definition, visible to anyone with `ecs:DescribeTaskDefinition`. Either way it
  still lands in Terraform state in plaintext, as with any Terraform-managed secret; the state
  bucket is encrypted and not publicly accessible, but anyone with read access to it can read these
  values — scope IAM access to that bucket accordingly.
- **SSH**: off by default. Set `key_pair_name` (an existing EC2 key pair) and `ssh_ingress_cidr`
  (your IP, not `0.0.0.0/0`) in `terraform.tfvars` if you need shell access — or use AWS Systems
  Manager Session Manager instead (the instance role already has `AmazonSSMManagedInstanceCore`),
  which needs no open port at all.
- **`force_destroy = true`** on the S3 bucket means `terraform destroy` deletes it even with objects
  inside — convenient for a low-traffic project, but double-check before running destroy against
  anything you care about.
