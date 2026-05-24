# SRE Runbook — Review Master

Production infrastructure: single EC2 instance (`t4g.medium`, Graviton ARM64) in `ap-south-1`.
All services run as Docker containers managed by Docker Compose.

## Quick Reference

| Item | Value |
|------|-------|
| EC2 instance ID | `i-0782bee2ff9885151` |
| Elastic IP | `13.203.163.202` |
| Region | `ap-south-1` (Mumbai) |
| App URL | `https://app.reviewbee.in` |
| AWS account | `270587882826` |
| AWS profile | `review-master` |

## Runbooks

| Topic | Guide |
|-------|-------|
| Access the server | [access.md](access.md) |
| View logs | [logs.md](logs.md) |
| Environment variables & secrets | [secrets.md](secrets.md) |
| Deploy & rollback | [deploy.md](deploy.md) |
| Database | [database.md](database.md) |
| Monitoring & alerts | [monitoring.md](monitoring.md) |
| Common incidents | [incidents.md](incidents.md) |
| Improvements backlog & Tier-1 triggers | [improvements.md](improvements.md) |

## Standard EC2 Session Setup

All `docker compose` commands must run as **root** with `ECR_IMAGE` exported — Docker Compose needs it to parse the compose file. Run this at the start of every EC2 session before using any command in these runbooks:

```bash
# 1. Connect
aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1

# 2. Switch to root and export ECR_IMAGE
sudo -i
export ECR_IMAGE="270587882826.dkr.ecr.ap-south-1.amazonaws.com/review-master/app:latest"
```

All commands in the runbooks below assume you have done this setup.

## Architecture at a Glance

```
Internet → Caddy (TLS termination) → Django/Daphne (ASGI)
                                    → Celery Worker (google-sync, ai-enrichment, default queues)
                                    → Celery Beat (scheduled tasks)
                                    → Flower (task monitor — localhost only)
                                    → Redis (broker + cache + channels)
RDS PostgreSQL (private subnet, accessible from EC2 SG only)
ECR → Docker images pulled on deploy
S3  → static files (CSS/JS) + collectstatic target
Secrets Manager → /etc/review-master.env on each deploy
CloudWatch Logs → all container stdout/stderr (30-day retention)
```
