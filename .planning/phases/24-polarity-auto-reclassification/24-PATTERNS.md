# Phase 24: Polarity Auto-Reclassification - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 6 new/modified files
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/reviews/services/reclassify.py` | service | batch / CRUD | `apps/reviews/services/finalise.py` (`_refresh_review_counts`) | exact |
| `apps/reviews/tasks.py` | task (thin wrapper) | batch | `apps/reviews/tasks.py` (`enqueue_incremental_syncs_task`, `retry_failed_enrichments_task`) | exact |
| `apps/reviews/migrations/0012_periodic_task_seed_polarity_reclassify.py` | migration (data) | — | `apps/reviews/migrations/0002_periodic_tasks_seed.py` | exact |
| `apps/reviews/migrations/0012_orgcanonicaltag_polarity_reclassified_at.py` | migration (schema) | — | `apps/reviews/migrations/0011_orgcanonicaltag_reviewtag_canonical_tag.py` | role-match |
| `config/settings/base.py` | config | — | same file, existing `SEED_PHASE_SIZE` / `OPENAI_GLOBAL_RATE_LIMIT` block | exact |
| `apps/reviews/tests/test_reclassify_service.py` | test | batch | `apps/reviews/tests/test_enrichment_service.py` + `test_finalise.py` | exact |

> The migration numbering depends on ordering: if `polarity_reclassified_at` schema migration comes first it is `0012` and the Beat seed is `0013`. The pattern is identical either way; the planner must confirm the sequence.

---

## Pattern Assignments

### `apps/reviews/services/reclassify.py` (service, batch)

**Analog:** `apps/reviews/services/finalise.py`

**Imports pattern** (lines 1-38 of `finalise.py`):
```python
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import OrgCanonicalTag, ReviewTag

logger = logging.getLogger(__name__)
```

**No-N+1 grouped aggregate — core pattern** (`finalise.py` lines 285-307, `_refresh_review_counts`):
```python
# Analog: one aggregate query, values+annotate, result iterated in Python
counts = (
    ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id)
    .values("canonical_tag_id")
    .annotate(cnt=Count("id"))
)
count_map: dict[int, int] = {row["canonical_tag_id"]: row["cnt"] for row in counts}
```

**Phase 24 adaptation** — two-dimension values (add `polarity`) and cross-org (no `organisation_id` filter in the aggregate; candidate pre-filter restricts the `canonical_tag_id__in=` set):
```python
rows = list(
    ReviewTag.objects.filter(
        canonical_tag_id__in=candidate_map.keys(),
        review__review_create_time__gte=cutoff,
        review__deleted_at__isnull=True,
    )
    .values("canonical_tag_id", "polarity")
    .annotate(cnt=Count("id"))
)
```

**`bulk_update` pattern** (`finalise.py` lines 301-306):
```python
if tags_to_update:
    OrgCanonicalTag.objects.bulk_update(tags_to_update, ["review_count"])
```
Phase 24 copies this exactly, replacing `["review_count"]` with `["polarity_type"]` (and optionally `["polarity_type", "polarity_reclassified_at"]`). MUST NOT include `review_count` in the field list (D-03 Phase 22).

**`transaction.atomic` + `select_for_update` pattern** (`finalise.py` lines 202-231, `_merge_group`):
```python
with transaction.atomic():
    candidates = list(
        OrgCanonicalTag.objects.select_for_update()
        .filter(...)
        .order_by(...)
    )
```
Phase 24 uses `@transaction.atomic` on `_flip_and_audit` (decorator form rather than context-manager form — both are present in the codebase; decorator is cleaner for a function-scoped transaction). No `select_for_update` needed here because `bulk_update` is the sole writer for `polarity_type`.

**AuditLog `bulk_create` pattern** — derived from `lifecycle.py` single-create convention scaled to batch:
```python
# lifecycle.py lines 80-96: single AuditLog.objects.create() — adapt to bulk_create
AuditLog.objects.create(
    organisation_id=organisation_id,
    actor=actor if getattr(actor, "is_authenticated", False) else None,
    entity_type="action_item",
    entity_id=str(item.pk),
    action="action_item.created",
    before_data={},
    after_data={...},
)
# Phase 24: build a list, call bulk_create once
AuditLog.objects.bulk_create(audit_rows)
```

**Structured logger calls** (`finalise.py` lines 178-185, 276-281):
```python
logger.info(
    "run_finalise_canonical_tags.done organisation_id=%s shop_id=%s "
    "merged_groups=%s stragglers_backfilled=%s",
    organisation_id,
    shop_id,
    merged_groups,
    stragglers_backfilled,
)
logger.debug(
    "_refresh_review_counts organisation_id=%s tags_updated=%s",
    organisation_id,
    len(tags_to_update),
)
```
Phase 24 copies the `"service_function.event key=value"` format for all log calls.

**Return dict convention** (`finalise.py` lines 186-191):
```python
return {
    "organisation_id": organisation_id,
    "shop_id": shop_id,
    "merged_groups": merged_groups,
    "stragglers_backfilled": stragglers_backfilled,
}
```
Phase 24 returns: `{"flipped": int, "skipped_low_sample": int, "evaluated": int}`.

---

### `apps/reviews/tasks.py` — `reclassify_polarity_task` addition (task, batch)

**Analog 1 (no-retry Beat task):** `enqueue_incremental_syncs_task` (`tasks.py` lines 155-176)
```python
@shared_task  # type: ignore[misc]
def enqueue_incremental_syncs_task() -> int:
    """Beat-scheduled fan-out: ..."""
    from apps.shops.models import Shop

    shop_ids = list(...)
    for shop_id in shop_ids:
        countdown = random.uniform(0, INCREMENTAL_JITTER_SECONDS_MAX)  # nosec B311  # noqa: S311
        sync_shop_reviews_task.apply_async(args=[shop_id], countdown=countdown)
    logger.info(
        "enqueue_incremental_syncs_task.dispatched shops_count=%s",
        len(shop_ids),
    )
    return len(shop_ids)
```
`reclassify_polarity_task` uses the same no-`bind`/no-`autoretry_for` shape (weekly, idempotent, no retry needed — a failed run simply runs again next week).

**Analog 2 (thin wrapper with logging):** `retry_failed_enrichments_task` (`tasks.py` lines 305-341) and `finalize_canonical_tags_task` (`tasks.py` lines 237-302) — both show the import-inside-function pattern and structured log lines:
```python
@shared_task  # type: ignore[misc]
def retry_failed_enrichments_task() -> int:
    from apps.reviews.models import Review
    ...
    logger.info(
        "retry_failed_enrichments_task.dispatched reviews_count=%s",
        len(ids),
    )
    return len(ids)
```

**Phase 24 task shape** (no bind, no autoretry, local import, structured log):
```python
@shared_task  # type: ignore[misc]
def reclassify_polarity_task() -> dict:
    """Phase 24 POL-02 — Weekly polarity reclassification.

    Beat-scheduled: Sunday 03:00 UTC (seeded in migration 0012/0013).
    Routes to default queue (low-frequency, low-concurrency).
    Business logic in apps.reviews.services.reclassify.run_polarity_reclassification().
    """
    from apps.reviews.services.reclassify import run_polarity_reclassification

    logger.info("reclassify_polarity_task.start")
    result = run_polarity_reclassification()
    logger.info(
        "reclassify_polarity_task.complete flipped=%s skipped_low_sample=%s evaluated=%s",
        result.get("flipped", 0),
        result.get("skipped_low_sample", 0),
        result.get("evaluated", 0),
    )
    return result
```

**File header import block** (`tasks.py` lines 1-34) — add no new top-level imports; the new task uses only a local import inside the function body, matching the existing convention for all service imports in this file.

---

### `apps/reviews/migrations/0012_periodic_task_seed_polarity_reclassify.py` (data migration)

**Analog:** `apps/reviews/migrations/0002_periodic_tasks_seed.py` (CrontabSchedule + PeriodicTask)

**Full pattern** (`0002_periodic_tasks_seed.py` lines 1-50):
```python
from __future__ import annotations

import json

from django.db import migrations


def seed_periodic_tasks(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="enqueue_incremental_syncs",
        defaults={
            "task": "apps.reviews.tasks.enqueue_incremental_syncs_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "google-sync",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": "Phase 11 SYNC-02: hourly fan-out, jitter applied per-shop.",
        },
    )


def remove_periodic_tasks(apps, schema_editor) -> None:  # type: ignore[no-untyped-def]
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="enqueue_incremental_syncs").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_periodic_tasks, remove_periodic_tasks),
    ]
```

**Phase 24 delta from analog:**
- `CrontabSchedule`: `minute="0"`, `hour="3"`, `day_of_week="0"` (Sunday), `day_of_month="*"`, `month_of_year="*"`, `timezone="UTC"`
- `PeriodicTask.name`: `"reclassify_polarity_tags"`
- `task`: `"apps.reviews.tasks.reclassify_polarity_task"`
- `queue`: `"default"`
- `dependencies`: `("reviews", "0011_orgcanonicaltag_reviewtag_canonical_tag")` (or `0012_...` if schema migration runs first) + `("django_celery_beat", "0019_alter_periodictasks_options")`
- Drop the `IntervalSchedule` import — not needed for a CrontabSchedule entry. Analog `0005_periodic_tasks_seed_retry_failed_enrichments.py` shows the IntervalSchedule variant for reference.

---

### `config/settings/base.py` — three `POLARITY_RECLASSIFY_*` settings + `CELERY_TASK_ROUTES` entry

**Analog pattern for operational knobs** (`base.py` lines 193-199):
```python
# Phase 23 — seed-phase size and global OpenAI rate limit (D-04, D-08).
# SEED_PHASE_SIZE: number of reviews enriched synchronously during the initial seed pass
# before handing remaining reviews off to the bulk ai-enrichment-high queue.
SEED_PHASE_SIZE = env.int("SEED_PHASE_SIZE", default=50)
# OPENAI_GLOBAL_RATE_LIMIT: per-org rolling 60-second call cap enforced by the
# rate:openai:org:{organisation_id} Redis token bucket (progress.py). Works cross-worker.
OPENAI_GLOBAL_RATE_LIMIT = env.int("OPENAI_GLOBAL_RATE_LIMIT", default=500)
```

**Phase 24 addition** — append after the existing `OPENAI_GLOBAL_RATE_LIMIT` block:
```python
# Phase 24 — polarity auto-reclassification (POL-02)
# POLARITY_RECLASSIFY_THRESHOLD: opposite-polarity fraction that triggers flip to mixed.
POLARITY_RECLASSIFY_THRESHOLD = env.float("POLARITY_RECLASSIFY_THRESHOLD", default=0.15)
# POLARITY_RECLASSIFY_WINDOW_DAYS: trailing window for review_create_time filter.
POLARITY_RECLASSIFY_WINDOW_DAYS = env.int("POLARITY_RECLASSIFY_WINDOW_DAYS", default=30)
# POLARITY_RECLASSIFY_MIN_REVIEWS: minimum sample guard (denominator must be >= this).
POLARITY_RECLASSIFY_MIN_REVIEWS = env.int("POLARITY_RECLASSIFY_MIN_REVIEWS", default=10)
```

Note: `env.float()` is available in `django-environ` (RESEARCH.md Assumption A2 notes a low-risk fallback: if `env.float` is absent, use `float(env("POLARITY_RECLASSIFY_THRESHOLD", default="0.15"))`).

**`CELERY_TASK_ROUTES` entry** — insert after the existing `finalize_canonical_tags_task` line (`base.py` lines 120-130):
```python
CELERY_TASK_ROUTES = {
    # ...existing entries...
    "apps.reviews.tasks.finalize_canonical_tags_task": {"queue": "tag-merge"},
    "apps.reviews.tasks.reclassify_polarity_task": {"queue": "default"},    # ADD
    "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"},
}
```

---

### `apps/reviews/migrations/0012_orgcanonicaltag_polarity_reclassified_at.py` (schema migration, optional)

**Analog:** Any `AddField` migration in `apps/reviews/migrations/` — the pattern is standard Django `AddField`. The `polarity_reclassified_at` field is a nullable `DateTimeField`.

```python
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0011_orgcanonicaltag_reviewtag_canonical_tag"),
    ]

    operations = [
        migrations.AddField(
            model_name="orgcanonicaltag",
            name="polarity_reclassified_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

If this migration runs, `_flip_and_audit` in `reclassify.py` must set `tag.polarity_reclassified_at = timezone.now()` and include `"polarity_reclassified_at"` in the `bulk_update` field list alongside `"polarity_type"`. The Beat seed migration then depends on this migration, not `0011`.

---

### `apps/reviews/tests/test_reclassify_service.py` (test, batch)

**Analog 1 (query-count test shape):** `test_enrichment_service.py` lines 1097-1131
```python
def _enrich_query_count(*, tag_count: int) -> int:
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _result_with_n_tags(tag_count)
    with (
        patch(...),
        CaptureQueriesContext(connection) as ctx,
    ):
        enrich_review(review_id=review.pk)
    return len(ctx.captured_queries)


@pytest.mark.django_db
def test_canonical_query_count_is_fixed_regardless_of_tag_count() -> None:
    two = _enrich_query_count(tag_count=2)
    five = _enrich_query_count(tag_count=5)
    assert two == five  # identical → no per-tag query growth
    assert five <= 15
```

**Phase 24 adaptation** — no patching needed (no Redis, no OpenAI, no WebSocket):
```python
@pytest.mark.django_db
def test_query_count_is_fixed() -> None:
    """Service runs fixed DB queries regardless of tag count (CLAUDE.md §6.9)."""
    org = OrganisationFactory()
    # Create N always_positive tags with qualifying reviews
    for _ in range(5):
        tag = OrgCanonicalTagFactory(
            organisation=org,
            polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
        )
        review = ReviewFactory(organisation=org)
        ReviewTagFactory(review=review, canonical_tag=tag, polarity="negative")
        # ... ensure min_reviews threshold met
    with CaptureQueriesContext(connection) as ctx:
        run_polarity_reclassification()
    assert len(ctx.captured_queries) <= 5  # candidate fetch + aggregate + optional bulk writes
```

**Analog 2 (AuditLog assertion shape):** `lifecycle.py` tests + `AuditLogFactory` from `factories.py` lines 58-68:
```python
class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    organisation = factory.SubFactory(OrganisationFactory)
    actor = None
    entity_type = "review"
    entity_id = factory.Sequence(lambda n: str(n))
    action = "reply_posted"
    before_data = None
    after_data = factory.LazyFunction(lambda: {"reply_text": "ok"})
```
Phase 24 tests assert `AuditLog.objects.filter(action="polarity_reclassified").count() == N` and validate `before_data`/`after_data` field contents.

**Imports pattern** for test file (`test_enrichment_service.py` lines 1-47):
```python
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag
from apps.reviews.services.reclassify import run_polarity_reclassification
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
)
from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
```

**`@pytest.mark.django_db` decorator** — used on every test function that touches the database (no class wrappers for service tests in this project; `test_enrichment_service.py` and `test_finalise.py` both use bare function style with the decorator).

---

## Shared Patterns

### AuditLog write — system event (actor=null)
**Source:** `apps/reviews/services/sync.py` (system events), `apps/action_items/services/lifecycle.py` lines 80-96 (human events)
**Apply to:** `apps/reviews/services/reclassify.py` `_flip_and_audit`

Key fields for Phase 24:
```python
AuditLog(
    organisation_id=tag.organisation_id,   # from FK — structurally org-scoped
    actor=None,                             # system/automated event (D-06)
    entity_type="canonical_tag",           # snake_case noun
    entity_id=str(tag.pk),                 # str(pk) convention
    action="polarity_reclassified",        # verb phrase, no dot prefix
    before_data={"polarity_type": old_polarity},
    after_data={
        "polarity_type": "mixed",
        "opposite_ratio": float,
        "window_days": int,
        "reviews_in_window": int,
    },
)
```

### `@transaction.atomic` + `bulk_update` + `bulk_create`
**Source:** `apps/reviews/services/finalise.py` (`_merge_group` lines 202-231, `_refresh_review_counts` lines 300-306)
**Apply to:** `apps/reviews/services/reclassify.py` `_flip_and_audit`

One transaction wraps both the `bulk_update` and `bulk_create` so a partial failure rolls back both — the tag stays at its old polarity and no AuditLog row is written.

### Structured logging key=value format
**Source:** `apps/reviews/services/finalise.py` logger calls throughout
**Apply to:** `apps/reviews/services/reclassify.py`, `apps/reviews/tasks.py`

Format: `"function_name.event key1=%s key2=%s"` with positional `%s` args (never f-strings in logger calls).

### `env.int()` / `env.float()` for configurable settings
**Source:** `config/settings/base.py` lines 193-199 (`SEED_PHASE_SIZE`, `OPENAI_GLOBAL_RATE_LIMIT`)
**Apply to:** `config/settings/base.py` — three `POLARITY_RECLASSIFY_*` additions

### `@shared_task` no-bind form for global Beat tasks
**Source:** `apps/reviews/tasks.py` lines 155-176 (`enqueue_incremental_syncs_task`) and lines 305-341 (`retry_failed_enrichments_task`)
**Apply to:** `apps/reviews/tasks.py` — `reclassify_polarity_task`

Local import inside task body (`from apps.reviews.services.reclassify import ...`) matches the existing convention for all service imports in this module.

### `CrontabSchedule.objects.get_or_create` + `PeriodicTask.objects.update_or_create`
**Source:** `apps/reviews/migrations/0002_periodic_tasks_seed.py` lines 14-34
**Apply to:** `apps/reviews/migrations/0012_periodic_task_seed_polarity_reclassify.py`

`update_or_create` keyed on `name=` makes the migration safely re-runnable (idempotent data migration). Always set `interval=None` when using a `CrontabSchedule` to avoid field conflict.

---

## No Analog Found

All files have close analogs in the codebase. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/reviews/services/`, `apps/reviews/tasks.py`, `apps/reviews/migrations/`, `apps/reviews/tests/`, `apps/action_items/services/lifecycle.py`, `apps/common/models.py`, `config/settings/base.py`
**Files scanned:** 10 source files read in full or in targeted ranges
**Pattern extraction date:** 2026-06-16
