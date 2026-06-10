---
phase: 23-four-step-initial-sync-seeding-queue-split
plan: 01
subsystem: infra
tags: [celery, redis, rate-limiting, token-bucket, openai, settings]

requires:
  - phase: 14-openai-enrichment
    provides: AiUsageLog/enrichment pipeline and per-worker ENRICHMENT_RATE_LIMIT
  - phase: 03-channels-sync-progress
    provides: progress.py Redis snapshot/counter helpers and Google token bucket analog
provides:
  - "Celery queue split: ai-enrichment-high / ai-enrichment-low / tag-merge (plus google-sync, default)"
  - "SEED_PHASE_SIZE and OPENAI_GLOBAL_RATE_LIMIT configurable settings"
  - "Cross-worker global OpenAI token bucket (rate:openai:org:{organisation_id})"
  - "_wait_for_openai_token() seed-path helper (blocks without raising) and bulk-path raise guard"
  - "Per-phase vocab and bulk-enriched Redis counters, cleared on snapshot clear"
affects: [23-02-finalise, 23-03-sync-orchestration, ai-enrichment, progress]

tech-stack:
  added: []
  patterns: ["Cross-worker Redis token bucket with INCR+EXPIRE pipeline", "Wait-vs-raise dual rate-limit primitives for seed vs bulk paths"]

key-files:
  created:
    - apps/reviews/tests/test_settings.py
    - apps/reviews/tests/test_rate_limit.py
  modified:
    - config/settings/base.py
    - apps/reviews/services/progress.py

key-decisions:
  - "D-04: SEED_PHASE_SIZE as configurable env.int setting (default 50)"
  - "D-08: cross-worker Redis token bucket as primary OpenAI rate guard; per-worker rate_limit retained as secondary"
  - "D-09: three-way queue split ai-enrichment-high / ai-enrichment-low / tag-merge"
  - "Seed path uses _wait_for_openai_token (never raises); bulk path uses raise guard — both primitives defined here for consistency"

patterns-established:
  - "rate:openai:org:{organisation_id} token bucket: increment_openai_token_bucket (INCR+EXPIRE), _wait_for_openai_token (bounded sleep-and-retry acquire), token-depleted check"
  - "Per-phase counters (vocab / bulk enriched) namespaced in Redis and cleared in clear_progress_snapshot"

requirements-completed: [QUEUE-01, DSYNC-01]

duration: ~9min
completed: 2026-06-10
---

# Phase 23 — Plan 01: Queue-split + Redis foundation Summary

**Split the monolithic `ai-enrichment` Celery queue into high/low/tag-merge lanes and added the cross-worker OpenAI token bucket plus seed-path wait helper that every downstream Phase 23 plan builds on.**

## Performance

- **Duration:** ~9 min (executor stalled while writing SUMMARY; metadata completed by orchestrator post-merge)
- **Completed:** 2026-06-10
- **Tasks:** 2 (Task 2 via TDD)
- **Files modified:** 4

## Accomplishments
- Queue split: `CELERY_QUEUE_NAMES` now lists `google-sync, ai-enrichment-high, ai-enrichment-low, tag-merge, default`; `CELERY_TASK_ROUTES` routes `enrich_review_task` / `retry_failed_enrichments_task` to `ai-enrichment-low` and `finalize_canonical_tags_task` to `tag-merge`.
- Added `SEED_PHASE_SIZE` (default 50) and `OPENAI_GLOBAL_RATE_LIMIT` (default 500) settings.
- Added the cross-worker global OpenAI token bucket (`rate:openai:org:{organisation_id}`) with `increment_openai_token_bucket` (INCR+EXPIRE pipeline) and the `_wait_for_openai_token()` seed-path helper that blocks (bounded sleep-and-retry) until headroom exists, then increments and returns without raising.
- Added per-phase vocab and bulk-enriched Redis counters, cleared in `clear_progress_snapshot`.

## Task Commits

1. **Task 1: Queue split + SEED_PHASE_SIZE + OPENAI_GLOBAL_RATE_LIMIT settings** — `04ad5db` (feat)
2. **Task 2 (TDD): OpenAI token bucket + _wait_for_openai_token + per-phase counters** — `5223805` (test, RED) → `21077a1` (feat, GREEN)

**Worktree merge:** `6ff7247`

## Files Created/Modified
- `config/settings/base.py` — queue-split routes/names, SEED_PHASE_SIZE, OPENAI_GLOBAL_RATE_LIMIT
- `apps/reviews/services/progress.py` — OpenAI token bucket, `_wait_for_openai_token`, vocab/bulk counters + clear
- `apps/reviews/tests/test_settings.py` — asserts queue names/routes and new settings
- `apps/reviews/tests/test_rate_limit.py` — token bucket acquire/deplete/expire + `_wait_for_openai_token`

## Verification
- `pytest apps/reviews/tests/test_settings.py apps/reviews/tests/test_rate_limit.py` — pass
- Full `apps/reviews/tests/` suite — pass (no regressions)

## Notes / Deviations
- Executor agent stalled (stream watchdog, no progress 600s) **after** committing both tasks but **before** writing SUMMARY.md. Code was fully committed and clean; the orchestrator merged the worktree branch, verified tests, and authored this SUMMARY during post-merge recovery. No re-execution was needed.

## Self-Check: PASSED
