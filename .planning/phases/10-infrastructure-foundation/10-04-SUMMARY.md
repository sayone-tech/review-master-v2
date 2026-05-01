---
phase: 10-infrastructure-foundation
plan: 04
status: complete
completed_at: "2026-05-01"
commits:
  - sha: 6b0e3ed
    message: "feat(10-04): add with_retry decorator and tests — INFRA-05 + INFRA-11"
requirements_met:
  - INFRA-05
  - INFRA-10
  - INFRA-11
---

# Plan 10-04 Summary — Redis Lock + Retry Decorator

## What Was Done

**Note:** `apps/common/locks.py` and `apps/common/tests/test_locks.py` (INFRA-10) were
committed by the plan 10-03 agent as part of its Task 1. This plan only needed to
deliver Task 2 (retry.py).

### Task 2: `apps/common/retry.py` + `apps/common/tests/test_retry.py`

Created `with_retry()` decorator factory backed by tenacity. Defaults match INFRA-05
spec exactly: `max_attempts=3`, `wait_min=30`, `wait_max=600`. 8 tests cover:
- Exhaustion (3 calls then raises original exception)
- Recovery (succeeds on 3rd attempt)
- First-success path (no retry needed)
- Exception type filtering (`retry_on` param)
- Default max_attempts introspection
- Default wait_min/wait_max introspection
- Default stop strategy introspection

Pre-commit fix: added `match="x"` to a `pytest.raises(ValueError)` call flagged by PT011.

## Requirements Satisfied

- **INFRA-05**: `with_retry(max_attempts=3, wait_min=30, wait_max=600)` — exponential
  backoff matching Celery's autoretry semantics for non-Celery call paths
- **INFRA-10**: `distributed_lock` context manager (committed in 10-03 agent's work)
- **INFRA-11**: Deliberately-failing function exhausts 3 attempts and re-raises original
  exception type unchanged

## Test Results

```
apps/common/tests/test_retry.py ........ 8 passed
apps/common/tests/test_locks.py ....... 7 passed (already committed)
```
