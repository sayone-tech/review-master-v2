---
phase: 12-ai-enrichment-pipeline
plan: "05"
subsystem: background-jobs
tags: [django, management-command, celery, enrichment, backfill]

# Dependency graph
requires:
  - phase: 12-04
    provides: enrich_review_task Celery task registered as @shared_task
  - phase: 12-01
    provides: Review model with EnrichmentStatus choices and deleted_at field
provides:
  - Django management command enrich_existing_reviews for one-time Phase 11 backlog drain
  - Management package skeleton (apps/reviews/management/__init__.py + commands/__init__.py)
  - 5 pytest tests covering all command behaviours (ENRCH-13)
affects: [12-ai-enrichment-pipeline, deployment-runbook, operator-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin management command: query + fan-out only, zero business logic in command body (CLAUDE.md §10)"
    - "values_list('id', flat=True) for memory-bounded iteration over large DB tables"
    - "Patch symbol at its import site in the command module — not in the source module"

key-files:
  created:
    - apps/reviews/management/__init__.py
    - apps/reviews/management/commands/__init__.py
    - apps/reviews/management/commands/enrich_existing_reviews.py
    - apps/reviews/tests/test_management_commands.py
  modified: []

key-decisions:
  - "Patch path is apps.reviews.management.commands.enrich_existing_reviews.enrich_review_task.delay — patching the bound name in the command module namespace, not the source module"
  - "dry_run output prefixed with [dry-run] to make stdout grep-friendly for operators"

patterns-established:
  - "Management command imports task at module top (not lazily inside handle) — safe because tasks.py has no circular dependency with management/"

requirements-completed:
  - ENRCH-13

# Metrics
duration: 2min
completed: 2026-05-02
---

# Phase 12 Plan 05: enrich_existing_reviews Management Command Summary

**One-time backfill Django management command that drains Phase 11's PENDING review backlog by fan-outing to enrich_review_task.delay, with --dry-run and --limit flags for safe staged rollouts**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-02T16:37:20Z
- **Completed:** 2026-05-02T16:39:30Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Created management package skeleton (both __init__.py files) so Django and mypy discover the command
- Built `enrich_existing_reviews` command: queries `Review.EnrichmentStatus.PENDING + deleted_at__isnull=True`, dispatches `enrich_review_task.delay(review_id)` per row
- Supports `--dry-run` (prints count without dispatching) and `--limit N` (caps enqueue count) for operator-controlled staged rollouts
- Memory-bounded: uses `.values_list("id", flat=True)` — iterates only PKs, safe on large Phase 11 backlogs
- Idempotent: re-running is safe because Plan 04's three-layer idempotency exits cleanly on IN_PROGRESS/SUCCESS rows
- 5 tests cover: pending-only enqueue, soft-delete skip, dry-run no-dispatch, limit cap, empty queue zero output
- ENRCH-13 closed — Phase 12 requirement set (ENRCH-01..ENRCH-14) now fully addressed

## Task Commits

1. **Task 1: Management command package + enrich_existing_reviews + tests** - `2f48e0a` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `apps/reviews/management/__init__.py` — empty package marker
- `apps/reviews/management/commands/__init__.py` — empty package marker
- `apps/reviews/management/commands/enrich_existing_reviews.py` — Command(BaseCommand) with --dry-run, --limit, thin query + fan-out
- `apps/reviews/tests/test_management_commands.py` — 5 pytest tests for ENRCH-13

## Decisions Made

- Patch path in tests targets `apps.reviews.management.commands.enrich_existing_reviews.enrich_review_task.delay` (bound import in command module namespace), not `apps.reviews.tasks.enrich_review_task.delay` — consistent with RESEARCH.md Pitfall 5
- `[dry-run]` prefix on dry-run stdout output for grep-friendly operator verification

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- ruff-format reformatted the two new files (collapsed multi-line string concat in --limit help, compacted create_batch call args) — re-staged and recommitted after pre-commit hook ran. No logic changes.
- `test_sync_service.py::test_fetch_and_persist_enqueues_enrichment_for_pending_reviews` is a pre-existing failure (module `apps.reviews.services.sync` has no attribute `enrich_review_task` — wrong patch target in that test). This failure predates Plan 12-05 and is out of scope per CLAUDE.md scope boundary rules. Deferred to `deferred-items.md`.

## User Setup Required

None - no external service configuration required. The command is invoked manually once per environment after Phase 12 deploys:

```bash
# Staged rollout — enqueue 100 reviews first, monitor, then drain remainder
python manage.py enrich_existing_reviews --limit 100
# After confirming enrichment is working:
python manage.py enrich_existing_reviews
```

## Next Phase Readiness

- Phase 12 is requirement-complete (ENRCH-01 through ENRCH-14 all addressed across plans 01-05)
- Plans 12-06 is the remaining incomplete plan
- The command is ready for production deployment in the Phase 12 deploy runbook

---
*Phase: 12-ai-enrichment-pipeline*
*Completed: 2026-05-02*
