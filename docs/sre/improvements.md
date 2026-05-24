# SRE Improvements Backlog

Optional follow-ups identified during the Tier-0 hardening (2026-05-24). None
are urgent. Each item is independent — pick when the trigger condition fires
or when you have spare cycles.

For deployed Tier-0 state see [monitoring.md](monitoring.md) and the
[terraform repo](../../../review-master-terraform/stacks/prod-app/).

---

## 1. Celery queue-depth alarms (recommended next)

**Why:** the Celery queue depth metric is now flowing to CloudWatch
(namespace `ReviewMaster/Celery`, metric `QueueDepth`), but there's no
alarm on it yet. Today you'd have to look at the graph manually to spot
worker backlog. With an alarm, SNS emails you the moment the worker falls
behind — that's the Tier-1 scale-trigger the original plan called out.

**Trigger threshold rationale:** at the current workload (~60 stores, a
handful of reviews each) every queue should drain back to 0 within a
minute. `QueueDepth > 200 sustained 15 min` means the worker is genuinely
behind, not just briefly busy during a sync window.

**Where to add:** `stacks/prod-app/cloudwatch.tf` in the terraform repo.

```hcl
resource "aws_cloudwatch_metric_alarm" "celery_backlog" {
  for_each = toset(["google-sync", "ai-enrichment", "default"])

  alarm_name          = "review-master-celery-backlog-${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3                              # 3 × 5 min = 15 min sustained
  metric_name         = "QueueDepth"
  namespace           = "ReviewMaster/Celery"
  period              = 300
  statistic           = "Maximum"
  threshold           = 200
  alarm_description   = "Celery queue ${each.key} > 200 sustained 15 min — worker falling behind"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = each.key
  }
}
```

**Cost:** 3 alarms × $0.10 = $0.30/mo. You currently have 7 alarms, free
tier covers 10, so this is effectively **$0** until you add an 8th alarm.

**Effort:** ~5 min in terraform. `terraform plan` should show 3 adds.

**What the alarm tells you to do:** investigate why the worker is behind
(slow OpenAI calls? RDS contention? a single bad task hogging the worker?).
If sustained, this is the trigger to either bump worker concurrency
(`--concurrency=4`) or move the worker to a dedicated EC2 instance
(see Tier-1 upgrades below).

---

## 2. Per-org OpenAI cost metric (when customer #2 joins)

**Why:** today there's only one customer, so "which customer is costing
me money?" is answered by a SQL query against `AiUsageLog`. As soon as
there's a second customer, you'll want a CloudWatch metric per
organisation so you can graph spend over time and alert on outliers.

**Implementation sketch:**

- New service function `apps/integrations/openai/services/metrics.py`:
  `publish_openai_cost(*, organisation_id, cost_usd)`.
- Call it from `apps/integrations/openai/client.py` immediately after
  the `AiUsageLog` row is written (one PutMetricData per OpenAI call).
- Namespace `ReviewMaster/OpenAI`, metric `CostUSD`, dimension
  `OrganisationId`.

**Cost:** $0.30 per organisation per month. Until 4 organisations exist
you're still inside the 10-custom-metric free tier (you have 6 in use
today: 3 CWAgent + 3 Celery).

**Skip until:** you onboard customer #2.

---

## 3. Celery queue-depth alarm thresholds tuning

After 2–3 weeks of baseline data, revisit the `>200` threshold in §1.
Look at the actual queue-depth graphs:

- If queues routinely peak at e.g. 400 during sync and drain in 10 min —
  raise threshold to 500 to avoid false positives.
- If queues never go above 50 — lower threshold to 50 for earlier signal.

The right threshold is whatever flags **real backlogs** without crying
wolf on normal sync spikes.

---

## 4. `templatefile()` for user-data.sh portability

**Why:** `stacks/prod-app/files/user-data.sh` has hardcoded values that
would need editing for a new AWS account or region (S3 bucket name,
region). Cleaner approach: use `templatefile()` so terraform variables
flow into the script.

**Where:** `stacks/prod-app/ec2.tf`.

```hcl
user_data = templatefile("${path.module}/files/user-data.sh.tpl", {
  aws_region = var.aws_region
  app_dir    = "/opt/review-master"
  s3_bucket  = aws_s3_bucket.static.id
})
```

Then rename `user-data.sh` → `user-data.sh.tpl` and replace the
hardcoded values with `${aws_region}`, `${s3_bucket}`, etc.

**Skip until:** you're about to spin up a second environment (staging,
DR, or second AWS account).

---

## 5. Migrate Terraform state to S3 remote backend

**Why:** state file lives on the operator's laptop today
(`stacks/prod-app/terraform.tfstate`). Fine for a solo operator, blocker
for a teammate. State contains the generated RDS password.

**Where:** `stacks/prod-app/main.tf`. The S3 backend block is already
written and commented out.

**Steps:**

1. Create `aws_s3_bucket.tfstate` (encrypted, versioned, BPA on) and
   `aws_dynamodb_table.tfstate_lock` — either via a one-time manual
   `terraform apply` or via console.
2. Uncomment the `backend "s3"` block in `main.tf`.
3. Run `terraform init -migrate-state`. Terraform copies local state
   into S3 and switches over.
4. Delete the local `terraform.tfstate` files.

**Cost:** ~$1/mo (tiny S3 + tiny DynamoDB).

**Skip until:** a second person needs to run terraform commands.

---

## 6. GuardDuty (security)

**Why:** machine-learns normal API and network behaviour, alerts on
credential abuse, crypto-mining on EC2, S3 anomalies, etc.

**Cost:** ~$4–6/mo at current volume.

**Where:** new file `stacks/prod-app/guardduty.tf`:

```hcl
resource "aws_guardduty_detector" "main" {
  enable                       = true
  finding_publishing_frequency = "SIX_HOURS"
}

resource "aws_sns_topic_subscription" "guardduty_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

Plus an EventBridge rule to route findings to the SNS topic.

**Skip until:** you have a compliance driver (SOC 2 roadmap, customer
contract) or you start storing customer credentials/PII at scale.

---

## 7. AWS Config (drift detection)

**Why:** detects when somebody clicks in the AWS console and changes
something that terraform would later revert (or worse, that terraform
no longer matches reality).

**Cost:** ~$2/mo for 5 critical rules
(`s3-bucket-public-read-prohibited`, `rds-storage-encrypted`,
`encrypted-volumes`, `iam-root-access-key-check`,
`vpc-default-security-group-closed`).

**Skip until:** more than one person has AWS console access.

---

## 8. Permission boundary / SCPs (residency + safety net)

**Why:** belt-and-braces guardrail. Even if a teammate or compromised
credential tries to launch something in `us-east-1`, the boundary denies
it. Same for unencrypted RDS, public security groups, etc.

**Cost:** $0.

**Effort:** moderate (~30 min). Write the policy JSON, attach as IAM
permission boundary to all human + CI roles. Care needed because a
mistake locks out terraform itself.

**Skip until:** second AWS user joins the account.

---

## 9. RDS restore-from-PITR drill

**Why:** RDS automated backups (7-day window) are enabled, but you've
never restored from them. RPO and RTO are theoretical until proven.

**Procedure:**

1. AWS Console → RDS → `review-master-prod` → Actions → Restore to
   point-in-time → restore to a brand-new instance
   (`review-master-prod-drill`).
2. Note start time, wait for the restore (~15–30 min).
3. Connect to the restored instance from a one-off EC2 or local + SSM
   port-forward. Run a few `SELECT COUNT(*) FROM reviews_review` etc.
   to confirm data is intact.
4. Note RTO (time from start to first successful query). Aim for ≤30 min.
5. Delete the drill instance immediately after to avoid extra cost.

**Cost:** ~$0.50 for the ~30 min of running a second db.t4g.micro.

**Cadence:** once now, then every 3 months. Record measured RTO in this
file when you do it.

---

## 10. Tier-1 upgrade triggers (quick reference)

These aren't follow-ups to schedule — they're decision rules for when
alarms fire. Re-document here for fast lookup.

| Alarm fires | First response | Cost delta |
|---|---|---|
| `ec2_cpu_high` or `ec2_memory_high` sustained 3 days | Upgrade EC2 t4g.medium → t4g.large | +$25/mo |
| `ec2_disk_high` | Grow gp3 volume in place (no downtime): `aws ec2 modify-volume --volume-id <id> --size 50` | +$0.08/GB-mo |
| `rds_memory_low` or `rds_cpu_high` sustained | Upgrade RDS db.t4g.micro → db.t4g.small | +$12/mo |
| `rds_storage_low` | RDS gp3 autoscales up to 100 GB cap — no action; just monitor | +$0.115/GB-mo |
| `celery_backlog` on any queue sustained 1h | Bump worker concurrency to 4, then if still backed up move worker to dedicated EC2 | +$15/mo |
| **Onboard 2nd paying customer** | Enable RDS Multi-AZ (config flip, no migration) | +$13/mo |
| Cost Anomaly Detection email | Investigate which service spiked; check `ce get-anomalies` for detail | $0 (just signal) |

Worst case if every Tier-1 trigger fires: ~$118/mo (still under what
ECS + ALB + ElastiCache would cost on day one).

---

## How to use this doc

- Read after every Tier-0/Tier-1 alarm to see if the trigger maps to an
  action listed in §10.
- When you finish an item, **delete it from this file** so the backlog
  reflects open work only (or move it to a "Completed" section at the
  bottom if you want an audit trail).
- Add new items as you discover gaps. Keep each item to the same shape:
  Why / Cost / Where / Effort / Skip-until.
