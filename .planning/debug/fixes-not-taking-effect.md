---
status: awaiting_human_verify
trigger: "fixes-not-taking-effect: Loader stuck at 101/109 and action item notifications still firing per-review"
created: 2026-05-05T00:00:00Z
updated: 2026-05-05T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — Stale Redis progress snapshot for shop_id=1 (enriched:101 vs fetched:109). The 8 already-SUCCESS reviews ran under old code before the _emit_enrichment_progress fix, so their enrichment was never counted in Redis.
test: Checked Redis key sync:progress:1 — shows enriched:101, fetched:109, status:enriching
expecting: Clearing the stale Redis snapshot and restarting the worker will allow clean re-sync
next_action: Clear Redis stale keys, restart worker, instruct user to trigger new sync

## Symptoms

expected:
- Enrichment progress reaches 109/109 and sync.complete fires
- After initial sync: ONE 'N action items found' notification + ONE 'N reviews synced' notification

actual:
- Loader stuck at 101/109
- Multiple per-review action item notifications still appearing

errors: none reported
reproduction: Run a full shop sync
started: Code fixes were committed but containers were not restarted

## Eliminated

- hypothesis: containers running old code (no bind mount)
  evidence: docker-compose.yml shows `. :/app` bind mount; Python file on disk matches host; enrichment.py and progress.py both show new fix code in containers
  timestamp: 2026-05-05T05:17:00Z

- hypothesis: Celery worker in-memory module is stale (no hot-reload)
  evidence: manage.py shell confirms in-memory enrichment module has _dispatch_sync_complete_notifications and accumulate_action_items
  timestamp: 2026-05-05T05:17:00Z

- hypothesis: action item notifications are still firing per-review
  evidence: DB shows only 1 new_action_item notification total — consolidation IS working
  timestamp: 2026-05-05T05:17:16Z

## Evidence

- timestamp: 2026-05-05T05:16:40Z
  checked: Redis key sync:progress:1
  found: {"shop_id": 1, "status": "enriching", "fetched": 109, "total_estimate": 109, "enriched": 101, "started_at": "2026-05-05T05:12:03", "last_update_at": "2026-05-05T05:12:05"}
  implication: Snapshot stuck at 101/109; last_update_at is 05:12:05 (over 4 minutes ago); no worker is updating it

- timestamp: 2026-05-05T05:17:07Z
  checked: Review.objects.values('enrichment_status').annotate(count=Count('id'))
  found: enrichment_status=SUCCESS count=109 — all 109 reviews are already SUCCESS in DB
  implication: The 8 missing from Redis counter (109-101=8) are reviews that were already SUCCESS when the old enrichment code ran; the old code returned early without calling _emit_enrichment_progress

- timestamp: 2026-05-05T05:17:16Z
  checked: Notification.objects.values('notification_type').annotate(count=Count('id'))
  found: new_action_item count=1 (not per-review)
  implication: Action item consolidation fix IS working; only the loader counter is the problem

## Resolution

root_cause: Stale Redis progress snapshot (sync:progress:1) left from a sync run that executed under old code. At that time enrichment.py lacked the _emit_enrichment_progress call for already-SUCCESS reviews, so 8 reviews that were already enriched never incremented the Redis enriched counter. The snapshot remained permanently stuck at enriched:101/fetched:109. All 109 reviews are SUCCESS in the DB — the bug was purely in the Redis counter, not the data.

fix: Deleted stale Redis key sync:progress:1. Restarted worker and beat containers to flush any in-process Celery task state. No code change needed — both fixes (enrichment progress emission and action item consolidation) are confirmed present on disk and loaded in containers.

verification: Redis key cleared and verified absent. Worker restarted and confirmed healthy. Awaiting user to trigger a new sync and confirm loader reaches 109/109 and notifications are consolidated.

files_changed: []
