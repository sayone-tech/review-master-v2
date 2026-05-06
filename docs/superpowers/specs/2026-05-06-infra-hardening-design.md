# Infrastructure Hardening Design

**Date:** 2026-05-06
**Status:** Approved

---

## Overview

Three tightly related infrastructure changes rolled out together:

1. Move the app to `app.reviewbee.in`
2. Migrate all secrets from SSM Parameter Store to AWS Secrets Manager
3. Replace SSH access with AWS Systems Manager Session Manager

---

## 1. Domain Change — `reviewbee.in` → `app.reviewbee.in`

### What changes

**Terraform (`deployment/terraform/`):**
- `route53.tf` — add an A record for `app.reviewbee.in` pointing to the Elastic IP
- `ssm.tf` → becomes `secrets.tf` after migration (see section 2), placeholders updated:
  - `CADDY_DOMAIN` → `app.reviewbee.in`
  - `DJANGO_ALLOWED_HOSTS` → `app.reviewbee.in`
  - `SITE_URL` → `https://app.reviewbee.in`
  - `GOOGLE_OAUTH_REDIRECT_URI` → `https://app.reviewbee.in/oauth/google/callback/`

**Live secrets (updated manually in Secrets Manager console after migration):**
- Same four values updated in the actual secret JSON

**Not changing:**
- `DEFAULT_FROM_EMAIL` / `DEFAULT_REPLY_TO` — email domain stays `@reviewbee.in`
- Old `reviewbee.in` Route 53 record — leave in place (Caddy will stop serving it but DNS still resolves; can be cleaned up later)

### How it works

Caddy reads `CADDY_DOMAIN` from the env file at startup and automatically obtains a Let's Encrypt TLS certificate for `app.reviewbee.in`. No manual cert management needed.

---

## 2. Secrets Manager Migration

### Approach

All 29 parameters become a **single JSON secret** named `review-master/prod` in AWS Secrets Manager. One secret instead of 29 SSM parameters.

**Why one secret (not one-per-parameter):**
- Cost: $0.40/month for one secret vs $0.40/parameter/month × 29 = $11.60/month for SSM SecureString
- Easier to view and edit in the console — one JSON blob, all values visible together
- `load-secrets.sh` becomes simpler — one API call instead of paginated SSM path fetch

### Terraform changes (`deployment/terraform/`)

**Remove:** `ssm.tf` entirely
**Add:** `secrets.tf` with:

```hcl
resource "aws_secretsmanager_secret" "app" {
  name        = "review-master/prod"
  description = "All production environment variables for review-master"
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
```

### IAM changes

**EC2 role** (`iam.tf`):
- Remove: SSM parameter read statements (`ssm:GetParametersByPath`, `ssm:GetParameter`, `ssm:GetParameters`, `kms:Decrypt` for SSM key)
- Add: `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:ap-south-1:*:secret:review-master/prod*`

**GitHub Actions role** (`iam.tf`):
- Remove: `ssm:GetParameter` statement
- Add: `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:ap-south-1:*:secret:review-master/prod*`

### `load-secrets.sh` changes

Replace the SSM fetch with a single Secrets Manager call:

```bash
aws secretsmanager get-secret-value \
  --secret-id "review-master/prod" \
  --region "${AWS_REGION}" \
  --query "SecretString" \
  --output text \
| python3 -c "
import json, sys
for k, v in json.load(sys.stdin).items():
    print(f'{k}={v}')
" > "${ENV_FILE}"
```

### `deploy.yml` smoke test change

Replace the SSM parameter lookup with Secrets Manager:

```bash
DOMAIN=$(aws secretsmanager get-secret-value \
  --secret-id "review-master/prod" \
  --region "$AWS_REGION" \
  --query "SecretString" \
  --output text | python3 -c "import json,sys; print(json.load(sys.stdin)['CADDY_DOMAIN'])")
```

### Migration order

1. Apply Terraform (creates Secrets Manager secret, keeps SSM params intact)
2. Copy real values from SSM console into the Secrets Manager secret JSON
3. Run `load-secrets.sh` on EC2 to verify it reads correctly
4. Run `deploy.sh` to restart containers with new env
5. Verify site is up on `app.reviewbee.in`
6. Delete old SSM parameters via Terraform (remove `ssm.tf`, apply)

---

## 3. Session Manager — Remove SSH

### What changes

**Terraform (`deployment/terraform/iam.tf`):**
- Remove: manual `ssmmessages:*` and `ssm:UpdateInstanceInformation` statements from EC2 role
- Add: `aws_iam_role_policy_attachment` attaching `AmazonSSMManagedInstanceCore` managed policy to EC2 role (covers Session Manager + patch manager cleanly)

**Terraform (`deployment/terraform/ec2.tf`):**
- Remove: `aws_key_pair.operator` resource
- Remove: `key_name` from `aws_instance.app`

**Terraform (`deployment/terraform/security_groups.tf`):**
- Remove: SSH inbound rule (port 22) from EC2 security group

**Terraform (`deployment/terraform/variables.tf`):**
- Remove: `operator_ip` variable (no longer needed)

**Terraform (`deployment/terraform/terraform.tfvars`):**
- Remove: `operator_ip` line

### How to connect after migration

From any terminal with AWS CLI configured:

```bash
# Interactive shell
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# Run a single command
aws ssm start-session \
  --target i-0782bee2ff9885151 \
  --region ap-south-1 \
  --document-name AWS-StartInteractiveCommand \
  --parameters command="sudo docker ps"
```

**Prerequisite (one-time, Mac):**
```bash
brew install --cask session-manager-plugin
```

### Security improvement

- Zero inbound ports open on the EC2 security group
- No long-lived SSH keys to rotate or leak
- All session activity logged to CloudWatch automatically by SSM Agent
- Access controlled entirely by IAM — revoke by changing IAM permissions, not by rotating keys

---

## Rollout Order

1. **Terraform apply** — creates Secrets Manager secret, adds Route 53 record, attaches `AmazonSSMManagedInstanceCore`, removes SSH rule and key pair
2. **Copy real values** into Secrets Manager console (from current SSM values)
3. **Run `load-secrets.sh`** on EC2 via Session Manager (first use of the new access method)
4. **Run `deploy.sh`** — restarts containers with new domain + secrets
5. **Verify** `https://app.reviewbee.in/healthz/` returns 200
6. **Delete old SSM parameters** — remove `ssm.tf`, apply Terraform again
7. **Push changes to main** — CI/CD pipeline validates everything

---

## Files Changed

| File | Change |
|------|--------|
| `deployment/terraform/secrets.tf` | New — replaces ssm.tf |
| `deployment/terraform/ssm.tf` | Deleted |
| `deployment/terraform/iam.tf` | EC2 role: swap SSM perms for Secrets Manager + managed policy; GitHub Actions role: swap ssm:GetParameter for secretsmanager:GetSecretValue |
| `deployment/terraform/route53.tf` | Add A record for `app.reviewbee.in` |
| `deployment/terraform/ec2.tf` | Remove key_pair resource and key_name from instance |
| `deployment/terraform/security_groups.tf` | Remove port 22 inbound rule |
| `deployment/terraform/variables.tf` | Remove operator_ip variable |
| `deployment/terraform/terraform.tfvars` | Remove operator_ip value |
| `deployment/scripts/load-secrets.sh` | Rewrite to use Secrets Manager |
| `.github/workflows/deploy.yml` | Update smoke test domain lookup to use Secrets Manager |
