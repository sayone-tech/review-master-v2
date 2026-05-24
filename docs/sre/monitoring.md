# Monitoring & Alerts

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `https://app.reviewbee.in/healthz/` | Lightweight liveness check — returns `{"status": "ok"}` |
| `https://app.reviewbee.in/readyz/` | Readiness check — verifies DB + Redis connectivity |

```bash
curl -fsSL https://app.reviewbee.in/healthz/
curl -fsSL https://app.reviewbee.in/readyz/
```

## CloudWatch Alarms

Seven alarms are configured (see `stacks/prod-app/cloudwatch.tf` in the [terraform repo](../../../review-master-terraform/stacks/prod-app/)). All notify the SNS topic `review-master-alerts`, which emails `renjith@sayonetech.com`.

| Alarm | Threshold | What it tells you |
|---|---|---|
| `review-master-ec2-cpu-high` | EC2 CPU > 70% sustained 10 min | Worker is busy — consider t4g.large upgrade |
| `review-master-ec2-memory-high` | `mem_used_percent` > 85% sustained 10 min | Real RAM pressure — consider t4g.large upgrade |
| `review-master-ec2-swap-high` | `swap_used_percent` > 50% sustained 10 min | Critical: hitting swap means OOM is near |
| `review-master-ec2-disk-high` | `disk_used_percent` > 80% | Grow gp3 volume (no downtime); see [database.md](database.md) for similar RDS guidance |
| `review-master-rds-cpu-high` | RDS CPU > 80% sustained 10 min | Slow queries or undersized DB instance |
| `review-master-rds-memory-low` | RDS FreeableMemory < 100 MB sustained 10 min | Upgrade db.t4g.micro → db.t4g.small |
| `review-master-rds-storage-low` | RDS FreeStorageSpace < 5 GB | Autoscaling triggers up to 100 GB cap |

> The memory, swap, and disk alarms depend on the **CloudWatch Agent** installed on the EC2 (see "CloudWatch Agent" section below). Installation is automated via SSM Association in terraform.

View alarm states:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix review-master \
  --region ap-south-1 \
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue,Reason:StateReason}" \
  --output table
```

## CloudWatch Agent

The agent is installed and configured on the EC2 instance via two SSM Associations (`AWS-ConfigureAWSPackage` + `AmazonCloudWatch-ManageAgent`). Configuration JSON lives in SSM Parameter Store at `/review-master/cwagent-config`.

Metrics shipped to the `CWAgent` namespace:

- `mem_used_percent`
- `swap_used_percent`
- `disk_used_percent` (path=/, fstype=xfs)

Verify metrics are flowing:

```bash
aws cloudwatch list-metrics --namespace CWAgent --region ap-south-1 \
  --dimensions Name=InstanceId,Value=i-0782bee2ff9885151 \
  --query 'Metrics[*].MetricName' --output text
# Expected: mem_used_percent disk_used_percent swap_used_percent
```

If metrics are missing, check the SSM Association status:

```bash
aws ssm describe-association-executions \
  --association-id $(aws ssm list-associations --region ap-south-1 \
    --query "Associations[?Name=='AmazonCloudWatch-ManageAgent'].AssociationId" --output text) \
  --region ap-south-1 --max-results 1
```

## Celery Queue Depth Metric

A periodic Beat task (`apps.common.tasks.publish_celery_queue_depths_task`, runs every 60s) publishes one CloudWatch metric per Celery queue to the `ReviewMaster/Celery` namespace.

| Metric | Dimension | Unit |
|---|---|---|
| `QueueDepth` | `QueueName=google-sync` | Count |
| `QueueDepth` | `QueueName=ai-enrichment` | Count |
| `QueueDepth` | `QueueName=default` | Count |

Use this to spot worker backlog before users do:

```bash
aws cloudwatch get-metric-statistics \
  --namespace ReviewMaster/Celery \
  --metric-name QueueDepth \
  --dimensions Name=QueueName,Value=ai-enrichment \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 --statistics Maximum \
  --region ap-south-1 --output table
```

Recommended alarm (not yet configured — add via terraform when first backlog seen):

| Alarm | Threshold | Action |
|---|---|---|
| `review-master-celery-backlog` | `QueueDepth` > 200 sustained 15 min on any queue | Investigate worker; scale Celery worker container or move to dedicated EC2 |

## Cost Anomaly Detection

Adopted the AWS-auto-created `Default-Services-Monitor` (DIMENSIONAL, SERVICE). Email subscription delivers daily summary alerts when an AWS service's spend anomaly impact is ≥ $5.

No SNS confirmation required — Cost Explorer uses native email delivery, not SNS.

View anomalies:

```bash
aws ce get-anomalies \
  --region us-east-1 \
  --date-interval StartDate=$(date -u -v-30d +%Y-%m-%d),EndDate=$(date -u +%Y-%m-%d) \
  --output table
```

(Cost Explorer is global, accessed via `us-east-1`.)

## Sentry

Application errors are captured in Sentry. Check the `SENTRY_DSN` in Secrets Manager to find the project URL. Errors from `web`, `worker`, and `beat` containers all report to the same Sentry project.

## Celery Task Monitoring

Use Flower for real-time task visibility. Access via SSM port forwarding (see [access.md](access.md)):

```bash
aws ssm start-session \
  --target i-0782bee2ff9885151 \
  --region ap-south-1 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["5555"],"localPortNumber":["5555"]}'
```

Then open `http://localhost:5555`.

Or check from the CLI on the EC2 (run [standard session setup](README.md) first):

```bash
# List active tasks
docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect active

# List scheduled tasks
docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect scheduled

# Check worker is alive
docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect ping
```

## CloudWatch Logs Insights — Useful Queries

Open CloudWatch → Log Insights → select log group `/review-master/prod`.

**Error rate in the last hour:**
```
fields @timestamp, levelname, name, message
| filter levelname = "ERROR"
| sort @timestamp desc
| limit 50
```

**Slow requests (> 1s):**
```
fields @timestamp, message
| filter message like /duration/
| sort @timestamp desc
```

**Failed Celery tasks:**
```
fields @timestamp, message
| filter @logStream = "worker"
| filter message like /FAILURE/
| sort @timestamp desc
| limit 20
```

## Container Status Check

Quick overview from your local machine:

```bash
aws ssm send-command \
  --region ap-south-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:Project,Values=review-master" \
  --parameters 'commands=["docker compose -f /opt/review-master/docker-compose.prod.yml ps"]' \
  --query "Command.CommandId" \
  --output text
```
