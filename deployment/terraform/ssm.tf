# All parameters use SecureString with the default SSM KMS key.
# Terraform seeds placeholder values only.
# lifecycle ignore_changes = [value] ensures terraform apply never overwrites
# values you have updated manually in the AWS console.

locals {
  ssm_prefix = "/review-master/prod"
  ssm_placeholders = {
    "DJANGO_SECRET_KEY"               = "CHANGE_ME_run_get_random_secret_key"
    "DJANGO_ALLOWED_HOSTS"            = "reviewbee.in,www.reviewbee.in"
    "SITE_URL"                        = "https://reviewbee.in"
    "DATABASE_URL"                    = "postgres://reviewbee:CHANGE_ME@CHANGE_ME_rds_endpoint:5432/reviewmaster"
    "REDIS_URL"                       = "redis://redis:6379"
    "GOOGLE_OAUTH_CLIENT_ID"          = "CHANGE_ME"
    "GOOGLE_OAUTH_CLIENT_SECRET"      = "CHANGE_ME"
    "GOOGLE_OAUTH_REDIRECT_URI"       = "https://reviewbee.in/oauth/google/callback/"
    "FERNET_SALT_KEY"                 = "CHANGE_ME_generate_fernet_key"
    "OPENAI_API_KEY"                  = "CHANGE_ME"
    "OPENAI_MODEL"                    = "gpt-4o-mini-2024-07-18"
    "OPENAI_MAX_RETRIES"              = "3"
    "ENRICHMENT_BATCH_SIZE"           = "10"
    "LANGSMITH_API_KEY"               = "CHANGE_ME"
    "LANGSMITH_PROJECT"               = "review-platform-production"
    "LANGSMITH_ENDPOINT"              = "https://api.smith.langchain.com"
    "SENTRY_DSN"                      = "CHANGE_ME"
    "ENVIRONMENT"                     = "production"
    "EMAIL_PROVIDER"                  = "resend"
    "RESEND_API_KEY"                  = "CHANGE_ME"
    "DEFAULT_FROM_EMAIL"              = "noreply@reviewbee.in"
    "DEFAULT_REPLY_TO"                = "support@reviewbee.in"
    "AWS_STORAGE_BUCKET_NAME"         = "review-master-static-prod"
    "AWS_S3_REGION_NAME"              = "ap-south-1"
    "CADDY_DOMAIN"                    = "reviewbee.in"
    "CADDY_ACME_EMAIL"                = "renjith@sayonetech.com"
    "INITIAL_SYNC_PAGE_SIZE"          = "50"
    "INCREMENTAL_SYNC_INTERVAL_HOURS" = "6"
    "INCREMENTAL_SYNC_JITTER_MINUTES" = "30"
  }
}

resource "aws_ssm_parameter" "app" {
  for_each = local.ssm_placeholders

  name  = "${local.ssm_prefix}/${each.key}"
  type  = "SecureString"
  value = each.value

  lifecycle {
    ignore_changes = [value]
  }
}
