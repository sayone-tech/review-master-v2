# Logs

All container logs ship to **CloudWatch Logs** (`/review-master/prod`, 90-day retention) and are also available locally on the EC2 via `docker logs`.

## CloudWatch Logs (recommended — no server access needed)

### Log streams

| Stream | Service |
|--------|---------|
| `web` | Django/Daphne (app requests, errors) |
| `worker` | Celery worker (task execution) |
| `beat` | Celery Beat (scheduler) |
| `caddy` | Reverse proxy / TLS (HTTP access log) |
| `flower` | Flower task monitor |
| `redis` | Redis |

### Via AWS Console

AWS Console → CloudWatch → Log groups → `/review-master/prod` → select stream.

### Via AWS CLI

```bash
# Tail web logs live
aws logs tail /review-master/prod --log-stream-name web --follow --region ap-south-1

# Tail worker logs live
aws logs tail /review-master/prod --log-stream-name worker --follow --region ap-south-1

# Last 100 lines from web (no follow)
aws logs tail /review-master/prod --log-stream-name web --since 1h --region ap-south-1

# Search for errors in the last 30 minutes
aws logs filter-log-events \
  --log-group-name /review-master/prod \
  --log-stream-names web \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 1800))000 \
  --region ap-south-1
```

## Docker Logs (on EC2 via Session Manager)

Connect first: `aws ssm start-session --target i-0782bee2ff9885151 --region ap-south-1`

```bash
# All containers, last 50 lines
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50

# Specific service, follow live
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs -f web
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs -f worker
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs -f caddy

# Last 100 lines from web with timestamps
sudo docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 --timestamps web
```

## Log Format

App logs are structured JSON. Each line looks like:

```json
{
  "asctime": "2026-05-06 16:30:43,139",
  "levelname": "INFO",
  "name": "apps.reviews.services.sync",
  "message": "Synced 42 reviews for shop 123",
  "request_id": "abc123",
  "user_id": 7,
  "organisation_id": 2
}
```

Filter by `levelname` to find errors:

```bash
aws logs filter-log-events \
  --log-group-name /review-master/prod \
  --log-stream-names web worker \
  --filter-pattern '{ $.levelname = "ERROR" }' \
  --region ap-south-1
```
