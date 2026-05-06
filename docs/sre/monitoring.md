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

Two alarms are configured and send email to `renjith@sayonetech.com` via SNS:

| Alarm | Threshold | Action |
|-------|-----------|--------|
| `review-master-ec2-cpu-high` | EC2 CPU > 70% for 10 min | Email alert |
| `review-master-rds-memory-low` | RDS FreeableMemory < 100 MB for 10 min | Email alert |

View alarms:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix review-master \
  --region ap-south-1 \
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue,Reason:StateReason}" \
  --output table
```

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

Or check from the CLI on the EC2:

```bash
# List active tasks
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect active

# List scheduled tasks
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
  exec worker celery -A config inspect scheduled

# Check worker is alive
sudo docker compose -f /opt/review-master/docker-compose.prod.yml \
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
