# AWS Monthly Cost Estimate

**Region:** ap-south-1 (Mumbai)
**Basis:** 30 days / 720 hours
**Prices sourced:** AWS Pricing API, 2026-05-07

---

## Compute

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| EC2 instance | t4g.medium, Linux, On-Demand | $0.0224 / hr | $16.13 |
| EBS volume | gp3, 30 GB (root) | $0.0912 / GB-month | $2.74 |
| Elastic IP | Public IPv4, in-use | $0.005 / hr | $3.60 |
| **Subtotal** | | | **$22.47** |

> Note: Elastic IP is billed regardless of association status since AWS's Feb 2024 IPv4 pricing change.

---

## Database

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| RDS instance | db.t4g.micro, PostgreSQL 16, Single-AZ, On-Demand | $0.021 / hr | $15.12 |
| RDS storage | gp3, 20 GB (auto-scales to 100 GB max) | $0.131 / GB-month | $2.62 |
| **Subtotal** | | | **$17.74** |

> Multi-AZ doubles the instance and storage cost (~+$18/mo). Recommended when a second paying customer joins.

---

## Storage

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| S3 Standard | ~5 GB static assets (CSS, JS, images) | $0.025 / GB-month | $0.13 |
| S3 GET requests | ~500,000 requests/month | $0.0004 / 1,000 reqs | $0.20 |
| ECR | ~5 GB container images (lifecycle: keep last 10) | $0.10 / GB-month | $0.50 |
| **Subtotal** | | | **$0.83** |

---

## Networking & DNS

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| Route 53 hosted zone | reviewbee.in | $0.50 / zone | $0.50 |
| Route 53 DNS queries | ~1 million/month | $0.40 / million | $0.40 |
| Data transfer OUT | ~10 GB/month to internet | $0.1093 / GB | $1.09 |
| **Subtotal** | | | **$1.99** |

---

## Security & Config

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| Secrets Manager | 1 secret (`review-master/prod`) | $0.40 / secret | $0.40 |
| **Subtotal** | | | **$0.40** |

---

## Monitoring (CloudWatch)

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| CloudWatch Alarms | 7 alarms (EC2 CPU/disk/memory/swap, RDS CPU/memory/storage) | $0.10 / alarm | $0.70* |
| CloudWatch Logs ingestion | ~2 GB/month | $0.67 / GB | $1.34* |
| CloudWatch Logs storage | ~2 GB (30-day retention) | $0.03 / GB-month | $0.06* |
| CloudWatch Custom Metrics | 6 metrics — CWAgent (mem/swap/disk) + Celery (3 queues) | $0.30 / metric | $1.80* |
| **Subtotal** | | | **$3.90** |

> *CloudWatch perpetual free tier: 10 alarms, 5 GB ingestion + 5 GB storage, 10 custom metrics. Current usage falls within all three free tiers, so **actual billed ≈ $0.00**. Each new alarm or custom metric beyond those caps adds $0.10 / $0.30 per month respectively.

---

## Audit / Detection (Tier-0, added 2026-05-24)

| Resource | Spec | Rate | Monthly |
|---|---|---|---|
| CloudTrail | 1 management-events trail, ap-south-1 only | First trail per region free | $0.00 |
| VPC Flow Logs | Parquet, 10-min aggregation → S3 | ~$0.50 / GB ingested | ~$0.50 |
| S3 logs bucket (`review-master-logs-prod`) | ~5 GB (CloudTrail + Flow Logs, 90-day retention) | $0.025 / GB-month | $0.13 |
| Cost Anomaly Detection | Adopted `Default-Services-Monitor` + email subscription | Free | $0.00 |
| **Subtotal** | | | **$0.63** |

---

## Summary

| Category | Monthly (USD) |
|---|---|
| Compute (EC2 + EBS + EIP) | $22.47 |
| Database (RDS instance + storage) | $17.74 |
| Storage (S3 + ECR) | $0.83 |
| Networking & DNS | $1.99 |
| Security (Secrets Manager) | $0.40 |
| Monitoring (CloudWatch — alarms/logs/metrics all within free tier) | $0.00 |
| Audit / Detection (CloudTrail + Flow Logs + logs bucket + Cost Anomaly) | $0.63 |
| **Total** | **~$44.06** |

---

## Notes

- **AWS Budget alert** is set at $70/month (alert at 80% forecast, 100% actual).
- **RDS backup storage:** 7-day retention window. Backup storage up to the size of provisioned storage (20 GB) is free.
- **SSM Parameter Store:** 1 parameter (`DB_PASSWORD_RAW`) — standard tier is free.
- **ECR image scanning** (scan on push) — free.
- **VPC, subnets, IGW, route tables, security groups** — no charge.
- **GitHub Actions OIDC role** — IAM is free.
- **Budgets:** first 2 budgets free; this project has 1.
- **CloudWatch agent is installed** as of 2026-05-24 via SSM Association (see `stacks/prod-app/cloudwatch_agent.tf` in the terraform repo). Ships `mem_used_percent`, `swap_used_percent`, `disk_used_percent` to the `CWAgent` namespace. These count against the 10-custom-metric free tier together with the 3 Celery queue depth metrics (6/10 used).
- **Tier-0 hardening cost delta:** +$0.63/mo (Flow Logs ingest ~$0.50 + logs bucket storage ~$0.13). Everything else stays in free tier.
- **Headroom before custom metrics start billing:** 4 more metrics. Per-org OpenAI cost (1 metric per org) would consume them as you add customers.

---

## Cost Reduction Options

| Option | Saving | Trade-off |
|---|---|---|
| EC2 1-year Reserved Instance (t4g.medium) | ~$6/mo | Upfront commitment |
| RDS 1-year Reserved Instance (db.t4g.micro) | ~$5/mo | Upfront commitment |
| Move to RDS free-tier eligible instance (first 12 months) | up to $15/mo | Only valid for new accounts |
| Reduce EBS to 20 GB (if disk stays <50% used) | ~$0.91/mo | Needs monitoring |
