#!/usr/bin/env bash
# Creates all SSM SecureString parameters with placeholder values.
# Run once after Terraform apply: bash deployment/ssm/seed-params.sh
# Then update each CHANGE_ME value in the AWS console or via CLI.
#
# Usage: AWS_PROFILE=review-master bash deployment/ssm/seed-params.sh
set -euo pipefail

REGION="ap-south-1"
PREFIX="/review-master/prod"

put_param() {
  local name="$1"
  local value="$2"
  aws ssm put-parameter \
    --region "${REGION}" \
    --name "${PREFIX}/${name}" \
    --value "${value}" \
    --type "SecureString" \
    --overwrite \
    --no-cli-pager
  echo "  OK: ${PREFIX}/${name}"
}

echo "Seeding SSM parameters in ${REGION} under ${PREFIX}/"
echo ""

# Django core
put_param "DJANGO_SECRET_KEY"    "CHANGE_ME_run_get_random_secret_key"
put_param "DJANGO_ALLOWED_HOSTS" "yourdomain.com,www.yourdomain.com"
put_param "SITE_URL"             "https://yourdomain.com"

# Database — update <rds-endpoint> after Terraform outputs it
put_param "DATABASE_URL" "postgres://app:CHANGE_ME_db_password@CHANGE_ME_rds_endpoint:5432/reviewmaster"

# Redis — internal Docker network, no change needed
put_param "REDIS_URL" "redis://redis:6379"

# Google OAuth
put_param "GOOGLE_OAUTH_CLIENT_ID"     "CHANGE_ME"
put_param "GOOGLE_OAUTH_CLIENT_SECRET" "CHANGE_ME"
put_param "GOOGLE_OAUTH_REDIRECT_URI"  "https://yourdomain.com/oauth/google/callback/"

# Encryption
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
put_param "FERNET_SALT_KEY" "CHANGE_ME_generate_fernet_key"

# OpenAI
put_param "OPENAI_API_KEY"        "CHANGE_ME"
put_param "OPENAI_MODEL"          "gpt-4o-mini-2024-07-18"
put_param "OPENAI_MAX_RETRIES"    "3"
put_param "ENRICHMENT_BATCH_SIZE" "10"

# LangSmith
put_param "LANGSMITH_API_KEY"  "CHANGE_ME"
put_param "LANGSMITH_PROJECT"  "review-platform-production"
put_param "LANGSMITH_ENDPOINT" "https://api.smith.langchain.com"

# Sentry
put_param "SENTRY_DSN"  "CHANGE_ME"
put_param "ENVIRONMENT" "production"

# Email
put_param "EMAIL_PROVIDER"     "resend"
put_param "RESEND_API_KEY"     "CHANGE_ME"
put_param "DEFAULT_FROM_EMAIL" "noreply@yourdomain.com"
put_param "DEFAULT_REPLY_TO"   "support@yourdomain.com"

# S3 static files — bucket name matches Terraform s3.tf
put_param "AWS_STORAGE_BUCKET_NAME" "review-master-static-prod"
put_param "AWS_S3_REGION_NAME"      "ap-south-1"

# Caddy — Let's Encrypt
put_param "CADDY_DOMAIN"     "yourdomain.com"
put_param "CADDY_ACME_EMAIL" "CHANGE_ME_your_email"

# Sync tuning
put_param "INITIAL_SYNC_PAGE_SIZE"          "50"
put_param "INCREMENTAL_SYNC_INTERVAL_HOURS" "6"
put_param "INCREMENTAL_SYNC_JITTER_MINUTES" "30"

echo ""
echo "Done. Update CHANGE_ME values in the AWS console:"
echo "  https://ap-south-1.console.aws.amazon.com/systems-manager/parameters"
echo ""
echo "Key values to generate:"
echo "  DJANGO_SECRET_KEY : python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
echo "  FERNET_SALT_KEY   : python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
