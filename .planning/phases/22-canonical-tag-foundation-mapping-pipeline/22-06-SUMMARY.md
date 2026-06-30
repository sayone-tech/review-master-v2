---
phase: 22-canonical-tag-foundation-mapping-pipeline
plan: 06
status: complete
requirements: [QUEUE-02]
key-files:
  modified:
    - apps/reviews/tasks.py
    - apps/reviews/tests/test_tasks.py
---

# 22-06 — Celery Enrichment Rate Limit (SUMMARY)

## What was built

Applied a configurable Celery `rate_limit` to `enrich_review_task` (QUEUE-02),
sourced from the `ENRICHMENT_RATE_LIMIT` setting added in 22-02, and documented
the per-worker caveat (D-06).

### `apps/reviews/tasks.py`
- Imported `from django.conf import settings`.
- Added `rate_limit=settings.ENRICHMENT_RATE_LIMIT` to the `@shared_task`
  decorator on `enrich_review_task` (default `"125/m"`).
- Extended the task docstring with the QUEUE-02 / D-06 note: Celery's
  `rate_limit` is enforced **per worker instance**, not globally across all
  workers; true global throttling is deferred to Phase 23.

### `apps/reviews/tests/test_tasks.py`
- Added `test_enrich_review_task_has_rate_limit` asserting
  `tasks.enrich_review_task.rate_limit == settings.ENRICHMENT_RATE_LIMIT`.

## Verification
- `pytest apps/reviews/tests/test_tasks.py` — green (13 tests)
- Task body stays thin (CLAUDE.md §12.3) — only the decorator changed.

## Notes / deviations
- Code was authored by the original background worktree executor but committed
  by the orchestrator after that agent was denied Bash permission; the edits
  were rescued from its worktree intact. No scope change from the plan.

## Self-Check: PASSED
