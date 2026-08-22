# infra

Terraform for deploying `dashboard/api` (FastAPI backend) and `dashboard/app` (React frontend) to
AWS, within the AWS Free Tier for a low-traffic project.

## What this creates

- **S3 bucket** (named `var.project_name`) — hosts the built frontend (`app/dist`) under the
  `app/` prefix, private, only reachable through CloudFront.
- **CloudFront distribution** — one HTTPS domain for everything. `/*` → S3 (frontend), `/api/*` →
  the EC2 instance (backend). Routing both through the same domain avoids CORS and avoids the
  browser blocking mixed HTTP/HTTPS content, since the EC2 instance itself has no TLS certificate.
- **CloudFront Origin Access Control (OAC)** — used only on the S3 origin. The bucket policy grants
  `s3:GetObject` on `app/*` to `cloudfront.amazonaws.com`, scoped by an `AWS:SourceArn` condition to
  this specific distribution, so nothing else (not even other CloudFront distributions) can read
  the bucket.
- **ECR repository** — holds the API's Docker image (built from `dashboard/api/Dockerfile`).
- **ECS cluster running on a single EC2 instance** (`t3a.micro`) — the API runs as an ECS task
  (`EC2` launch type, host networking) rather than a hand-installed process; the instance just runs
  the ECS agent and pulls whatever image/tag the task definition points at. The instance's security
  group only accepts port 8000 from CloudFront's IP ranges — the API is not reachable directly.

## Prerequisites

- Terraform >= 1.5
- Docker, for building the API image
- AWS credentials configured (`aws configure`, or env vars) with permission to create the resources above
- A MongoDB connection string reachable from the EC2 instance (Atlas, or your own)

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
`vpc_id`, `subnet_id`, and `acm_certificate_arn` (blank to skip), then runs `terraform apply`
and the steps below in one shot. `mongo_uri` is entered with hidden input and passed straight
to `terraform apply -var` — it's never written to disk. The other three are non-secret and get
saved to `terraform.tfvars` (gitignored), so the next run offers them back as defaults instead
of asking from scratch.

```bash
cd infra
./scripts/deploy.sh
```

To run Terraform yourself instead:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set vpc_id, subnet_id (and optionally acm_certificate_arn)

terraform init
terraform apply -var="mongo_uri=mongodb://user:password@host:27017"
```

This provisions the bucket, CloudFront distribution, ECR repo, and the ECS cluster/instance. The
ECS service will fail to start tasks until an image actually exists in ECR — push one next:

```bash
cd ../api
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$(terraform -chdir=../infra output -raw ecr_repository_url | cut -d/ -f1)"
docker build -t "$(terraform -chdir=../infra output -raw ecr_repository_url):latest" .
docker push "$(terraform -chdir=../infra output -raw ecr_repository_url):latest"
```

ECS will pick up the new image on the next deployment. To force it immediately:

```bash
aws ecs update-service --cluster roxy-dashboard-api --service roxy-dashboard-api --force-new-deployment --region us-east-1
```

Then build and deploy the frontend against this deployment:

```bash
cd ../app
VITE_API_URL=/api npm run build
aws s3 sync dist/ "s3://$(terraform -chdir=../infra output -raw s3_bucket_name)/app/" --delete
```

`terraform output site_url` is the URL to open.

## Redeploying the API after a code change

Rebuild and push a new image (as above), then force a new ECS deployment — no Terraform apply
needed for a plain code change. Bump `api_image_tag` (e.g. to a git SHA) and `terraform apply` only
if you want the exact deployed tag tracked in Terraform state.

## Notes and caveats

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
