terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "roxy-dashboard-terraform-state"
    key            = "dashboard.tfstate"
    region         = "us-east-1"
    dynamodb_table = "roxy-dashboard-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "app" {
  bucket        = var.project_name
  force_destroy = true

  tags = {
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket = aws_s3_bucket.app.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "app" {
  bucket = aws_s3_bucket.app.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_cloudfront_origin_access_control" "app" {
  name                              = "${var.project_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_s3_bucket_policy" "app" {
  bucket = aws_s3_bucket.app.id
  policy = data.aws_iam_policy_document.app_bucket.json
}

resource "aws_cloudfront_function" "strip_api_prefix" {
  name    = "${var.project_name}-strip-api-prefix"
  runtime = "cloudfront-js-1.0"
  comment = "Rewrites /api/* to /* before forwarding to the EC2 origin"
  publish = true
  code    = file("${path.module}/templates/strip_api_prefix.js")
}

resource "aws_cloudfront_function" "strip_gateway_prefix" {
  name    = "${var.project_name}-strip-gateway-prefix"
  runtime = "cloudfront-js-1.0"
  comment = "Rewrites /gateway/* to /* before forwarding to the roxy-gateway origin"
  publish = true
  code    = file("${path.module}/templates/strip_gateway_prefix.js")
}

resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "${var.project_name} frontend + API"
  price_class         = "PriceClass_100"
  aliases             = var.domain_aliases

  origin {
    domain_name              = aws_s3_bucket.app.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.app.id
    origin_path              = "/app"
  }

  origin {
    domain_name = aws_eip.api.public_dns
    origin_id   = "ec2-api"

    custom_origin_config {
      http_port              = 8000
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name = aws_eip.api.public_dns
    origin_id   = "ec2-roxy-gateway"

    custom_origin_config {
      http_port              = 8002
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name = aws_eip.api.public_dns
    origin_id   = "ec2-mcp-server"

    custom_origin_config {
      http_port              = 8003
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    compress               = true
  }

  ordered_cache_behavior {
    path_pattern             = "/api/*"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "ec2-api"
    viewer_protocol_policy   = "redirect-to-https"
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    compress                 = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.strip_api_prefix.arn
    }
  }

  ordered_cache_behavior {
    path_pattern             = "/gateway/*"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "ec2-roxy-gateway"
    viewer_protocol_policy   = "redirect-to-https"
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    compress                 = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.strip_gateway_prefix.arn
    }
  }

  # No prefix-stripping function here: mongodb-mcp-server's HTTP endpoint is a single fixed
  # path, /mcp (not a prefix scheme like /api/* or /gateway/*), so the CDN path already
  # matches the origin path 1:1 — CloudFront forwards the request URI unchanged.
  ordered_cache_behavior {
    path_pattern             = "/mcp*"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "ec2-mcp-server"
    viewer_protocol_policy   = "redirect-to-https"
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    compress                 = true
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.acm_certificate_arn == null
    acm_certificate_arn            = var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn != null ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != null ? "TLSv1.2_2021" : null
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_ecr_repository" "api" {
  name                 = "${var.project_name}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_security_group" "api" {
  name_prefix = "${var.project_name}-api-"
  description = "API instance: SSH (optional, restricted) + API ports from CloudFront only"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = var.key_pair_name != null ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.ssh_ingress_cidr]
    }
  }

  # Dashboard API (8000), demo-api (8001), roxy-gateway (8002), and mcp-server (8003) as
  # one contiguous port-range rule, not four separate rules. A rule referencing a managed
  # prefix list counts against the security group's rule quota once PER ENTRY IN THE LIST
  # (not once per rule) — the CloudFront origin-facing list has 50-60+ CIDRs, so separate
  # references to it blow past the default 60-rules-per-security-group quota fast. One
  # reference fits comfortably; keep any future service on this instance on the next
  # contiguous port too.
  ingress {
    description     = "Dashboard API + demo-api + roxy-gateway + mcp-server, only from CloudFront IP ranges"
    from_port       = 8000
    to_port         = 8003
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-api"
  }
}

resource "aws_ssm_parameter" "mongo_uri" {
  name  = "/${var.project_name}/mongo_uri"
  type  = "SecureString"
  value = var.mongo_uri
}

resource "aws_iam_role" "api" {
  name = "${var.project_name}-api-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      },
      {
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_ecs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "api_ssm_core" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.project_name}-api-policy"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_role.json
}

resource "aws_iam_instance_profile" "api" {
  name = "${var.project_name}-api-profile"
  role = aws_iam_role.api.name
}

resource "aws_ecs_cluster" "api" {
  name = "${var.project_name}-api"
}

resource "aws_instance" "api" {
  ami                         = data.aws_ssm_parameter.ecs_ami.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.api.id]
  iam_instance_profile        = aws_iam_instance_profile.api.name
  associate_public_ip_address = true
  key_name                    = var.key_pair_name

  user_data = <<-EOF
    #!/bin/bash
    echo ECS_CLUSTER=${aws_ecs_cluster.api.name} >> /etc/ecs/ecs.config
  EOF

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-api"
  }
}

resource "aws_eip" "api" {
  instance = aws_instance.api.id
  domain   = "vpc"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-api"
  retention_in_days = 3
}

resource "aws_ecs_task_definition" "api" {
  family             = "${var.project_name}-api"
  network_mode       = "host"
  task_role_arn      = aws_iam_role.api.arn
  execution_role_arn = aws_iam_role.api.arn

  container_definitions = jsonencode([{
    name              = "api"
    image             = "${aws_ecr_repository.api.repository_url}:${var.api_image_tag}"
    essential         = true
    memory            = 700
    memoryReservation = 300
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "MONGO_DB", value = var.mongo_db },
    ]
    secrets = [
      { name = "MONGO_URI", valueFrom = aws_ssm_parameter.mongo_uri.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.api.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}

# demo-api (block 4): a second ECS service on the same EC2 instance/cluster as the
# dashboard API, on its own port (8001) and ECR repo, sharing the instance's IAM role
# and the mongo_uri secret (same Mongo cluster, different database).
resource "aws_ecr_repository" "demo_api" {
  name                 = "${var.project_name}-demo-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "demo_api" {
  name              = "/ecs/${var.project_name}-demo-api"
  retention_in_days = 3
}

resource "aws_ecs_task_definition" "demo_api" {
  family             = "${var.project_name}-demo-api"
  network_mode       = "host"
  task_role_arn      = aws_iam_role.api.arn
  execution_role_arn = aws_iam_role.api.arn

  container_definitions = jsonencode([{
    name              = "demo-api"
    image             = "${aws_ecr_repository.demo_api.repository_url}:${var.demo_api_image_tag}"
    essential         = true
    memory            = 300
    memoryReservation = 150
    portMappings = [{
      containerPort = 8001
      hostPort      = 8001
      protocol      = "tcp"
    }]
    environment = [
      { name = "DB_NAME", value = var.demo_api_db_name },
    ]
    secrets = [
      { name = "MONGO_URI", valueFrom = aws_ssm_parameter.mongo_uri.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.demo_api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "demo_api" {
  name            = "${var.project_name}-demo-api"
  cluster         = aws_ecs_cluster.api.id
  task_definition = aws_ecs_task_definition.demo_api.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}

# roxy-gateway (block 2): a third ECS service on the same EC2 instance/cluster, on its
# own port (8002) and ECR repo, sharing the instance's IAM role and the mongo_uri secret
# (same Mongo cluster/database as the dashboard API — roxy-gateway writes what the
# dashboard reads). Also needs evaluator_url: the URL of the policy/verification service
# it calls per request (block 10, "verifier" — not yet deployed by this Terraform).
resource "aws_ecr_repository" "roxy_gateway" {
  name                 = "${var.project_name}-roxy-gateway"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "roxy_gateway" {
  name              = "/ecs/${var.project_name}-roxy-gateway"
  retention_in_days = 3
}

resource "aws_ecs_task_definition" "roxy_gateway" {
  family             = "${var.project_name}-roxy-gateway"
  network_mode       = "host"
  task_role_arn      = aws_iam_role.api.arn
  execution_role_arn = aws_iam_role.api.arn

  container_definitions = jsonencode([{
    name              = "roxy-gateway"
    image             = "${aws_ecr_repository.roxy_gateway.repository_url}:${var.roxy_gateway_image_tag}"
    essential         = true
    memory            = 250
    memoryReservation = 100
    portMappings = [{
      containerPort = 8002
      hostPort      = 8002
      protocol      = "tcp"
    }]
    environment = [
      { name = "PORT", value = "8002" },
      { name = "MONGO_DB_NAME", value = var.mongo_db },
      { name = "EVALUATOR_URL", value = var.evaluator_url },
      { name = "DASHBOARD_URL", value = var.dashboard_url },
      { name = "ANTHROPIC_MODEL", value = var.anthropic_model },
      { name = "ANTHROPIC_BASE_URL", value = var.anthropic_base_url },
      { name = "MONGO_URI", value = var.mongo_uri },
      { name = "ANTHROPIC_API_KEY", value = var.anthropic_api_key },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.roxy_gateway.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "roxy_gateway" {
  name            = "${var.project_name}-roxy-gateway"
  cluster         = aws_ecs_cluster.api.id
  task_definition = aws_ecs_task_definition.roxy_gateway.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}

# mcp-server: a fourth ECS service on the same EC2 instance/cluster, on its own port
# (8003), running the official self-hosted mongodb-mcp-server image (public Docker Hub
# image — no ECR repo/build step, unlike the other three services which build from source
# in this repo). Talks directly to mongo_uri, no OAuth/Service Account — sidesteps the
# hosted Atlas Managed MCP Server (mcp.mongodb.com) entirely. Reachable from roxy-gateway
# (and anything else on this instance) at mcp_server_url.
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/ecs/${var.project_name}-mcp-server"
  retention_in_days = 3
}

resource "aws_ecs_task_definition" "mcp_server" {
  family             = "${var.project_name}-mcp-server"
  network_mode       = "host"
  task_role_arn      = aws_iam_role.api.arn
  execution_role_arn = aws_iam_role.api.arn

  container_definitions = jsonencode([{
    name              = "mcp-server"
    image             = "mongodb/mongodb-mcp-server:${var.mcp_server_image_tag}"
    essential         = true
    memory            = 200
    memoryReservation = 80
    portMappings = [{
      containerPort = 8003
      hostPort      = 8003
      protocol      = "tcp"
    }]
    environment = [
      { name = "MDB_MCP_TRANSPORT", value = "http" },
      { name = "MDB_MCP_HTTP_HOST", value = "0.0.0.0" },
      { name = "MDB_MCP_HTTP_PORT", value = "8003" },
      { name = "MDB_MCP_CONNECTION_STRING", value = var.mongo_uri },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.mcp_server.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "mcp_server" {
  name            = "${var.project_name}-mcp-server"
  cluster         = aws_ecs_cluster.api.id
  task_definition = aws_ecs_task_definition.mcp_server.arn
  desired_count   = 1
  launch_type     = "EC2"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}
