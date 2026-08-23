variable "aws_region" {
  description = "AWS region for the S3 bucket and EC2 instance (CloudFront itself is global)."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used to name and tag every resource."
  type        = string
  default     = "roxy-dashboard"
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "instance_type" {
  description = "EC2 instance type running the ECS-managed API container."
  type        = string
  default     = "t3a.micro"
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed to SSH into the API instance. Restrict this to your own IP (e.g. \"203.0.113.4/32\") — 0.0.0.0/0 exposes SSH to the whole internet. Only used if key_pair_name is set."
  type        = string
  default     = "0.0.0.0/0"
}

variable "key_pair_name" {
  description = "Name of an existing EC2 key pair to attach for SSH access. Leave null to skip SSH entirely (no key, no open port 22)."
  type        = string
  default     = null
}

variable "mongo_uri" {
  description = "MongoDB connection string (e.g. mongodb://host:27017 or an Atlas SRV URI). Stored in SSM Parameter Store, injected into the container as MONGO_URI by ECS at task start."
  type        = string
  sensitive   = true
}

variable "mongo_db" {
  description = "MongoDB database name. Passed to the container as a plain (non-secret) MONGO_DB env var."
  type        = string
  default     = "roxy"
}

variable "api_image_tag" {
  description = "ECR image tag to deploy for the dashboard API."
  type        = string
  default     = "latest"
}

variable "demo_api_image_tag" {
  description = "ECR image tag to deploy for demo-api."
  type        = string
  default     = "latest"
}

variable "demo_api_db_name" {
  description = "MongoDB database name for demo-api. Passed to the container as a plain (non-secret) DB_NAME env var. Uses the same mongo_uri/cluster as the dashboard API, a different database."
  type        = string
  default     = "demo_billing"
}

variable "roxy_gateway_image_tag" {
  description = "ECR image tag to deploy for roxy-gateway."
  type        = string
  default     = "latest"
}

variable "evaluator_url" {
  description = "URL of the policy/verification service roxy-gateway calls per request to evaluate context against rules (block 10, \"verifier\"). Required by roxy-gateway's own config — it refuses to start without it."
  type        = string
}

variable "dashboard_url" {
  description = "URL roxy-gateway POSTs security log notifications to (dashboard API's POST /log). Defaults to the dashboard API over localhost, since both containers share the same EC2 instance (host networking) — no CloudFront/internet round-trip needed. Optional: roxy-gateway no-ops the notification if this is empty."
  type        = string
  default     = "http://localhost:8000/log"
}

variable "acm_certificate_arn" {
  type    = string
  default = null
}

variable "domain_aliases" {
  type    = list(string)
  default = []
}
