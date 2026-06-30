# Phase 23: Four-Step Initial Sync, Seeding & Queue Split — Pattern Map

**Mapped:** 2026-06-10
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/reviews/services/progress.py` | service / utility | event-driven, Redis I/O | same file (extend) | exact |
| `apps/reviews/services/sync.py` | service / orchestrator | batch, event-driven | same file (extend) | exact |
| `apps/reviews/services/finalise.py` | service | batch, CRUD | `apps/reviews/services/enrichment.py` | role-match |
| `apps/reviews/selectors/canonical_tags.py` | selector | CRUD | same file (extend) | exact |
| `apps/reviews/tasks.py` | task / thin wrapper | event-driven | same file (extend) | exact |
| `config/settings/base.py` | config | — | same file (extend) | exact |
| `apps/reviews/consumers.py` | consumer | event-driven | same file (no change) | exact |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | component | event-driven, WebSocket | same file (extend) | exact |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | component | event-driven, WebSocket | same file (extend) | exact |
| `apps/reviews/tests/test_finalise_service.py` | test | — | `apps/reviews/tests/test_enrichment_service.py` | role-match |

---

## Pattern Assignments

### `apps/reviews/services/progress.py` (service/utility, Redis I/O) — extend

**Analog:** same file

**Imports pattern** (lines 23-29):
```python
from __future__ import annotations

import json
from typing import Any

from django_redis import get_redis_connection
```

**Existing token-bucket keys and constants** (lines 39-42):
```python
GOOGLE_BUCKET_KEY = "rate:google:project"
GOOGLE_BUCKET_WINDOW_SECONDS = 60
GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE = 1800
```

**Core INCR+EXPIRE pipeline pattern** — `increment_google_token_bucket` (lines 176-186):
```python
def increment_google_token_bucket(*, count: int = 1) -> int:
    """Increment the global Google API counter; refresh expiry to 60s window.

    Returns the new counter value.
    """
    conn = get_redis_connection("default")
    pipe = conn.pipeline()
    pipe.incrby(GOOGLE_BUCKET_KEY, count)
    pipe.expire(GOOGLE_BUCKET_KEY, GOOGLE_BUCKET_WINDOW_SECONDS)
    new_value, _ = pipe.execute()
    return int(new_value)
```

**Depletion check pattern** — `token_bucket_depleted` (lines 189-198):
```python
def token_bucket_depleted(*, max_calls: int = GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE) -> bool:
    """Return True when the rolling 60-second counter is at/above the cap."""
    conn = get_redis_connection("default")
    raw = conn.get(GOOGLE_BUCKET_KEY)
    if raw is None:
        return False
    try:
        return int(raw) >= max_calls
    except (TypeError, ValueError):
        return False
```

**Per-shop counter pattern** — `increment_enriched_counter` (lines 106-119):
```python
def increment_enriched_counter(*, shop_id: int) -> int:
    conn = get_redis_connection("default")
    key = ENRICHED_COUNTER_KEY_TMPL.format(shop_id=shop_id)
    pipe = conn.pipeline()
    pipe.incr(key)
    pipe.expire(key, TTL_ACTIVE_SECONDS)
    new_value, _ = pipe.execute()
    return int(new_value)
```

**New additions to copy from these patterns:**
- Add `OPENAI_BUCKET_KEY_TMPL = "rate:openai:org:{organisation_id}"` (per CLAUDE.md §7.7 key convention)
- Add `OPENAI_BUCKET_WINDOW_SECONDS = 60`
- Add `increment_openai_token_bucket(*, organisation_id: int) -> int` — same INCR+EXPIRE pipeline as `increment_google_token_bucket`
- Add `openai_token_bucket_depleted(*, organisation_id: int, max_calls: int) -> bool` — same shape as `token_bucket_depleted`
- Add `VOCAB_COUNTER_KEY_TMPL = "sync:vocab:{shop_id}"` and `BULK_COUNTER_KEY_TMPL = "sync:bulk:{shop_id}"` for per-phase enriched counters (same pattern as `ENRICHED_COUNTER_KEY_TMPL`)
- Add `increment_vocab_counter(*, shop_id: int) -> int` and `increment_bulk_counter(*, shop_id: int) -> int` — same `incr + expire` pipeline shape
- Update `clear_progress_snapshot` (lines 77-85) to also delete the new `sync:vocab:{shop_id}` and `sync:bulk:{shop_id}` counter keys

---

### `apps/reviews/services/sync.py` (service/orchestrator, batch + event-driven) — extend

**Analog:** same file

**Imports pattern** (lines 19-50):
```python
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction
from django.utils import timezone as dj_timezone

from apps.common.locks import distributed_lock
from apps.reviews.services.progress import (
    bulk_increment_enriched_counter,
    clear_progress_snapshot,
    increment_google_token_bucket,
    token_bucket_depleted,
    write_progress_snapshot,
)
```

**Progress event emission pattern** — `emit_progress_event` (lines 93-106):
```python
def emit_progress_event(*, shop_id: int, payload: dict[str, Any]) -> None:
    """Send a progress event to the SyncProgressConsumer group.

    Safe to call from Celery prefork workers — async_to_sync creates a new
    event loop per call. Must NOT be called inside transaction.atomic() — emit
    AFTER commit to avoid sending events for rolled-back state.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"sync-progress-{shop_id}",
        {"type": "progress.event", "payload": payload},
    )
```

**Progress snapshot write pattern** (lines 449-468):
```python
snapshot = {
    "shop_id": shop_id,
    "status": "fetching",
    "fetched": total_persisted,
    "total_estimate": progress_total,
    "enriched": 0,
    "started_at": started_at.isoformat(),
    "last_update_at": dj_timezone.now().isoformat(),
    "page_count": page_count,
}
write_progress_snapshot(shop_id=shop_id, data=snapshot)
emit_progress_event(
    shop_id=shop_id,
    payload={
        "type": "sync.fetch.progress",
        "shop_id": shop_id,
        "fetched": total_persisted,
        "total_estimate": progress_total,
    },
)
```

**Existing thin orchestrators** (lines 562-569):
```python
def run_initial_backfill(*, shop_id: int) -> dict[str, Any]:
    """Initial backfill — same engine, trigger="initial"."""
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="initial")


def run_incremental_sync(*, shop_id: int) -> dict[str, Any]:
    """6-hour incremental sync — same engine, trigger="incremental"."""
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="incremental")
```

**Existing enrich dispatch inside fetch loop** (lines 444-447):
```python
for review_id in pending_ids:
    enrich_review_task.delay(review_id)
```

**New additions:**
- `run_initial_backfill` is rewritten to a 4-phase orchestrator: fetch → seed loop → bulk dispatch → finalise dispatch
- Seed loop calls `enrich_review(review_id=review_id)` directly (not via `.delay()`), preceded by a token-bucket guard
- Bulk dispatch uses `enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-high")`
- Finalise dispatch uses `finalize_canonical_tags_task.apply_async(kwargs={...}, queue="tag-merge", countdown=300)`
- `run_incremental_sync` dispatch site changes from `.delay(review_id)` → `.apply_async(args=[review_id], queue="ai-enrichment-low")`
- New event types `sync.vocab.progress` and `sync.finalising.progress` emitted with same `emit_progress_event` function (unchanged)
- Snapshot `status` field extended to carry new step values: `"vocab"`, `"enriching"`, `"finalising"` alongside existing `"fetching"`, `"success"`, `"failed"`
- The existing token-bucket check before Google API pages (lines 374-381) is the pattern to copy for the OpenAI bucket guard before each seed iteration

---

### `apps/reviews/services/finalise.py` (service, batch CRUD) — NEW FILE

**Analog:** `apps/reviews/services/enrichment.py`

**Module docstring and imports pattern** (lines 1-48 of enrichment.py):
```python
"""Phase 23 — Canonical tag finalising pass.

run_finalise_canonical_tags(organisation_id, shop_id) — dedup, backfill, count-refresh.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.db.models import Count, Lower
from django.utils import timezone as dj_timezone

from apps.common.locks import distributed_lock
from apps.reviews.models import OrgCanonicalTag, ReviewTag
from apps.reviews.services.progress import write_progress_snapshot
from apps.reviews.services.sync import emit_progress_event

logger = logging.getLogger(__name__)

LOCK_KEY_TMPL = "lock:tag_merge:org:{organisation_id}"
LOCK_TIMEOUT_SECONDS = 300
```

**Distributed lock pattern** — `enrich_review` (lines 460-463 of enrichment.py):
```python
lock_key = LOCK_KEY_TMPL.format(review_id=review_id)
with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
    if not acquired:
        logger.info("enrich_review_lock_held review_id=%s", review_id)
        return
```

**transaction.atomic + select_for_update pattern** — `enrich_review` / `_persist_success` (lines 92-93 of enrichment.py):
```python
with transaction.atomic():
    Review.objects.filter(pk=review.pk).update(...)
```

**Bulk FK re-point (one UPDATE, no N+1)** — copy from CLAUDE.md §6.10 and RESEARCH.md Pattern 6:
```python
# Re-point all ReviewTag FKs for the loser in ONE query (no N+1)
ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)
```

**Aggregate + bulk_update pattern for review_count refresh** — CLAUDE.md §6.5 + §6.10:
```python
from django.db.models import Count

counts = (
    ReviewTag.objects
    .filter(canonical_tag__organisation_id=org_id)
    .values("canonical_tag_id")
    .annotate(cnt=Count("id"))
)
count_map = {row["canonical_tag_id"]: row["cnt"] for row in counts}
tags_to_update = []
for tag in OrgCanonicalTag.objects.filter(organisation_id=org_id):
    tag.review_count = count_map.get(tag.pk, 0)
    tags_to_update.append(tag)
OrgCanonicalTag.objects.bulk_update(tags_to_update, ["review_count"])
```

**Error handling / raise pattern** — `_persist_failure` (lines 302-331 of enrichment.py):
```python
def _persist_failure(*, review: Review, usage_data: dict[str, Any] | None, exc: Exception) -> None:
    """Write FAILED state + AiUsageLog row. ENRCH-04 + ENRCH-05."""
    usage = usage_data or {}
    with transaction.atomic():
        Review.objects.filter(pk=review.pk).update(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            ...
        )
```

**Emit-AFTER-commit pattern** (lines 175-176 of enrichment.py):
```python
    # AFTER commit: emit progress event for the live ProgressModal.
    _emit_enrichment_progress(review=review)
```

---

### `apps/reviews/selectors/canonical_tags.py` (selector, CRUD) — extend

**Analog:** same file

**Full current file** (lines 1-23):
```python
"""Phase 22 — Canonical tag selectors (read-only query helpers)."""

from __future__ import annotations

from apps.reviews.models import OrgCanonicalTag


def get_org_vocabulary(*, organisation_id: int, limit: int) -> list[str]:
    """Return the org's top-N canonical labels ordered by ``-review_count``."""
    return list(
        OrgCanonicalTag.objects.filter(organisation_id=organisation_id)
        .order_by("-review_count")
        .values_list("label", flat=True)[:limit]
    )
```

**New selector additions:**
- `get_duplicate_canonical_tag_groups(*, organisation_id: int) -> list[str]` — returns lowercase labels with count ≥ 2, using `annotate(lower_label=Lower("label")).values("lower_label").annotate(count=Count("id")).filter(count__gte=2)`. Follows the same selector pattern: no mutations, returns a bounded list.
- `get_null_straggler_review_tags(*, organisation_id: int, limit: int) -> QuerySet` — returns `ReviewTag.objects.filter(canonical_tag__isnull=True, review__organisation_id=organisation_id, review__deleted_at__isnull=True).select_related("review").order_by("id")[:limit]`. Same shape: bounded selector, no writes.

---

### `apps/reviews/tasks.py` (task/thin wrapper, event-driven) — extend

**Analog:** same file

**Shared task decorator pattern with retry** (lines 43-50):
```python
@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
```

**Task body pattern: log, call service, log result** (lines 51-91 for `initial_backfill_task`):
```python
def initial_backfill_task(self: Any, shop_id: int) -> dict[str, Any]:
    """Initial historical review backfill for a shop, dispatched after OAuth."""
    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "initial_backfill_task.start task_id=%s shop_id=%s attempt=%s",
        task_id, shop_id, attempt,
    )
    try:
        result = run_initial_backfill(shop_id=shop_id)
    except Exception as exc:
        logger.error(
            "initial_backfill_task.error task_id=%s shop_id=%s ...",
            ...
            exc_info=True,
        )
        raise
    ...
    return result
```

**Fan-out task with apply_async + jitter** (lines 145-166 for `enqueue_incremental_syncs_task`):
```python
@shared_task  # type: ignore[misc]
def enqueue_incremental_syncs_task() -> int:
    from apps.shops.models import Shop
    shop_ids = list(Shop.objects.filter(...).values_list("id", flat=True))
    for shop_id in shop_ids:
        countdown = random.uniform(0, INCREMENTAL_JITTER_SECONDS_MAX)  # nosec B311  # noqa: S311
        sync_shop_reviews_task.apply_async(args=[shop_id], countdown=countdown)
    ...
    return len(shop_ids)
```

**Deferred model import pattern** (line 425 of sync.py, line 196 of tasks.py):
```python
from apps.reviews.tasks import enrich_review_task  # inside function body
```

**New additions:**
- Add `finalize_canonical_tags_task` following same decorator + log + service call pattern. Use `retry_backoff=60` (longer than 30s default since this is a finalising pass, not a hot-path task).
- Update `retry_failed_enrichments_task` (line 254): change `enrich_review_task.delay(review_id)` → `enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")`.
- Update `enrich_review_task` decorator: the `rate_limit=settings.ENRICHMENT_RATE_LIMIT` stays; add `soft_time_limit` override on `initial_backfill_task` decorator (540s).

---

### `config/settings/base.py` (config) — extend

**Analog:** same file

**Existing Celery routes block** (lines 119-126):
```python
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment"},
    "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"},
}
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 300
```

**Existing queue names list** (line 195):
```python
CELERY_QUEUE_NAMES = ["google-sync", "ai-enrichment", "default"]
```

**Existing configurable-knob pattern** (lines 171-185):
```python
INITIAL_SYNC_PAGE_SIZE = env.int("INITIAL_SYNC_PAGE_SIZE", default=50)
ENRICHMENT_BATCH_SIZE = env.int("ENRICHMENT_BATCH_SIZE", default=10)
INCREMENTAL_SYNC_INTERVAL_HOURS = env.int("INCREMENTAL_SYNC_INTERVAL_HOURS", default=6)
INCREMENTAL_SYNC_JITTER_MINUTES = env.int("INCREMENTAL_SYNC_JITTER_MINUTES", default=30)
CANONICAL_VOCAB_INJECT_LIMIT = env.int("CANONICAL_VOCAB_INJECT_LIMIT", default=200)
ENRICHMENT_RATE_LIMIT = env("ENRICHMENT_RATE_LIMIT", default="125/m")
```

**New additions following these patterns:**
```python
# Phase 23 queue split
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    # conservative fallback — explicit queue= overrides this at call site
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.finalize_canonical_tags_task": {"queue": "tag-merge"},
    "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"},
}
CELERY_QUEUE_NAMES = ["google-sync", "ai-enrichment-high", "ai-enrichment-low", "tag-merge", "default"]

# Phase 23 new knobs (D-04, D-08)
SEED_PHASE_SIZE = env.int("SEED_PHASE_SIZE", default=50)
OPENAI_GLOBAL_RATE_LIMIT = env.int("OPENAI_GLOBAL_RATE_LIMIT", default=500)
```

---

### `apps/reviews/consumers.py` (consumer, event-driven) — NO CHANGE

**Analog:** same file

The `SyncProgressConsumer` requires no code changes. The consumer already broadcasts any event payload via `progress_event` (line 44-45):

```python
async def progress_event(self, event: dict[str, Any]) -> None:
    await self.send_json(event["payload"])
```

The two new event types (`sync.vocab.progress`, `sync.finalising.progress`) are emitted from the backend and will flow through unchanged. The only change needed is in `apps/reviews/selectors/sync_progress.py::get_progress_snapshot` — it reads from Redis and now returns the extended snapshot schema with `step` and new counters. The `get_progress_snapshot` function itself (lines 14-31) requires no code changes; it is a pass-through that forwards whatever is in Redis.

---

### `frontend/src/widgets/review-management/ProgressModal.tsx` (component, WebSocket event-driven) — extend

**Analog:** same file

**Existing SnapshotState interface** (lines 5-17):
```typescript
interface SnapshotState {
  shop_id: number;
  status: "fetching" | "enriching" | "success" | "failed";
  fetched: number;
  total_estimate: number | null;
  enriched: number;
  started_at: string;
  last_update_at: string;
  page_count: number;
  duration_seconds?: number | null;
  error_code?: string | null;
  error_message?: string | null;
}
```

**New fields to add** (source: 23-UI-SPEC.md §TypeScript Interface Extension):
```typescript
step: "fetching" | "vocab" | "enriching" | "finalising" | "success" | "failed";
vocab_enriched?: number;
vocab_total?: number;
finalising_processed?: number;
finalising_total?: number;
```

**Existing onmessage event handler pattern** (lines 58-126):
```typescript
ws.onmessage = (ev) => {
  try {
    const data = JSON.parse(ev.data);
    if (data.type === "sync.fetch.progress") {
      setSnapshot((prev) => prev ? { ...prev, fetched: data.fetched, ... } : { ... });
    } else if (data.type === "sync.enrichment.progress") {
      setSnapshot((prev) => prev ? { ...prev, enriched: data.enriched, ... } : null);
    } else if (data.type === "sync.complete") {
      setSnapshot((prev) => prev ? { ...prev, status: "success", ... } : null);
    } else if (data.type === "sync.error") {
      setSnapshot((prev) => ({ ...defaults }));
    } else if (typeof data.status === "string") {
      // Initial snapshot from consumer.connect
      setSnapshot(data as SnapshotState);
    }
  } catch {
    // ignore malformed messages
  }
};
```

**New cases to add following this same pattern:**
```typescript
} else if (data.type === "sync.vocab.progress") {
  setSnapshot((prev) =>
    prev ? { ...prev, step: "vocab", vocab_enriched: data.enriched, vocab_total: data.total }
         : null
  );
} else if (data.type === "sync.finalising.progress") {
  setSnapshot((prev) =>
    prev ? { ...prev, step: "finalising", finalising_processed: data.processed, finalising_total: data.total }
         : null
  );
```

**Existing progress bar JSX pattern** (lines 254-293) — the fetch section:
```tsx
<div>
  <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
    Fetched from Google
  </label>
  <div className="text-[14px] font-semibold text-ink mt-1">
    {hasDeterminate ? <>{fetched} of ~{total}</> : <>{fetched} fetched</>}
  </div>
  <div
    className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
    role="progressbar"
    aria-valuenow={hasDeterminate ? fetchPct : undefined}
    aria-valuemin={0}
    aria-valuemax={hasDeterminate ? 100 : undefined}
    aria-label={...}
  >
    {hasDeterminate ? (
      <div className="h-full bg-yellow rounded-full transition-all" style={{ width: `${fetchPct}%` }} />
    ) : (
      <div className="h-full w-1/3 bg-yellow rounded-full animate-pulse" />
    )}
  </div>
</div>
```

**New steps 2–4 follow this exact JSX structure** with differences:
- Step 2 ("Building Tag Vocabulary"): `bg-green`, counter `vocab_enriched / vocab_total`, hint "Seeding vocabulary…" when `vocab_enriched === 0`
- Step 3 ("Analysing with Review Bee AI Engine"): existing AI section, label unchanged, now uses `step === "enriching"` to determine active state
- Step 4 ("Finalising"): `bg-amber`, counter `finalising_processed / finalising_total`, hint "Deduplicating tags…" when `finalising_processed === 0`

**Pending step visual** (source: 23-UI-SPEC.md — steps not yet started):
```tsx
{/* pending state — step not yet started */}
<div className="opacity-60">
  <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
    {stepLabel}
  </label>
  <div className="text-[14px] text-muted mt-1">–</div>
  <div className="w-full h-2 bg-line rounded-full mt-2" role="progressbar" aria-label="{stepName}: not started" />
</div>
```

---

### `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` (component, WebSocket event-driven) — extend

**Analog:** same file

**Existing SyncingShop interface** (lines 6-9):
```typescript
interface SyncingShop {
  shop_id: number;
  shop_name: string;
  stage?: "fetching" | "enriching";
}
```

**Extend `stage` union** (source: 23-UI-SPEC.md):
```typescript
stage?: "fetching" | "vocab" | "enriching" | "finalising";
```

**Existing onmessage event handler for stage update** (lines 76-92):
```typescript
ws.onmessage = (ev) => {
  try {
    const data = JSON.parse(ev.data);
    if (data.type === "sync.enrichment.progress") {
      setActive((prev) => prev.map((s) =>
        s.shop_id === shop.shop_id ? { ...s, stage: "enriching" } : s
      ));
    } else if (data.type === "sync.fetch.progress") {
      setActive((prev) => prev.map((s) =>
        s.shop_id === shop.shop_id && s.stage !== "enriching"
          ? { ...s, stage: "fetching" }
          : s
      ));
    }
```

**New cases to add following this pattern:**
```typescript
} else if (data.type === "sync.vocab.progress") {
  setActive((prev) => prev.map((s) =>
    s.shop_id === shop.shop_id ? { ...s, stage: "vocab" } : s
  ));
} else if (data.type === "sync.finalising.progress") {
  setActive((prev) => prev.map((s) =>
    s.shop_id === shop.shop_id ? { ...s, stage: "finalising" } : s
  ));
```

**Existing sub-label + icon color switch** (lines 187-193):
```typescript
const isEnriching = s.stage === "enriching";
const subLabel = isEnriching
  ? "Analysing reviews with AI…"
  : "Fetching reviews from Google…";
const iconColorClass = isEnriching ? "text-green" : "text-yellow";
```

**Replace with four-stage switch** (source: 23-UI-SPEC.md):
```typescript
const stageLabels: Record<string, string> = {
  fetching: "Fetching reviews from Google…",
  vocab: "Building tag vocabulary…",
  enriching: "Analysing reviews with AI…",
  finalising: "Finalising…",
};
const stageColors: Record<string, string> = {
  fetching: "text-yellow",
  vocab: "text-green",
  enriching: "text-green",
  finalising: "text-amber",
};
const subLabel = stageLabels[s.stage ?? "fetching"] ?? "Fetching reviews from Google…";
const iconColorClass = stageColors[s.stage ?? "fetching"] ?? "text-yellow";
```

---

### `apps/reviews/tests/test_finalise_service.py` (test) — NEW FILE

**Analog:** `apps/reviews/tests/test_enrichment_service.py` + `apps/reviews/tests/test_progress_service.py`

**Test file header pattern** (from test_enrichment_service.py):
```python
"""Phase 23 — Tests for the canonical tag finalising pass service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.reviews.services.finalise import run_finalise_canonical_tags
from apps.reviews.models import OrgCanonicalTag, ReviewTag
from apps.reviews.tests.factories import ReviewFactory, ReviewTagFactory

pytestmark = pytest.mark.django_db
```

**FakeRedis test helper pattern** (from test_progress_service.py, lines 24-60):
```python
class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def delete(self, *keys: str) -> int: ...
    def pipeline(self): ...
```

**Query-count assertion pattern** (from CLAUDE.md §6.9):
```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_finalise_fk_repoint_no_n_plus_one() -> None:
    ...
    with CaptureQueriesContext(connection) as ctx:
        run_finalise_canonical_tags(organisation_id=org.pk, shop_id=shop.pk)
    # FK re-point is 1 UPDATE regardless of how many ReviewTags are repointed
    update_queries = [q for q in ctx.captured_queries if "UPDATE" in q["sql"].upper()]
    assert len(update_queries) <= 5  # fixed ceiling, not proportional to ReviewTag count
```

**Test categories required (from RESEARCH.md §Validation Architecture):**
- `test_dedup_case_insensitive_merge_winner` — SEED-04: merge winner = higher review_count (tie → earliest created)
- `test_dedup_fk_repointed_to_winner` — SEED-04: loser's ReviewTag FKs re-pointed in 1 UPDATE
- `test_dedup_loser_deleted` — SEED-04: loser OrgCanonicalTag row deleted
- `test_backfill_null_straggler_tags` — SEED-04: null canonical_tag stragglers resolved
- `test_review_count_refreshed` — SEED-04: review_count bulk-updated from aggregate
- `test_no_op_when_no_duplicates` — idempotency check
- `test_finalise_fk_repoint_no_n_plus_one` — query-count test (CLAUDE.md §6.9)

---

## Shared Patterns

### Redis Pipeline Pattern
**Source:** `apps/reviews/services/progress.py` lines 176-186 (`increment_google_token_bucket`)
**Apply to:** `apps/reviews/services/progress.py` new `increment_openai_token_bucket`, `increment_vocab_counter`, `increment_bulk_counter`
```python
conn = get_redis_connection("default")
pipe = conn.pipeline()
pipe.incrby(key, count)
pipe.expire(key, WINDOW_SECONDS)
new_value, _ = pipe.execute()
return int(new_value)
```

### Distributed Lock + Early Return
**Source:** `apps/reviews/services/enrichment.py` lines 460-464
**Apply to:** `apps/reviews/services/finalise.py` (per-org lock: `lock:tag_merge:org:{organisation_id}`)
```python
with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
    if not acquired:
        logger.info("lock_held reason=...")
        return
```

### transaction.atomic + select_for_update
**Source:** `apps/reviews/services/enrichment.py` lines 92-93, 470-478
**Apply to:** `apps/reviews/services/finalise.py` — each `(winner, loser)` merge pair runs inside `transaction.atomic()` with `select_for_update()` on the candidate set
```python
with transaction.atomic():
    candidates = OrgCanonicalTag.objects.select_for_update().filter(
        organisation_id=org_id, label__iexact=lower_label
    ).order_by("-review_count", "created_at")
```

### Emit AFTER transaction.atomic Commits
**Source:** `apps/reviews/services/enrichment.py` line 175-176 ("AFTER commit: emit progress event")
**Apply to:** `apps/reviews/services/finalise.py` — `sync.finalising.progress` and `sync.complete` events emitted AFTER the atomic block exits
```python
# AFTER commit: emit progress event for the live ProgressModal.
emit_progress_event(shop_id=shop_id, payload={"type": "sync.finalising.progress", ...})
```

### Thin Celery Task Wrapper
**Source:** `apps/reviews/tasks.py` lines 43-91 (`initial_backfill_task`)
**Apply to:** `apps/reviews/tasks.py` new `finalize_canonical_tags_task`
```python
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,   # longer for a non-hot-path finalising task
    retry_backoff_max=600,
    retry_jitter=True,
)
def finalize_canonical_tags_task(self: Any, *, organisation_id: int, shop_id: int) -> dict:
    from apps.reviews.services.finalise import run_finalise_canonical_tags
    task_id = self.request.id
    logger.info("finalize_canonical_tags_task.start task_id=%s org_id=%s shop_id=%s",
                task_id, organisation_id, shop_id)
    return run_finalise_canonical_tags(organisation_id=organisation_id, shop_id=shop_id)
```

### apply_async Queue Override
**Source:** `apps/reviews/tasks.py` line 161 (`sync_shop_reviews_task.apply_async(args=[shop_id], countdown=countdown)`)
**Apply to:** `apps/reviews/services/sync.py` all new dispatch sites
```python
# Initial sync bulk phase → high priority queue
enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-high")

# Finalising task → tag-merge queue with countdown
finalize_canonical_tags_task.apply_async(
    kwargs={"organisation_id": org_id, "shop_id": shop_id},
    queue="tag-merge",
    countdown=300,
)

# Incremental sync → low priority queue
enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")
```

### Configurable Setting with env.int Default
**Source:** `config/settings/base.py` lines 171-185
**Apply to:** `config/settings/base.py` new `SEED_PHASE_SIZE` and `OPENAI_GLOBAL_RATE_LIMIT`
```python
SEED_PHASE_SIZE = env.int("SEED_PHASE_SIZE", default=50)
OPENAI_GLOBAL_RATE_LIMIT = env.int("OPENAI_GLOBAL_RATE_LIMIT", default=500)
```

### TypeScript onmessage Event Handler (additive case)
**Source:** `frontend/src/widgets/review-management/ProgressModal.tsx` lines 58-126
**Apply to:** both `ProgressModal.tsx` and `TopbarSyncIndicator.tsx` new event type cases
```typescript
} else if (data.type === "sync.vocab.progress") {
  setSnapshot((prev) =>
    prev ? { ...prev, step: "vocab", vocab_enriched: data.enriched, vocab_total: data.total }
         : null
  );
```

---

## No Analog Found

All 10 files have strong codebase analogs. No file requires falling back to RESEARCH.md external patterns alone.

| File | Role | Data Flow | Notes |
|------|------|-----------|-------|
| `apps/reviews/services/finalise.py` | service | batch CRUD | New file, no prior finalising service, but `enrichment.py` provides exact structural analog (lock + atomic + emit-after-commit) |

---

## Metadata

**Analog search scope:** `apps/reviews/services/`, `apps/reviews/tasks.py`, `apps/reviews/consumers.py`, `apps/reviews/selectors/`, `apps/reviews/tests/`, `config/settings/base.py`, `frontend/src/widgets/review-management/`
**Files scanned:** 14 source files read directly
**Pattern extraction date:** 2026-06-10
