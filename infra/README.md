# infra

Terraform for deploying `dashboard/api` (FastAPI backend), `dashboard/app` (React frontend), and
`demo-api` (block 4's demo billing API) to AWS, within the AWS Free Tier for a low-traffic project.

## What this creates

- **S3 bucket** (named `var.project_name`) — hosts the built frontend (`app/dist`) under the
  `app/` prefix, private, only reachable through CloudFront.
- **CloudFront distribution** — one HTTPS domain for everything. `/*` → S3 (frontend), `/api/*` →
  the EC2 instance (dashboard backend). Routing both through the same domain avoids CORS and avoids
  the browser blocking mixed HTTP/HTTPS content, since the EC2 instance itself has no TLS
  certificate. demo-api isn't routed through CloudFront (see below).
- **CloudFront Origin Access Control (OAC)** — used only on the S3 origin. The bucket policy grants
  `s3:GetObject` on `app/*` to `cloudfront.amazonaws.com`, scoped by an `AWS:SourceArn` condition to
  this specific distribution, so nothing else (not even other CloudFront distributions) can read
  the bucket.
- **ECS cluster running on a single EC2 instance** (`t3a.micro`) — **two** ECS services share this
  one instance/cluster, each an EC2-launch-type task with host networking (a hand-installed process
  each, essentially, but ECS-managed):
  - **dashboard API** — port 8000, its own ECR repo, connects to the `roxy` database.
  - **demo-api** — port 8001, its own ECR repo, connects to the `demo_billing` database (same
    `mongo_uri`/cluster, different database — see `demo_api_db_name`).

  Both ports only accept traffic from CloudFront's IP ranges (the security group), but only the
  dashboard API is actually wired into the CloudFront distribution's `/api/*` behavior — demo-api's
  port is open the same way but has no CloudFront origin routing to it yet. Add one (mirroring the
  existing `ec2-api` origin/behavior, on port 8001) if you want it served through the CDN too.
  Because both tasks share one `t3a.micro` (1GiB RAM total, split ~700MB/300MB across the two
  containers' hard memory limits), this is tight — watch for OOM kills under concurrent load and
  size up the instance if that happens.

## Prerequisites

- Terraform >= 1.5
- Docker, for building the API images
- AWS credentials configured (`aws configure`, or env vars) with permission to create the resources above
- A MongoDB connection string reachable from the EC2 instance (Atlas, or your own), with both a
  `roxy` and a `demo_billing` database

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

The easiest path is `./scripts/deploy.sh`, which prompts interactively for `mongo_uri`, `vpc_id`,
`subnet_id`, `acm_certificate_arn`, and `domain_aliases` (the last two blank to skip), then runs
`terraform apply` and builds/pushes/deploys both the dashboard API and demo-api in one shot.
`mongo_uri` is entered with hidden input and passed straight to `terraform apply -var` — it's never
written to disk. The other four are non-secret and get saved to `terraform.tfvars` (gitignored), so
the next run offers them back as defaults instead of asking from scratch. Any of the five can also
come from the environment instead of a prompt (see `./scripts/deploy-from-env.sh` below) — whichever
are already set are used as-is, only what's missing gets prompted for. Pass positional flags to skip
steps: `./scripts/deploy.sh <do_infra> <do_api> <do_app> <do_demo_api>` (each `true`/`false`, all
default `true`).

```bash
cd infra
./scripts/deploy.sh
```

For a non-interactive run (CI, or just avoiding retyping things), `./scripts/deploy-from-env.sh`
reads `mongo_uri`/`vpc_id`/`subnet_id`/`acm_certificate_arn`/`domain_aliases` from an `.env` file
and exports them, so `deploy.sh` finds them already set and skips every prompt. `mongo_uri`,
`vpc_id`, and `subnet_id` are required in `.env`; the other two stay optional:

```bash
cd infra
cp .env.example .env   # fill in MONGO_URI, VPC_ID, SUBNET_ID (others optional)
./scripts/deploy-from-env.sh
```

To run Terraform yourself instead:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set vpc_id, subnet_id (and optionally acm_certificate_arn, domain_aliases)

terraform init
terraform apply -var="mongo_uri=mongodb://user:password@host:27017"
```

This provisions the bucket, CloudFront distribution, both ECR repos, and the ECS cluster/instance.
Both ECS services will fail to start tasks until images actually exist in their ECR repos — push
them next (same ECR login covers both repos, same registry). **Build with `--platform linux/amd64`
explicitly** — the EC2 instance (`t3a.micro`) is x86_64, and building without a platform flag on an
Apple Silicon Mac produces an arm64-only image that ECS can't pull
(`CannotPullContainerError: no matching manifest for linux/amd64`):

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$(terraform -chdir=infra output -raw ecr_repository_url | cut -d/ -f1)"

cd dashboard/api
docker buildx build --platform linux/amd64 -t "$(terraform -chdir=../../infra output -raw ecr_repository_url):latest" --push .

cd ../../demo-api
docker buildx build --platform linux/amd64 -t "$(terraform -chdir=../infra output -raw demo_api_ecr_repository_url):latest" --push .
```

ECS will pick up new images on the next deployment. To force it immediately:

```bash
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-api --force-new-deployment --region us-east-1
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-demo-api --force-new-deployment --region us-east-1
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
Terraform apply needed for a plain code change. Bump `api_image_tag` or `demo_api_image_tag` (e.g.
to a git SHA) and `terraform apply` only if you want the exact deployed tag tracked in Terraform
state.

## Notes and caveats

- **Image architecture**: both `deploy.sh` and the manual instructions above build with
  `docker buildx build --platform linux/amd64`. Don't drop that flag — a plain `docker build` on
  an Apple Silicon Mac (or any arm64 machine) produces an arm64-only image, and the `t3a.micro`
  instance is x86_64, so ECS fails every task with `CannotPullContainerError: no matching manifest
  for linux/amd64` — a silent crash loop, not an application bug.
- **Cost**: ~$10.50/month minimum, running 24/7, with no free-tier path — the two components that
  can't be free:
  - **EC2 t3a.micro**: ~$6.86/mo. Not free-tier eligible (the free tier only covers t2.micro/t3.micro,
    or t3.small/t4g.micro/etc. for accounts created after July 2025) — t3a is a different instance
    family and isn't on either list. Switch `instance_type` to `t3.micro` if free-tier eligibility
    matters more than the (small) t3a price advantage.
  - **Elastic IP**: ~$3.65/mo. AWS made all public IPv4 addresses billable in Feb 2024, attached or
    not — there's no free allowance for this regardless of account age.

  Everything else is free at this project's scale: the 30GB EBS volume is covered by the EBS free
  tier in an account's first 12 months (small charge after); S3 and ECR usage here (a few MB) is
  negligible either way; CloudWatch Logs, SSM (standard parameters), and CloudFront (1TB / 10M
  requests per month, no 12-month expiry — it's part of AWS's perpetual "Always Free" tier) round to
  $0 at this traffic level.
- **Secrets**: `mongo_uri` is stored in SSM Parameter Store (`SecureString`, free) and injected
  directly into the container as an env var by ECS at task start (task definition `secrets`) —
  never baked into the image or written to disk on the instance. It still lands in Terraform state
  in plaintext, as with any Terraform-managed secret; the state bucket is encrypted and not
  publicly accessible, but anyone with read access to it can read this value — scope IAM access to
  that bucket accordingly.
- **SSH**: off by default. Set `key_pair_name` (an existing EC2 key pair) and `ssh_ingress_cidr`
  (your IP, not `0.0.0.0/0`) in `terraform.tfvars` if you need shell access — or use AWS Systems
  Manager Session Manager instead (the instance role already has `AmazonSSMManagedInstanceCore`),
  which needs no open port at all.
- **`force_destroy = true`** on the S3 bucket means `terraform destroy` deletes it even with objects
  inside — convenient for a low-traffic project, but double-check before running destroy against
  anything you care about.
