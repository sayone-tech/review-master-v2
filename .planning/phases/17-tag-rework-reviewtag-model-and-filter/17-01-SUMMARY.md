---
phase: 17-tag-rework-reviewtag-model-and-filter
plan: 01
subsystem: reviews
tags: [model, migration, factory, tests, schema]
requires: []
provides:
  - ReviewTag relational model
  - reviewtag_review_label_idx composite index
  - ReviewTagFactory
  - Review.tags JSONField removed (replaced by related_name=tags RelatedManager)
affects:
  - apps.reviews.serializers (ReviewReadSerializer.tags auto-discovery now broken — to be re-declared in Plan 17-02)
  - apps.reviews.services.enrichment (still writes to Review.tags JSON column — must be migrated in Plan 17-02)
  - apps.reviews.tests.test_enrichment_service (review.tags == [] assertions will fail until Plan 17-02 rewrites them)
tech-stack:
  added: []
  patterns:
    - Django TextChoices inner class
    - Composite Meta.indexes for FK + filter column
    - factory_boy SubFactory with DjangoModelFactory
key-files:
  created:
    - apps/reviews/migrations/0008_reviewtag.py
  modified:
    - apps/reviews/models.py
    - apps/reviews/tests/factories.py
    - apps/reviews/tests/test_models.py
    - apps/reviews/tests/test_enrichment_service.py
decisions:
  - Migration polarity field includes choices and id field includes verbose_name=ID so makemigrations --check passes (pre-commit hook enforces this; deviating from the plan's minimal-migration instruction was unavoidable).
metrics:
  duration: ~10 minutes
  completed_date: 2026-05-21
  tasks_completed: 3
  files_changed: 5
requirements:
  - TAG-01
---

# Phase 17 Plan 01: ReviewTag Model & Migration Summary

Introduced the relational `ReviewTag` model (table `reviews_reviewtag`) with FK to `Review` (CASCADE, `related_name="tags"`), `label` (CharField(100) indexed), `polarity` (CharField(10) with `Polarity` TextChoices), and a composite index `reviewtag_review_label_idx` on `(review, label)`. Migration `0008_reviewtag` creates the table, adds the index, and removes the legacy `Review.tags` JSONField — in that order so the column drop runs after the new table exists. `ReviewTagFactory` added to the test factory layer; the stale `tags: ClassVar[list] = []` was removed from `ReviewFactory` and one downstream `ReviewFactory(tags=[])` call site in `test_enrichment_service.py` was cleaned up. New `TestReviewTagModel` test class covers `__str__`, db_table, composite index, label db_index, polarity choices, cascade-delete, and the `related_name="tags"` RelatedManager exposure.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Add ReviewTag model and remove Review.tags JSONField | 950adc7 |
| 2 | Add migration 0008_reviewtag | b4d94e7 |
| 3 | Add ReviewTagFactory and ReviewTag model tests | ee1eb72 |

## Verification Run

- `python manage.py check reviews` → System check identified no issues
- `python manage.py makemigrations --check --dry-run` → No changes detected
- `pytest apps/reviews/tests/test_models.py -x -q` → 14 passed

## Acceptance Criteria

- [x] `python manage.py check apps.reviews` exits with no errors
- [x] `grep -n "class ReviewTag" apps/reviews/models.py` → match
- [x] `grep -n "tags = models.JSONField" apps/reviews/models.py` → no match
- [x] `grep -n "reviewtag_review_label_idx" apps/reviews/models.py` → match
- [x] Migration file exists; `makemigrations --check` reports no changes
- [x] `pytest apps/reviews/tests/test_models.py` exits 0
- [x] `grep -n "ReviewTagFactory" apps/reviews/tests/factories.py` → match
- [x] `grep -n "reviewtag_review_label_idx" apps/reviews/tests/test_models.py` → match
- [x] `grep -rn "ReviewFactory.*tags=" apps/` → no match

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Migration needed `choices=` on polarity and `verbose_name="ID"` on id**
- **Found during:** Task 2 verification
- **Issue:** Plan specified omitting `polarity` choices from the migration to keep it lean. However, `makemigrations --check` (run by the project's `missing-migrations` pre-commit hook) detected drift and would auto-generate a `0009_alter_reviewtag_*` migration to add the choices and the verbose_name. Pre-commit hook blocked commit until the migration matched what Django would auto-generate.
- **Fix:** Added `choices=[("positive", "Positive"), ("neutral", "Neutral"), ("negative", "Negative")]` to the polarity field and `verbose_name="ID"` to the id field in the migration. Migration semantics are unchanged — choices live only in Python-side validation, not in the DB schema.
- **Files modified:** apps/reviews/migrations/0008_reviewtag.py
- **Commit:** b4d94e7

**2. [Rule 3 — Blocking] Stale `ReviewFactory(tags=[])` kwarg in `test_enrichment_service.py`**
- **Found during:** Task 3 acceptance-criteria scan (`grep -rn "ReviewFactory.*tags="`)
- **Issue:** Removing `Review.tags` field caused `ReviewFactory(tags=[])` to raise `TypeError` at test instantiation time.
- **Fix:** Removed only the `tags=[]` kwarg from the one ReviewFactory call site that used it. Assertions like `review.tags == []` were left untouched — they are Plan 17-02's responsibility when the enrichment service is migrated to write `ReviewTag` rows.
- **Files modified:** apps/reviews/tests/test_enrichment_service.py
- **Commit:** ee1eb72

## Known Stubs

None.

## Threat Flags

None — no new security surface introduced.

## Self-Check: PASSED

- FOUND: apps/reviews/migrations/0008_reviewtag.py
- FOUND: apps/reviews/models.py (modified — ReviewTag class present, Review.tags JSONField removed)
- FOUND: apps/reviews/tests/factories.py (modified — ReviewTagFactory present)
- FOUND: apps/reviews/tests/test_models.py (modified — TestReviewTagModel present)
- FOUND commit: 950adc7
- FOUND commit: b4d94e7
- FOUND commit: ee1eb72
