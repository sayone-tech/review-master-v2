---
phase: 11-reviews
plan: "04"
subsystem: api
tags: [celery, django-celery-beat, google-sync, background-tasks, redis]

# Dependency graph
requires:
  - phase: 11-reviews-03
    provides: run_initial_backfill and run_incremental_sync service functions
provides:
  - initial_backfill_task Celery task on google-sync queue
  - sync_shop_reviews_task Celery task on google-sync queue
  - enqueue_incremental_syncs_task fan-out task with 30-min jitter
  - Beat schedule data migration seeding hourly enqueue_incremental_syncs
affects: [11-reviews, ai-enrichment, Beat schedules]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin Celery task wrappers: tasks call service functions; zero business logic in task bodies"
    - "Data migration seeds django-celery-beat PeriodicTask so fresh environments work without admin config"
    - "Per-shop jitter (random.uniform 0..1800s) prevents thundering herd on hourly incremental sync"

key-files:
  created:
    - apps/reviews/tasks.py
    - apps/reviews/migrations/0002_periodic_tasks_seed.py
    - apps/reviews/tests/test_tasks.py
  modified: []

key-decisions:
  - "enqueue_incremental_syncs_task placed on default queue, not google-sync — it is a lightweight fan-out with no Google API calls"
  - "INCREMENTAL_JITTER_SECONDS_MAX=1800 (30 min) per CLAUDE.md §14.8 INCREMENTAL_SYNC_JITTER_MINUTES setting"
  - "random.uniform marked # noqa: S311 / # nosec B311 — jitter is timing, not cryptographic randomness"
  - "IntervalSchedule import removed from migration (unused; CrontabSchedule is sufficient for hourly-at-minute-0 schedule)"

patterns-established:
  - "Task signature: (self: Any, shop_id: int) -> dict[str, Any] with # type: ignore[misc] for celery decorator stubs"
  - "Beat seed migration depends on (reviews, 0001_initial) + (django_celery_beat, 0019_alter_periodictasks_options)"
  - "tests patch tasks module-level names (tasks.run_initial_backfill) not the service module directly"

requirements-completed: [SYNC-01, SYNC-02, SYNC-08, SYNC-10]

# Metrics
duration: 12min
completed: 2026-05-02
---

# Phase 11 Plan 04: Celery Task Wrappers + Beat Seed Migration Summary

**Three thin Celery task wrappers on google-sync queue with autoretry + 30-min jitter fan-out, Beat schedule seeded by data migration so fresh deployments sync automatically**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-02T04:48:00Z
- **Completed:** 2026-05-02T04:53:17Z
- **Tasks:** 2 (TDD: RED + GREEN combined)
- **Files modified:** 3 created

## Accomplishments

- `initial_backfill_task` and `sync_shop_reviews_task` wrap sync service with max_retries=3, autoretry_for=(Exception,), exponential backoff (30s base, 600s max)
- `enqueue_incremental_syncs_task` fans out per CONNECTED+active shop with random jitter (0–1800s) to prevent Google API thundering herd
- Data migration `0002_periodic_tasks_seed` creates CrontabSchedule (hourly at minute 0) + PeriodicTask pointing to `enqueue_incremental_syncs_task` on `google-sync` queue

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Implement task wrappers + Beat schedule data migration + tests** - `a1f2321` (feat)

_Note: Tasks 1 and 2 were committed together as GREEN phase (TDD RED written first, GREEN implemented, both committed in one atomic commit since they're tightly coupled)_

## Files Created/Modified

- `apps/reviews/tasks.py` — Three Celery tasks: initial_backfill_task, sync_shop_reviews_task, enqueue_incremental_syncs_task
- `apps/reviews/migrations/0002_periodic_tasks_seed.py` — Data migration seeding Beat PeriodicTask for hourly fan-out
- `apps/reviews/tests/test_tasks.py` — 6 tests: delegation, dispatch filtering, jitter window bounds, Beat seed presence, queue routing

## Decisions Made

- `enqueue_incremental_syncs_task` routes to `default` queue (not `google-sync`) — it only fans out task IDs, no Google API calls. Kept `queue="google-sync"` in the PeriodicTask `queue` field so beat dispatches it to the right queue for monitoring purposes, but the task body itself is lightweight.
- `random.uniform` suppressed with `# noqa: S311 / # nosec B311` — this is scheduling jitter, not security-sensitive randomness. No need for `secrets` module.
- Unused `IntervalSchedule` import removed from migration (was copied from plan template, not needed since CrontabSchedule is used for the hourly-at-minute-0 pattern).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused IntervalSchedule import from migration**
- **Found during:** Task 1 (migration creation)
- **Issue:** Plan template included `IntervalSchedule = apps.get_model(...)` but it was never used (CrontabSchedule is sufficient)
- **Fix:** Removed the unused assignment to pass ruff F841
- **Files modified:** apps/reviews/migrations/0002_periodic_tasks_seed.py
- **Verification:** ruff check passes, migration logic unchanged
- **Committed in:** a1f2321

**2. [Rule 1 - Bug] Added # noqa: S311 / # nosec B311 to random.uniform call**
- **Found during:** Task 1 (pre-commit hook failure)
- **Issue:** ruff S311 and bandit B311 flag random.uniform as cryptographic risk; jitter for scheduling is not a security concern
- **Fix:** Added inline suppressions to clarify intent
- **Files modified:** apps/reviews/tasks.py
- **Verification:** ruff check passes, bandit passes, 6 tests still pass
- **Committed in:** a1f2321

---

**Total deviations:** 2 auto-fixed (both Rule 1 - minor code quality fixes)
**Impact on plan:** Zero impact on functionality. Both fixes were linting cleanups required for pre-commit to pass.

## Issues Encountered

Pre-commit hooks on first commit attempt reported ruff S311 (random.uniform) and bandit B311 — resolved by adding `# noqa: S311  # nosec B311` comment. Migration's RUF012 warnings are excluded by `extend-exclude = ["migrations"]` in ruff config.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Celery tasks are live; Beat schedule will seed automatically on `manage.py migrate`
- Plans 05+ (enrichment tasks, reply service) can follow the same thin-wrapper pattern established here
- No blockers

---
*Phase: 11-reviews*
*Completed: 2026-05-02*
