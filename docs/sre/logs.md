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

Connect first and run the [standard session setup](README.md), then:

```bash
# All containers, last 50 lines
docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=50

# Specific service, follow live
docker compose -f /opt/review-master/docker-compose.prod.yml logs -f web
docker compose -f /opt/review-master/docker-compose.prod.yml logs -f worker
docker compose -f /opt/review-master/docker-compose.prod.yml logs -f caddy

# Last 100 lines from web with timestamps
docker compose -f /opt/review-master/docker-compose.prod.yml logs --tail=100 --timestamps web
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

---

## Celery Task Logs

All tasks emit structured log lines to the `worker` stream. Every line carries `task_id`, `shop_id` or `review_id`, and `attempt` number so you can trace a full task lifecycle with a single query.

### Log line patterns

| Pattern | Meaning |
| ------- | ------- |
| `sync_shop_reviews_task.start` | Incremental sync started for a shop |
| `sync_shop_reviews_task.success` | Sync completed — includes `fetched`, `soft_deleted`, `duration_seconds` |
| `sync_shop_reviews_task.skipped` | Sync skipped — `reason=locked` (another worker running) or `reason=expired` (token expired) |
| `sync_shop_reviews_task.error` | Sync failed — full traceback follows |
| `initial_backfill_task.start/success/skipped/error` | Same shape for initial OAuth backfill |
| `enqueue_incremental_syncs_task.dispatched` | Beat fired the fan-out — includes `shops_count` |
| `enrich_review_task.start/success/error` | AI enrichment for a single review |
| `retry_failed_enrichments_task.dispatched` | Beat re-queued failed enrichments — includes `reviews_count` |

### Example log lines

```text
INFO  sync_shop_reviews_task.start task_id=abc-123 shop_id=5 attempt=1
INFO  sync_shop_reviews_task.success task_id=abc-123 shop_id=5 fetched=3 soft_deleted=0 duration_seconds=2.4
INFO  sync_shop_reviews_task.skipped task_id=abc-123 shop_id=5 reason=locked
ERROR sync_shop_reviews_task.error task_id=abc-123 shop_id=5 attempt=2 max_retries=3 error=GoogleQuotaError(...)
      Traceback (most recent call last): ...
```

### CloudWatch Insights queries

#### Step-by-step via AWS Console UI

1. Open [AWS Console](https://ap-south-1.console.aws.amazon.com/cloudwatch) and make sure the region is **ap-south-1 (Mumbai)**.
2. In the left sidebar, click **Logs → Logs Insights**.
3. At the top, click **Select log group(s)** and choose `/review-master/prod`.
4. Set the **time range** using the date picker in the top-right (e.g. "Last 3 hours" or a custom window).
5. Paste one of the queries below into the editor.
6. Click **Run query** (or press `Ctrl+Enter`).
7. Results appear below — click any row to expand the full log line including the traceback.

> **Tip:** Click the **Export results** button (top-right of results) to download as CSV for incident reports.

Go to: **CloudWatch → Logs Insights → select `/review-master/prod`**

**All task errors in the last 24 hours:**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like ".error"
| sort @timestamp desc
| limit 50
```

**Sync success summary (fetched counts per run):**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like "sync_shop_reviews_task.success"
| sort @timestamp desc
| limit 50
```

**Full lifecycle for a specific task (paste real task_id):**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like "task_id=<PASTE_TASK_ID_HERE>"
| sort @timestamp
```

**All activity for a specific shop:**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like "shop_id=<SHOP_ID>"
| sort @timestamp desc
| limit 100
```

**Skipped syncs (locked or expired token):**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like ".skipped"
| sort @timestamp desc
| limit 50
```

**Beat fan-out health — confirm cron fired:**

```text
fields @timestamp, @message
| filter @logStream = "worker"
| filter @message like "enqueue_incremental_syncs_task.dispatched"
| sort @timestamp desc
| limit 10
```

### AWS CLI equivalents

```bash
# All task errors in the last hour
aws logs filter-log-events \
  --log-group-name /review-master/prod \
  --log-stream-names worker \
  --filter-pattern ".error" \
  --start-time $(($(date +%s) - 3600))000 \
  --region ap-south-1

# Sync results for a specific shop
aws logs filter-log-events \
  --log-group-name /review-master/prod \
  --log-stream-names worker \
  --filter-pattern "shop_id=5" \
  --start-time $(($(date +%s) - 86400))000 \
  --region ap-south-1

# Confirm Beat fired the cron in the last 7 hours
aws logs filter-log-events \
  --log-group-name /review-master/prod \
  --log-stream-names worker \
  --filter-pattern "enqueue_incremental_syncs_task.dispatched" \
  --start-time $(($(date +%s) - 25200))000 \
  --region ap-south-1
```

### Common SRE scenarios

#### "Is the 6-hour sync actually running?"

Search for `enqueue_incremental_syncs_task.dispatched` — should appear every ~6 hours. If absent, Beat may be down; check `docker ps` on EC2.

#### "Why did sync fail for shop X?"

1. Search `shop_id=<X>` in the `worker` stream.
2. Find the `.error` line and note the `task_id`.
3. Search that `task_id` to see the full context including attempt count.
4. If `reason=expired`, the Google OAuth token needs re-authorisation from the Shops page.

#### "How many reviews did the last sync fetch?"

Search `sync_shop_reviews_task.success shop_id=<X>` — the line includes `fetched=N`.
