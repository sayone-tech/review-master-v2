# Logs

All container logs ship to **CloudWatch Logs** (`/review-master/prod`, 30-day retention) and are also available locally on the EC2 via `docker logs`. AWS audit trails (CloudTrail) and network forensics (VPC Flow Logs) go to S3 — see [Audit Trail Logs](#audit-trail-logs) at the end of this doc.

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

---

## Audit Trail Logs

Two AWS-managed audit log streams write to a private S3 bucket (`review-master-logs-prod`) with 90-day retention. Both were added in Tier-0 hardening (2026-05-24).

### CloudTrail — every AWS API call

A single-region trail (`review-master-trail`, ap-south-1 only — for India residency) records every AWS API call made on this account: who, when, from where, with what parameters, and the response.

**Bucket path:** `s3://review-master-logs-prod/cloudtrail/AWSLogs/270587882826/CloudTrail/ap-south-1/`

**Check the trail is still logging:**

```bash
aws cloudtrail get-trail-status --name review-master-trail --region ap-south-1 \
  --query '{IsLogging:IsLogging, LatestDeliveryTime:LatestDeliveryTime}' --output table
```

**Look up recent activity for a user (via CloudTrail Lake / Event History — fastest):**

AWS Console → CloudTrail → Event history → filter by **User name** or **Event source**. Last 90 days are queryable in the console UI without downloading log files.

**Download raw logs from S3 for forensic analysis:**

```bash
# List today's log files
aws s3 ls "s3://review-master-logs-prod/cloudtrail/AWSLogs/270587882826/CloudTrail/ap-south-1/$(date -u +%Y/%m/%d)/" --region ap-south-1

# Download a specific file (gzipped JSON)
aws s3 cp s3://review-master-logs-prod/cloudtrail/AWSLogs/.../<file>.json.gz . --region ap-south-1
gunzip <file>.json.gz | jq .
```

### VPC Flow Logs — network traffic forensics

Every accepted/rejected TCP/UDP flow in the VPC is captured. Stored in Parquet format with 10-minute aggregation to keep cost down (~$0.50/mo at current traffic).

**Bucket path:** `s3://review-master-logs-prod/flow-logs/AWSLogs/270587882826/vpcflowlogs/ap-south-1/`

**Common use cases:**

- "What IPs hit our EC2 in the last hour?" — Athena query on the parquet files
- "Was there a port scan?" — count REJECTed flows per source IP
- "Did EC2 reach an unexpected outbound endpoint?" — filter outbound flows

**Quick analysis via Athena** (one-time setup, then queryable forever):

AWS Console → Athena → create database `vpc_logs` → create table pointing at the flow-logs prefix in parquet format. Then query like:

```sql
-- Top source IPs hitting the EC2 in the last hour
SELECT srcaddr, COUNT(*) AS hits
FROM vpc_logs.flow_logs
WHERE start >= to_unixtime(current_timestamp - interval '1' hour)
  AND dstaddr = '10.0.0.X'   -- EC2 private IP
GROUP BY srcaddr ORDER BY hits DESC LIMIT 20;
```

### Retention

Lifecycle rule on the logs bucket deletes objects after **90 days** and noncurrent versions after **30 days**. Extend in `stacks/prod-app/logs_bucket.tf` if a compliance requirement appears.
