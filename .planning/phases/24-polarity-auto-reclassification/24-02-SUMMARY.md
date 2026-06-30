---
phase: 24-polarity-auto-reclassification
plan: "02"
subsystem: reviews/services
tags: [celery, beat, audit-log, polarity, reclassification, no-n+1]
dependency_graph:
  requires: ["24-01"]
  provides: ["POL-02", "POL-03"]
  affects: ["apps/reviews/services/reclassify.py", "apps/reviews/tasks.py", "apps/reviews/migrations/0013"]
tech_stack:
  added: []
  patterns:
    - "Single grouped values+annotate aggregate for no-N+1 polarity counts"
    - "transaction.atomic + bulk_update + AuditLog.bulk_create in one write"
    - "Thin @shared_task no-bind wrapper calling service function"
    - "data migration update_or_create Beat PeriodicTask seed"
key_files:
  created:
    - apps/reviews/services/reclassify.py
    - apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py
  modified:
    - apps/reviews/tasks.py
decisions:
  - "D-01: mixed tags pre-filtered — never in candidate queryset; sticky one-way"
  - "D-02: strict > threshold; denominator = ALL polarities incl. neutral; numerator = opposite only"
  - "D-03: review_count excluded from bulk_update field list"
  - "D-05: idempotent — second run returns flipped=0 since mixed tags already excluded"
  - "D-06: AuditLog with actor=None, before_data/after_data per spec, inside transaction.atomic"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-16"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 24 Plan 02: Polarity Auto-Reclassification Service Summary

## One-liner

Weekly Beat job flips always_positive/always_negative OrgCanonicalTag to mixed when opposite-polarity ratio exceeds 0.15 over 30-day window, using a single grouped aggregate query with per-flip AuditLog (no GPT, no Redis).

## What was built

### Task 1 — `apps/reviews/services/reclassify.py`

`run_polarity_reclassification()` implements the full POL-02 service:

1. Reads three settings: `POLARITY_RECLASSIFY_THRESHOLD`, `POLARITY_RECLASSIFY_WINDOW_DAYS`, `POLARITY_RECLASSIFY_MIN_REVIEWS`
2. Fetches all `always_positive` + `always_negative` candidates via `.only("id","organisation_id","polarity_type")` — mixed tags excluded at the queryset level (sticky D-01)
3. ONE aggregate query: `ReviewTag.objects.filter(canonical_tag_id__in=..., review__review_create_time__gte=cutoff, review__deleted_at__isnull=True).values("canonical_tag_id","polarity").annotate(cnt=Count("id"))` — no per-tag loop
4. Groups rows in Python into `by_tag[tag_id][polarity]=cnt`
5. For each candidate: `total = sum(counts.values())` (denominator incl. neutral); numerator = opposite polarity count; ratio strictly > threshold AND total >= min_reviews triggers flip collection
6. `_flip_and_audit()` is `@transaction.atomic`: sets `polarity_type=MIXED`, `polarity_reclassified_at=now()`, `bulk_update(["polarity_type","polarity_reclassified_at"])` (review_count intentionally excluded — D-03), `AuditLog.bulk_create` with before/after_data (D-06)
7. Returns `{"flipped": N, "skipped_low_sample": N, "evaluated": N}`

### Task 2 — `apps/reviews/tasks.py` + migration `0013`

- `reclassify_polarity_task`: `@shared_task` no-bind, no autoretry, local import of `run_polarity_reclassification` inside body, structured `logger.info` with result fields
- Migration `0013_periodic_task_seed_polarity_reclassify.py`: `CrontabSchedule(minute="0", hour="3", day_of_week="0")` (Sunday 03:00 UTC), `PeriodicTask.update_or_create(name="reclassify_polarity_tags", queue="default")`, reversible via `remove_polarity_reclassify`

## Test Results

All 14 Wave-0 tests from Plan 01 are now GREEN:

| Test | Coverage Area | Result |
|------|--------------|--------|
| test_flip_always_positive_to_mixed_when_threshold_exceeded | (a) flip | PASS |
| test_flip_always_negative_to_mixed_when_threshold_exceeded | (a) flip reversed | PASS |
| test_no_flip_below_min_reviews | (b) min-sample guard | PASS |
| test_boundary_exactly_threshold_does_not_flip | (c) strict > | PASS |
| test_mixed_tags_are_skipped_no_audit_log | (d) one-way sticky | PASS |
| test_neutral_reviews_in_denominator_only | (e) neutral in denom | PASS |
| test_neutral_reviews_never_trigger_flip_even_when_majority | (e) neutral never trigger | PASS |
| test_soft_deleted_reviews_excluded | (f) soft-delete exclusion | PASS |
| test_reviews_older_than_window_excluded | (g) window cutoff | PASS |
| test_multi_tenant_isolation | (h) tenant isolation | PASS |
| test_idempotency_second_run_changes_nothing | (i) idempotency | PASS |
| test_query_count_is_fixed_regardless_of_tag_count | (j) no-N+1 | PASS |
| test_audit_log_written_on_flip | (k) AuditLog D-06 | PASS |
| test_pol01_reconfirm_new_tag_has_non_empty_polarity_type | POL-01 regression | PASS |

Full reviews suite: **265 passed** (1 pre-existing unrelated isolation failure in test_models.py).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The service runs as a Beat-dispatched background task with no user-facing trigger surface. All STRIDE threats T-24-04 through T-24-08 are mitigated as specified in the plan threat model.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `apps/reviews/services/reclassify.py` exists | FOUND |
| `apps/reviews/tasks.py` modified | FOUND |
| `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` exists | FOUND |
| Commit `2e06192` (Task 1 service) | FOUND |
| Commit `dd61446` (Task 2 task + migration) | FOUND |
| `review_count` absent from `bulk_update` field list | VERIFIED |
| `reclassify_polarity_task` routed to default queue in settings | VERIFIED |
| All 14 Wave-0 tests GREEN | VERIFIED |
