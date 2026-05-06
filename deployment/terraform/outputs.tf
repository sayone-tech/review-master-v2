output "rds_endpoint" {
  description = "RDS endpoint — use in SSM DATABASE_URL after apply"
  value       = aws_db_instance.main.endpoint
}

output "ecr_url" {
  description = "ECR repository URL — used in GitHub Actions workflow"
  value       = aws_ecr_repository.app.repository_url
}

output "static_bucket_name" {
  description = "S3 bucket name — update SSM AWS_STORAGE_BUCKET_NAME if different"
  value       = aws_s3_bucket.static.id
}

output "github_oidc_role_arn" {
  description = "IAM role ARN — add as AWS_DEPLOY_ROLE_ARN GitHub secret"
  value       = aws_iam_role.github_actions.arn
}

output "ec2_eip_allocation_id" {
  description = "Elastic IP allocation ID — associate with EC2 after launch"
  value       = aws_eip.ec2.allocation_id
}

output "elastic_ip" {
  description = "EC2 Elastic IP — already set as Route 53 A record by Terraform"
  value       = aws_eip.ec2.public_ip
}
