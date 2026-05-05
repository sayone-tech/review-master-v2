# AWS Deployment Design — review-master

**Date:** 2026-05-05
**Region:** ap-south-1 (Mumbai)
**Status:** Approved — ready for implementation planning

---

## 1. Goals

- First production deployment for one organisation (~57 stores, 50–60 users)
- Lowest credible monthly cost (~$47–50/mo on-demand in ap-south-1)
- Fully reproducible infra via Terraform
- Clear upgrade path — no rewrites required to scale

---

## 2. Architecture Summary

Single EC2 box (t4g.medium, Graviton) running 6 containers via Docker Compose. RDS PostgreSQL managed separately. All secrets in SSM Parameter Store. GitHub Actions deploys via OIDC + SSM Run Command (no SSH keys in CI).

```
Internet → Route 53 (A record) → EC2 Elastic IP
                                  └── Caddy (80/443, auto-TLS)
                                        └── web:8000 (Daphne/ASGI)
                                              ├── worker (Celery)
                                              ├── beat (Celery Beat)
                                              ├── flower (127.0.0.1:5555 only)
                                              └── redis (internal only)
                                  └── RDS PostgreSQL 16 (private subnet)
```

---

## 3. Infrastructure (Terraform-managed)

### 3.1 What Terraform owns

| Resource | Spec |
|---|---|
| VPC | 1 VPC, 2 public subnets (EC2), 2 private subnets (RDS subnet group across 2 AZs) |
| Security Group — EC2 | 80/443 from `0.0.0.0/0`; 22 from operator IP only |
| Security Group — RDS | 5432 from EC2 SG only |
| RDS PostgreSQL 16 | db.t4g.micro, Single-AZ, 20 GB gp3, autoscale cap 100 GB, 7-day PITR |
| ECR | Private repo: `review-master/app` |
| IAM — EC2 instance profile | ECR pull, SSM `GetParameter*`, KMS Decrypt, CloudWatch logs write |
| IAM — GitHub OIDC role | ECR push, SSM `SendCommand` on this EC2 only |
| SSM Parameter Store | All SecureString params under `/review-master/prod/` with placeholder values |
| S3 | Static files bucket, public-read for `/static/*` |
| Route 53 | Hosted zone + A record → Elastic IP |
| CloudWatch | Log groups `/review-master/prod`, 4 alarms (CPU, memory, disk, RDS memory) |

### 3.2 What is NOT in Terraform

EC2 instance — launched once via AWS console or CLI, bootstrapped via user-data. All subsequent updates go through GitHub Actions → SSM Run Command.

### 3.3 Folder layout

```
deployment/terraform/
├── main.tf             # provider (aws, ap-south-1), backend config
├── variables.tf        # domain, db_username, operator_ip, environment
├── outputs.tf          # EC2 IP, RDS endpoint, ECR URL, Route 53 NS records
├── vpc.tf
├── security_groups.tf
├── rds.tf
├── ecr.tf
├── iam.tf              # EC2 instance profile + GitHub OIDC role
├── ssm.tf              # all SecureString params with placeholder values
├── s3.tf               # static files bucket
└── route53.tf          # hosted zone + A record
```

---

## 4. EC2 Bootstrap

### 4.1 Instance config

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023 (64-bit ARM / Graviton) |
| Instance type | t4g.medium (2 vCPU, 4 GB RAM) |
| Storage | 30 GB EBS gp3 root |
| IAM instance profile | Terraform-created (ECR pull, SSM read, CloudWatch write) |
| Elastic IP | Attached after launch; never changes |

### 4.2 User-data (runs once on first boot)

1. Install Docker + Compose plugin (aarch64 binary)
2. Enable Docker service
3. ECR login via instance profile (no keys)
4. Run `load-secrets.sh` → writes `/etc/review-master.env`
5. `docker compose -f /opt/review-master/docker-compose.prod.yml up -d`

### 4.3 Secrets loading — `load-secrets.sh`

Reads all SSM parameters under `/review-master/prod/` using `aws ssm get-parameters-by-path --with-decryption` and writes them as `KEY=VALUE` lines to `/etc/review-master.env`. This file is loaded by prod compose via `env_file`.

Script runs:
- On first boot (user-data)
- At the start of every deploy (so secret rotation takes effect immediately)

---

## 5. Production Docker Compose

File: `deployment/compose/docker-compose.prod.yml`

### 5.1 Containers

| Container | Image | Command | Ports |
|---|---|---|---|
| `caddy` | `caddy:2-alpine` | default | 80, 443 (host) |
| `web` | ECR image | `daphne -b 0.0.0.0 -p 8000 config.asgi:application` | internal only |
| `worker` | ECR image | `celery -A config worker -Q google-sync,ai-enrichment,default --concurrency=2` | none |
| `beat` | ECR image | `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler` | none |
| `flower` | ECR image | `celery -A config flower --port=5555 --address=127.0.0.1` | 127.0.0.1:5555 only |
| `redis` | `redis:7-alpine` | default | internal only |

### 5.2 Key prod settings (applies to web/worker/beat)

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `env_file: /etc/review-master.env` (written by load-secrets.sh)
- `restart: unless-stopped`
- No source code volume mounts — image is self-contained
- `awslogs` log driver → CloudWatch log group `/review-master/prod`

### 5.3 Caddy — TLS

Caddyfile (`deployment/caddy/Caddyfile`):
```
yourdomain.com {
    reverse_proxy web:8000
}
```

Caddy fetches a Let's Encrypt certificate on first request and **auto-renews ~30 days before the 90-day expiry** — no renewal scripts or cron jobs needed. Certs stored in a named Docker volume that persists across restarts. Caddy logs renewal events to stdout → CloudWatch.

**Prerequisite:** Domain A record must point to the EC2 Elastic IP before first boot so Let's Encrypt can validate domain ownership over HTTP.

---

## 6. SSM Parameter Store — Full Parameter List

All parameters: SecureString, default KMS key, path prefix `/review-master/prod/`.

| SSM Path | Seeded default | How to get real value |
|---|---|---|
| `/review-master/prod/django/secret_key` | `CHANGE_ME_generate_50_chars` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `/review-master/prod/django/allowed_hosts` | `yourdomain.com,www.yourdomain.com` | Update with real domain |
| `/review-master/prod/django/site_url` | `https://yourdomain.com` | Update with real domain |
| `/review-master/prod/db/url` | `postgres://app:CHANGE_ME@<rds-endpoint>:5432/reviewmaster` | Terraform outputs RDS endpoint |
| `/review-master/prod/redis/url` | `redis://redis:6379` | Internal Docker network — no change needed |
| `/review-master/prod/google/oauth_client_id` | `CHANGE_ME` | Google Cloud Console |
| `/review-master/prod/google/oauth_client_secret` | `CHANGE_ME` | Google Cloud Console |
| `/review-master/prod/google/oauth_redirect_uri` | `https://yourdomain.com/oauth/google/callback/` | Update with real domain |
| `/review-master/prod/fernet/salt_key` | `CHANGE_ME_generate_fernet_key` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `/review-master/prod/openai/api_key` | `CHANGE_ME` | OpenAI dashboard |
| `/review-master/prod/openai/model` | `gpt-4o-mini-2024-07-18` | Ready to use |
| `/review-master/prod/langsmith/api_key` | `CHANGE_ME` | LangSmith dashboard |
| `/review-master/prod/langsmith/project` | `review-platform-production` | Ready to use |
| `/review-master/prod/langsmith/endpoint` | `https://api.smith.langchain.com` | Ready to use |
| `/review-master/prod/sentry/dsn` | `CHANGE_ME` | Sentry project settings |
| `/review-master/prod/email/provider` | `resend` | Switch to `ses` when SES approved |
| `/review-master/prod/email/resend_api_key` | `CHANGE_ME` | Resend dashboard |
| `/review-master/prod/email/default_from` | `noreply@yourdomain.com` | Update with real domain |
| `/review-master/prod/email/default_reply_to` | `support@yourdomain.com` | Update with real domain |
| `/review-master/prod/aws/ses_region` | `ap-south-1` | For when SES is approved later |

---

## 7. GitHub Actions — Deploy Workflow

File: `.github/workflows/deploy.yml` (new, separate from existing `ci.yml`)

### 7.1 Trigger

Push to `main` branch (deploy runs after CI passes — use `needs: ci` or separate workflow with `workflow_run`).

### 7.2 Steps

1. Checkout code
2. Configure AWS credentials via OIDC (assume GitHub IAM role — no long-lived keys)
3. Login to ECR
4. Build Docker image for `linux/arm64` (Graviton) using `docker buildx` + QEMU emulation
5. Push to ECR: `review-master/app:latest` + `review-master/app:<sha>`
6. Send SSM Run Command to EC2 — runs `deployment/scripts/deploy.sh`
7. Poll SSM command status until complete (timeout 10 min)
8. Smoke test: `curl https://yourdomain.com/healthz/` expects 200

### 7.3 deploy.sh (runs on EC2 via SSM Run Command)

```
1. aws ecr get-login-password | docker login (instance profile, no keys)
2. /opt/review-master/scripts/load-secrets.sh  (refresh SSM → /etc/review-master.env)
3. docker compose -f docker-compose.prod.yml pull
4. docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
5. docker compose -f docker-compose.prod.yml up -d
```

### 7.4 GitHub secrets required

**None.** AWS access is via OIDC. No SSH keys, no AWS access keys stored in GitHub.

---

## 8. Static Files — S3

- Django setting: `DJANGO_STORAGES` with S3 backend (already in `CLAUDE.md §2.7`)
- `collectstatic` runs during Docker image build
- S3 bucket created by Terraform, public-read policy for `/static/*`
- No CloudFront initially — add when static asset latency becomes an issue

---

## 9. DNS — GoDaddy → Route 53 Delegation

1. Terraform creates Route 53 hosted zone for `yourdomain.com`
2. Terraform outputs the 4 NS records for the zone
3. You log into GoDaddy and replace the default nameservers with the Route 53 NS records
4. Terraform creates an A record: `yourdomain.com` → EC2 Elastic IP
5. DNS propagation: 15 min – 48 hours (usually <1 hour)

---

## 10. Observability

### 10.1 CloudWatch Logs

Docker `awslogs` log driver on web, worker, beat containers:
- Log group: `/review-master/prod`
- Stream prefix: container name (`web`, `worker`, `beat`)
- Region: `ap-south-1`

### 10.2 CloudWatch Alarms (all created by Terraform)

| Alarm | Threshold | Notification |
|---|---|---|
| EC2 CPUUtilization | > 70% for 10 min | SNS → email |
| EC2 mem_used_percent | > 85% | SNS → email |
| EC2 disk_used_percent | > 80% | SNS → email |
| RDS FreeableMemory | < 100 MB | SNS → email |

### 10.3 Sentry

DSN seeded in SSM. Wired via `SENTRY_DSN` env var. Captures errors from web + Celery worker. Free tier (5k events/mo) sufficient at this scale.

---

## 11. Folder Layout (final)

```
deployment/
├── README.md                          # existing architecture decisions doc
├── caddy/
│   └── Caddyfile                      # yourdomain.com { reverse_proxy web:8000 }
├── compose/
│   ├── docker-compose.prod.yml        # 6 containers (no db/mailhog/vite)
│   └── .env.prod.example              # documents expected env vars (no secrets)
├── github-actions/
│   └── deploy.yml                     # copied to .github/workflows/deploy.yml
├── scripts/
│   ├── user-data.sh                   # EC2 first-boot bootstrap
│   ├── load-secrets.sh                # SSM → /etc/review-master.env
│   └── deploy.sh                      # SSM Run Command deploy script
├── ssm/
│   └── seed-params.sh                 # creates all SSM params with placeholder values
└── terraform/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    ├── vpc.tf
    ├── security_groups.tf
    ├── rds.tf
    ├── ecr.tf
    ├── iam.tf
    ├── ssm.tf
    ├── s3.tf
    └── route53.tf
```

---

## 12. Prerequisites (collected during execution)

| Item | Who provides |
|---|---|
| AWS account ID | You |
| Domain name (exact) | You |
| Operator IP (for SSH SG rule) | You |
| GitHub org/repo name (for OIDC trust policy) | You |
| Alert email address (CloudWatch SNS) | You |
| RDS master username | You (or default: `app`) |

---

## 13. Monthly Cost Estimate (ap-south-1, on-demand)

| Item | Monthly |
|---|---|
| EC2 t4g.medium | ~$27 |
| EBS gp3 30 GB | ~$2.50 |
| EBS daily snapshots | ~$1.50 |
| RDS db.t4g.micro | ~$13 |
| RDS gp3 20 GB | ~$2.50 |
| Route 53 | ~$0.90 |
| SSM Parameter Store | $0.00 |
| ECR ~1 GB | ~$0.05 |
| S3 static files | ~$0.50 |
| CloudWatch logs | ~$0.50 |
| **Total on-demand** | **~$48/mo** |

---

## 14. Upgrade Triggers (from spec)

| Signal | Next step |
|---|---|
| Second paying customer | RDS Multi-AZ (+$13/mo) |
| EC2 CPU > 70% sustained | t4g.large (+$27/mo) |
| Daily jobs > 1,000 stores | Dedicated worker EC2 or ECS Fargate |
| Need zero-downtime deploys | ALB + second EC2 (+$16/mo + EC2) |
| Compliance requirement | Migrate secrets to Secrets Manager (+$3/mo) |
