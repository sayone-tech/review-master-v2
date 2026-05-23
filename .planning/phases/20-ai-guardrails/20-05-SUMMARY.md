---
phase: 20-ai-guardrails
plan: 05
subsystem: reviews/enrichment
tags: [ai, guardrails, moderation, idempotency]
requires:
  - apps/integrations/openai/guardrails.py (moderate_input — Plan 20-04)
  - apps/integrations/openai/exceptions.py (ContentModeratedException — Plan 20-02)
  - apps/reviews/models.py (Review.enrichment_error_code — Plan 20-03)
  - apps/integrations/openai/models.py (AiUsageLog.Status.MODERATED — Plan 20-01)
provides:
  - apps/reviews/services/enrichment.py::_persist_moderated
  - enrich_review wired with input-moderation pre-OpenAI call
affects:
  - apps/reviews/services/enrichment.py
  - apps/reviews/tests/test_enrichment_service.py
tech-stack:
  added: []
  patterns:
    - moderation-before-OpenAI gate (D-15)
    - audit-row-survives-rollback via call-outside-atomic (D-33)
    - denormalized error_code for retry-task exclusion (D-31)
key-files:
  created: []
  modified:
    - apps/reviews/services/enrichment.py
    - apps/reviews/tests/test_enrichment_service.py
decisions:
  - "moderate_input call site is OUTSIDE any transaction.atomic block (D-33) so the MODERATED AiUsageLog row written inside guardrails survives a downstream rollback"
  - "Truncated text flows into the prompt by mutating the in-memory review.comment (not saved) — simplest hand-off that respects the existing build_enrichment_messages contract"
  - "_persist_moderated does NOT write AiUsageLog (guardrails already did) and does NOT use _persist_failure (which would duplicate the row)"
  - "Atomic-isolation regression test uses savepoint_ids depth (not in_atomic_block) because @pytest.mark.django_db wraps every test in an outer atomic"
metrics:
  duration: ~10 min
  completed: 2026-05-23
---

# Phase 20 Plan 05: Wire moderate_input into enrich_review Summary

Plan 20-05 wires the Phase 20 input-moderation guardrail into the review-enrichment pipeline. Calls `moderate_input(review.comment)` before `call_openai_enrichment`, persists a FAILED + `content_moderated` Review row on block (via new `_persist_moderated` helper), and pins the call-outside-atomic invariant (D-33) plus the SUCCESS-status idempotency short-circuit (D-15) with regression tests.

## What Was Built

### `apps/reviews/services/enrichment.py`
- **Imports added** — `ContentModeratedException` (from existing exceptions module) and `moderate_input` (from the Plan 20-04 guardrails module).
- **New helper `_persist_moderated(review)`** — sets `enrichment_status=FAILED`, `enrichment_error_code="content_moderated"`, `enrichment_attempted_at=timezone.now()`, and saves the three fields. No `transaction.atomic` wrapper (single-row save). No `AiUsageLog` write (guardrails already wrote the MODERATED row before raising, per D-33).
- **`enrich_review` wired** between the no-comment skip block and the OpenAI call:
  - `truncated_text = moderate_input(review.comment, review=review, request_type="enrichment")` inside a `try`.
  - On `ContentModeratedException`: `_persist_moderated(review)` and return — no OpenAI call.
  - On success: mutate `review.comment = truncated_text` (in-memory only, not saved) so the existing `build_enrichment_messages` prompt assembly picks up the truncated form (D-21).
  - The moderation call sits OUTSIDE the `with transaction.atomic()` block that opened at line ~400 and closed at line ~427 (Pitfall 3).

### `apps/reviews/tests/test_enrichment_service.py`
- **New `TestEnrichReviewModeration` class** with four tests:
  1. `test_moderate_input_called_before_openai` — asserts call order via a recorded list; verifies the OpenAI mock receives a review whose `.comment` is the truncated value from `moderate_input`.
  2. `test_moderate_input_blocks_sets_failed_with_error_code` — patches `moderate_input` to raise `ContentModeratedException`; asserts `call_openai_enrichment` not called, Review row is `FAILED` + `error_code="content_moderated"` + `enrichment_attempted_at` set.
  3. `test_moderate_input_does_not_use_atomic_block` — Pitfall 3 / D-33 regression. Captures `len(connection.savepoint_ids)` before the call and at the moderation call site; asserts depth unchanged (no nested `transaction.atomic` from `enrich_review` is open). Snapshots-vs-`in_atomic_block` because `@pytest.mark.django_db` always wraps tests in an outer atomic.
  4. `test_already_success_review_skips_moderation` — D-15 idempotency regression. SUCCESS-status review → `moderate_input` and `call_openai_enrichment` both NOT called; `AiUsageLog` count unchanged. Prevents a future refactor from moving `moderate_input` above the `select_for_update` SUCCESS guard and silently re-billing moderated traffic.

## How To Verify

```bash
# All four new tests pass
.venv/bin/python -m pytest apps/reviews/tests/test_enrichment_service.py::TestEnrichReviewModeration -x -q

# Full test file regression
.venv/bin/python -m pytest apps/reviews/tests/test_enrichment_service.py

# Pitfall 3: zero atomic occurrences in 10 lines preceding moderate_input call
grep -B 10 'moderate_input(review.comment' apps/reviews/services/enrichment.py | grep -v '^#' | grep -c 'transaction.atomic'   # → 0

# Ruff + mypy via pre-commit
.venv/bin/ruff check apps/reviews/services/enrichment.py apps/reviews/tests/test_enrichment_service.py
```

Result: 4/4 new tests pass; 32/32 tests in the file pass; ruff clean; mypy clean (pre-commit hook).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Pitfall-3 regression test rewritten to use savepoint depth**
- **Found during:** Task 2 verification (initial test run).
- **Issue:** The plan's `<action>` suggested asserting `transaction.get_connection().in_atomic_block is False` at the moderation call site. Under `@pytest.mark.django_db`, every test executes inside an outer atomic block, so `in_atomic_block` is always `True` and the assertion always fails — even though the implementation is correct.
- **Fix:** Snapshot `len(connection.savepoint_ids)` immediately before invoking `enrich_review`, record the same value at the moderation call-site side-effect, and assert equality. This proves no nested atomic block was pushed by `enrich_review` between the two reads — which is the actual invariant D-33 cares about. The docstring documents the reasoning so future maintainers don't "fix" it back to the broken pattern.
- **Files modified:** `apps/reviews/tests/test_enrichment_service.py` (test body and docstring only).
- **Commit:** `0fd2e8e`

### Auth Gates
None — task is fully isolated unit-test work.

## Threat Surface

No new threat surface introduced. This plan IMPLEMENTS mitigations for the Phase 20 threat register:

| Threat ID | Mitigation Implemented |
|-----------|-------------------------|
| T-20-01 (prompt injection) | `moderate_input` runs before prompt assembly; truncated return value flows into the prompt |
| T-20-05 (audit-log loss) | Call site outside `transaction.atomic`; regression test asserts savepoint depth unchanged |
| T-20-RT (Celery retry of moderated row) | `Review.enrichment_error_code = "content_moderated"` populated for Plan 20-08 retry exclusion |

## Self-Check: PASSED

- File `apps/reviews/services/enrichment.py` exists and contains `_persist_moderated`, `moderate_input` import, `ContentModeratedException` import. FOUND.
- File `apps/reviews/tests/test_enrichment_service.py` contains `class TestEnrichReviewModeration` with four tests. FOUND.
- File `.planning/phases/20-ai-guardrails/20-05-SUMMARY.md` exists. FOUND.
- Commit `49f75be` (Task 1): FOUND.
- Commit `0fd2e8e` (Task 2): FOUND.
- Pytest `TestEnrichReviewModeration`: 4 passed.
- Pytest full file: 32 passed.
- Ruff: clean.
