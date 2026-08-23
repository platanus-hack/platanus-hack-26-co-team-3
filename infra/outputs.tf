output "site_url" {
  description = "Public URL for the deployed dashboard — frontend and /api/* are both served over HTTPS through this one CloudFront domain."
  value       = "https://${length(var.domain_aliases) > 0 ? var.domain_aliases[0] : aws_cloudfront_distribution.app.domain_name}"
}

output "s3_bucket_name" {
  description = "Bucket to sync the built frontend (dashboard/app/dist) into, under the app/ prefix."
  value       = aws_s3_bucket.app.id
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.app.id
}

output "frontend_build_api_base_url" {
  description = "Set VITE_API_URL to this when building the frontend for this deployment (e.g. VITE_API_URL=/api npm run build)."
  value       = "/api"
}

output "ecr_repository_url" {
  description = "Push the API image here (see README for the build/push commands)."
  value       = aws_ecr_repository.api.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.api.name
}

output "ecs_service_name" {
  value = aws_ecs_service.api.name
}

output "demo_api_ecr_repository_url" {
  description = "Push the demo-api image here (see README for the build/push commands)."
  value       = aws_ecr_repository.demo_api.repository_url
}

output "demo_api_ecs_service_name" {
  value = aws_ecs_service.demo_api.name
}

output "roxy_gateway_ecr_repository_url" {
  description = "Push the roxy-gateway image here (see README for the build/push commands)."
  value       = aws_ecr_repository.roxy_gateway.repository_url
}

output "roxy_gateway_ecs_service_name" {
  value = aws_ecs_service.roxy_gateway.name
}

output "roxy_gateway_base_url" {
  description = "Path roxy-gateway is served under through CloudFront (e.g. https://<site_url>/gateway/v1/evaluate)."
  value       = "/gateway"
}

output "mcp_server_ecs_service_name" {
  value = aws_ecs_service.mcp_server.name
}

output "mcp_server_url" {
  description = "Internal URL for the self-hosted MCP server, reachable from roxy-gateway (or anything else on this instance) over localhost. Use this as an MCP's server.url in Mongo."
  value       = "http://localhost:8003/mcp"
}

output "mcp_server_public_url" {
  description = "Public URL for the self-hosted MCP server, through CloudFront (e.g. https://<site_url>/mcp)."
  value       = "/mcp"
}

output "demo_api_base_url" {
  description = "Path demo-api is served under through CloudFront (e.g. https://<site_url>/demo-api/invoices)."
  value       = "/demo-api"
}

output "aws_region" {
  value = var.aws_region
}

output "ec2_public_dns" {
  description = "EC2 instance's stable public DNS name (Elastic IP) — also the CloudFront /api/* origin."
  value       = aws_eip.api.public_dns
}

output "ec2_public_ip" {
  value = aws_eip.api.public_ip
}
