# Phase 24: Polarity Auto-Reclassification - Research

**Researched:** 2026-06-16
**Domain:** Django ORM aggregation, Celery Beat periodic tasks, AuditLog conventions
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Reclassification direction (POL-02):** One-way only — `always_positive` / `always_negative` → `mixed`. Once `mixed`, stays `mixed` (sticky). Weekly job skips tags already `mixed`. Auto re-promotion is out of scope.

**D-02 — Threshold computation (POL-02):**
- Denominator = count of `ReviewTag` rows mapped to that canonical tag whose `Review.review_create_time` falls in the trailing window, **all polarities including neutral**, soft-deleted reviews excluded (`Review.deleted_at IS NULL`).
- Numerator = count of the **opposite** polarity only (`always_positive` ← `negative`; `always_negative` ← `positive`). Neutral is never in the numerator.
- Flip when `numerator / denominator > threshold` AND `denominator >= min_reviews`.

**D-03 — Window measurement:** `Review.review_create_time` (when the review happened on Google), not enrichment time.

**D-04 — Configurable settings:** `POLARITY_RECLASSIFY_THRESHOLD` (default 0.15), `POLARITY_RECLASSIFY_WINDOW_DAYS` (default 30), `POLARITY_RECLASSIFY_MIN_REVIEWS` (default 10) — added to `config/settings/base.py`.

**D-05 — Weekly Celery Beat job:** Seeded via data migration (CLAUDE.md §12.5). Scans only `always_positive`/`always_negative` tags, org-scoped aggregation. Pure DB aggregation, zero GPT calls. Idempotent. No-N+1.

**D-06 — AuditLog row:** `organisation` = tag's org, `actor` = null (system), `entity_type = "canonical_tag"`, `entity_id` = tag pk, `action = "polarity_reclassified"`, `before_data = {"polarity_type": "<old>"}`, `after_data = {"polarity_type": "mixed", "opposite_ratio": <float>, "window_days": <int>, "reviews_in_window": <int>}`.

**D-07 — UI visibility deferred:** Tag list page showing `polarity_type` is Phase 25. Phase 24 guarantees correctness + auditability only.

### Claude's Discretion

- Exact Beat cadence (e.g. Sunday 03:00 UTC) and queue (`default` queue, low-frequency low-concurrency — not `ai-enrichment-*`).
- Global single task aggregating all orgs vs per-org fan-out — research call; must stay org-scoped and no-N+1.
- Whether a `polarity_reclassified_at` timestamp is added to `OrgCanonicalTag` (helps Phase 25 display) or AuditLog row is sole record.

### Deferred Ideas (OUT OF SCOPE)

- Auto re-promotion (`mixed` → `always_*`)
- Rendering current `polarity_type` on the tag list page (Phase 25)
- Dashboard polarity split for `mixed` tags (Phase 25)
- Per-tag reclassification-history view
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| POL-01 | A new canonical tag is assigned one of `always_positive` / `always_negative` / `mixed` by GPT at creation time | Already shipped in Phase 22 (D-01); Phase 24 re-confirms and owns the reclassification lifecycle. No new prompt/parser change needed. |
| POL-02 | A weekly Celery Beat job reclassifies an `always_*` canonical tag to `mixed` when the opposite polarity exceeds 15% of its reviews over the last 30 days (pure DB aggregation, no GPT call) | Core deliverable: single-grouped aggregate query, weekly Beat task seeded via data migration, threshold/window/min-sample configurable settings, one-way flip, idempotent. |
| POL-03 | Reclassification events are logged and the current `polarity_type` is visible on the tag list page | Events: AuditLog row per flip (D-06). Visibility: DEFERRED to Phase 25 (D-07). Phase 24 satisfies the "logged" half fully. |
</phase_requirements>

---

## Summary

Phase 24 is a pure backend/infrastructure phase: a weekly Celery Beat job that aggregates `ReviewTag` polarity counts per `OrgCanonicalTag` over a trailing 30-day window and flips `always_*` tags to `mixed` when the opposite-polarity fraction exceeds a threshold. No GPT calls, no new models (beyond potentially one nullable timestamp column), no new API endpoints, no UI.

The core technical challenge is the single-pass no-N+1 aggregate query that evaluates ALL candidate tags across ALL organisations in one SQL round-trip. The codebase already has the exact ORM patterns needed: `_refresh_review_counts` in `apps/reviews/services/finalise.py` shows the grouped-annotate-then-bulk-update pattern; Beat migration seeds in `apps/reviews/migrations/0002_*` and `0005_*` show the exact data migration approach for `CrontabSchedule` + `PeriodicTask`.

The job runs as a single global task on the `default` queue (low-frequency, low-concurrency, not ai-enrichment). Each flip writes one `AuditLog` row (actor=null, system event) inside a `transaction.atomic()` block. `review_count` is NOT touched. `mixed` tags are skipped on every run (idempotent by design). The Beat cadence is weekly (Sunday 03:00 UTC) seeded via a data migration in `apps/reviews/migrations/`.

**Primary recommendation:** Single global task that runs one aggregate query (grouped by `canonical_tag_id`) covering all orgs, fetches matching `OrgCanonicalTag` rows, then performs a `bulk_update` for flipped tags and `bulk_create` for AuditLog rows — all inside one `transaction.atomic()`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Polarity distribution aggregate | Database / Storage | — | Single SQL GROUP BY over `ReviewTag` joined to `Review` window filter |
| Reclassification decision logic | API / Backend (service) | — | Pure Python threshold comparison after aggregate; no web layer |
| Flip + AuditLog write | Database / Storage | — | `bulk_update` + `bulk_create` inside `transaction.atomic()` |
| Weekly scheduling | Celery Beat | django_celery_beat DB | Beat-scheduled task seeded via data migration |
| Audit visibility | API / Backend (existing) | — | AuditLog rows surface in existing Phase 21 Activity Log viewer |
| Tag-list polarity display | DEFERRED (Phase 25) | — | Out of scope for Phase 24 |

---

## Standard Stack

No new external packages are required. Phase 24 uses only what is already installed.

### Core (all existing, no new installs)

| Library | Already in pyproject.toml | Purpose |
|---------|--------------------------|---------|
| `celery` + `django-celery-beat` | Yes (Phase 12) | Beat scheduling, task execution |
| `django` ORM (`values`/`annotate`/`Count`/`Case`/`When`) | Yes | Grouped aggregate, bulk_update |
| `apps.common.models.AuditLog` | Yes (Phase 21) | Reclassification event log sink |
| `apps.reviews.models.OrgCanonicalTag`, `ReviewTag`, `Review` | Yes (Phase 22) | Data models |
| `apps.common.locks.distributed_lock` | Yes (Phase 12) | Optional per-org locking if fan-out chosen |

### Installation

No new `pip install` / `uv add` commands. Zero new packages.

---

## Package Legitimacy Audit

> No new external packages are introduced in this phase. This section is not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Beat Scheduler (weekly Sunday 03:00 UTC)
    |
    v
reclassify_polarity_task()    [apps/reviews/tasks.py, default queue]
    |
    v
run_polarity_reclassification()    [apps/reviews/services/reclassify.py]
    |
    +---> READ settings: threshold, window_days, min_reviews
    |
    +---> AGGREGATE QUERY (single SQL round-trip)
    |       ReviewTag JOIN Review
    |       WHERE canonical_tag__organisation IS NOT NULL
    |         AND Review.review_create_time >= cutoff
    |         AND Review.deleted_at IS NULL
    |         AND OrgCanonicalTag.polarity_type IN ('always_positive', 'always_negative')
    |       GROUP BY canonical_tag_id, polarity
    |       --> returns (canonical_tag_id, polarity, count) rows
    |
    +---> PYTHON: group by canonical_tag_id, compute numerator/denominator
    |
    +---> FETCH OrgCanonicalTag rows for candidates that cross threshold
    |
    +---> transaction.atomic()
    |       bulk_update(tags_to_flip, ["polarity_type"])
    |       AuditLog.objects.bulk_create(audit_rows)
    |
    +---> RETURN {"flipped": N, "skipped_mixed": M, "skipped_low_sample": K}
```

### Recommended Project Structure

```
apps/reviews/
├── services/
│   ├── reclassify.py           # NEW — run_polarity_reclassification() service
│   └── ...existing...
├── tasks.py                    # MODIFIED — add reclassify_polarity_task
├── migrations/
│   └── 0012_periodic_task_seed_polarity_reclassify.py   # NEW — Beat seed
config/settings/base.py         # MODIFIED — add 3 POLARITY_RECLASSIFY_* settings
```

### Pattern 1: Single-Pass Grouped Aggregate (No-N+1)

**What:** One SQL query returns all the data needed to evaluate every candidate tag across all orgs. No per-tag query loop.

**When to use:** Any time you evaluate a metric per entity over a set of entities — aggregate once, decide in Python.

**Concrete ORM shape** [VERIFIED: codebase — mirrors `_refresh_review_counts` in `finalise.py`]:

```python
# Source: apps/reviews/services/finalise.py — _refresh_review_counts pattern,
# adapted for polarity distribution (Phase 24)

from django.db.models import Case, Count, IntegerField, Q, When
from django.utils import timezone

def _get_polarity_distributions(*, cutoff: datetime) -> list[dict]:
    """Single SQL round-trip: per-canonical-tag polarity counts over the window.

    Returns rows like:
      {"canonical_tag_id": 7, "polarity": "positive", "cnt": 42}
      {"canonical_tag_id": 7, "polarity": "negative", "cnt": 6}
      {"canonical_tag_id": 7, "polarity": "neutral",  "cnt": 12}
    for ALL canonical tags (all orgs) whose reviews fall in the window.

    Filters:
      - Review.review_create_time >= cutoff  (D-03: review date, not enrichment date)
      - Review.deleted_at IS NULL            (D-02: exclude soft-deleted)
      - canonical_tag IS NOT NULL            (only mapped tags)
    """
    return list(
        ReviewTag.objects.filter(
            canonical_tag__isnull=False,
            review__review_create_time__gte=cutoff,
            review__deleted_at__isnull=True,
        )
        .values("canonical_tag_id", "polarity")
        .annotate(cnt=Count("id"))
        .order_by("canonical_tag_id", "polarity")
    )
```

This produces a list of `(canonical_tag_id, polarity, cnt)` rows. Python then groups by `canonical_tag_id` to build a per-tag distribution dict in O(rows) time — no additional DB queries.

**Alternative shape using `Case/When` for a single aggregate row per tag:**

```python
# Alternative: one row per canonical_tag_id with separate columns per polarity.
# More compact but less readable. Use the grouped approach above instead —
# it avoids hard-coding polarity values into ORM expressions.
from django.db.models import Case, Count, IntegerField, When

ReviewTag.objects.filter(
    canonical_tag__isnull=False,
    review__review_create_time__gte=cutoff,
    review__deleted_at__isnull=True,
).values("canonical_tag_id").annotate(
    total=Count("id"),
    negative_cnt=Count(Case(When(polarity="negative", then=1), output_field=IntegerField())),
    positive_cnt=Count(Case(When(polarity="positive", then=1), output_field=IntegerField())),
)
```

**Recommendation:** Use the first shape (values + polarity + annotate cnt) — it generalises to any polarity value without hard-coding, and the Python grouping step is trivial.

### Pattern 2: Threshold Decision in Python

```python
# Source: pure Python — no ORM needed here
from collections import defaultdict

def _compute_candidates(
    rows: list[dict],
    *,
    candidate_polarity_types: dict[int, str],  # {canonical_tag_id: polarity_type}
    threshold: float,
    min_reviews: int,
) -> list[dict]:
    """
    candidate_polarity_types: only always_positive / always_negative tags (pre-filtered).

    Returns list of dicts:
      {"canonical_tag_id": int, "old_polarity": str, "opposite_ratio": float,
       "reviews_in_window": int}
    for each tag that should flip to mixed.
    """
    # Group by canonical_tag_id
    by_tag: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        tag_id = row["canonical_tag_id"]
        if tag_id in candidate_polarity_types:
            by_tag[tag_id][row["polarity"]] += row["cnt"]

    candidates = []
    for tag_id, counts in by_tag.items():
        old_polarity = candidate_polarity_types[tag_id]
        total = sum(counts.values())  # denominator: all polarities (D-02)
        if total < min_reviews:
            continue  # minimum sample guard
        # Opposite polarity: always_positive -> negative; always_negative -> positive
        opposite = "negative" if old_polarity == "always_positive" else "positive"
        opp_count = counts.get(opposite, 0)  # numerator
        ratio = opp_count / total
        if ratio > threshold:
            candidates.append({
                "canonical_tag_id": tag_id,
                "old_polarity": old_polarity,
                "opposite_ratio": round(ratio, 6),
                "reviews_in_window": total,
            })
    return candidates
```

### Pattern 3: Atomic Flip + AuditLog (bulk)

**What:** `bulk_update` the flipped tags, `bulk_create` the AuditLog rows — one transaction, two round-trips.

**Why `bulk_update` over `select_for_update`:** A `select_for_update` loop makes one query per tag (N+1 lock acquisition). Since the weekly job is the ONLY writer of `polarity_type` (enrichment never touches it after creation; Phase 25 manual changes are future), `bulk_update` is safe and dramatically faster for orgs with many tags to flip. The service uses an outer `transaction.atomic()` so any AuditLog write failure rolls back the bulk_update too.

```python
# Source: apps/reviews/services/finalise.py — bulk_update pattern (Phase 23)
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import OrgCanonicalTag, ReviewTag

logger = logging.getLogger(__name__)


@transaction.atomic
def _flip_and_audit(
    *,
    candidates: list[dict],
    tag_map: dict[int, OrgCanonicalTag],
    window_days: int,
) -> int:
    """Flip polarity_type to mixed + write AuditLog rows atomically.

    candidates: output of _compute_candidates()
    tag_map: {canonical_tag_id: OrgCanonicalTag instance} (pre-fetched)
    Returns number of tags flipped.
    """
    if not candidates:
        return 0

    tags_to_update = []
    audit_rows = []

    for c in candidates:
        tag = tag_map[c["canonical_tag_id"]]
        old_polarity = tag.polarity_type  # confirmed before update
        tag.polarity_type = OrgCanonicalTag.PolarityType.MIXED
        tags_to_update.append(tag)
        audit_rows.append(
            AuditLog(
                organisation_id=tag.organisation_id,
                actor=None,  # system/automated event (D-06)
                entity_type="canonical_tag",
                entity_id=str(tag.pk),
                action="polarity_reclassified",
                before_data={"polarity_type": old_polarity},
                after_data={
                    "polarity_type": "mixed",
                    "opposite_ratio": c["opposite_ratio"],
                    "window_days": window_days,
                    "reviews_in_window": c["reviews_in_window"],
                },
            )
        )

    OrgCanonicalTag.objects.bulk_update(tags_to_update, ["polarity_type"])
    AuditLog.objects.bulk_create(audit_rows)

    logger.info(
        "polarity_reclassification.flipped count=%s",
        len(tags_to_update),
    )
    return len(tags_to_update)
```

### Pattern 4: Beat Schedule — Data Migration (CrontabSchedule)

**What:** Weekly Beat task seeded via Django data migration using `CrontabSchedule`.

**Existing repo precedent** [VERIFIED: codebase — `apps/reviews/migrations/0002_periodic_tasks_seed.py`]:

```python
# Source: apps/reviews/migrations/0002_periodic_tasks_seed.py (hourly CrontabSchedule)
# Adapted for weekly polarity reclassification (Phase 24)

import json
from django.db import migrations


def seed_polarity_reclassify(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # Sunday 03:00 UTC  (day_of_week="0" = Sunday in Celery/cron convention)
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="0",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.update_or_create(
        name="reclassify_polarity_tags",
        defaults={
            "task": "apps.reviews.tasks.reclassify_polarity_task",
            "crontab": crontab,
            "interval": None,
            "enabled": True,
            "queue": "default",
            "args": json.dumps([]),
            "kwargs": json.dumps({}),
            "description": (
                "Phase 24 POL-02: weekly Sunday 03:00 UTC — flip always_* "
                "OrgCanonicalTags to mixed when opposite-polarity ratio exceeds "
                "POLARITY_RECLASSIFY_THRESHOLD over the trailing window."
            ),
        },
    )


def remove_polarity_reclassify(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="reclassify_polarity_tags").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0011_orgcanonicaltag_reviewtag_canonical_tag"),  # latest migration
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_polarity_reclassify, remove_polarity_reclassify),
    ]
```

**Migration number:** Next is `0012_periodic_task_seed_polarity_reclassify.py` (confirmed: `ls apps/reviews/migrations/` shows `0011_orgcanonicaltag_reviewtag_canonical_tag.py` as the latest). [VERIFIED: codebase]

### Pattern 5: Celery Task Wrapper

```python
# Source: thin task pattern from apps/reviews/tasks.py (enqueue_incremental_syncs_task)

@shared_task  # No bind=True needed — no retries (service is idempotent, weekly gap)
def reclassify_polarity_task() -> dict:
    """Phase 24 POL-02 — Weekly polarity reclassification.

    Beat-scheduled: Sunday 03:00 UTC (seeded in migration 0012).
    Routes to default queue (low-frequency, low-concurrency).
    Business logic in apps.reviews.services.reclassify.run_polarity_reclassification().
    """
    from apps.reviews.services.reclassify import run_polarity_reclassification

    logger.info("reclassify_polarity_task.start")
    result = run_polarity_reclassification()
    logger.info(
        "reclassify_polarity_task.complete flipped=%s skipped_mixed=%s "
        "skipped_low_sample=%s evaluated=%s",
        result.get("flipped", 0),
        result.get("skipped_mixed", 0),
        result.get("skipped_low_sample", 0),
        result.get("evaluated", 0),
    )
    return result
```

**No `bind=True`/`autoretry_for`:** The job is weekly and fully idempotent. A transient DB error will be logged by Sentry; the next weekly run re-evaluates cleanly. If you want retry behaviour, add `bind=True` + `max_retries=2` with a short backoff — but it is not necessary for correctness.

### Anti-Patterns to Avoid

- **Per-tag query loop:** `for tag in always_positive_tags: ReviewTag.objects.filter(canonical_tag=tag).count()` — this is N+1 and is the primary pitfall for this phase. The aggregate query must GROUP BY `canonical_tag_id` in ONE SQL call.
- **Touching `review_count`:** D-03 from Phase 22 explicitly prohibits incrementing `review_count` in this job. The reclassify service MUST NOT update `review_count`.
- **Inline `AuditLog.objects.create()` per flip inside a loop:** generates N round-trips. Use `bulk_create` with a list built in Python, called once per job run.
- **Selecting soft-deleted reviews into the denominator:** `deleted_at__isnull=False` rows must be excluded from the aggregate filter.
- **Using `Review.updated_at` or `ReviewTag.created_at` for the window:** D-03 mandates `Review.review_create_time`.
- **Querying `mixed` tags:** Skip them immediately. A filter `polarity_type__in=["always_positive", "always_negative"]` on `OrgCanonicalTag` is needed before (or after) fetching the aggregate to avoid evaluating `mixed` tags.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Grouped aggregate with per-polarity counts | A custom SQL string or RawQuerySet | `values("canonical_tag_id","polarity").annotate(cnt=Count("id"))` | Django ORM handles the GROUP BY cleanly; test-friendly |
| Atomic multi-row update | Per-row `.save()` in a loop | `OrgCanonicalTag.objects.bulk_update(tags, ["polarity_type"])` | One SQL UPDATE vs N; already pattern-established in `finalise.py` |
| Multi-row audit write | Per-row `AuditLog.objects.create()` | `AuditLog.objects.bulk_create(audit_rows)` | One INSERT vs N; matches project convention for batch ops |
| Weekly Beat schedule | A management command called by cron | `django-celery-beat` `CrontabSchedule` + data migration | Consistent with all other Beat schedules in this repo |
| Threshold/window constants | Hardcoded literals | `settings.POLARITY_RECLASSIFY_*` | Operational flexibility; matches Phase 22/23 knob pattern |

---

## Runtime State Inventory

> This section is N/A — Phase 24 is a greenfield service (new task + new service + Beat entry). No rename/refactor is involved.

---

## Common Pitfalls

### Pitfall 1: N+1 Aggregate (Critical)
**What goes wrong:** Looping over `OrgCanonicalTag.objects.filter(polarity_type__in=[...])` and issuing one `ReviewTag.objects.filter(canonical_tag=tag).count()` per tag — produces N DB queries.
**Why it happens:** Intuitive but wrong; `OrgCanonicalTag.review_tags` is a reverse FK, so accessing it per-tag triggers a query.
**How to avoid:** Use the single grouped `values("canonical_tag_id","polarity").annotate(cnt=Count("id"))` query described in Pattern 1. All counts come back in one SQL round-trip.
**Warning signs:** `CaptureQueriesContext` test shows query count proportional to tag count.

### Pitfall 2: `review_count` Mutation
**What goes wrong:** Service inadvertently updates `OrgCanonicalTag.review_count` during `bulk_update`.
**Why it happens:** It's on the same model; easy to accidentally include in `bulk_update` field list.
**How to avoid:** The `bulk_update` call MUST specify `["polarity_type"]` only — not `["polarity_type", "review_count"]`. Phase 22 D-03 is explicit.
**Warning signs:** Phase 25 `review_count` values are wrong after a Phase 24 run.

### Pitfall 3: Wrong Time Window Field
**What goes wrong:** Using `ReviewTag.created_at` or `Review.updated_at` for the window filter instead of `Review.review_create_time`.
**Why it happens:** `ReviewTag` doesn't have its own timestamp; `created_at` from `TimeStampedModel` might seem equivalent but it's enrichment time.
**How to avoid:** Filter `review__review_create_time__gte=cutoff` in the aggregate query. Enforced by test: create a review with a `review_create_time` outside the window and verify it is excluded.
**Warning signs:** Tags with old reviews that were recently enriched get incorrectly included in the window.

### Pitfall 4: Including Soft-Deleted Reviews
**What goes wrong:** Soft-deleted reviews (where `Review.deleted_at IS NOT NULL`) contribute to the denominator, diluting the ratio and potentially preventing a valid flip.
**Why it happens:** The `ReviewTag` FK to `Review` doesn't cascade-delete; the `ReviewTag` rows for soft-deleted reviews still exist.
**How to avoid:** Always filter `review__deleted_at__isnull=True` in the aggregate query.
**Warning signs:** A tag that should flip doesn't because deleted reviews inflate the denominator.

### Pitfall 5: Evaluating Already-Mixed Tags
**What goes wrong:** The aggregate query includes `mixed` tags; they always pass the "0 opposite vs 0 total" or vary randomly, wasting computation and potentially writing spurious no-op AuditLog rows.
**Why it happens:** The aggregate filter doesn't pre-exclude `mixed`.
**How to avoid:** Pre-fetch only `always_positive` / `always_negative` tags into `candidate_polarity_types`. The aggregate query itself doesn't need to filter by polarity_type (it's filtered per-tag in Python), but the candidate map ensures mixed tags are never evaluated.
**Warning signs:** AuditLog rows with `before_data = {"polarity_type": "mixed"}` appear.

### Pitfall 6: Tags With Zero Reviews in Window
**What goes wrong:** A tag with 0 reviews in the window doesn't appear in the aggregate result at all (no rows → no entry in `by_tag`). This is correct (they don't flip), but the "skipped_low_sample" counter must count them.
**Why it happens:** LEFT JOIN semantics — tags with no matching rows don't appear in `GROUP BY` results.
**How to avoid:** After computing `by_tag`, any `candidate_polarity_types` tag NOT present in `by_tag` has `total = 0` — it naturally passes the `total < min_reviews` guard and is skipped. Log it as `skipped_low_sample`. No special handling needed.

### Pitfall 7: Multi-Org Isolation
**What goes wrong:** Tags from org A are evaluated against reviews from org B (e.g., a `canonical_tag_id` collision if PKs ever cross).
**Why it happens:** The aggregate query doesn't filter by `organisation_id` on the `Review` side.
**How to avoid:** The JOIN path `ReviewTag -> canonical_tag -> organisation` implicitly scopes reviews to the tag's org (a ReviewTag can only point to a Review from the same org because the enrichment service scopes it). But for defence-in-depth and correctness on the candidate filter, pre-fetch candidates with `canonical_tag__organisation_id` and confirm the `tag_map` only contains tags from their correct orgs. The aggregate query itself is safe because `canonical_tag__isnull=False` ensures the ReviewTag is mapped to a tag that has an explicit `organisation_id` FK.

### Pitfall 8: Beat CrontabSchedule `day_of_week` Value
**What goes wrong:** `day_of_week="7"` (Sunday) vs `day_of_week="0"` (Sunday) — cron uses 0 or 7 for Sunday but celery-beat's `CrontabSchedule` uses 0.
**Why it happens:** Ambiguity between cron conventions.
**How to avoid:** Use `day_of_week="0"` for Sunday in `CrontabSchedule` (Celery convention). Verified against existing repo seed migration for the hourly crontab. [VERIFIED: codebase — `apps/reviews/migrations/0002_periodic_tasks_seed.py` uses `day_of_week="*"`; the weekly value should be `"0"` for Sunday.]

---

## Code Examples

### Full service skeleton

```python
# apps/reviews/services/reclassify.py
# Source: derived from finalise.py patterns (VERIFIED: codebase)

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import OrgCanonicalTag, ReviewTag

logger = logging.getLogger(__name__)


def run_polarity_reclassification() -> dict:
    """POL-02: Evaluate all always_* OrgCanonicalTag rows and flip to mixed
    where the opposite-polarity fraction exceeds threshold.

    Returns:
        {"flipped": int, "skipped_mixed": int, "skipped_low_sample": int,
         "evaluated": int}
    """
    threshold: float = settings.POLARITY_RECLASSIFY_THRESHOLD
    window_days: int = settings.POLARITY_RECLASSIFY_WINDOW_DAYS
    min_reviews: int = settings.POLARITY_RECLASSIFY_MIN_REVIEWS

    cutoff: datetime = timezone.now() - timezone.timedelta(days=window_days)

    # Step 1: fetch all candidate (always_*) tags across all orgs
    candidate_qs = OrgCanonicalTag.objects.filter(
        polarity_type__in=[
            OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
            OrgCanonicalTag.PolarityType.ALWAYS_NEGATIVE,
        ]
    ).only("id", "organisation_id", "polarity_type")
    candidate_map: dict[int, OrgCanonicalTag] = {tag.pk: tag for tag in candidate_qs}

    if not candidate_map:
        return {"flipped": 0, "skipped_mixed": 0, "skipped_low_sample": 0, "evaluated": 0}

    # Step 2: single aggregate query (no-N+1)
    rows = list(
        ReviewTag.objects.filter(
            canonical_tag_id__in=candidate_map.keys(),
            review__review_create_time__gte=cutoff,
            review__deleted_at__isnull=True,
        )
        .values("canonical_tag_id", "polarity")
        .annotate(cnt=Count("id"))
    )

    # Step 3: group in Python
    by_tag: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        by_tag[row["canonical_tag_id"]][row["polarity"]] += row["cnt"]

    # Step 4: evaluate each candidate
    to_flip: list[tuple[OrgCanonicalTag, dict]] = []
    skipped_low_sample = 0
    for tag_id, tag in candidate_map.items():
        counts = by_tag.get(tag_id, {})
        total = sum(counts.values())
        if total < min_reviews:
            skipped_low_sample += 1
            continue
        opposite = (
            "negative"
            if tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE
            else "positive"
        )
        ratio = counts.get(opposite, 0) / total
        if ratio > threshold:
            to_flip.append((
                tag,
                {
                    "opposite_ratio": round(ratio, 6),
                    "reviews_in_window": total,
                },
            ))

    # Step 5: flip + audit atomically
    flipped = _flip_and_audit(
        to_flip=to_flip,
        window_days=window_days,
    )

    return {
        "flipped": flipped,
        "skipped_mixed": 0,   # already excluded by candidate_qs filter
        "skipped_low_sample": skipped_low_sample,
        "evaluated": len(candidate_map),
    }


@transaction.atomic
def _flip_and_audit(
    *,
    to_flip: list[tuple[OrgCanonicalTag, dict]],
    window_days: int,
) -> int:
    if not to_flip:
        return 0

    audit_rows = []
    for tag, stats in to_flip:
        old_polarity = tag.polarity_type
        tag.polarity_type = OrgCanonicalTag.PolarityType.MIXED
        audit_rows.append(
            AuditLog(
                organisation_id=tag.organisation_id,
                actor=None,
                entity_type="canonical_tag",
                entity_id=str(tag.pk),
                action="polarity_reclassified",
                before_data={"polarity_type": old_polarity},
                after_data={
                    "polarity_type": "mixed",
                    "opposite_ratio": stats["opposite_ratio"],
                    "window_days": window_days,
                    "reviews_in_window": stats["reviews_in_window"],
                },
            )
        )

    OrgCanonicalTag.objects.bulk_update(
        [tag for tag, _ in to_flip],
        ["polarity_type"],
    )
    AuditLog.objects.bulk_create(audit_rows)
    return len(to_flip)
```

### Settings additions

```python
# config/settings/base.py additions (after OPENAI_GLOBAL_RATE_LIMIT)
# Source: follows SEED_PHASE_SIZE / OPENAI_GLOBAL_RATE_LIMIT pattern (VERIFIED: codebase)

# Phase 24 — polarity auto-reclassification (POL-02)
POLARITY_RECLASSIFY_THRESHOLD = env.float("POLARITY_RECLASSIFY_THRESHOLD", default=0.15)
POLARITY_RECLASSIFY_WINDOW_DAYS = env.int("POLARITY_RECLASSIFY_WINDOW_DAYS", default=30)
POLARITY_RECLASSIFY_MIN_REVIEWS = env.int("POLARITY_RECLASSIFY_MIN_REVIEWS", default=10)
```

### CELERY_TASK_ROUTES addition

```python
# config/settings/base.py — CELERY_TASK_ROUTES dict
"apps.reviews.tasks.reclassify_polarity_task": {"queue": "default"},
```

---

## Global Task vs Per-Org Fan-Out: Decision

**Chosen: Single global task** (Claude's Discretion, CONTEXT.md).

**Rationale:**

| Criterion | Global task | Per-org fan-out |
|-----------|------------|-----------------|
| Concurrency risk | Single run, no parallel writes to same tag | Needs per-org lock (like `distributed_lock`) |
| N+1 risk | Zero — one aggregate covers all orgs | Each per-org task also runs one aggregate, but Beat dispatches N tasks |
| Complexity | One task, one service call | Enqueue task + per-org task (two task types) |
| Tenant isolation | Aggregate is org-scoped via canonical_tag FK | Naturally isolated |
| Run time | Weekly, O(all_tags), typically fast | Distributed but more overhead |
| Beat entries | One CrontabSchedule | One enqueue + N per-org tasks |

The `enqueue_incremental_syncs_task` fan-out pattern exists for Google sync because shops need jitter (rate limits) and per-shop isolation (a shop failing doesn't block others). Polarity reclassification has no Google API calls, no rate limits, and no per-org isolation concern — the aggregate query handles all orgs in one SQL call. A single global task is simpler, easier to monitor, and appropriate for this use case.

**Queue:** `default` — not `google-sync` (no Google API), not `ai-enrichment-*` (no OpenAI calls), not `tag-merge` (no merge operation). The `default` queue is correct per CLAUDE.md §10. [VERIFIED: codebase — `CELERY_TASK_DEFAULT_QUEUE = "default"` in settings].

---

## Optional: `polarity_reclassified_at` Timestamp

**Claude's Discretion** item from CONTEXT.md. Recommendation: **add it**.

`OrgCanonicalTag` currently has `created_at`/`updated_at` from `TimeStampedModel`. Adding a nullable `polarity_reclassified_at = models.DateTimeField(null=True, blank=True)` gives Phase 25's tag list page a cheap, indexed "last reclassified" column without an AuditLog JOIN. The AuditLog row remains authoritative; the timestamp is a denormalized cache.

**Migration:** One field addition, no data backfill needed (null = "never auto-reclassified").

**Impact:** Adds one migration (`0012_orgcanonicaltag_polarity_reclassified_at.py`), one field in `bulk_update` call, and one additional field in the service. Very low cost for meaningful Phase 25 value.

If the planner decides NOT to add it, Phase 25 can derive "last reclassified" from AuditLog — but it requires a JOIN per tag on the tag-list endpoint.

---

## AuditLog House Style (Verified)

All three existing writers follow the same pattern [VERIFIED: codebase]:

| Field | Convention | Source |
|-------|-----------|--------|
| `organisation_id` | From the entity being written | sync.py, replies.py, lifecycle.py |
| `actor` | `None` for system events (sync, enrichment); User for human events | sync.py `_audit()`: always None; replies.py: `actor if is_authenticated else None` |
| `entity_type` | Snake_case noun of the entity | `"shop_sync"`, `"review"`, `"action_item"` |
| `entity_id` | `str(pk)` | All three writers |
| `action` | Dot-notation verb | `"reply_posted"`, `"action_item.created"`, `"sync.completed"` |
| `before_data` | `None` or `{}` for creation events; dict of changed fields for mutations | lifecycle.py uses `{}` for before_data on create |
| `after_data` | Dict of new state / context | All writers include relevant fields |

**Phase 24 reclassification row** follows this convention:
- `entity_type = "canonical_tag"` (snake_case noun, consistent pattern)
- `action = "polarity_reclassified"` (verb phrase, no dot prefix — consistent with `"reply_posted"`)
- `before_data = {"polarity_type": "<old_value>"}` (mutation pattern — old value of changed field)
- `after_data = {"polarity_type": "mixed", "opposite_ratio": float, "window_days": int, "reviews_in_window": int}` (new value + diagnostic context per D-06)

The Activity Log viewer (Phase 21) filters by `entity_type` and `action` for display — the Phase 24 row will appear in the viewer without any changes to the viewer code.

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|-----------------|-------|
| `IntervalSchedule` (every N hours) | `CrontabSchedule` (specific day/hour/minute) | Both used in this repo — use CrontabSchedule for the weekly job (day_of_week precision needed) |
| Per-entity fan-out Beat tasks | Global aggregate task | Appropriate here because no API rate limit concerns |
| `update()` on filtered QS | `bulk_update()` with explicit field list | `bulk_update` preferred when instances are already in memory (avoid refetch); `update()` preferred when no instances needed |

---

## Index Support

The aggregate query traverses `ReviewTag -> canonical_tag_id -> canonical_tag (OrgCanonicalTag) -> organisation_id` and `ReviewTag -> review -> review_create_time` and `deleted_at`. [VERIFIED: codebase — `apps/reviews/models.py`]:

| Index | Table | Fields | Supports |
|-------|-------|--------|---------|
| `review_org_date_idx` | `Review` | `(organisation, review_create_time)` | Window filter by date |
| `reviewtag_review_label_idx` | `ReviewTag` | `(review, label)` | Review FK traversal |
| `reviews_reviewtag.canonical_tag_id` | `ReviewTag` | `canonical_tag_id` (db_index=True) | Candidate filter |
| `orgcanon_org_count_idx` | `OrgCanonicalTag` | `(organisation, -review_count)` | Candidate fetch order |

The aggregate query `ReviewTag.filter(canonical_tag_id__in=candidate_ids, review__review_create_time__gte=cutoff, review__deleted_at__isnull=True)` uses the `canonical_tag_id` index for the IN filter and `review_org_date_idx` for the date window. No new indexes are required. [VERIFIED: codebase]

A composite index on `ReviewTag (canonical_tag_id, review_id)` would marginally improve the JOIN but is not required — `canonical_tag_id` (db_index=True) is sufficient for the weekly job cadence.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `day_of_week="0"` is Sunday in django-celery-beat's CrontabSchedule | Beat Migration pattern | Job runs on wrong day — operator can fix via Django admin without code change |
| A2 | `env.float()` is available in `django-environ` for `POLARITY_RECLASSIFY_THRESHOLD` | Settings additions | Falls back to `env()` returning a string that needs explicit float() cast — minor code change |

**If this table were empty:** All other claims in this research were verified against the live codebase.

---

## Open Questions

1. **`polarity_reclassified_at` field addition**
   - What we know: AuditLog row is the authoritative record; Phase 25 will need to display the last reclassification date.
   - What's unclear: Whether Phase 25 can tolerate an AuditLog JOIN on the tag-list endpoint (adds 1 query) or prefers the denormalized field.
   - Recommendation: Add the field (one nullable DateTimeField on `OrgCanonicalTag`, one migration). Low cost now, avoids rework in Phase 25. Planner should include it unless explicitly told otherwise.

2. **Zero `always_*` tags at job start**
   - What we know: The service returns early if `candidate_map` is empty.
   - What's unclear: Whether the job should log at INFO or DEBUG for a no-op run.
   - Recommendation: Log at INFO — makes monitoring easier (distinguishes "ran and found nothing" from "never ran").

---

## Environment Availability

> Phase 24 is code/config-only changes using existing infrastructure. No new external dependencies.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Celery + django-celery-beat | Beat task | Yes (Phase 12) | Already in pyproject.toml |
| PostgreSQL | ORM aggregate | Yes | Project-wide requirement |
| Redis DB 3 | Celery broker | Yes | Phase 12 |
| `apps.common.models.AuditLog` | Reclassification logging | Yes (Phase 21) | Model exists, no migration needed |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest apps/reviews/tests/test_reclassify_service.py -x` |
| Full suite command | `pytest apps/reviews/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| POL-01 | `polarity_type` is set at creation by GPT (Phase 22 — re-confirm not regressed) | unit | `pytest apps/reviews/tests/test_enrichment_service.py -k polarity -x` | Yes |
| POL-02: threshold flip | Tag with opposite_ratio > 0.15 flips to mixed | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_flips_when_ratio_exceeds_threshold -x` | No — Wave 0 |
| POL-02: threshold boundary | Tag at exactly 0.15 ratio does NOT flip (> not >=) | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_no_flip_at_exact_threshold -x` | No — Wave 0 |
| POL-02: min sample guard | Tag with total < min_reviews does not flip | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_no_flip_below_min_sample -x` | No — Wave 0 |
| POL-02: mixed sticky | Already-mixed tag is never re-evaluated or logged | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_mixed_tags_are_skipped -x` | No — Wave 0 |
| POL-02: soft-delete exclusion | Soft-deleted reviews excluded from denominator | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_soft_deleted_reviews_excluded -x` | No — Wave 0 |
| POL-02: neutral exclusion | Neutral reviews in denominator but not numerator | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_neutral_in_denominator_not_numerator -x` | No — Wave 0 |
| POL-02: window date filter | Review outside trailing window excluded | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_review_outside_window_excluded -x` | No — Wave 0 |
| POL-02: no-N+1 | Query count is constant regardless of tag count | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_query_count_is_fixed -x` | No — Wave 0 |
| POL-02: idempotency | Second run same week = no additional flips, no extra AuditLog | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_idempotent_second_run -x` | No — Wave 0 |
| POL-02: multi-tenant | Org A flip does not affect Org B tags | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_multi_tenant_isolation -x` | No — Wave 0 |
| POL-03 | Each flip writes exactly one AuditLog row with correct fields | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_audit_log_written -x` | No — Wave 0 |
| POL-03 | AuditLog after_data includes opposite_ratio, window_days, reviews_in_window | unit | `pytest apps/reviews/tests/test_reclassify_service.py::test_audit_log_after_data_fields -x` | No — Wave 0 |
| Beat schedule | PeriodicTask "reclassify_polarity_tags" exists after migration | integration | `pytest apps/reviews/tests/test_reclassify_task.py::test_periodic_task_seeded -x` | No — Wave 0 |
| Task wrapper | reclassify_polarity_task calls service and logs result | unit | `pytest apps/reviews/tests/test_reclassify_task.py::test_task_calls_service -x` | No — Wave 0 |

### Key test pattern (query count) [VERIFIED: codebase — mirrors `test_canonical_query_count_is_fixed_regardless_of_tag_count`]

```python
@pytest.mark.django_db
def test_query_count_is_fixed() -> None:
    """Service runs exactly the same number of DB queries regardless of tag count."""
    org = OrganisationFactory()
    # Setup N=5 always_positive tags, each with reviews
    ...
    with CaptureQueriesContext(connection) as ctx:
        result = run_polarity_reclassification()
    # Expected: 1 (fetch candidates) + 1 (aggregate) + optional bulk_update + bulk_create
    # Must NOT scale with N
    assert len(ctx.captured_queries) <= 5
```

### Sampling Rate
- **Per task commit:** `pytest apps/reviews/tests/test_reclassify_service.py -x`
- **Per wave merge:** `pytest apps/reviews/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `apps/reviews/tests/test_reclassify_service.py` — all POL-02 and POL-03 service tests (13 test functions above)
- [ ] `apps/reviews/tests/test_reclassify_task.py` — task wrapper and Beat seed tests (2 test functions)
- [ ] `apps/reviews/services/reclassify.py` — the service itself (new file)

*(Existing test infrastructure covers the framework — no new conftest.py or fixtures beyond what exists.)*

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | System (actor=null) task — no user auth |
| V3 Session Management | No | Celery worker context |
| V4 Access Control | No | No endpoint exposed |
| V5 Input Validation | Yes (minimal) | Settings values are typed (`env.float`, `env.int`); no user input |
| V6 Cryptography | No | No secrets handled |

**Tenant isolation (CLAUDE.md §22 Phase 3+):** Every Celery task that handles user-scoped data must verify `organisation_id` matches. This task is non-user-scoped (global scan), but the AuditLog writes are scoped to `tag.organisation_id` (derived from the model FK — not a parameter), so tenant isolation is structural, not parameterized. [VERIFIED: codebase — `AuditLog.organisation_id=tag.organisation_id` pattern matches `sync.py` and `replies.py`]

---

## Project Constraints (from CLAUDE.md)

| Constraint | Section | Impact on Phase 24 |
|-----------|---------|-------------------|
| No N+1 queries — blocker-level bug | §6 | Aggregate query MUST be single grouped SQL; query-count test required |
| Atomic transactions for multi-step writes | §6.11 | `_flip_and_audit` MUST use `@transaction.atomic` |
| Tasks receive IDs not model instances | §12.3 | `reclassify_polarity_task` takes no args (global scan); consistent |
| No business logic in task bodies | §12.3 | Service function `run_polarity_reclassification()` in `services/reclassify.py`; task is thin |
| Beat schedules seeded via data migration | §12.5 | Data migration `0012_periodic_task_seed_polarity_reclassify.py` required |
| pytest + pytest-django + factory-boy | §16 | All tests use `ReviewFactory`, `OrgCanonicalTagFactory`, `ReviewTagFactory` |
| Never hit external APIs in tests | §16 | No GPT calls — N/A (no mocking needed for this phase) |
| `CELERY_TASK_ALWAYS_EAGER = True` in test settings | §12.8 | Task integration tests work without a worker |
| Thin views; business logic in services | §5 | No views in this phase |
| Use `logger` not `print()` | §24 | All logging via `logger = logging.getLogger(__name__)` |
| Ruff + mypy + bandit must pass | §17 | Full type annotations on service functions required |
| Celery tasks that handle user-scoped data verify organisation_id | §22 | AuditLog writes use `tag.organisation_id` from FK — structurally correct |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase] `apps/reviews/models.py` — `OrgCanonicalTag.PolarityType`, `ReviewTag.Polarity`, `Review.review_create_time`, `deleted_at`, index definitions
- [VERIFIED: codebase] `apps/common/models.py` — `AuditLog` exact field set
- [VERIFIED: codebase] `apps/reviews/migrations/0002_periodic_tasks_seed.py` — `CrontabSchedule` + `PeriodicTask` data migration pattern
- [VERIFIED: codebase] `apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py` — `IntervalSchedule` pattern (used for `retry_failed_enrichments`; confirms update_or_create idiom)
- [VERIFIED: codebase] `apps/reviews/services/finalise.py` — `_refresh_review_counts` grouped-annotate-bulk_update pattern; `select_for_update` usage
- [VERIFIED: codebase] `apps/reviews/tasks.py` — `enqueue_incremental_syncs_task` (global fan-out pattern), thin task body convention
- [VERIFIED: codebase] `apps/action_items/services/lifecycle.py` — AuditLog write convention with `before_data`/`after_data`
- [VERIFIED: codebase] `config/settings/base.py` — existing `POLARITY_RECLASSIFY_*` keys absent (confirmed); `CELERY_TASK_ROUTES`, `CELERY_TASK_DEFAULT_QUEUE`, `SEED_PHASE_SIZE` pattern
- [VERIFIED: codebase] `apps/reviews/tests/test_enrichment_service.py` — `CaptureQueriesContext` query-count test pattern
- [VERIFIED: codebase] `apps/reviews/tests/factories.py` — `OrgCanonicalTagFactory`, `ReviewTagFactory`, `ReviewFactory`, `AuditLogFactory`

### Secondary (MEDIUM confidence)
- [ASSUMED] `env.float()` exists in `django-environ` — used for `POLARITY_RECLASSIFY_THRESHOLD` (0.15 is a float). Likely exists but not explicitly verified against the installed version. Fallback: `env("POLARITY_RECLASSIFY_THRESHOLD", default="0.15")` with explicit `float()` cast.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing patterns verified against codebase
- Aggregate ORM shape: HIGH — mirrors `_refresh_review_counts` which is live and tested
- Beat migration pattern: HIGH — two exact precedents verified
- AuditLog conventions: HIGH — three existing writers verified
- Architecture (global vs fan-out): HIGH — rationale clear; fan-out adds unnecessary complexity
- Pitfalls: HIGH — derived from code inspection of actual constraint/index definitions

**Research date:** 2026-06-16
**Valid until:** 2026-08-16 (stable Django/Celery conventions; no fast-moving dependencies)
