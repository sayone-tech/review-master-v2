# Phase 23: Four-Step Initial Sync, Seeding & Queue Split - Research

**Researched:** 2026-06-10
**Domain:** Celery queue orchestration, Redis token-bucket rate limiting, Django Channels WebSocket event extension, sequential-seed orchestration, OrgCanonicalTag finalising merge
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Four steps = Fetching (Google fetch) → Building Tag Vocabulary (sequential seed, real GPT enrichment, vocab grows per review) → AI Enrichment (parallel bulk phase, remaining reviews) → Finalising (dedup/backfill/count-refresh). No separate vocabulary-only pre-pass; seed reviews are enriched once only.
- **D-02:** Progress text is per-step with counts (`Building vocabulary 12/50`, `Enriching 340/520`). Extend `SyncProgressConsumer` and `sync:progress:{shop_id}` Redis snapshot with a `step` discriminator and per-step counters. Add event types following CLAUDE.md §13.5 conventions (`sync.vocab.progress`, `sync.finalising.progress`). No new consumer.
- **D-03:** Seed set = newest N reviews (most representative), processed sequentially. If fewer than N reviews, seed all of them.
- **D-04:** N is `SEED_PHASE_SIZE` (default 50), a configurable Django setting. Sequential loop re-reads org vocabulary each iteration using the existing `get_org_vocabulary` selector.
- **D-05:** Duplicate definition = two `OrgCanonicalTag` rows whose normalized Title-Case labels match case-insensitively. No fuzzy/semantic matching this phase.
- **D-06:** Merge winner = higher `review_count` (tie → earliest `created`). Re-point loser's `ReviewTag.canonical_tag` FKs to winner, keep winner's `polarity_type`, delete loser.
- **D-07:** Finalising pass also backfills `canonical_tag` on null stragglers and refreshes `review_count` cache. Resolves Phase 22 D-03 deferral. Merge + backfill + count-refresh on dedicated `tag-merge` queue.
- **D-08:** Build the true cross-worker global Redis token-bucket rate limiter now. Uses `rate:openai:*` key convention (CLAUDE.md §7.7). Target ~500/min aggregate. Per-worker `rate_limit` stays as secondary guard.
- **D-09:** Queue split: `ai-enrichment-high` (initial sync seed + bulk), `ai-enrichment-low` (daily incremental), `tag-merge` (finalising/merge). Update `CELERY_TASK_ROUTES`, `CELERY_QUEUE_NAMES`, worker `-Q` args. Routing mechanism for same task to high vs low is a research/planning choice (NOT locked).
- **D-10:** Daily incremental sync routes enrichment to `ai-enrichment-low`. New canonical tags auto-added, no approval step.

### Claude's Discretion

- Exact new event `type` names and Redis snapshot schema for the 4 steps (follow CLAUDE.md §13.5 payload conventions).
- The high-vs-low queue routing mechanism for `enrich_review_task` (D-09).
- Token-bucket implementation details (refill cadence, key TTL) within the CLAUDE.md §7.7 `rate:openai:*` convention.
- Beat-schedule wiring for the daily incremental fan-out (reuse `enqueue_incremental_syncs_task` pattern).
- Whether `review_count` is a refreshed denormalized column vs computed-on-read aggregate (D-03/P22 permits either, as long as it is never incremented inline); pick the simpler one.

### Deferred Ideas (OUT OF SCOPE)

- Fuzzy/semantic duplicate merging (beyond case-insensitive label match) — Phase 25.
- Weekly polarity auto-reclassification + reclassification visibility — Phase 24.
- Org Admin Tags page (rename/merge UI), dashboard polarity split — Phase 25.
- Superadmin data reset — Phase 26.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEED-01 | Initial sync shows four steps per store — Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising — with progress text per step | §Architecture Patterns: SyncProgressConsumer extension; WebSocket event payload schema; Redis snapshot schema |
| SEED-02 | Seed phase processes first 50 reviews sequentially (all if fewer than 50), updating canonical vocabulary before each next review | §Architecture Patterns: sequential seed orchestration; `get_org_vocabulary` re-query pattern |
| SEED-03 | Bulk phase enriches remaining reviews in parallel against current vocabulary; still able to add new canonical tags | §Architecture Patterns: parallel bulk dispatch; `apply_async(queue="ai-enrichment-high")` pattern |
| SEED-04 | Finalising pass resolves residual duplicate tags by string match and backfills `canonical_tag` on any stragglers | §Architecture Patterns: finalising merge; case-insensitive dedup; FK re-point without N+1 |
| DSYNC-01 | Daily incremental sync enriches new reviews through the same canonical pipeline on the low-priority enrichment queue | §Architecture Patterns: `apply_async(queue="ai-enrichment-low")` at daily sync dispatch site |
| QUEUE-01 | Enrichment work split across `ai-enrichment-high`, `ai-enrichment-low`, and `tag-merge` queues; routes, `CELERY_QUEUE_NAMES`, worker `-Q` args updated | §Standard Stack: Celery queue wiring; §Architecture Patterns: CELERY_TASK_ROUTES additions |
</phase_requirements>

---

## Summary

Phase 23 extends the existing Phase 22 canonical tag pipeline with four interlocking concerns: (1) a sequential seed phase that stabilises the per-org vocabulary before the parallel bulk phase, (2) a Redis cross-worker token-bucket global rate limiter that gates OpenAI calls to ~500/min aggregate, (3) a three-way Celery queue split (`ai-enrichment-high`, `ai-enrichment-low`, `tag-merge`), and (4) extending the two-stage `SyncProgressConsumer` to four stages by adding `sync.vocab.progress` and `sync.finalising.progress` events.

All four concerns build directly on shipped Phase 22 code. The seed loop re-uses the existing `enrich_review` service and `get_org_vocabulary` selector unchanged. The global rate limiter mirrors the existing Google token-bucket pattern in `apps/reviews/services/progress.py`. The queue split is a configuration change to `CELERY_TASK_ROUTES` + `CELERY_QUEUE_NAMES` plus a change at the dispatch call site (using `apply_async(queue=...)` override, which is Celery's documented mechanism for routing the same task to different queues at call time). The WebSocket extension adds two event types while preserving CLAUDE.md §13.2 scope discipline (no new consumer).

The finalising pass is the highest-complexity piece: a `tag-merge` task that must do a case-insensitive ORM query, re-point FK references for the loser in one `update()` call (no N+1), delete the loser, then compute `review_count` as an aggregate and write it back as a cached denormalized value — all inside `transaction.atomic()` with `select_for_update()`.

**Primary recommendation:** Structure `run_initial_backfill` as a three-phase orchestrator — synchronous seed loop in the task body, parallel bulk dispatch via `group().apply_async(queue="ai-enrichment-high")`, then a Celery chord/callback that triggers `finalize_canonical_tags_task` on the `tag-merge` queue after the bulk group completes. Emit progress events from within `enrich_review` for both seed and bulk phases; distinguish them by the `step` discriminator in the Redis snapshot.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Sequential seed phase loop | API / Backend (Celery task body) | — | Blocking loop must run in a worker, not web process |
| Parallel bulk enrichment fan-out | API / Backend (Celery chord) | — | Fan-out via Celery primitives, each review is a task |
| Global OpenAI rate limiter | API / Backend (Redis) | — | Cross-worker shared state; only Redis is appropriate |
| Finalising merge / dedup | API / Backend (Celery task, tag-merge queue) | Database | FK re-point in ORM; isolated queue to avoid blocking enrichment |
| WebSocket progress events (4 steps) | API / Backend + Browser | — | Backend emits events; frontend (ProgressModal.tsx) renders them |
| Redis snapshot `step` discriminator | API / Backend (Redis) | — | Persisted per shop for reconnect correctness |
| Queue routing (high vs low) | API / Backend (Celery dispatch) | — | `apply_async(queue=...)` override at call site in sync.py |
| `review_count` refresh | Database / Storage | — | Aggregate query + UPDATE; runs in finalising task |

---

## Standard Stack

### Core (all already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery | ^5.4.0 (installed) | Task queuing, chord/group primitives | Project standard, CLAUDE.md §12 |
| channels | ^4.2.0 (installed) | WebSocket consumer | Project standard, CLAUDE.md §13 |
| django-redis / redis-py | installed | Redis raw connection for token bucket | `get_redis_connection("default")` used in progress.py |
| Django ORM | 6.0.x (installed) | `update()`, `select_for_update()`, `F()` for FK re-point | No extra library needed |

### No New Packages Required

This phase installs **no new dependencies**. All required capabilities (Celery chords, Redis pipelines, `apply_async` queue override, ORM bulk operations) are already available in the installed stack.

---

## Package Legitimacy Audit

No new packages are installed in this phase. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Initial Backfill Flow
─────────────────────
OAuth Connect
    │
    ▼
initial_backfill_task (google-sync queue)
    │
    ├──[1]─► fetch_and_persist_reviews()
    │         ├── pages Google API → upsert Reviews
    │         ├── emit sync.fetch.progress events
    │         └── return total_fetched
    │
    ├──[2]─► Sequential Seed Loop (in service, blocking)
    │         for review_id in seed_ids (newest N):
    │           get_org_vocabulary()  ◄─── re-query per iteration
    │           enrich_review(review_id)   (calls OpenAI)
    │           emit sync.vocab.progress
    │         [token bucket check before each call]
    │
    ├──[3]─► Parallel Bulk Fan-out
    │         group(enrich_review_task.s(id) for id in bulk_ids)
    │         .apply_async(queue="ai-enrichment-high")
    │         emit sync.enrichment.progress (per task, as before)
    │         [token bucket check before each OpenAI call]
    │
    └──[4]─► finalize_canonical_tags_task (tag-merge queue)
              ├── case-insensitive dedup merge (winner by review_count)
              ├── backfill null ReviewTag.canonical_tag stragglers
              ├── refresh OrgCanonicalTag.review_count (aggregate)
              ├── emit sync.finalising.progress
              └── emit sync.complete

Daily Incremental Flow
──────────────────────
enqueue_incremental_syncs_task (Beat)
    │
    ▼
sync_shop_reviews_task (google-sync queue)
    │
    ▼
run_incremental_sync()
    ├── fetch + upsert new reviews
    └── enrich_review_task.apply_async(queue="ai-enrichment-low")
        (token bucket still applies)

Redis State
───────────
rate:openai:org:{org_id}  ──► global token bucket (INCR+EXPIRE, 1-min window)
sync:progress:{shop_id}   ──► snapshot with step + per-step counters
sync:vocab:{shop_id}      ──► vocab-phase enriched counter (INCR)
sync:bulk:{shop_id}       ──► bulk-phase enriched counter (INCR)
```

### Recommended Project Structure

No new directories needed. Files modified or created:

```
apps/reviews/
├── services/
│   ├── sync.py            ← extend run_initial_backfill, run_incremental_sync
│   └── progress.py        ← add OpenAI token bucket helpers
├── selectors/
│   └── canonical_tags.py  ← add finalising-pass selector helpers
├── tasks.py               ← add finalize_canonical_tags_task; update queue routing
├── models.py              ← no changes (OrgCanonicalTag already has review_count)
│
config/settings/
└── base.py                ← add SEED_PHASE_SIZE, OPENAI_RATE_LIMIT_GLOBAL,
                              update CELERY_TASK_ROUTES + CELERY_QUEUE_NAMES

frontend/src/widgets/review-management/
├── ProgressModal.tsx      ← extend SnapshotState, add 2 new event handlers
└── TopbarSyncIndicator.tsx ← extend SyncingShop.stage, add vocab/finalising labels
```

---

### Pattern 1: Global OpenAI Redis Token Bucket

**What:** A shared Redis counter (`rate:openai:org:{org_id}`) gates all `enrich_review` calls across ALL workers to a configurable aggregate limit (~500/min). The existing Google token bucket in `progress.py` is the direct analog.

**When to use:** Before every `call_openai_enrichment()` invocation — both seed (sequential) and bulk (parallel). This is the "always-on" global guard.

**Design decision:** Use the existing INCR+EXPIRE pattern (not a Lua script) because: (1) the existing `increment_google_token_bucket` already uses this pattern successfully, (2) the window is 60 seconds (not sub-second), (3) the risk of the INCR/EXPIRE gap (< 1ms) is negligible at this scale — a brief window where a second INCR could reset the TTL on a near-expiry key is the only race, which causes a 1-minute grace window at worst, not bypass of the limit. A Lua script would eliminate this entirely but introduces complexity not justified by the use case.

**IMPORTANT CAVEAT (ASSUMED):** The INCR+EXPIRE two-command pattern has a theoretical race: if the key expires between INCR (which recreates it at `1`) and the EXPIRE call, the TTL is set on a fresh key correctly. The real risk is a worker calling INCR when the key is at 499, then the key expires, and another worker also sees 0 → INCR → 1 and both proceed. This race is bounded by the 60-second window and the ~500/min target — at 500 calls/min, a 1ms window makes the burst-budget miss negligible in practice. For strict enforcement, use a Lua EVAL (shown in the Lua variant below).

```python
# Source: apps/reviews/services/progress.py (increment_google_token_bucket pattern)
# apps/reviews/services/progress.py — add these helpers

OPENAI_BUCKET_KEY_TMPL = "rate:openai:org:{organisation_id}"
OPENAI_BUCKET_WINDOW_SECONDS = 60

def increment_openai_token_bucket(*, organisation_id: int) -> int:
    """Increment the per-org OpenAI call counter; refresh expiry to 60s window.

    Returns the new counter value.
    Mirrors increment_google_token_bucket — same INCR+EXPIRE pattern.
    """
    conn = get_redis_connection("default")
    pipe = conn.pipeline()
    pipe.incrby(OPENAI_BUCKET_KEY_TMPL.format(organisation_id=organisation_id), 1)
    pipe.expire(OPENAI_BUCKET_KEY_TMPL.format(organisation_id=organisation_id), OPENAI_BUCKET_WINDOW_SECONDS)
    new_value, _ = pipe.execute()
    return int(new_value)


def openai_token_bucket_depleted(*, organisation_id: int, max_calls: int) -> bool:
    """Return True when the rolling 60-second counter is at/above the cap."""
    conn = get_redis_connection("default")
    raw = conn.get(OPENAI_BUCKET_KEY_TMPL.format(organisation_id=organisation_id))
    if raw is None:
        return False
    try:
        return int(raw) >= max_calls
    except (TypeError, ValueError):
        return False
```

**When bucket is depleted:** The seed loop checks the bucket BEFORE calling `enrich_review`. If depleted, sleep briefly (e.g., 0.5s) and retry in the same worker — the seed must complete sequentially. For the bulk phase, tasks that hit the limit should raise a retriable exception (e.g., `OpenAITransientError`) and Celery's `retry_backoff` handles re-queuing with countdown. Do NOT block the worker — raise + retry.

**Settings to add to `config/settings/base.py`:**
```python
SEED_PHASE_SIZE = env.int("SEED_PHASE_SIZE", default=50)
# Global aggregate OpenAI calls/min across all workers (D-08)
OPENAI_GLOBAL_RATE_LIMIT = env.int("OPENAI_GLOBAL_RATE_LIMIT", default=500)
```

**Composing with per-worker `rate_limit`:** The per-worker `rate_limit="125/m"` (Phase 22) remains as the secondary guard — it limits how fast a single worker can dispatch tasks to the broker. The global bucket is the primary cross-worker guard inside `enrich_review` itself. The two operate independently: per-worker `rate_limit` throttles task acceptance; the global bucket throttles actual API calls. They are additive safety layers, not alternatives.

[CITED: https://redis.io/docs/latest/develop/use-cases/rate-limiter/]
[CITED: https://blog.callr.tech/rate-limiting-for-distributed-systems-with-redis-and-lua/]

---

### Pattern 2: Queue Routing — Same Task, Different Queues

**What:** `enrich_review_task` must route to `ai-enrichment-high` (initial sync) or `ai-enrichment-low` (daily incremental). Celery's documented mechanism for this is `apply_async(queue=...)` which takes priority over `CELERY_TASK_ROUTES` at call time.

**Confirmed from Celery docs:** "The routing arguments to `Task.apply_async()` take priority over: Routing attributes on the Task itself; Routes defined in `task_routes`." [CITED: https://docs.celeryq.dev/en/stable/userguide/routing.html]

**Chosen mechanism:** `apply_async(queue=...)` override at the dispatch call site. Rationale: simpler than two task aliases, simpler than a custom router function, no changes to the `enrich_review_task` decorator, and makes the routing decision visible exactly where it is made (in `sync.py` at the dispatch point).

```python
# Source: Celery docs (calling.html + routing.html)
# In apps/reviews/services/sync.py — initial backfill dispatch
enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-high")

# In apps/reviews/services/sync.py — incremental sync dispatch
enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")
```

**CELERY_TASK_ROUTES update:** Remove the existing `"apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment"}` entry. The static route is superseded by the call-site `queue=` parameter. Keep the entry only as a fallback default (`"queue": "ai-enrichment-low"`) so any unguarded `.delay()` call still routes to low priority — a conservative default.

```python
# config/settings/base.py
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    # enrich_review_task falls back to ai-enrichment-low when no queue= override
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.finalize_canonical_tags_task": {"queue": "tag-merge"},
    "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"},
}
CELERY_QUEUE_NAMES = ["google-sync", "ai-enrichment-high", "ai-enrichment-low", "tag-merge", "default"]
```

**Worker `-Q` args update (CLAUDE.md §20, deployment):**
```
# Old: celery -A config worker -Q google-sync,ai-enrichment,default --concurrency=8
# New:
celery -A config worker -Q google-sync,ai-enrichment-high,ai-enrichment-low,tag-merge,default --concurrency=8
```
For production scaling, run separate workers per queue family:
- `ai-enrichment-high` + `ai-enrichment-low` workers: scale on queue depth
- `tag-merge` worker: 1-2 instances (low-frequency, sequential-ish merge jobs)
- `google-sync` worker: separate (no contention with AI)

[CITED: https://docs.celeryq.dev/en/stable/userguide/calling.html]
[CITED: https://docs.celeryq.dev/en/stable/userguide/routing.html]

---

### Pattern 3: Sequential Seed Loop Inside `run_initial_backfill`

**What:** After the Google fetch completes, process the first `SEED_PHASE_SIZE` reviews (newest-first) sequentially — calling `enrich_review()` directly (synchronous, not via `.delay()`), re-querying `get_org_vocabulary` before each one.

**Why synchronous in the task body (not Celery chain):** A Celery chain of N tasks for the seed would work but introduces retry complexity (if one link fails, the entire chain stalls) and makes progress harder to track. Running the seed as a blocking loop in the backfill task body is simpler, naturally sequential, and makes it easy to emit `sync.vocab.progress` events after each review. The `initial_backfill_task` already has a 10-minute hard limit (`CELERY_TASK_TIME_LIMIT = 600`) — 50 reviews × ~2–5s per OpenAI call = 100–250s well within limit.

**Idempotency:** Each `enrich_review()` call checks the three-layer idempotency guard (Redis lock, `select_for_update`, status flag) — if a review is already `SUCCESS`, it exits immediately. Re-running the seed loop on retry is safe.

**Concurrency with bulk:** The seed loop completes before the bulk fan-out starts (sequential code execution). The vocabulary is maximally stable at bulk-start time.

```python
# Source: apps/reviews/services/sync.py pattern (existing sequential fetch loop)
# apps/reviews/services/sync.py — run_initial_backfill (restructured)

def run_initial_backfill(*, shop_id: int) -> dict[str, Any]:
    # Phase 1: Fetch (unchanged — calls fetch_and_persist_reviews)
    fetch_result = fetch_and_persist_reviews(shop_id=shop_id, trigger="initial")
    total_fetched = fetch_result.get("fetched", 0)
    if fetch_result.get("skipped"):
        return fetch_result

    shop = Shop.objects.select_related("organisation").get(pk=shop_id)
    org_id = shop.organisation_id

    # Phase 2: Sequential seed
    seed_ids = list(
        Review.objects.filter(
            shop_id=shop_id,
            deleted_at__isnull=True,
            enrichment_status=Review.EnrichmentStatus.PENDING,
        ).order_by("-review_create_time").values_list("id", flat=True)
        [:settings.SEED_PHASE_SIZE]
    )
    for i, review_id in enumerate(seed_ids, start=1):
        # Global rate limiter check (D-08)
        _wait_for_openai_token(organisation_id=org_id)
        enrich_review(review_id=review_id)  # direct call, not .delay()
        emit_progress_event(shop_id=shop_id, payload={
            "type": "sync.vocab.progress",
            "shop_id": shop_id,
            "enriched": i,
            "total": len(seed_ids),
        })
        write_progress_snapshot(shop_id=shop_id, data={
            "step": "vocab", "vocab_enriched": i, "vocab_total": len(seed_ids), ...
        })

    # Phase 3: Parallel bulk
    bulk_ids = list(
        Review.objects.filter(
            shop_id=shop_id,
            deleted_at__isnull=True,
            enrichment_status=Review.EnrichmentStatus.PENDING,
        ).values_list("id", flat=True)
    )
    for review_id in bulk_ids:
        enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-high")

    # Phase 4: Finalising (dispatched to tag-merge queue)
    finalize_canonical_tags_task.apply_async(
        kwargs={"organisation_id": org_id, "shop_id": shop_id},
        queue="tag-merge",
    )
    return {**fetch_result, "seed_count": len(seed_ids), "bulk_count": len(bulk_ids)}
```

**NOTE on orchestration model:** The above uses fire-and-forget for the bulk phase (tasks dispatch independently) and a separately dispatched finalising task. The finalising task MUST NOT assume all bulk tasks are complete when it starts — it runs on a separate queue and will process whatever is complete. The finalising pass is safe to run at any point after the bulk dispatch because: (1) it only merges existing duplicate labels; (2) the backfill for null `canonical_tag` on stragglers catches any reviews that the bulk phase hasn't finished yet (the finalising task should be dispatched with a reasonable countdown delay, e.g., `countdown=300`). Alternatively, use a Celery chord (group + callback) for stricter sequencing — see Pattern 4 below.

---

### Pattern 4: Celery Chord Alternative for Strict Sequencing

**What:** Use a Celery chord so the finalising task only runs after ALL bulk enrichment tasks complete.

**Trade-off:**
- Chord PROS: strict "bulk done → finalise" ordering; finalising sees complete vocabulary.
- Chord CONS: if any single bulk task permanently fails (max retries exhausted), the chord's error callback fires and the finalising task may not run. Also, chord result tracking requires the `CELERY_RESULT_BACKEND` (already configured on Redis DB 4).

**Recommendation:** Use the fire-and-forget pattern (Pattern 3) with a `countdown=300` delay on `finalize_canonical_tags_task`. The finalising task is idempotent (it can run multiple times safely because merge is idempotent and backfill only touches null rows). If the chord failure-mode risk is unacceptable, use a chord with an error callback that still enqueues the finalising task.

[ASSUMED: chord behaviour when a member task exceeds max_retries — training knowledge, not verified in current Celery 5.4 docs in this session]

---

### Pattern 5: SyncProgressConsumer Extension (2 → 4 Stages)

**What:** Extend the existing consumer to handle two new event types (`sync.vocab.progress`, `sync.finalising.progress`) and update the Redis snapshot schema to carry a `step` discriminator. **No new consumer** (CLAUDE.md §13.2).

**Redis snapshot schema extension:**
```json
{
  "shop_id": 123,
  "status": "fetching | vocab | enriching | finalising | success | failed",
  "step": "fetching | vocab | enriching | finalising | success | failed",
  "fetched": 520,
  "total_estimate": 520,
  "enriched": 0,
  "vocab_enriched": 0,
  "vocab_total": 50,
  "finalising_processed": 0,
  "finalising_total": null,
  "started_at": "...",
  "last_update_at": "...",
  "page_count": 10,
  "duration_seconds": null,
  "error_code": null,
  "error_message": null
}
```

The `step` field is the discriminator for the frontend modal. Existing fields (`fetched`, `enriched`) are preserved unchanged for backward compatibility with the UI during reconnect.

**New event type payloads (CLAUDE.md §13.5 conventions):**

| Event | Fields |
|-------|--------|
| `sync.vocab.progress` | `shop_id, enriched, total` |
| `sync.finalising.progress` | `shop_id, processed, total` |

**Consumer change:** No code changes required to `SyncProgressConsumer` itself — it already broadcasts every event payload via `progress_event`. The change is in `apps/reviews/selectors/sync_progress.py::get_progress_snapshot` which now reads the enriched snapshot schema (backward-compatible: new fields are additive).

**Frontend `SnapshotState` extension** (TypeScript — in `ProgressModal.tsx`):
```typescript
// Source: 23-UI-SPEC.md §TypeScript Interface Extension
step: "fetching" | "vocab" | "enriching" | "finalising" | "success" | "failed";
vocab_enriched?: number;
vocab_total?: number;
finalising_processed?: number;
finalising_total?: number;
```

---

### Pattern 6: Finalising Pass — Case-Insensitive Dedup Without N+1

**What:** Find `OrgCanonicalTag` pairs that are case-insensitive duplicates, merge loser into winner, backfill null `ReviewTag.canonical_tag` stragglers, refresh `review_count` cache.

**Case-insensitive lookup** — use `iexact` or `annotate` with `Lower()`:
```python
# Source: Django ORM docs — iexact lookup (ASSUMED for exact syntax; logic is standard ORM)
# Find all labels that appear more than once when lowercased:
from django.db.models import Lower, Count

dupes = (
    OrgCanonicalTag.objects
    .filter(organisation_id=org_id)
    .annotate(lower_label=Lower("label"))
    .values("lower_label")
    .annotate(count=Count("id"))
    .filter(count__gte=2)
    .values_list("lower_label", flat=True)
)
```

**Merge without N+1 — `update()` batch FK re-point:**
```python
# Source: CLAUDE.md §6.10 bulk_update / F() expressions pattern
# Re-point all ReviewTag FKs for the loser in ONE query
with transaction.atomic():
    # Lock both rows (select_for_update)
    candidates = OrgCanonicalTag.objects.select_for_update().filter(
        organisation_id=org_id,
        label__iexact=lower_label,  # matches both winner and loser
    ).order_by("-review_count", "created_at")
    winner = candidates[0]
    loser = candidates[1]

    # Re-point: one UPDATE, no N+1
    ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)

    # Delete loser
    loser.delete()
```

**`review_count` refresh** — aggregate over `ReviewTag` and write back:
```python
# Source: CLAUDE.md §6.5 annotate + aggregate pattern
from django.db.models import Count

# Compute all counts in ONE query for the org
counts = (
    ReviewTag.objects
    .filter(canonical_tag__organisation_id=org_id)
    .values("canonical_tag_id")
    .annotate(cnt=Count("id"))
)
count_map = {row["canonical_tag_id"]: row["cnt"] for row in counts}

# Bulk-update review_count (CLAUDE.md §6.10)
tags_to_update = []
for tag in OrgCanonicalTag.objects.filter(organisation_id=org_id):
    tag.review_count = count_map.get(tag.pk, 0)
    tags_to_update.append(tag)
OrgCanonicalTag.objects.bulk_update(tags_to_update, ["review_count"])
```

**Backfill null stragglers:**
```python
# Reviews with at least one ReviewTag whose canonical_tag is null
# after the bulk phase completes. For each such tag, re-run
# canonical lookup (the vocabulary is now stable post-seed).
# Use batch processing to avoid unbounded query size.
null_tags = ReviewTag.objects.filter(
    canonical_tag__isnull=True,
    review__organisation_id=org_id,
    review__deleted_at__isnull=True,
).select_related("review").order_by("id")[:500]  # batched

vocab_map = {
    ct.label: ct
    for ct in OrgCanonicalTag.objects.filter(organisation_id=org_id)
}
# For each null tag, attempt case-insensitive label match and assign FK
# This is the "straggler backfill" — it covers tags from the parallel
# bulk phase that proposed new labels that now have OrgCanonicalTag rows.
```

**Important:** The backfill query must be bounded (`:500` batch) and the task must handle the case where no stragglers exist (skip gracefully).

---

### Pattern 7: Beat Schedule for Daily Incremental (DSYNC-01)

The existing `enqueue_incremental_syncs_task` Beat pattern is reused. The only change is that `run_incremental_sync` dispatches enrichment tasks to `ai-enrichment-low` instead of via `.delay()` (which previously defaulted to `ai-enrichment`).

```python
# apps/reviews/services/sync.py — run_incremental_sync
# Change: enrich_review_task.delay(review_id) →
enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")
```

No new Beat schedule entry required. The existing `enqueue_incremental_syncs_task` and `retry_failed_enrichments_task` schedules remain unchanged.

---

### Anti-Patterns to Avoid

- **Blocking the bulk fan-out on the seed loop:** The bulk phase must start AFTER the seed loop completes in code flow, but individual bulk tasks run on workers — never await individual bulk task results in the orchestrator.
- **Incrementing `review_count` in `enrich_review`:** D-03 prohibition. The `_persist_success` block must never touch `review_count`; the finalising task owns count refresh.
- **Using `chord` for seed (sequential) phase:** A chord implies parallel execution. The seed loop must be a plain `for` loop in the task body.
- **Emitting WebSocket events inside `transaction.atomic()`:** Existing anti-pattern already documented in `enrichment.py`. Emit AFTER commit to avoid sending events for rolled-back state.
- **Hard-coding queue names in service modules:** Queue names should come from settings or be constants in `tasks.py`. The `queue=` argument in `apply_async()` is acceptable at call sites in `sync.py` since the routing is a deliberate orchestration decision, not scattered business logic.
- **Running `finalize_canonical_tags_task` without a per-org Redis lock:** Phase 25 will introduce `merge_canonical_tags` on the same `tag-merge` queue. Use `distributed_lock(f"lock:tag_merge:org:{org_id}")` to prevent concurrent finalising + merge tasks.
- **N+1 on the loser FK re-point:** Always use a single `ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)`, never iterate over ReviewTags.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-worker rate limiting | Custom multi-process semaphore | Redis INCR+EXPIRE (same pattern as `increment_google_token_bucket`) | Already proven in this codebase; atomic at the Redis command level |
| Sequential-then-parallel orchestration | Custom future/promise system | Plain for-loop (seed) + `apply_async` group (bulk) | Celery's design; simpler, already understood by this codebase |
| Bulk FK re-point | Loop + individual `save()` | `ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)` | O(1) vs O(n) queries; N+1 blocker per CLAUDE.md §6 |
| Duplicate detection | Full-text similarity / Levenshtein | ORM `iexact` filter + `Lower()` annotation | D-05 explicitly limits to case-insensitive string match only |
| review_count maintenance | Inline increment in hot path | Aggregate on finalize, write via `bulk_update` | D-03 — inline increment double-counts on re-enrichment |
| Task routing to different queues | Two separate task functions | `apply_async(queue=...)` override | Celery's documented mechanism; avoids code duplication |

---

## Common Pitfalls

### Pitfall 1: Seed Loop Blocks Beyond `CELERY_TASK_SOFT_TIME_LIMIT`
**What goes wrong:** If each OpenAI call takes 5s and SEED_PHASE_SIZE=50, the seed loop may take 250s. `CELERY_TASK_SOFT_TIME_LIMIT=300` fires `SoftTimeLimitExceeded` at 5 min, aborting mid-seed.
**Why it happens:** The current soft limit is 300s; 50 × 5s + fetch time can approach this.
**How to avoid:** Either (a) raise `CELERY_TASK_SOFT_TIME_LIMIT` to 600s for `initial_backfill_task` specifically (using Celery's `time_limit` override on the task decorator), or (b) set a reasonable max seed time guard in the loop that breaks and dispatches remaining seed reviews to the bulk phase. Option (a) is simpler.
**Warning signs:** `SoftTimeLimitExceeded` errors in Sentry on `initial_backfill_task`.

### Pitfall 2: Finalising Task Runs Before Bulk Phase Completes
**What goes wrong:** If `finalize_canonical_tags_task` is dispatched immediately after the bulk fan-out, it may run before most bulk tasks complete. The dedup merge sees an incomplete vocabulary. Stragglers backfill is incomplete.
**Why it happens:** Fire-and-forget dispatch; no synchronisation point.
**How to avoid:** Use `countdown=300` (5-minute delay) on the finalising task dispatch. This gives bulk workers time to process. The task is idempotent — it can be re-run manually if needed. For strict ordering, use a Celery chord.
**Warning signs:** `review_count` stays near 0 for many tags after sync completes.

### Pitfall 3: `review_count` Refresh Is a Full-Table Scan
**What goes wrong:** `ReviewTag.objects.filter(canonical_tag__organisation_id=org_id).values("canonical_tag_id").annotate(cnt=Count("id"))` does a sequential scan of `ReviewTag` without proper index support.
**Why it happens:** The `canonical_tag_id` FK on `ReviewTag` has `db_index=True` (from Phase 22 models.py:192), but the composite query joins through `OrgCanonicalTag.organisation_id`. At scale (millions of ReviewTags), this may be slow.
**How to avoid:** Run `EXPLAIN ANALYZE` on the count refresh query during integration testing. If slow, add a composite index `(canonical_tag_id)` on `ReviewTag` and filter by `canonical_tag__in=org_tag_ids` (pre-fetch org tag IDs first) rather than traversing the FK join.
**Warning signs:** Finalising task takes > 30s on a large org.

### Pitfall 4: Case-Insensitive Dedup Produces Transitive Duplicates
**What goes wrong:** "Food Quality" and "food quality" are duplicates. After merging "food quality" → "Food Quality", there may be a third tag "FOOD QUALITY" that now needs to merge. The single-pass dedup misses transitive cycles.
**Why it happens:** The dedup pass processes pairs but not chains.
**How to avoid:** Run the dedup in a loop until no duplicates remain, or sort candidates by `review_count DESC, created_at ASC` and merge all to the winner in one pass (multiple losers → one winner). The query `filter(count__gte=2).values_list("lower_label")` returns ALL lowercase-label groups; process each group by picking the winner and merging all others into it in a single transaction.
**Warning signs:** Duplicate tags persist after finalising.

### Pitfall 5: Token Bucket INCR+EXPIRE Race at Low Redis Latency
**What goes wrong:** Worker A: `INCR` → counter=500. Worker B: `INCR` → counter=501. Both proceed to OpenAI before either calls `EXPIRE`. Both calls succeed but the limit is technically exceeded by 1.
**Why it happens:** INCR and EXPIRE are two separate Redis commands, not atomic together.
**How to avoid:** Accept this small overage (maximum 1 call over the limit per worker pair) as a negligible operational tolerance at 500/min. If strict enforcement is needed, use a Lua script:
```lua
-- Atomic token bucket check-and-increment
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('INCR', key)
if current == 1 then
  redis.call('EXPIRE', key, window)
end
if current > limit then
  return 0  -- rejected
end
return 1  -- allowed
```
**Warning signs:** OpenAI 429 errors despite the token bucket.

### Pitfall 6: Existing `enrich_review_task.delay()` Calls Route to Old Queue
**What goes wrong:** After removing `ai-enrichment` from `CELERY_QUEUE_NAMES` and `CELERY_TASK_ROUTES`, any existing code that calls `enrich_review_task.delay(review_id)` (no `queue=` override) will try to route to a non-existent queue.
**Why it happens:** `retry_failed_enrichments_task` calls `enrich_review_task.delay(review_id)` without a `queue=` parameter (tasks.py line 254).
**How to avoid:** Update the `CELERY_TASK_ROUTES` fallback for `enrich_review_task` to `"ai-enrichment-low"` (not `"ai-enrichment"`). Update `retry_failed_enrichments_task` to use `enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")`. Audit all call sites.
**Warning signs:** Tasks silently dropped or `Invalid queue` broker errors.

### Pitfall 7: Sync Progress Events Emitted From Inside `transaction.atomic()`
**What goes wrong:** If `emit_progress_event()` is called inside a `with transaction.atomic():` block, the event is sent to the WebSocket channel before the DB write commits. If the transaction rolls back, the UI shows progress for state that never actually persisted.
**Why it happens:** Easy to accidentally place inside the atomic block when restructuring `run_initial_backfill`.
**How to avoid:** Follow the existing pattern — `emit_progress_event` is ALWAYS called AFTER the `with transaction.atomic():` block exits (see `_persist_success` in `enrichment.py:176` and `fetch_and_persist_reviews` at line 499). Use `transaction.on_commit()` if the emit must be inside a context that wraps multiple atomic blocks.

---

## Code Examples

### Complete Redis snapshot schema with step discriminator
```python
# Source: apps/reviews/services/progress.py pattern + CONTEXT.md D-02 + 23-UI-SPEC.md
snapshot = {
    "shop_id": shop_id,
    "step": "vocab",          # NEW: "fetching"|"vocab"|"enriching"|"finalising"|"success"|"failed"
    "status": "vocab",        # keep for backward-compat with existing snapshot readers
    "fetched": total_fetched,
    "total_estimate": total_fetched,
    "enriched": 0,            # keeps existing field for bulk phase reuse
    "vocab_enriched": 12,     # NEW
    "vocab_total": 50,        # NEW
    "finalising_processed": None,  # NEW
    "finalising_total": None,      # NEW
    "started_at": started_at.isoformat(),
    "last_update_at": dj_timezone.now().isoformat(),
    "page_count": page_count,
}
write_progress_snapshot(shop_id=shop_id, data=snapshot)
```

### Celery queue split — settings block
```python
# Source: config/settings/base.py pattern (lines 119-195)
# D-09 queue split
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment-low"},   # conservative fallback
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.finalize_canonical_tags_task": {"queue": "tag-merge"},
    "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"},
}
CELERY_QUEUE_NAMES = ["google-sync", "ai-enrichment-high", "ai-enrichment-low", "tag-merge", "default"]
SEED_PHASE_SIZE = env.int("SEED_PHASE_SIZE", default=50)
OPENAI_GLOBAL_RATE_LIMIT = env.int("OPENAI_GLOBAL_RATE_LIMIT", default=500)
```

### finalize_canonical_tags_task skeleton
```python
# Source: apps/reviews/tasks.py pattern (thin wrapper → service)
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def finalize_canonical_tags_task(self, *, organisation_id: int, shop_id: int) -> dict:
    """Finalising pass: dedup, backfill, review_count refresh. Routes to tag-merge queue."""
    from apps.reviews.services.finalise import run_finalise_canonical_tags
    return run_finalise_canonical_tags(organisation_id=organisation_id, shop_id=shop_id)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `ai-enrichment` queue | Three queues: `ai-enrichment-high`, `ai-enrichment-low`, `tag-merge` | Phase 23 | Initial sync enrichment no longer blocked by incremental backlog |
| Per-worker `rate_limit` only | Per-worker `rate_limit` + global Redis token bucket | Phase 23 | True cross-worker OpenAI TPM protection |
| Two-stage sync progress (fetch + enrich) | Four-stage (fetch + vocab + enrich + finalise) | Phase 23 | Vocabulary seeding step visible to user |
| `review_count = 0` (never updated) | `review_count` refreshed by finalising task | Phase 23 | Resolves Phase 22 D-03 deferral |
| `SyncProgressConsumer` handles 2 event types | Handles 4 (adds `sync.vocab.progress`, `sync.finalising.progress`) | Phase 23 | No new consumer; CLAUDE.md §13.2 scope discipline maintained |

**Deprecated/outdated:**
- `"ai-enrichment"` queue name: replaced by `ai-enrichment-high` and `ai-enrichment-low`. Must be removed from `CELERY_QUEUE_NAMES` and all worker `-Q` args in deployment config.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Celery chord failure mode (one member exhausts max_retries) prevents the callback from running — fire-and-forget + countdown preferred | Pattern 4 | If chord callbacks run despite member failure, chord is viable and preferred |
| A2 | INCR+EXPIRE has a sub-1ms race window acceptable for 500/min target | Pattern 1 | If strict enforcement needed, Lua EVAL must replace INCR+EXPIRE |
| A3 | 50 × 5s (max OpenAI latency) = 250s well within raised `time_limit=600s` | Pitfall 1 | If OpenAI latency spikes to 10s+, even 600s is insufficient — SEED_PHASE_SIZE must be reduced |

---

## Open Questions

1. **Chord vs fire-and-forget for bulk → finalising sequencing**
   - What we know: Celery chord requires result backend (configured). fire-and-forget + countdown=300 is simpler.
   - What's unclear: acceptable risk of finalising running before all bulk tasks complete. In practice, at 500/min, 520 bulk reviews take ~1min to enrich, well within 5-minute countdown.
   - Recommendation: Use fire-and-forget + `countdown=300`. Document that a manual re-trigger of `finalize_canonical_tags_task` is always safe.

2. **`CELERY_TASK_TIME_LIMIT` per-task override for `initial_backfill_task`**
   - What we know: Global soft limit is 300s; seed of 50 reviews could take 250s + fetch time.
   - What's unclear: Whether the current production worker actually has time to do a full initial sync of a store with thousands of reviews within 10min hard limit.
   - Recommendation: Set `soft_time_limit=540, time_limit=600` on `initial_backfill_task` decorator specifically. This is already the global limit — just make it explicit on the task.

---

## Environment Availability

This phase is code + configuration changes only. No new external services or tools.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | Token bucket, progress snapshot | ✓ | Existing installation | — |
| Celery | Queue split, new task | ✓ | ^5.4.0 installed | — |
| Django Channels | WebSocket event extension | ✓ | ^4.2.0 installed | — |
| PostgreSQL | Aggregate query for review_count | ✓ | 16.x | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `config/settings/test.py` |
| Quick run command | `pytest apps/reviews/tests/ -x` |
| Full suite command | `pytest apps/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEED-01 | Four progress events emitted in correct order during initial sync | integration | `pytest apps/reviews/tests/test_sync_service.py -k test_initial_backfill_four_step -x` | ❌ Wave 0 |
| SEED-02 | Seed reviews processed sequentially; vocabulary grows per review; bulk reviews not in seed set | unit | `pytest apps/reviews/tests/test_sync_service.py -k test_seed_sequential -x` | ❌ Wave 0 |
| SEED-03 | Bulk reviews dispatched to ai-enrichment-high queue with apply_async | unit | `pytest apps/reviews/tests/test_tasks.py -k test_bulk_queue_routing -x` | ❌ Wave 0 |
| SEED-04 | Finalising task merges case-insensitive dupes; FK re-pointed; review_count refreshed; stragglers backfilled | unit | `pytest apps/reviews/tests/test_finalise_service.py -x` | ❌ Wave 0 |
| DSYNC-01 | Incremental sync dispatches enrichment to ai-enrichment-low | unit | `pytest apps/reviews/tests/test_tasks.py -k test_incremental_queue_routing -x` | ❌ Wave 0 |
| QUEUE-01 | CELERY_TASK_ROUTES contains correct queue assignments; CELERY_QUEUE_NAMES includes all 5 queues | unit | `pytest apps/reviews/tests/test_settings.py -x` | ❌ Wave 0 |
| QUEUE-01 | Global token bucket depleted → enrichment waits/retries | unit | `pytest apps/reviews/tests/test_progress_service.py -k test_openai_token_bucket -x` | ❌ Wave 0 |
| — | No N+1 in finalising pass FK re-point (query-count test) | unit | `pytest apps/reviews/tests/test_finalise_service.py -k test_query_count -x` | ❌ Wave 0 |
| — | WebSocket consumer delivers correct step discriminator on reconnect | integration | `pytest apps/reviews/tests/test_asgi.py -k test_reconnect_step -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/reviews/tests/ -x`
- **Per wave merge:** `pytest apps/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `apps/reviews/tests/test_finalise_service.py` — covers SEED-04 finalising pass, query count, merge correctness
- [ ] `apps/reviews/tests/test_sync_service.py` — extend with four-step initial backfill tests (SEED-01, SEED-02)
- [ ] `apps/reviews/tests/test_tasks.py` — add queue routing assertions (SEED-03, DSYNC-01, QUEUE-01)
- [ ] `apps/reviews/tests/test_progress_service.py` — add OpenAI token bucket tests
- [ ] `apps/reviews/services/finalise.py` — new service file for the finalising pass logic

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes (tenant scoping) | `organisation_id` filter on all OrgCanonicalTag queries; Celery tasks verify org ownership |
| V5 Input Validation | no (no new user input paths) | — |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-org canonical tag merge (finalising task processes wrong org) | Tampering | All OrgCanonicalTag queries filtered by `organisation_id=org_id` (CLAUDE.md §9); `finalize_canonical_tags_task` receives `organisation_id` as explicit arg |
| Replay of `finalize_canonical_tags_task` for wrong org | Elevation of privilege | Per-org Redis lock `lock:tag_merge:org:{org_id}` prevents concurrent merge tasks |
| Token bucket bypass via direct `enrich_review()` call | Tampering | Global bucket check inside `enrich_review` service (not only in task body) |

---

## Sources

### Primary (HIGH confidence)
- `apps/reviews/services/progress.py` — `increment_google_token_bucket` pattern (INCR+EXPIRE); direct codebase read
- `apps/reviews/services/sync.py` — existing `run_initial_backfill`, `fetch_and_persist_reviews`, `emit_progress_event`; direct codebase read
- `apps/reviews/consumers.py` — `SyncProgressConsumer`; direct codebase read
- `apps/reviews/tasks.py` — `enrich_review_task`, `enqueue_incremental_syncs_task`; direct codebase read
- `apps/reviews/services/enrichment.py` — `_persist_success` atomic block, `enrich_review` three-layer idempotency; direct codebase read
- `apps/reviews/selectors/canonical_tags.py` — `get_org_vocabulary`; direct codebase read
- `.planning/phases/23-four-step-initial-sync-seeding-queue-split/23-CONTEXT.md` — all locked decisions D-01..D-10
- `.planning/phases/23-four-step-initial-sync-seeding-queue-split/23-UI-SPEC.md` — WebSocket payload contract, TypeScript interface extension, step labels
- `config/settings/base.py` — CELERY_TASK_ROUTES, CELERY_QUEUE_NAMES, existing queue wiring

### Secondary (MEDIUM confidence)
- [Celery Calling Tasks docs](https://docs.celeryq.dev/en/stable/userguide/calling.html) — `apply_async(queue=...)` override verified
- [Celery Routing Tasks docs](https://docs.celeryq.dev/en/stable/userguide/routing.html) — `apply_async` priority over `task_routes` verified
- [Redis Rate Limiting docs](https://redis.io/docs/latest/develop/use-cases/rate-limiter/) — INCR+EXPIRE pattern and Lua atomicity verified

### Tertiary (LOW confidence)
- [Callr Tech Blog — Redis Lua rate limiting](https://blog.callr.tech/rate-limiting-for-distributed-systems-with-redis-and-lua/) — Lua script pattern; useful as cross-reference for Pitfall 5 Lua alternative

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing packages, verified in codebase
- Architecture (queue routing, token bucket): HIGH — verified against Celery docs and existing codebase patterns
- Architecture (chord vs fire-and-forget): MEDIUM — chord failure mode is [ASSUMED] from training knowledge
- Pitfalls: HIGH — derived from existing code patterns and direct codebase analysis
- Frontend (ProgressModal extension): HIGH — verified against 23-UI-SPEC.md and existing ProgressModal.tsx

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (stable stack; Celery + Redis patterns are long-lived)
