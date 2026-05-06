# AWS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy review-master to a single EC2 box on AWS Mumbai (ap-south-1) with RDS PostgreSQL, Caddy TLS, SSM secrets, and a GitHub Actions → SSM Run Command deploy pipeline.

**Architecture:** Terraform manages all stateful AWS infra (VPC, RDS, ECR, IAM, SSM, S3, CloudWatch). Route 53 hosted zone already exists (manually created with DNS migrated from GoDaddy) — Terraform uses a `data` source to reference it and only manages A records. EC2 is launched once via the console and bootstrapped by a user-data script. GitHub Actions builds an arm64 Docker image, pushes to ECR, then triggers a deploy on EC2 via SSM Run Command — no SSH keys in CI. Use `deploy-on-aws` MCP tools (`awsiac`, `awsknowledge`, `awspricing`) when generating or validating IaC.

**Tech Stack:** Terraform ~> 5.0 AWS provider, Docker Compose (prod), Caddy 2, Amazon Linux 2023, GitHub Actions OIDC, django-storages[s3], SSM Parameter Store (SecureString).

**SSM naming convention:** Flat env-var paths — `/review-master/prod/<ENV_VAR_NAME>` (e.g. `/review-master/prod/DJANGO_SECRET_KEY`). `load-secrets.sh` strips the prefix to get the exact env var name. No mapping table needed.

---

## File Map

```
# New files — application
config/settings/production.py          MODIFY — add S3 static files block
pyproject.toml                         MODIFY — add django-storages[s3]

# New files — deployment
deployment/caddy/Caddyfile
deployment/compose/docker-compose.prod.yml
deployment/compose/.env.prod.example
deployment/scripts/load-secrets.sh
deployment/scripts/user-data.sh
deployment/scripts/deploy.sh
deployment/ssm/seed-params.sh
deployment/terraform/main.tf
deployment/terraform/variables.tf
deployment/terraform/outputs.tf
deployment/terraform/vpc.tf
deployment/terraform/security_groups.tf
deployment/terraform/rds.tf
deployment/terraform/ecr.tf
deployment/terraform/s3.tf
deployment/terraform/iam.tf
deployment/terraform/ssm.tf
deployment/terraform/route53.tf
deployment/terraform/cloudwatch.tf

# CI/CD
.github/workflows/deploy.yml
```

---

## Task 1: Add django-storages and Production S3 Static Files

**Why:** Static files are served from S3 in production. `collectstatic` runs as a deploy step on EC2 using the instance profile credentials — no AWS keys needed in the Docker image.

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/settings/production.py`

- [ ] **Step 1: Add django-storages to dependencies**

```bash
uv add "django-storages[s3]==1.14.4"
```

Expected: `pyproject.toml` and `uv.lock` updated.

- [ ] **Step 2: Add S3 static files block to production.py**

Open `config/settings/production.py`. After the existing `SALT_KEY` line at the end, add:

```python
# S3 static files — served from S3 in production (EC2 instance profile provides credentials)
INSTALLED_APPS = [*list(INSTALLED_APPS), "storages"]

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_S3_CUSTOM_DOMAIN = (
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
)
AWS_LOCATION = "static"
AWS_DEFAULT_ACL = None  # inherit bucket policy (public-read set by Terraform)
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"

# base.py does not define STORAGES — define both backends explicitly here.
# "default" keeps filesystem storage (no media uploads in scope).
# "staticfiles" routes collectstatic to S3.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    },
}
```

- [ ] **Step 3: Verify no import errors**

```bash
DJANGO_SETTINGS_MODULE=config.settings.production \
  AWS_STORAGE_BUCKET_NAME=dummy-bucket \
  DJANGO_SECRET_KEY=dummy \
  DJANGO_ALLOWED_HOSTS=localhost \
  FERNET_SALT_KEY=dummy \
  DATABASE_URL=postgres://x:x@localhost/x \
  RESEND_API_KEY=dummy \
  uv run python -c "import django; django.setup(); print('OK')"
```

Expected: `OK` (no ImportError or settings misconfiguration).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock config/settings/production.py
git commit -m "feat(deploy): add django-storages S3 backend for production static files"
```

---

## Task 2: Production Docker Compose and Caddyfile

**Why:** The dev `docker-compose.yml` is for local use only. The prod compose is a clean slate — 6 containers, env_file from SSM, awslogs driver, no source mounts.

**Files:**
- Create: `deployment/caddy/Caddyfile`
- Create: `deployment/compose/docker-compose.prod.yml`
- Create: `deployment/compose/.env.prod.example`

- [ ] **Step 1: Create directories**

```bash
mkdir -p deployment/caddy deployment/compose
```

- [ ] **Step 2: Write Caddyfile**

Create `deployment/caddy/Caddyfile`:

```caddy
{
    email {$CADDY_ACME_EMAIL}
}

{$CADDY_DOMAIN} {
    reverse_proxy web:8000
    encode gzip
    log {
        output stdout
    }
}
```

`CADDY_DOMAIN` and `CADDY_ACME_EMAIL` are env vars injected by the prod compose — this avoids hardcoding the domain in the file.

- [ ] **Step 3: Write docker-compose.prod.yml**

Create `deployment/compose/docker-compose.prod.yml`:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /opt/review-master/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    env_file: /etc/review-master.env
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /review-master/prod
        awslogs-stream-prefix: caddy

  web:
    image: ${ECR_IMAGE}
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    restart: unless-stopped
    env_file: /etc/review-master.env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
    depends_on:
      - redis
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /review-master/prod
        awslogs-stream-prefix: web
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/healthz/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s

  worker:
    image: ${ECR_IMAGE}
    command: >
      celery -A config worker
      -Q google-sync,ai-enrichment,default
      --concurrency=2
      --loglevel=info
    restart: unless-stopped
    env_file: /etc/review-master.env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
    depends_on:
      - redis
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /review-master/prod
        awslogs-stream-prefix: worker
    healthcheck:
      test: ["CMD-SHELL", "celery -A config inspect ping --timeout 5 2>&1 | grep -q OK"]
      interval: 30s
      timeout: 15s
      retries: 3
      start_period: 30s

  beat:
    image: ${ECR_IMAGE}
    command: >
      celery -A config beat
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
      --loglevel=info
    restart: unless-stopped
    env_file: /etc/review-master.env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
    depends_on:
      - redis
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /review-master/prod
        awslogs-stream-prefix: beat
    healthcheck:
      test: ["CMD-SHELL", "cat /proc/*/cmdline 2>/dev/null | tr '\\0' ' ' | grep -q 'celery.*beat'"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  flower:
    image: ${ECR_IMAGE}
    command: celery -A config flower --port=5555 --address=127.0.0.1
    restart: unless-stopped
    env_file: /etc/review-master.env
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
    depends_on:
      - redis
    ports:
      - "127.0.0.1:5555:5555"
    logging:
      driver: awslogs
      options:
        awslogs-region: ap-south-1
        awslogs-group: /review-master/prod
        awslogs-stream-prefix: flower

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  caddy_data:
  caddy_config:
  redis_data:
```

- [ ] **Step 4: Write .env.prod.example**

Create `deployment/compose/.env.prod.example`:

```bash
# This file documents the env vars that /etc/review-master.env must contain.
# DO NOT put real values here. Real values live in AWS SSM Parameter Store.
# load-secrets.sh writes the real /etc/review-master.env on each deploy.

ECR_IMAGE=<account-id>.dkr.ecr.ap-south-1.amazonaws.com/review-master/app:latest

DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<from ssm>
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com

DATABASE_URL=postgres://app:<password>@<rds-endpoint>:5432/reviewmaster
REDIS_URL=redis://redis:6379

GOOGLE_OAUTH_CLIENT_ID=<from ssm>
GOOGLE_OAUTH_CLIENT_SECRET=<from ssm>
GOOGLE_OAUTH_REDIRECT_URI=https://yourdomain.com/oauth/google/callback/

FERNET_SALT_KEY=<from ssm>

OPENAI_API_KEY=<from ssm>
OPENAI_MODEL=gpt-4o-mini-2024-07-18
OPENAI_MAX_RETRIES=3
ENRICHMENT_BATCH_SIZE=10

LANGSMITH_API_KEY=<from ssm>
LANGSMITH_PROJECT=review-platform-production
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

SENTRY_DSN=<from ssm>
ENVIRONMENT=production

EMAIL_PROVIDER=resend
RESEND_API_KEY=<from ssm>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
DEFAULT_REPLY_TO=support@yourdomain.com

AWS_STORAGE_BUCKET_NAME=review-master-static-prod
AWS_S3_REGION_NAME=ap-south-1
AWS_SES_REGION_NAME=ap-south-1

CADDY_DOMAIN=yourdomain.com
CADDY_ACME_EMAIL=your@email.com

INITIAL_SYNC_PAGE_SIZE=50
INCREMENTAL_SYNC_INTERVAL_HOURS=6
INCREMENTAL_SYNC_JITTER_MINUTES=30
```

- [ ] **Step 5: Validate compose syntax**

```bash
# Provide minimum required env vars for syntax check
ECR_IMAGE=dummy docker compose \
  -f deployment/compose/docker-compose.prod.yml \
  config --quiet && echo "Compose syntax OK"
```

Expected: `Compose syntax OK` with no errors.

- [ ] **Step 6: Commit**

```bash
git add deployment/caddy/ deployment/compose/
git commit -m "feat(deploy): add production Docker Compose and Caddyfile"
```

---

## Task 3: EC2 Bootstrap and Deploy Scripts

**Files:**
- Create: `deployment/scripts/load-secrets.sh`
- Create: `deployment/scripts/user-data.sh`
- Create: `deployment/scripts/deploy.sh`

- [ ] **Step 1: Create scripts directory**

```bash
mkdir -p deployment/scripts
```

- [ ] **Step 2: Write load-secrets.sh**

Create `deployment/scripts/load-secrets.sh`:

```bash
#!/usr/bin/env bash
# Reads all SSM params under /review-master/prod/ and writes /etc/review-master.env
# SSM path convention: /review-master/prod/<ENV_VAR_NAME>
# e.g. /review-master/prod/DJANGO_SECRET_KEY -> DJANGO_SECRET_KEY=<value>
set -euo pipefail

AWS_REGION="ap-south-1"
PARAM_PATH="/review-master/prod"
ENV_FILE="/etc/review-master.env"

echo "[load-secrets] Fetching SSM parameters from ${PARAM_PATH}..."

# Fetch all params, output as tab-separated Name\tValue lines
aws ssm get-parameters-by-path \
  --path "${PARAM_PATH}" \
  --with-decryption \
  --recursive \
  --region "${AWS_REGION}" \
  --query "Parameters[*].[Name,Value]" \
  --output text \
| while IFS=$'\t' read -r name value; do
    # Strip prefix to get env var name: /review-master/prod/DJANGO_SECRET_KEY -> DJANGO_SECRET_KEY
    key="${name#${PARAM_PATH}/}"
    printf '%s=%s\n' "${key}" "${value}"
  done > "${ENV_FILE}"

chmod 600 "${ENV_FILE}"
echo "[load-secrets] Written ${ENV_FILE} ($(wc -l < "${ENV_FILE}") vars)"
```

- [ ] **Step 3: Write user-data.sh**

Create `deployment/scripts/user-data.sh`:

```bash
#!/usr/bin/env bash
# EC2 first-boot bootstrap — Amazon Linux 2023, Graviton (aarch64)
# Runs once as root via EC2 user-data.
set -euo pipefail

AWS_REGION="ap-south-1"
APP_DIR="/opt/review-master"
LOG_FILE="/var/log/review-master-init.log"

exec > >(tee -a "${LOG_FILE}") 2>&1
echo "[user-data] Starting at $(date)"

# ---------- Docker ----------
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

# ---------- Docker Compose plugin (aarch64) ----------
COMPOSE_VERSION="2.27.1"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
echo "[user-data] Docker Compose $(docker compose version)"

# ---------- App directory ----------
mkdir -p "${APP_DIR}/scripts" "${APP_DIR}/caddy"

# ---------- Copy scripts (uploaded separately via deploy) ----------
# Scripts land via SSM Run Command on first deploy.
# Seed load-secrets.sh manually from S3 or paste if bootstrapping from scratch.

# ---------- ECR login ----------
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS \
    --password-stdin \
    "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "[user-data] Done at $(date)"
```

- [ ] **Step 4: Write deploy.sh**

Create `deployment/scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
# Runs on EC2 via SSM Run Command on every deploy.
# Called by GitHub Actions after pushing a new image to ECR.
set -euo pipefail

AWS_REGION="ap-south-1"
APP_DIR="/opt/review-master"
COMPOSE_FILE="${APP_DIR}/docker-compose.prod.yml"
ECR_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${ECR_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
# Export so docker compose variable interpolation (${ECR_IMAGE} in image: field)
# resolves correctly. env_file only injects vars INTO containers — it never
# reaches compose's own substitution step.
export ECR_IMAGE="${ECR_REGISTRY}/review-master/app:latest"

echo "[deploy] Starting at $(date)"

# 1. ECR login (instance profile, no keys)
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# 2. Refresh secrets from SSM -> /etc/review-master.env
"${APP_DIR}/scripts/load-secrets.sh"

# 3. Pull latest image
docker compose -f "${COMPOSE_FILE}" pull

# 4. Run migrations
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py migrate --noinput

# 5. Collect static files to S3
docker compose -f "${COMPOSE_FILE}" run --rm web \
  python manage.py collectstatic --noinput --clear

# 6. Restart all services
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

# 8. Wait for web healthcheck
echo "[deploy] Waiting for web healthcheck..."
for i in $(seq 1 24); do
  if docker compose -f "${COMPOSE_FILE}" exec -T web \
       curl -fsS http://localhost:8000/healthz/ > /dev/null 2>&1; then
    echo "[deploy] Web healthy after ${i}x5s"
    break
  fi
  sleep 5
done

echo "[deploy] Done at $(date)"
```

- [ ] **Step 5: Make scripts executable**

```bash
chmod +x deployment/scripts/load-secrets.sh \
         deployment/scripts/user-data.sh \
         deployment/scripts/deploy.sh
```

- [ ] **Step 6: Commit**

```bash
git add deployment/scripts/
git commit -m "feat(deploy): add EC2 bootstrap and deploy scripts"
```

---

## Task 4: SSM Parameter Seed Script

**Why:** Creates all 20 SSM parameters with placeholder values in one command. You fill in real values via the AWS console or CLI after creation.

**Files:**
- Create: `deployment/ssm/seed-params.sh`

- [ ] **Step 1: Create SSM directory**

```bash
mkdir -p deployment/ssm
```

- [ ] **Step 2: Write seed-params.sh**

Create `deployment/ssm/seed-params.sh`:

```bash
#!/usr/bin/env bash
# Creates all SSM SecureString parameters with placeholder values.
# Run once: bash deployment/ssm/seed-params.sh
# After running, update each CHANGE_ME value in the AWS console.
#
# Usage: AWS_PROFILE=your-profile bash deployment/ssm/seed-params.sh
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
  echo "  Created: ${PREFIX}/${name}"
}

echo "Seeding SSM parameters in ${REGION}..."

# Django core
put_param "DJANGO_SECRET_KEY"     "CHANGE_ME_run_get_random_secret_key"
put_param "DJANGO_ALLOWED_HOSTS"  "yourdomain.com,www.yourdomain.com"
put_param "SITE_URL"              "https://yourdomain.com"

# Database — Terraform outputs the RDS endpoint; replace <rds-endpoint> below
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
put_param "SENTRY_DSN"    "CHANGE_ME"
put_param "ENVIRONMENT"   "production"

# Email
put_param "EMAIL_PROVIDER"      "resend"
put_param "RESEND_API_KEY"      "CHANGE_ME"
put_param "DEFAULT_FROM_EMAIL"  "noreply@yourdomain.com"
put_param "DEFAULT_REPLY_TO"    "support@yourdomain.com"

# S3 static files
put_param "AWS_STORAGE_BUCKET_NAME" "review-master-static-prod"
put_param "AWS_S3_REGION_NAME"      "ap-south-1"

# Caddy
put_param "CADDY_DOMAIN"      "yourdomain.com"
put_param "CADDY_ACME_EMAIL"  "CHANGE_ME_your_email"

# Sync tuning
put_param "INITIAL_SYNC_PAGE_SIZE"          "50"
put_param "INCREMENTAL_SYNC_INTERVAL_HOURS" "6"
put_param "INCREMENTAL_SYNC_JITTER_MINUTES" "30"

echo ""
echo "Done. Update CHANGE_ME values in the AWS console:"
echo "  https://ap-south-1.console.aws.amazon.com/systems-manager/parameters"
```

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x deployment/ssm/seed-params.sh
git add deployment/ssm/
git commit -m "feat(deploy): add SSM parameter seed script"
```

---

## Task 5: Terraform Foundation — Provider, VPC, Security Groups

**Note:** Use `awsiac` MCP (`mcp__plugin_deploy-on-aws_awsiac__*`) to validate Terraform patterns when writing or reviewing these files.

**Files:**
- Create: `deployment/terraform/main.tf`
- Create: `deployment/terraform/variables.tf`
- Create: `deployment/terraform/outputs.tf`
- Create: `deployment/terraform/vpc.tf`
- Create: `deployment/terraform/security_groups.tf`

- [ ] **Step 1: Create terraform directory**

```bash
mkdir -p deployment/terraform
```

- [ ] **Step 2: Write main.tf**

Create `deployment/terraform/main.tf`:

```hcl
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
  # backend "s3" { bucket = "review-master-tfstate" key = "prod/terraform.tfstate" ... }
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
```

- [ ] **Step 3: Write variables.tf**

Create `deployment/terraform/variables.tf`:

```hcl
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
  description = "Root domain name, e.g. example.com"
  type        = string
}

variable "operator_ip" {
  description = "Your public IP in CIDR notation for SSH access, e.g. 1.2.3.4/32"
  type        = string
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "app"
}

variable "github_org" {
  description = "GitHub organisation or username (for OIDC trust policy)"
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
```

- [ ] **Step 4: Write outputs.tf**

Create `deployment/terraform/outputs.tf`:

```hcl
output "rds_endpoint" {
  description = "RDS endpoint — replace CHANGE_ME_rds_endpoint in SSM DATABASE_URL"
  value       = aws_db_instance.main.endpoint
}

output "ecr_url" {
  description = "ECR repository URL — used in GitHub Actions workflow"
  value       = aws_ecr_repository.app.repository_url
}

output "static_bucket_name" {
  description = "S3 bucket name — used in SSM AWS_STORAGE_BUCKET_NAME"
  value       = aws_s3_bucket.static.id
}

output "github_oidc_role_arn" {
  description = "IAM role ARN — paste into .github/workflows/deploy.yml"
  value       = aws_iam_role.github_actions.arn
}

output "ec2_eip_allocation_id" {
  description = "Elastic IP allocation ID — run: aws ec2 associate-address --instance-id <id> --allocation-id <this>"
  value       = aws_eip.ec2.allocation_id
}

output "elastic_ip" {
  description = "EC2 Elastic IP — set as A record; also shown in Route 53 already"
  value       = aws_eip.ec2.public_ip
}
```

- [ ] **Step 5: Write vpc.tf**

Create `deployment/terraform/vpc.tf`:

```hcl
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "review-master-vpc" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "review-master-public-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = { Name = "review-master-private-${count.index + 1}" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "review-master-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "review-master-public-rt" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_db_subnet_group" "main" {
  name       = "review-master-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "review-master-db-subnet-group" }
}
```

- [ ] **Step 6: Write security_groups.tf**

Create `deployment/terraform/security_groups.tf`:

```hcl
resource "aws_security_group" "ec2" {
  name        = "review-master-ec2"
  description = "Review Master EC2 — HTTP/HTTPS public, SSH operator-only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH — operator IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.operator_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "review-master-ec2-sg" }
}

resource "aws_security_group" "rds" {
  name        = "review-master-rds"
  description = "Review Master RDS — PostgreSQL from EC2 SG only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from EC2 only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "review-master-rds-sg" }
}
```

- [ ] **Step 7: Run terraform init and validate**

```bash
cd deployment/terraform
terraform init
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 8: Commit**

```bash
cd ../..
git add deployment/terraform/main.tf deployment/terraform/variables.tf \
        deployment/terraform/outputs.tf deployment/terraform/vpc.tf \
        deployment/terraform/security_groups.tf
git commit -m "feat(deploy): add Terraform foundation — provider, VPC, security groups"
```

---

## Task 6: Terraform Data Layer — RDS, ECR, S3, Elastic IP

**Files:**
- Create: `deployment/terraform/rds.tf`
- Create: `deployment/terraform/ecr.tf`
- Create: `deployment/terraform/s3.tf`

- [ ] **Step 1: Write rds.tf**

Create `deployment/terraform/rds.tf`:

```hcl
resource "random_password" "db_password" {
  length  = 32
  special = false  # avoid shell escaping issues in DATABASE_URL
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/review-master/prod/DB_PASSWORD_RAW"
  type  = "SecureString"
  value = random_password.db_password.result

  lifecycle {
    ignore_changes = [value]  # don't overwrite if manually rotated later
  }
}

resource "aws_db_instance" "main" {
  identifier        = "review-master-prod"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  max_allocated_storage = 100
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "reviewmaster"
  username = var.db_username
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  backup_window           = "03:00-04:00"  # UTC (08:30 IST)
  maintenance_window      = "Mon:04:00-Mon:05:00"

  skip_final_snapshot       = false
  final_snapshot_identifier = "review-master-prod-final"
  deletion_protection       = true

  performance_insights_enabled = true

  tags = { Name = "review-master-prod" }
}
```

- [ ] **Step 2: Write ecr.tf**

Create `deployment/terraform/ecr.tf`:

```hcl
resource "aws_ecr_repository" "app" {
  name                 = "review-master/app"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
```

- [ ] **Step 3: Write s3.tf**

Create `deployment/terraform/s3.tf`:

```hcl
resource "aws_s3_bucket" "static" {
  bucket = "review-master-static-${var.environment}"
  tags   = { Name = "review-master-static-${var.environment}" }
}

resource "aws_s3_bucket_public_access_block" "static" {
  bucket = aws_s3_bucket.static.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "static" {
  bucket     = aws_s3_bucket.static.id
  depends_on = [aws_s3_bucket_public_access_block.static]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadStaticFiles"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.static.arn}/static/*"
    }]
  })
}

resource "aws_s3_bucket_cors_configuration" "static" {
  bucket = aws_s3_bucket.static.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["https://${var.domain_name}", "https://www.${var.domain_name}"]
    max_age_seconds = 3600
  }
}
```

- [ ] **Step 4: Validate**

```bash
cd deployment/terraform && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
cd ../..
git add deployment/terraform/rds.tf deployment/terraform/ecr.tf \
        deployment/terraform/s3.tf
git commit -m "feat(deploy): add Terraform RDS, ECR, S3"
```

---

## Task 7: Terraform IAM and SSM Parameters

**Files:**
- Create: `deployment/terraform/iam.tf`
- Create: `deployment/terraform/ssm.tf`

- [ ] **Step 1: Write iam.tf**

Create `deployment/terraform/iam.tf`:

```hcl
# ---------- GitHub Actions OIDC provider ----------
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

# ---------- EC2 instance profile ----------
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "review-master-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "ec2_permissions" {
  # ECR — pull images (GetAuthorizationToken requires *)
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # SSM — read secrets
  statement {
    actions = [
      "ssm:GetParametersByPath",
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:*:parameter/review-master/prod*",
    ]
  }

  # KMS — decrypt SecureString params (default SSM key)
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.aws_region}:*:key/alias/aws/ssm"]
  }

  # CloudWatch Logs — write container logs
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/review-master/*:*"]
  }

  # SSM Agent — required for SSM Run Command to reach the instance
  statement {
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
      "ssm:UpdateInstanceInformation",
    ]
    resources = ["*"]
  }

  # S3 — collectstatic writes to the static bucket
  statement {
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.static.arn,
      "${aws_s3_bucket.static.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "ec2" {
  name   = "review-master-ec2-policy"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_permissions.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "review-master-ec2"
  role = aws_iam_role.ec2.name
}

# ---------- GitHub Actions OIDC role ----------
data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "review-master-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

data "aws_iam_policy_document" "github_permissions" {
  # ECR — push images
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # SSM Run Command — send commands to EC2 tagged with Project=review-master
  statement {
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ec2:${var.aws_region}:*:instance/*",
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = ["review-master"]
    }
  }

  # SSM — poll command status
  statement {
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "review-master-github-actions-policy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_permissions.json
}
```

- [ ] **Step 2: Write ssm.tf**

Create `deployment/terraform/ssm.tf`:

```hcl
# All parameters use SecureString with the default SSM KMS key.
# Terraform seeds placeholder values only. Update real values in the AWS console
# or via: aws ssm put-parameter --name "/review-master/prod/PARAM" --value "real" --overwrite
#
# lifecycle ignore_changes = [value] ensures terraform apply never overwrites
# values you've updated manually.

locals {
  ssm_prefix = "/review-master/prod"
  ssm_placeholders = {
    "DJANGO_SECRET_KEY"              = "CHANGE_ME_run_get_random_secret_key"
    "DJANGO_ALLOWED_HOSTS"           = "yourdomain.com,www.yourdomain.com"
    "SITE_URL"                       = "https://yourdomain.com"
    "DATABASE_URL"                   = "postgres://app:CHANGE_ME@CHANGE_ME_rds_endpoint:5432/reviewmaster"
    "REDIS_URL"                      = "redis://redis:6379"
    "GOOGLE_OAUTH_CLIENT_ID"         = "CHANGE_ME"
    "GOOGLE_OAUTH_CLIENT_SECRET"     = "CHANGE_ME"
    "GOOGLE_OAUTH_REDIRECT_URI"      = "https://yourdomain.com/oauth/google/callback/"
    "FERNET_SALT_KEY"                = "CHANGE_ME_generate_fernet_key"
    "OPENAI_API_KEY"                 = "CHANGE_ME"
    "OPENAI_MODEL"                   = "gpt-4o-mini-2024-07-18"
    "OPENAI_MAX_RETRIES"             = "3"
    "ENRICHMENT_BATCH_SIZE"          = "10"
    "LANGSMITH_API_KEY"              = "CHANGE_ME"
    "LANGSMITH_PROJECT"              = "review-platform-production"
    "LANGSMITH_ENDPOINT"             = "https://api.smith.langchain.com"
    "SENTRY_DSN"                     = "CHANGE_ME"
    "ENVIRONMENT"                    = "production"
    "EMAIL_PROVIDER"                 = "resend"
    "RESEND_API_KEY"                 = "CHANGE_ME"
    "DEFAULT_FROM_EMAIL"             = "noreply@yourdomain.com"
    "DEFAULT_REPLY_TO"               = "support@yourdomain.com"
    "AWS_STORAGE_BUCKET_NAME"        = "review-master-static-prod"
    "AWS_S3_REGION_NAME"             = "ap-south-1"
    "CADDY_DOMAIN"                   = "yourdomain.com"
    "CADDY_ACME_EMAIL"               = "CHANGE_ME_your_email"
    "INITIAL_SYNC_PAGE_SIZE"         = "50"
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
```

- [ ] **Step 3: Validate**

```bash
cd deployment/terraform && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Commit**

```bash
cd ../..
git add deployment/terraform/iam.tf deployment/terraform/ssm.tf
git commit -m "feat(deploy): add Terraform IAM roles and SSM parameters"
```

---

## Task 8: Terraform DNS, Elastic IP, and CloudWatch

**Files:**
- Create: `deployment/terraform/route53.tf`
- Create: `deployment/terraform/cloudwatch.tf`

- [ ] **Step 1: Write route53.tf**

Route 53 hosted zone already exists (DNS migrated from GoDaddy). Terraform uses a `data` source — it will never create or destroy the hosted zone, only manage the A records.

Create `deployment/terraform/route53.tf`:

```hcl
resource "aws_eip" "ec2" {
  domain = "vpc"
  tags   = { Name = "review-master-ec2-eip" }
}

# Reference the existing hosted zone — do NOT recreate it
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

resource "aws_route53_record" "apex" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}

resource "aws_route53_record" "www" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}
```

- [ ] **Step 2: Write cloudwatch.tf**

Create `deployment/terraform/cloudwatch.tf`:

```hcl
resource "aws_cloudwatch_log_group" "app" {
  name              = "/review-master/prod"
  retention_in_days = 30
}

resource "aws_sns_topic" "alerts" {
  name = "review-master-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# EC2 alarms — only created when ec2_instance_id is provided
resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  count = var.ec2_instance_id != "" ? 1 : 0

  alarm_name          = "review-master-ec2-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "EC2 CPU > 70% sustained for 10 min"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = var.ec2_instance_id
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_memory" {
  alarm_name          = "review-master-rds-memory-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeableMemory"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 104857600  # 100 MB in bytes
  alarm_description   = "RDS freeable memory < 100 MB"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}
```

**Note on memory/disk alarms:** EC2 memory and disk metrics require the CloudWatch agent running on the instance. These are installed and configured in Task 10 (EC2 launch). Add the remaining alarms after the agent is confirmed running.

- [ ] **Step 3: Final validate**

```bash
cd deployment/terraform && terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 4: Run checkov security scan**

```bash
pip install checkov  # or: brew install checkov
checkov -d deployment/terraform --framework terraform
```

Review any HIGH findings before proceeding. Known acceptable findings:
- `CKV_AWS_144` (S3 cross-region replication) — not needed at this scale
- `CKV_AWS_18` (S3 access logging) — not needed at this scale
- `CKV2_AWS_62` (S3 event notifications) — not needed

- [ ] **Step 5: Commit**

```bash
cd ../..
git add deployment/terraform/route53.tf deployment/terraform/cloudwatch.tf
git commit -m "feat(deploy): add Terraform Route 53, EIP, CloudWatch alarms"
```

---

## Task 9: GitHub Actions Deploy Workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write deploy.yml**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

# Prevent concurrent deploys
concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  deploy:
    name: Build → Push ECR → Deploy EC2
    runs-on: ubuntu-latest
    # Only deploy after CI passes (ci.yml runs on same push)
    needs: []  # remove if you want to gate on a separate CI job

    permissions:
      id-token: write   # required for OIDC
      contents: read

    env:
      AWS_REGION: ap-south-1
      ECR_REPOSITORY: review-master/app

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx (arm64 via QEMU)
        uses: docker/setup-buildx-action@v3

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3
        with:
          platforms: arm64

      - name: Build and push image (linux/arm64)
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/arm64
          push: true
          tags: |
            ${{ steps.ecr-login.outputs.registry }}/${{ env.ECR_REPOSITORY }}:latest
            ${{ steps.ecr-login.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy via SSM Run Command
        id: ssm-deploy
        run: |
          COMMAND_ID=$(aws ssm send-command \
            --region "$AWS_REGION" \
            --document-name "AWS-RunShellScript" \
            --targets "Key=tag:Project,Values=review-master" \
            --parameters 'commands=["/opt/review-master/scripts/deploy.sh"]' \
            --timeout-seconds 600 \
            --query "Command.CommandId" \
            --output text)
          echo "command_id=$COMMAND_ID" >> "$GITHUB_OUTPUT"
          echo "SSM Command ID: $COMMAND_ID"

      - name: Wait for SSM command to complete
        run: |
          COMMAND_ID="${{ steps.ssm-deploy.outputs.command_id }}"
          echo "Polling command $COMMAND_ID..."
          for i in $(seq 1 60); do
            STATUS=$(aws ssm list-command-invocations \
              --region "$AWS_REGION" \
              --command-id "$COMMAND_ID" \
              --details \
              --query "CommandInvocations[0].Status" \
              --output text 2>/dev/null || echo "Pending")
            echo "[$i/60] Status: $STATUS"
            if [[ "$STATUS" == "Success" ]]; then
              echo "Deploy succeeded."
              exit 0
            elif [[ "$STATUS" == "Failed" || "$STATUS" == "TimedOut" || "$STATUS" == "Cancelled" ]]; then
              echo "Deploy failed with status: $STATUS"
              aws ssm list-command-invocations \
                --region "$AWS_REGION" \
                --command-id "$COMMAND_ID" \
                --details \
                --query "CommandInvocations[0].CommandPlugins[0].Output" \
                --output text
              exit 1
            fi
            sleep 10
          done
          echo "Timed out waiting for deploy."
          exit 1

      - name: Smoke test
        run: |
          DOMAIN=$(aws ssm get-parameter \
            --name "/review-master/prod/CADDY_DOMAIN" \
            --with-decryption \
            --query "Parameter.Value" \
            --output text)
          echo "Smoke testing https://$DOMAIN/healthz/"
          curl -fsSL "https://$DOMAIN/healthz/" | grep -q "ok" && echo "Healthcheck passed."
```

- [ ] **Step 2: Add AWS_DEPLOY_ROLE_ARN GitHub secret**

After `terraform apply` (Task 10), run:

```bash
terraform -chdir=deployment/terraform output github_oidc_role_arn
```

Go to GitHub → repo Settings → Secrets and variables → Actions → New secret:
- Name: `AWS_DEPLOY_ROLE_ARN`
- Value: the ARN from the output above

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(deploy): add GitHub Actions OIDC deploy workflow"
```

---

## Task 10: First Deployment Execution

**This task is operational — no code files are created. Follow steps in order.**

**Prerequisites to collect before starting (ask user for these):**
- AWS account ID
- Domain name (exact, e.g. `reviewmaster.app`)
- Your public IP address (run `curl ifconfig.me`)
- GitHub org and repo name
- Alert email address

- [ ] **Step 1: Create terraform.tfvars**

Create `deployment/terraform/terraform.tfvars` (gitignored — contains your IP):

```hcl
domain_name     = "yourdomain.com"
operator_ip     = "YOUR_IP/32"
alert_email     = "your@email.com"
github_org      = "your-github-org"
github_repo     = "review-master"
```

Add to `.gitignore`:

```
deployment/terraform/terraform.tfvars
deployment/terraform/.terraform/
deployment/terraform/terraform.tfstate*
```

- [ ] **Step 2: Run terraform apply**

```bash
cd deployment/terraform
terraform init
terraform plan -out=tfplan
# Review the plan — should show ~30 resources to create
terraform apply tfplan
```

Note the outputs:
```
ecr_url                 = "<account>.dkr.ecr.ap-south-1.amazonaws.com/review-master/app"
elastic_ip              = "<ip>"
ec2_eip_allocation_id   = "eipalloc-xxxx"
rds_endpoint            = "review-master-prod.xxxx.ap-south-1.rds.amazonaws.com"
github_oidc_role_arn    = "arn:aws:iam::<account>:role/review-master-github-actions"
static_bucket_name      = "review-master-static-prod"
```

**Note:** No nameserver step needed — Route 53 hosted zone already exists with DNS migrated. Terraform will only add/update the A records for apex and www.

- [x] **Step 3: Seed SSM params and update real values**

```bash
# Seed placeholders (if not already done by terraform apply)
AWS_PROFILE=your-profile bash deployment/ssm/seed-params.sh

# Update real values — do this for each CHANGE_ME param:
aws ssm put-parameter \
  --region ap-south-1 \
  --name "/review-master/prod/DJANGO_SECRET_KEY" \
  --value "$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")" \
  --type SecureString --overwrite

# Update DATABASE_URL with the real RDS endpoint from Terraform output
aws ssm put-parameter \
  --region ap-south-1 \
  --name "/review-master/prod/DATABASE_URL" \
  --value "postgres://app:<raw_password>@<rds_endpoint>:5432/reviewmaster" \
  --type SecureString --overwrite

# Get the raw DB password (Terraform stored it here)
aws ssm get-parameter \
  --region ap-south-1 \
  --name "/review-master/prod/DB_PASSWORD_RAW" \
  --with-decryption \
  --query "Parameter.Value" --output text

# Repeat for GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET,
# FERNET_SALT_KEY, OPENAI_API_KEY, LANGSMITH_API_KEY, SENTRY_DSN,
# RESEND_API_KEY, CADDY_DOMAIN, CADDY_ACME_EMAIL, DEFAULT_FROM_EMAIL,
# DEFAULT_REPLY_TO, DJANGO_ALLOWED_HOSTS, SITE_URL, GOOGLE_OAUTH_REDIRECT_URI
```

- [x] **Step 5: Launch EC2 instance**

Via AWS console (EC2 → Launch Instance):
- Name: `review-master-prod`
- AMI: Amazon Linux 2023 (64-bit ARM)
- Instance type: `t4g.medium`
- Key pair: create one and download (for emergency SSH)
- Network: select the `review-master-vpc`, public subnet 1
- Security group: select `review-master-ec2`
- IAM instance profile: `review-master-ec2`
- Storage: 30 GB gp3
- User data: paste contents of `deployment/scripts/user-data.sh`
- Tag: `Project = review-master` (required for SSM Run Command targeting)

- [x] **Step 6: Associate Elastic IP to EC2**

```bash
aws ec2 associate-address \
  --region ap-south-1 \
  --instance-id <your-instance-id> \
  --allocation-id <ec2_eip_allocation_id from terraform output>
```

- [x] **Step 7: Upload scripts to EC2**

```bash
# Copy the app files to EC2 (one-time setup)
scp -r deployment/scripts deployment/compose deployment/caddy \
  ec2-user@<elastic-ip>:/opt/review-master/

# SSH in and move files into place
ssh ec2-user@<elastic-ip>
sudo mkdir -p /opt/review-master/scripts /opt/review-master/caddy
sudo cp /opt/review-master/scripts/* /opt/review-master/scripts/
sudo cp /opt/review-master/caddy/Caddyfile /opt/review-master/caddy/
sudo cp /opt/review-master/compose/docker-compose.prod.yml /opt/review-master/
sudo chmod +x /opt/review-master/scripts/*.sh
```

- [x] **Step 8: Add GitHub secret and trigger first deploy**

```bash
# Get role ARN
terraform -chdir=deployment/terraform output github_oidc_role_arn
```

Add GitHub secret `AWS_DEPLOY_ROLE_ARN`. Push to main:

```bash
git push origin main
```

Watch the GitHub Actions run. First deploy will:
1. Build arm64 image (~3-5 min due to QEMU)
2. Push to ECR
3. SSM Run Command: load secrets → migrate → collectstatic → compose up

- [x] **Step 9: Enable CloudWatch EC2 alarms**

After EC2 is running, get the instance ID and re-apply Terraform:

```bash
INSTANCE_ID=$(aws ec2 describe-instances \
  --region ap-south-1 \
  --filters "Name=tag:Project,Values=review-master" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

echo "ec2_instance_id = \"$INSTANCE_ID\"" >> deployment/terraform/terraform.tfvars
cd deployment/terraform && terraform apply -auto-approve
```

- [x] **Step 10: Verify smoke tests**

```bash
# Healthcheck
curl -fsSL https://yourdomain.com/healthz/

# Ready check (DB + Redis)
curl -fsSL https://yourdomain.com/readyz/

# Confirm TLS cert is valid (Let's Encrypt)
curl -vsSL https://yourdomain.com/healthz/ 2>&1 | grep "SSL certificate verify ok"
```

Expected: all return 200, cert verified.

- [x] **Step 11: Confirm RDS snapshot exists**

```bash
aws rds describe-db-snapshots \
  --region ap-south-1 \
  --db-instance-identifier review-master-prod \
  --query "DBSnapshots[*].[DBSnapshotIdentifier,Status,SnapshotCreateTime]" \
  --output table
```

---

## Self-Review Checklist

- [x] Route 53 hosted zone pre-exists — `data` source used, no create/destroy risk
- [x] All SSM params from `.env.example` are covered in ssm.tf and seed-params.sh
- [x] Caddy auto-renews Let's Encrypt — no cron needed
- [x] Flower bound to 127.0.0.1 only — never exposed publicly
- [x] Beat has exactly one instance — prod compose has one `beat` service
- [x] EC2 IAM role has S3 write for collectstatic (added to iam.tf)
- [x] `terraform.tfvars` and `.terraform/` added to .gitignore in Task 10
- [x] RDS has `deletion_protection = true`
- [x] GitHub OIDC role scoped to `ref:refs/heads/main` only
- [x] SSM params use `lifecycle { ignore_changes = [value] }` — manual updates are safe
- [x] `ECR_IMAGE` injected into env file in deploy.sh before compose starts
- [x] CloudWatch alarms gated on `ec2_instance_id != ""` — no error on first apply
