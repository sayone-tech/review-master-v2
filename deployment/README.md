# Deployment

AWS deployment plan for the review-master platform. **Status: planning. Implementation deferred until after GSD Phase 13.**

This document captures the decisions made so we can resume without re-deciding. Detailed implementation files (Caddyfile, docker-compose.prod.yml, GitHub Actions workflow, IaC, etc.) will land in subfolders below as they're written.

---

## 1. Goals

- First production deployment for one organisation (~57 stores, 50–60 users).
- Lowest credible monthly cost while remaining a "real" deployment (not a single-container hack).
- Path to scale: known upgrade triggers and known next architecture, no rewrites required.

---

## 2. Decisions

### 2.1 Compute — single EC2 box running Docker Compose

| | Decision |
|---|---|
| Instance type | **t4g.medium** (2 vCPU, 4 GB, Graviton) |
| OS | Amazon Linux 2023 (or Ubuntu 22.04 LTS) |
| Disk | 30 GB EBS gp3 root volume |
| Region | us-east-1 (cheapest) — final region TBD |
| Backups | Daily EBS snapshot |

The box runs **all six containers** via Docker Compose:

| Container | Purpose |
|---|---|
| `caddy` | Reverse proxy + TLS termination (Let's Encrypt, auto-renew) |
| `web` | Daphne running `config.asgi:application` (HTTP + WebSockets) |
| `worker` | Celery worker — queues `google-sync,ai-enrichment,default`, `--concurrency=2` |
| `beat` | Celery Beat (scheduled tasks). **Exactly one instance — non-negotiable.** |
| `flower` | Celery monitoring UI, bound to `127.0.0.1:5555`, **never published**. SSH-tunnel access only. |
| `redis` | Redis 7 (cache, throttling, sessions, Celery broker/backend, Channels layer) |

Why a single box: the workload is genuinely tiny (60 stores/day, ~5–10 reviews each). ECS Fargate + ALB + ElastiCache would multiply cost ~3× for no functional gain at this scale.

### 2.2 Database — Amazon RDS PostgreSQL

| | Decision |
|---|---|
| Engine | PostgreSQL 16 |
| Instance | db.t4g.micro (Single-AZ, 1 GB RAM) |
| Storage | 20 GB gp3, autoscaling cap **100 GB** |
| Backups | 7-day retention, point-in-time recovery enabled |
| Subnet | RDS subnet group across 2 AZs; **instance launched in same AZ as EC2** to avoid cross-AZ data transfer charges |
| Multi-AZ | **Off** for now (doubles cost). Turn on before second paying customer. |

Why RDS over Postgres-in-Docker: managed backups, point-in-time recovery, and easy upgrade path are worth $14/mo. We never want to lose a customer's data because we forgot to run `pg_dump`.

### 2.3 Networking & TLS

- **Reverse proxy: Caddy** (Let's Encrypt auto-TLS, HTTP/2, gzip, WebSocket out of the box). Decision recorded over nginx because it eliminates certbot + renewal cron — fewer moving parts at this scale.
- **No ALB.** TLS terminates at Caddy on the EC2 box.
- **No ACM** (ACM certs cannot install on EC2 directly; only attach to ALB/CloudFront/API Gateway).
- **Route 53** for DNS. One hosted zone, A record → EC2 Elastic IP.
- **Security groups:**
  - EC2: 80/443 from `0.0.0.0/0`; 22 from operator IP only.
  - RDS: 5432 from EC2 SG only.

### 2.4 Secrets — SSM Parameter Store (SecureString)

Chosen over AWS Secrets Manager: same encryption-at-rest behaviour for static secrets, $0/mo vs ~$3/mo, and we don't need automatic rotation yet.

Parameters (all SecureString, default KMS key):

| Name | Source |
|---|---|
| `/review-master/prod/django/secret_key` | generated once |
| `/review-master/prod/db/password` | RDS master password |
| `/review-master/prod/openai/api_key` | OpenAI dashboard |
| `/review-master/prod/google/oauth_client_id` | Google Cloud Console |
| `/review-master/prod/google/oauth_client_secret` | Google Cloud Console |
| `/review-master/prod/langsmith/api_key` | LangSmith dashboard |

EC2 instance profile gets `ssm:GetParameter*` + `kms:Decrypt` on those paths only.

### 2.5 Container registry — ECR (private)

- One repo: `review-master/app`.
- Single image, three Compose `command:` entries select web/worker/beat behaviour.
- ECR storage: ~1 GB image → effectively free (free tier covers first 500 MB/12 mo, then ~$0.05/mo).
- Pulls from EC2 in same region: free.

### 2.6 CI/CD — GitHub Actions → ECR → EC2

1. **Auth:** GitHub OIDC → AWS IAM role (no long-lived access keys in GitHub).
2. **Build:** `docker build` on Actions runner.
3. **Push:** `aws-actions/amazon-ecr-login@v2` → `docker push`.
4. **Deploy:** SSH (or AWS Systems Manager Run Command) into EC2 → `docker compose pull && docker compose up -d`.
5. **Migrations:** run as a one-off `docker compose run --rm web python manage.py migrate` step before bringing services up.

GitHub Actions cost: $0 (within 2,000 free minutes/month for private repos).

### 2.7 Static & media files — S3

- `django-storages` with S3 backend.
- `collectstatic` runs in the Docker build, then static files are uploaded to S3 in a deploy step.
- S3 bucket public-read for static assets, presigned URLs for any media if needed.
- No CloudFront in front of S3 yet — added when traffic justifies it.

### 2.8 Email — deferred

SES is not yet approved. Until it is, either:

- Use a free third-party transactional sender (Resend free tier, Brevo free tier) via SMTP, OR
- Disable email-sending features in production until SES production access is granted.

When SES is approved, integration is already specified in `CLAUDE.md` §15.

### 2.9 Observability — CloudWatch + Sentry

- **CloudWatch logs:** Docker `awslogs` log driver ships container stdout/stderr.
- **CloudWatch metrics + agent:** track CPU, memory, disk on EC2; RDS metrics are automatic.
- **Sentry:** errors from web + worker. Free tier (5k events/mo) is sufficient.
- **Alarms** (set up at deploy time):
  - RDS `FreeableMemory` < 100 MB sustained → upgrade DB
  - EC2 `CPUUtilization` > 70% sustained
  - EC2 `mem_used_percent` > 85%
  - EC2 `disk_used_percent` > 80%

---

## 3. Monthly cost estimate (us-east-1, on-demand)

| Item | Spec | Monthly |
|---|---|---|
| EC2 t4g.medium | 2 vCPU, 4 GB | $24.53 |
| EBS gp3 root | 30 GB | $2.40 |
| EBS daily snapshots | ~30 GB stored | $1.50 |
| RDS db.t4g.micro PostgreSQL | Single-AZ | $11.68 |
| RDS gp3 storage | 20 GB | $2.30 |
| Route 53 | 1 hosted zone + queries | $0.90 |
| SSM Parameter Store | SecureString, default KMS | $0.00 |
| ECR | ~1 GB image (within free tier yr 1) | ~$0.05 |
| GitHub Actions | OIDC, 2k free min/mo | $0.00 |
| S3 (static files) | <1 GB | ~$0.50 |
| CloudWatch logs | minimal | ~$0.00 |
| Data transfer out | <10 GB/mo (free tier) | $0.00 |
| **Total — on-demand** | | **~$43.86 / month** |
| **Total — with 1-yr Compute Savings Plan + RDS RI** | | **~$33 / month** |

**Outside this budget:** OpenAI (~$0.50–$1.50/mo at this scale), domain (~$1/mo), Sentry (free).

---

## 4. Upgrade triggers — when to leave this architecture

| Signal | Next step | Cost delta |
|---|---|---|
| Second paying customer | RDS Multi-AZ | +$12/mo |
| Sustained EC2 CPU > 70% or mem > 85% | EC2 → t4g.large | +$24/mo |
| Daily Celery jobs > 1,000 stores | Move worker to dedicated EC2 OR ECS Fargate | +$10–30/mo |
| Need zero-downtime deploys | Add ALB + second EC2 | +$16/mo + EC2 |
| Compliance / audit requirement | Move secrets to Secrets Manager (rotation) | +$3/mo |

---

## 5. Pre-deploy checklist (when implementation resumes)

- [ ] AWS account ready, billing alarms configured
- [ ] Domain registered → Route 53 hosted zone
- [ ] VPC + security groups created (default VPC is fine)
- [ ] RDS instance launched, master password in SSM
- [ ] All secrets seeded in SSM Parameter Store
- [ ] ECR repo created
- [ ] GitHub OIDC IAM role created with ECR push + EC2 deploy permissions
- [ ] EC2 instance launched with IAM instance profile + Elastic IP
- [ ] EC2 user-data: install Docker + Compose plugin, ECR login, pull image, `docker compose up -d`
- [ ] Caddy fetches Let's Encrypt cert on first request
- [ ] Smoke test: `/healthz/` returns 200, `/readyz/` returns 200 (DB + Redis OK)
- [ ] First migration run as one-off task
- [ ] CloudWatch alarms armed
- [ ] Sentry project + DSN wired up
- [ ] Backup verification: confirm RDS snapshot exists; confirm restore procedure works on a throwaway

---

## 6. Folder layout (to be filled in)

```
deployment/
├── README.md              # this file
├── caddy/                 # Caddyfile + any TLS config
├── compose/               # docker-compose.prod.yml + .env.example
├── github-actions/        # build-and-deploy workflow YAML
├── scripts/               # ec2 user-data, deploy.sh, migration helpers
├── ssm/                   # parameter naming convention + seed script (no secret values)
└── terraform/             # OPTIONAL — IaC for VPC/RDS/EC2/IAM/ECR. May skip and use console initially.
```

---

## 7. Open questions to resolve before implementation

1. **Region:** us-east-1 (cheapest) vs region nearer customers' Google Business Profiles. Latency to Google API not critical.
2. **Terraform vs console-first:** Terraform is the right answer long-term. Console first may be faster for the first deploy. **Recommendation: Terraform from day one for everything except the EC2 instance itself**, so RDS/IAM/ECR/SSM/Route53 are reproducible.
3. **Domain registrar:** Route 53 directly (~$12/yr `.com`) vs migrate from existing registrar.
4. **Email provider during SES sandbox:** Resend, Brevo, or hold off email features.
5. **Static asset CDN:** ship without CloudFront initially, revisit if static asset latency hurts UX.

---

## 8. Status

- **Architecture decisions:** locked in (this document).
- **Implementation files:** not yet written.
- **Resume point:** after GSD Phase 13 (`13-action-items-and-notifications`) is complete.
