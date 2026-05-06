variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name (prod, staging)"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Root domain name, e.g. reviewbee.in"
  type        = string
}

variable "operator_ip" {
  description = "Your public IP in CIDR notation for SSH access, e.g. 59.94.147.0/32"
  type        = string
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "reviewbee"
}

variable "github_org" {
  description = "GitHub organisation (for OIDC trust policy)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (for OIDC trust policy)"
  type        = string
}

variable "ec2_instance_id" {
  description = "EC2 instance ID — set after instance is launched to enable CloudWatch alarms"
  type        = string
  default     = ""
}
