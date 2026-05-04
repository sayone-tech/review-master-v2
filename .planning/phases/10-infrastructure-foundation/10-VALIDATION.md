---
phase: 10
slug: infrastructure-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 + pytest-asyncio (Wave 0 installs) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest apps/common/tests/test_celery_smoke.py apps/common/tests/test_locks.py apps/common/tests/test_retry.py -x -q` |
| **Full suite command** | `pytest apps/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/common/tests/ apps/reviews/tests/test_consumers.py -x -q`
- **After every plan wave:** Run `pytest apps/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | INFRA-01 | smoke | `pytest apps/common/tests/test_celery_smoke.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | INFRA-04 | unit | `pytest apps/common/tests/test_celery_config.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | INFRA-02 | smoke | `pytest apps/common/tests/test_beat_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 1 | INFRA-03 | manual | Review deployment config — Flower absent | manual-only | ⬜ pending |
| 10-03-01 | 03 | 2 | INFRA-08 | unit | `pytest apps/reviews/tests/test_asgi.py -x -q` | ❌ W0 | ⬜ pending |
| 10-03-02 | 03 | 2 | INFRA-09 | integration | `pytest apps/reviews/tests/test_consumers.py -x -q` | ❌ W0 | ⬜ pending |
| 10-04-01 | 04 | 2 | INFRA-10 | unit | `pytest apps/common/tests/test_locks.py -x -q` | ❌ W0 | ⬜ pending |
| 10-04-02 | 04 | 2 | INFRA-05 | unit | `pytest apps/common/tests/test_retry.py -x -q` | ❌ W0 | ⬜ pending |
| 10-04-03 | 04 | 2 | INFRA-11 | unit | `pytest apps/common/tests/test_retry.py -x -q` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 3 | INFRA-06 | unit | `pytest apps/common/tests/test_sentry_integration.py -x -q` | ❌ W0 | ⬜ pending |
| 10-05-02 | 05 | 3 | INFRA-07 | smoke | `pytest apps/common/tests/test_celery_smoke.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/common/tasks.py` — `smoke_test_task` (no-op task on both queues)
- [ ] `apps/common/tests/test_celery_smoke.py` — INFRA-01, INFRA-07
- [ ] `apps/common/tests/test_beat_schema.py` — INFRA-02
- [ ] `apps/common/tests/test_celery_config.py` — INFRA-04
- [ ] `apps/common/tests/test_locks.py` — INFRA-10
- [ ] `apps/common/tests/test_retry.py` — INFRA-05, INFRA-11
- [ ] `apps/common/tests/test_sentry_integration.py` — INFRA-06
- [ ] `apps/reviews/tests/test_consumers.py` — INFRA-09
- [ ] `apps/reviews/tests/test_asgi.py` — INFRA-08
- [ ] `apps/reviews/selectors/sync_progress.py` — stub (consumer import dependency)
- [ ] `uv add --dev pytest-asyncio` — async consumer tests
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` add `asyncio_mode = "auto"`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flower never deployed to production | INFRA-03 | Deployment config, not runtime code | Verify Flower absent from production Cloud Run service definition / Dockerfile CMD |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
