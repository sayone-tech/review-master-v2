resource "aws_secretsmanager_secret" "app" {
  name        = "review-master/prod"
  description = "All production environment variables for review-master"

  tags = { Project = "review-master" }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DJANGO_SECRET_KEY               = "CHANGE_ME_run_get_random_secret_key"
    DJANGO_ALLOWED_HOSTS            = "app.reviewbee.in"
    SITE_URL                        = "https://app.reviewbee.in"
    DATABASE_URL                    = "postgres://reviewbee:CHANGE_ME@CHANGE_ME_rds_endpoint:5432/reviewmaster"
    REDIS_URL                       = "redis://redis:6379"
    GOOGLE_OAUTH_CLIENT_ID          = "CHANGE_ME"
    GOOGLE_OAUTH_CLIENT_SECRET      = "CHANGE_ME"
    GOOGLE_OAUTH_REDIRECT_URI       = "https://app.reviewbee.in/oauth/google/callback/"
    FERNET_SALT_KEY                 = "CHANGE_ME_generate_fernet_key"
    OPENAI_API_KEY                  = "CHANGE_ME"
    OPENAI_MODEL                    = "gpt-4o-mini-2024-07-18"
    OPENAI_MAX_RETRIES              = "3"
    ENRICHMENT_BATCH_SIZE           = "10"
    LANGSMITH_API_KEY               = "CHANGE_ME"
    LANGSMITH_PROJECT               = "review-platform-production"
    LANGSMITH_ENDPOINT              = "https://api.smith.langchain.com"
    SENTRY_DSN                      = "CHANGE_ME"
    ENVIRONMENT                     = "production"
    EMAIL_PROVIDER                  = "resend"
    RESEND_API_KEY                  = "CHANGE_ME"
    DEFAULT_FROM_EMAIL              = "noreply@reviewbee.in"
    DEFAULT_REPLY_TO                = "support@reviewbee.in"
    AWS_STORAGE_BUCKET_NAME         = "review-master-static-prod"
    AWS_S3_REGION_NAME              = "ap-south-1"
    CADDY_DOMAIN                    = "app.reviewbee.in"
    CADDY_ACME_EMAIL                = "renjith@sayonetech.com"
    INITIAL_SYNC_PAGE_SIZE          = "50"
    INCREMENTAL_SYNC_INTERVAL_HOURS = "6"
    INCREMENTAL_SYNC_JITTER_MINUTES = "30"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
