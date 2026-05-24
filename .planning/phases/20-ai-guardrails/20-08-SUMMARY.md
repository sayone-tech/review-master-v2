---
phase: 20-ai-guardrails
plan: 08
subsystem: reviews
tags: [celery-task, queryset-filter, moderation, retry-policy]
requires: [20-03]
provides: ["retry_failed_enrichments_task excludes content_moderated rows"]
affects: [apps/reviews/tasks.py, apps/reviews/tests/test_tasks.py]
tech_stack:
  added: []
  patterns: [Django ORM .exclude() chain on queryset, factory-driven Celery task tests with TASK_ALWAYS_EAGER]
key_files:
  created: []
  modified:
    - apps/reviews/tasks.py
    - apps/reviews/tests/test_tasks.py
decisions: [D-25, D-31]
metrics:
  duration: ~5 min (executor stalled before writing SUMMARY; orchestrator wrote post-hoc)
  completed: 2026-05-23
---

# Phase 20 Plan 08: Skip Content-Moderated Rows in Retry Task

Added a single `.exclude(enrichment_error_code="content_moderated")` clause to
`retry_failed_enrichments_task` (D-25) backed by the denormalized
`Review.enrichment_error_code` field from Plan 20-03 (D-31). Review text is
immutable, so re-running moderation on a row whose content was already flagged
is pure waste — every retry would re-bill the moderation call and re-fail with
the same outcome. Other `FAILED` rows (transient `openai_5xx`, parse failures,
timeouts, and the legacy empty-string default) remain retry-eligible up to
`MAX_TOTAL_ENRICH_ATTEMPTS`.

## Changes

### `apps/reviews/tasks.py` (4 lines added, 1 modified)

The existing `retry_failed_enrichments_task` queryset was:

```python
Review.objects.filter(
    enrichment_status=Review.EnrichmentStatus.FAILED,
    enrichment_version__lt=MAX_TOTAL_ENRICH_ATTEMPTS,
    deleted_at__isnull=True,
)
```

Chained one new clause (D-25):

```python
.exclude(enrichment_error_code="content_moderated")
```

No other filter changes. The exclusion is idempotent: rows that have not been
moderation-blocked carry the default empty-string `enrichment_error_code` and
pass through unaffected.

### `apps/reviews/tests/test_tasks.py` (58 lines added — 2 new tests)

- `test_retry_failed_enrichments_excludes_moderated`: creates a moderated
  review (`enrichment_status=FAILED`, `enrichment_error_code="content_moderated"`)
  and a transient-failure review (`enrichment_status=FAILED`,
  `enrichment_error_code="openai_5xx"`) and a legacy-failure review (empty-string
  `enrichment_error_code`). Runs the task. Asserts only the transient and legacy
  rows get re-enqueued via `enrich_review_task.delay` (mocked); the moderated
  row is silently skipped.
- `test_retry_failed_enrichments_includes_other_failure_codes`: parameterised
  over `["openai_5xx", "parse_error", "openai_timeout", ""]` — each one yields
  a row that the task re-enqueues. Belt-and-braces regression guard so a future
  refactor of the exclude clause cannot accidentally widen the filter.

## Decisions

- **D-25 (locked):** content-moderated rows are NEVER retried. Reviewer text is
  immutable; retry would just re-bill the moderation call and re-fail
  identically. Operationally this also caps platform exposure to
  moderation-API spend for adversarial review content.
- **D-31 (locked):** the denormalized `Review.enrichment_error_code` field
  (Plan 20-03) is the source of truth for this filter — avoiding a subquery
  join through `AiUsageLog` which would require a "latest row per review"
  pattern. One column, one `exclude` clause; idiomatic Django.

## Pitfalls Avoided

- **Field name accuracy** — used `enrichment_error_code` (NOT `error_code`)
  to match the D-31 field. `AiUsageLog` also has an `error_code` field; mixing
  the two would silently never match.
- **String casing** — `"content_moderated"` is lowercase per D-04/D-31
  (distinct from D-28's uppercase `AiUsageLog.Status.MODERATED`). The two
  string conventions are NOT interchangeable.
- **Empty-string default** — legacy rows from before Phase 20 carry the
  default `""` (per migration 0010). The parameterised test explicitly
  exercises this case so historical `FAILED` rows continue to retry.

## Verification

- `pytest apps/reviews/tests/test_tasks.py -k retry -x` — all retry tests pass
- Pre-commit (ruff, mypy, bandit, missing-migrations) — clean
- Acceptance criteria from PLAN.md met: queryset exclude clause present, both
  regression tests exist and pass

## Notes

The executor stalled before writing this SUMMARY (stream watchdog kicked in
after Task 2 commit). The two code commits (`f634e9e fix(20-08)` and
`b8ec71c test(20-08)`) were cherry-picked from the worktree branch
`worktree-agent-abf160646e91a2e75` into `feature/categories` by the
orchestrator. This SUMMARY was written post-hoc by the orchestrator based on
the diff and the plan contract.
