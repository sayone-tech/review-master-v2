terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # Local state for first deploy. Migrate to S3 backend once infra is stable:
  # backend "s3" {
  #   bucket  = "review-master-tfstate"
  #   key     = "prod/terraform.tfstate"
  #   region  = "ap-south-1"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "review-master"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
