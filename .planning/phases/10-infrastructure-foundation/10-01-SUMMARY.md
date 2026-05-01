---
phase: 10
plan: "01"
subsystem: celery-runtime
tags: [celery, background-jobs, infrastructure, redis, testing]
dependency_graph:
  requires: []
  provides:
    - celery-app-instance
    - celery-settings
    - smoke-test-task
    - worker-docker-service
  affects:
    - all future plans that register @shared_task
    - Plan 10-02 (Beat + Flower docker services build on this)
    - Phase 11+ (reviews sync, enrichment tasks route through these queues)
tech_stack:
  added:
    - celery==5.6.3
    - django-celery-beat==2.9.0
    - flower==2.0.1 (dev)
    - pytest-asyncio==1.1.0 (dev)
  patterns:
    - config/celery.py + config/__init__.py import pattern for shared_task registration
    - CELERY_TASK_ALWAYS_EAGER in test.py for broker-free CI testing
    - type: ignore[misc] on @shared_task(bind=True) for mypy strict mode compatibility
key_files:
  created:
    - config/celery.py
    - apps/common/tasks.py
    - apps/common/tests/test_celery_smoke.py
    - apps/common/tests/test_celery_config.py
  modified:
    - config/__init__.py (replaced empty file with celery_app import)
    - config/settings/base.py (CELERY_* block + django_celery_beat in INSTALLED_APPS)
    - config/settings/test.py (django_celery_beat in INSTALLED_APPS + ALWAYS_EAGER flags)
    - docker-compose.yml (worker service added)
    - pyproject.toml (4 new deps + mypy overrides for celery/kombu/billiard/django_celery_beat)
    - .pre-commit-config.yaml (celery + django-celery-beat as mypy additional_dependencies)
    - uv.lock (regenerated with 22 new packages)
decisions:
  - "@shared_task(bind=True) with type: ignore[misc] and Any for self — mypy strict mode has no stubs for celery decorators; this is the idiomatic solution"
  - "Added celery/django-celery-beat to pre-commit mypy additional_dependencies so the isolated hook env has the packages available for Django settings initialisation"
  - "Reused web_venv volume for worker — simplest approach; each service runs uv sync --frozen independently (per CONTEXT.md decision)"
metrics:
  duration: "7 minutes"
  completed_date: "2026-05-01"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 7
---

# Phase 10 Plan 01: Celery Runtime Foundation Summary

Celery 5.6.3 installed with Redis broker (DB 3) + result backend (DB 4), two named queues (`google-sync`, `ai-enrichment`), all CLAUDE.md §12.2 settings verbatim, and smoke tests proving INFRA-01, INFRA-04, INFRA-07 in eager mode.

## What Was Built

| Component | Description |
|-----------|-------------|
| `config/celery.py` | Celery app instance (`Celery("review_master")`) with Django settings namespace and autodiscover |
| `config/__init__.py` | Exposes `celery_app` so Django startup registers it; enables `@shared_task` across all apps |
| `config/settings/base.py` | Full `CELERY_*` settings block: broker, result backend, two queue routes, time limits, ack-late, prefetch=1 |
| `config/settings/test.py` | `CELERY_TASK_ALWAYS_EAGER=True` + `CELERY_TASK_EAGER_PROPAGATES=True` for broker-free CI |
| `apps/common/tasks.py` | `smoke_test_task` — no-op `@shared_task` for INFRA-07 CI gate |
| `apps/common/tests/test_celery_smoke.py` | 3 tests: task on google-sync, ai-enrichment, default queue |
| `apps/common/tests/test_celery_config.py` | 7 tests: time limits, queues, routes, ack-late, prefetch, broker/backend DB indices |
| `docker-compose.yml` | `worker` service subscribes to all 3 queues; concurrency via `CELERY_WORKER_CONCURRENCY` env (default 2) |

## Commits

| Hash | Description |
|------|-------------|
| `7b952d3` | feat(10-01): install Celery 5.6.3 + django-celery-beat 2.9.0; create Celery app instance |
| `f4dda9a` | feat(10-01): add CELERY_* settings; create smoke_test_task and config tests |
| `77a47b6` | feat(10-01): add worker service to docker-compose.yml |

## Test Results

```
10 passed in 0.45s
apps/common/tests/test_celery_smoke.py ...     (3 tests)
apps/common/tests/test_celery_config.py ....... (7 tests)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added celery to pre-commit mypy hook dependencies**
- **Found during:** Task 1 commit attempt
- **Issue:** The pre-commit mypy hook runs in an isolated Python environment. When `config/__init__.py` imports from `config/celery.py`, and the mypy hook tries to initialise Django settings, it hits `ModuleNotFoundError: No module named 'celery'` because celery isn't in the isolated pre-commit env.
- **Fix:** Added `celery==5.6.3` and `django-celery-beat==2.9.0` to the mypy hook's `additional_dependencies` in `.pre-commit-config.yaml`. Also added `mypy overrides` for `celery.*`, `kombu.*`, `billiard.*`, and `django_celery_beat.*` with `ignore_missing_imports = true` as belt-and-braces.
- **Files modified:** `.pre-commit-config.yaml`, `pyproject.toml`
- **Commit:** `7b952d3`

**2. [Rule 1 - Bug] Added type annotation to smoke_test_task self parameter**
- **Found during:** Task 2 commit attempt
- **Issue:** mypy strict mode flagged `@shared_task(bind=True)` as an untyped decorator making `smoke_test_task` untyped, and `self` as missing a type annotation.
- **Fix:** Added `from typing import Any`, typed `self: Any`, added `# type: ignore[misc]` on the decorator. Celery has no official mypy stubs; this is the idiomatic workaround.
- **Files modified:** `apps/common/tasks.py`
- **Commit:** `f4dda9a`

## Requirements Satisfied

| ID | Status | Evidence |
|----|--------|---------|
| INFRA-01 | DONE | `test_celery_smoke.py` proves tasks complete on `google-sync` and `ai-enrichment` queues |
| INFRA-04 | DONE | `test_celery_config.py` asserts `TIME_LIMIT=600`, `SOFT_TIME_LIMIT=300`, `WORKER_PREFETCH_MULTIPLIER=1` |
| INFRA-07 | DONE | `test_celery_smoke.py` CI gate proves tasks complete within timeout |
