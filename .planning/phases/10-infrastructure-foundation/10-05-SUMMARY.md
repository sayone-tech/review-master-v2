---
phase: 10-infrastructure-foundation
plan: 05
status: complete
completed_at: "2026-05-01"
commits:
  - sha: de4a082
    message: "feat(10-05): add Sentry integration + CI workflow — INFRA-06 + INFRA-07"
requirements_met:
  - INFRA-06
  - INFRA-07
---

# Plan 10-05 Summary — Sentry Integration + CI Gate

## What Was Done

### Task 1: Install sentry-sdk + Sentry init block in base.py
- Added `sentry-sdk==2.58.0` to `pyproject.toml` dependencies
- Added `sentry-sdk==2.58.0` to mypy pre-commit hook additional_dependencies
- Appended Sentry init block to `config/settings/base.py` after LOGGING block:
  - Imports `sentry_sdk`, `DjangoIntegration`, `CeleryIntegration`, `EventScrubber`
  - `_SENSITIVE_SUBSTRINGS = frozenset({"email", "token", "key", "secret", "password", "refresh", "access"})`
  - `_before_send()` recursively scrubs matching keys to `[Filtered]`
  - `sentry_sdk.init()` called ONLY when `SENTRY_DSN` is set — silent in dev/tests
  - Both `DjangoIntegration()` and `CeleryIntegration(propagate_traces=True)` passed
  - `send_default_pii=False`, `traces_sample_rate=0.1`
- Pre-commit fixes: changed `dict` to `dict[str, Any]` / `Event` type, used `[*DEFAULT_DENYLIST, ...]` syntax
- Appended `SENTRY_DSN=` and `ENVIRONMENT=local` to `.env.example`

### Task 2: Sentry integration tests (10 tests)
Created `apps/common/tests/test_sentry_integration.py` covering:
- All 7 sensitive substrings scrubbed (email, token, password, secret/key, recursive)
- Safe keys preserved unchanged
- None values handled (key still scrubbed, value untouched)
- Init skipped when SENTRY_DSN is None
- Init called with both integrations when DSN is set
- `ENVIRONMENT` var passed through to init

### Task 3: CI workflow
Created `.github/workflows/ci.yml` (no prior CI file existed):
- Triggers: pull_request + push to main
- Steps: checkout → install uv → Python 3.12 → uv sync → pre-commit → mypy →
  migration check → deployment check → **Celery smoke test** → pytest with coverage
- Celery smoke step: `timeout 30s uv run pytest apps/common/tests/test_celery_smoke.py -x -q --no-cov`
  - `timeout 30s` enforces INFRA-07's 30-second requirement at OS level
  - `--no-cov` prevents coverage instrumentation from slowing eager tasks
- Coverage step: `pytest --cov=apps --cov-fail-under=85`

## Requirements Satisfied

- **INFRA-06**: Sentry captures unhandled exceptions in BOTH web (DjangoIntegration)
  and Celery worker (CeleryIntegration) with PII scrubbing; gated on SENTRY_DSN
- **INFRA-07**: CI smoke test gate runs `test_celery_smoke.py` with 30s timeout on
  every PR; ensures task completion verified automatically

## Test Results

```
apps/common/tests/test_sentry_integration.py .......... 10 passed
Full suite: 487 passed, 0 failures
```
