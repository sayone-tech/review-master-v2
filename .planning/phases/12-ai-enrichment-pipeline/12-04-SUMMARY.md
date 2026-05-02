---
phase: 12-ai-enrichment-pipeline
plan: "04"
subsystem: reviews/enrichment
tags: [celery, openai, idempotency, redis-lock, ai-enrichment]
dependency_graph:
  requires:
    - 12-03  # call_openai_enrichment + AiPricing seed
    - 12-02  # AiUsageLog model + Review enrichment fields
    - 11-04  # Celery infrastructure
  provides:
    - enrich_review service (three-layer idempotency)
    - enrich_review_task (Celery, ai-enrichment queue)
    - retry_failed_enrichments_task (Beat-scheduled)
  affects:
    - 12-05  # sync wiring calls enrich_review_task.delay(review.pk)
    - 12-06  # backfill command calls enrich_review_task.delay
tech_stack:
  added: []
  patterns:
    - Three-layer idempotency (Redis lock + select_for_update + status flag)
    - OpenAI call OUTSIDE transaction.atomic to avoid holding row lock during HTTP
    - enrichment_version as dual-purpose attempt counter
key_files:
  created:
    - apps/reviews/services/enrichment.py
    - apps/reviews/tests/test_enrichment_service.py
  modified:
    - apps/reviews/tasks.py
    - apps/reviews/tests/test_tasks.py
decisions:
  - enrichment_version incremented on BOTH SUCCESS and FAILED (doubles as attempt counter for retry_failed_enrichments_task)
  - OpenAI call OUTSIDE transaction.atomic (holding row lock during slow HTTP is anti-pattern)
  - Cap 500 reviews per retry_failed_enrichments_task run (bounds worker hold time on large failed backlogs)
  - OpenAIPermanentError NOT in autoretry_for AND not re-raised (Beat retry_failed_enrichments is sole re-attempt mechanism)
  - models.F("enrichment_version") + 1 for atomic increment without read-modify-write race
metrics:
  duration: 5 minutes
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 4
---

# Phase 12 Plan 04: Enrichment Service and Celery Tasks Summary

Enrichment service `enrich_review(review_id)` with three-layer idempotency (Redis lock + select_for_update + status flag) plus `enrich_review_task` and `retry_failed_enrichments_task` Celery tasks.

## What Was Built

### Task 1: apps/reviews/services/enrichment.py

The core enrichment service function with complete idempotency guarantees:

**Layer 1 - Redis lock:** Acquires `lock:enrich:review:{review_id}` with 5-minute TTL via `distributed_lock`. If not acquired (another worker holds it), returns cleanly — no DB work, no OpenAI call.

**Layer 2 + 3 - DB transaction with row lock + status check:** Inside `transaction.atomic()`, calls `select_for_update()` to lock the Review row, then checks `enrichment_status`. Exits early (idempotent no-op) if status is `SUCCESS` or `IN_PROGRESS`. Transitions to `IN_PROGRESS` and releases the transaction before making the OpenAI call.

**OpenAI call outside transaction:** The HTTP call to OpenAI happens after the transaction commits. This is intentional — holding a database row lock during a slow external HTTP call (potentially 1–5 seconds) is an anti-pattern that blocks other database writers and can cause deadlocks.

**Success path:** Writes Review fields (sentiment, tags, extracted_action_items, enrichment_version), creates AiUsageLog with computed cost locked at write time via `calculate_cost()`.

**Failure paths:**
- `OpenAITransientError` or `EnrichmentParseError`: marks FAILED, writes AiUsageLog with `status=FAILED`, then re-raises so Celery `autoretry_for` applies exponential backoff (30s, 2m, 10m).
- `OpenAIPermanentError`: marks FAILED, writes AiUsageLog with `status=FAILED`, returns `None` — no re-raise per ENRCH-04 (4xx other than 429 should not be retried immediately).

**enrichment_version as attempt counter:** The version field is incremented on every terminal state transition (both SUCCESS and FAILED). `retry_failed_enrichments_task` uses `enrichment_version < 3` as its re-enqueue gate, so each failed attempt increments the counter toward the cap of 3 total attempts.

### Task 2: apps/reviews/tasks.py additions

**enrich_review_task:**
- `@shared_task(bind=True, autoretry_for=(OpenAITransientError, EnrichmentParseError), max_retries=3, retry_backoff=30, retry_backoff_max=600, retry_jitter=True)`
- Routes to `ai-enrichment` queue (configured in `CELERY_TASK_ROUTES`)
- Thin wrapper: calls `enrich_review(review_id=review_id)`
- `OpenAIPermanentError` is NOT in `autoretry_for` because the service handles it by returning `None` (not raising). If the service returned None without raising, Celery would consider the task successful — which is the correct behaviour. `retry_failed_enrichments_task` (Beat-scheduled every 6h) serves as the sole re-attempt mechanism for permanent failures.

**retry_failed_enrichments_task:**
- `@shared_task` (no bind=True, no autoretry — this is a fan-out task, not a worker)
- Selects `FAILED` reviews where `enrichment_version < 3` and `deleted_at IS NULL`
- Capped at 500 reviews per run to prevent a single Beat tick from holding a worker for unbounded time when there is a large failed backlog
- Re-enqueues each via `enrich_review_task.delay(review_id)`
- Returns count of dispatched reviews

**MAX_TOTAL_ENRICH_ATTEMPTS = 3:** Module-level constant shared between `retry_failed_enrichments_task`'s queryset filter and the test's assertion of correct boundary behaviour.

## Key Design Decisions

### enrichment_version incremented on both SUCCESS and FAILED

**Why:** `enrichment_version` serves two purposes: (1) a semantic version for enrichment data (so `retry_failed_enrichments_task` can target reviews with older enrichment version), and (2) an attempt counter for `retry_failed_enrichments_task`'s re-enqueue gate. Incrementing on FAILED means each failed attempt counts toward the cap of 3, preventing infinite retry loops. This was the recommendation from RESEARCH.md Open Question 3.

### OpenAI call OUTSIDE transaction.atomic()

**Why:** Holding a PostgreSQL row lock (`select_for_update`) during a slow HTTP call (typically 1-5+ seconds for OpenAI) blocks other database writers for that row and can contribute to deadlocks under concurrency. The correct pattern is: acquire lock + read + short state transition (PENDING → IN_PROGRESS) in one fast transaction, release the lock, do the slow work, then do the final state transition in a second fast transaction.

### Cap of 500 reviews per retry_failed_enrichments_task run

**Why:** If many reviews fail simultaneously (e.g., OpenAI outage affecting 10,000+ reviews), a single Beat tick could enqueue all 10,000 tasks at once, potentially overloading the `ai-enrichment` worker pool. The 500-review cap means each 6-hour Beat tick re-enqueues a bounded batch, allowing the workers to process them gradually without being overwhelmed.

### OpenAIPermanentError not in autoretry_for and not re-raised

**Why:** Celery's `autoretry_for` retries when the specified exceptions are raised from the task body. If `OpenAIPermanentError` were in `autoretry_for`, Celery would retry (max_retries=3) — but permanent errors (400 Bad Request, context length exceeded) won't succeed on retry; they are programmer/data errors, not transient failures. By having the service catch and swallow the error (returning `None`), the Celery task completes as `SUCCESS` from Celery's perspective. `retry_failed_enrichments_task` then serves as the intentional human-in-the-loop retry mechanism for permanent failures, respecting the `enrichment_version < 3` cap.

### models.F("enrichment_version") + 1

**Why:** Using `models.F()` for the increment prevents a read-modify-write race condition. If two workers somehow concurrently update the same review's enrichment_version (e.g., after Redis lock expiry), each `F()` expression reads the current database value atomically and increments it. A Python-side `review.enrichment_version + 1` read from a stale local copy could silently lose an increment.

## Tests Written

12 tests in `apps/reviews/tests/test_enrichment_service.py`:
1. `test_lock_not_acquired_exits_without_calling_openai` — ENRCH-02 Redis lock gate
2. `test_idempotency_skips_when_status_success` — ENRCH-02 status flag (SUCCESS)
3. `test_idempotency_skips_when_status_in_progress` — ENRCH-02 status flag (IN_PROGRESS)
4. `test_status_transitions_pending_to_success` — ENRCH-03 full success path
5. `test_usage_log_written_on_success` — ENRCH-07 AiUsageLog write with correct fields + cost
6. `test_trace_id_persisted_when_present` — ENRCH-12 trace_id surfaces on AiUsageLog
7. `test_trace_id_blank_when_langsmith_disabled` — ENRCH-12 None trace_id becomes ''
8. `test_transient_error_marks_failed_and_raises` — ENRCH-04 OpenAITransientError path
9. `test_parse_error_marks_failed_and_raises` — ENRCH-04 EnrichmentParseError path
10. `test_permanent_error_marks_failed_and_returns` — ENRCH-04 OpenAIPermanentError (no raise)
11. `test_missing_review_exits_silently` — defensive Review.DoesNotExist handling
12. `test_failed_review_appears_in_serializer` — ENRCH-05 FAILED reviews not hidden

4 tests in `apps/reviews/tests/test_tasks.py` (Phase 12 additions):
1. `test_enrich_review_task_calls_service` — task is thin wrapper
2. `test_retry_failed_enrichments_task_enqueues_failed_reviews` — ENRCH-06 filtering logic
3. `test_retry_failed_enrichments_task_returns_zero_when_no_candidates` — empty case
4. `test_retry_failed_enrichments_task_caps_at_500_per_run` — defensive 500-cap

## Verification Results

- `pytest apps/reviews/tests/test_enrichment_service.py` — 12 passed
- `pytest apps/reviews/tests/test_tasks.py` — 10 passed (6 Phase 11 + 4 Phase 12)
- `pytest apps/common/tests/test_celery_config.py` — 7 passed
- `pytest apps/reviews/tests/` — 85 passed, 0 failures (no Phase 11 regressions)

## Deviations from Plan

None - plan executed exactly as written. The only difference is ruff-format auto-reformatted some `with` statement groups in the test file to the parenthesized form (Python 3.10+ style), which is a style improvement accepted by pre-commit.

## Self-Check: PASSED

Files created/modified:
- `apps/reviews/services/enrichment.py` — FOUND
- `apps/reviews/tests/test_enrichment_service.py` — FOUND
- `apps/reviews/tasks.py` — FOUND (modified)
- `apps/reviews/tests/test_tasks.py` — FOUND (modified)

Commits:
- `fde4ad4` — feat(12-04): build enrich_review service with three-layer idempotency
- `95c85d2` — feat(12-04): add enrich_review_task + retry_failed_enrichments_task
