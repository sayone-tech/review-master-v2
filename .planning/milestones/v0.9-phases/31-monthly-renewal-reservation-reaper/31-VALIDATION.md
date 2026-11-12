---
phase: "31"
slug: "monthly-renewal-reservation-reaper"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-11"
---

# Phase 31 — Validation Strategy

> Per-phase validation contract. Requirement → test map: `31-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 + factory-boy (`--strict-markers --ds=config.settings.test`) |
| **Config file** | `pyproject.toml`; root `conftest.py` (pg auto-skip / `REQUIRE_PG`) |
| **Quick run command** | `.venv/bin/pytest apps/credits -x -q --no-cov` |
| **Full suite command** | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` |
| **Postgres command** | `make test-pg` (or a throwaway PG with `REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs`) |
| **Extra gates** | `makemigrations --check --dry-run`, `mypy apps/credits`, `ruff check . && ruff format --check .` |
| **Estimated runtime** | ~30 seconds quick run |

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest apps/credits -x -q --no-cov`
- **After every plan wave:** full suite + `makemigrations --check` + PG `pg_concurrency` run (passed, not skipped)
- **Before `/gsd-verify-work`:** full suite + gates green; post-push `backend-pg` CI green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner from PLAN.md task IDs.

| Requirement | Test file(s) | Type | Status |
|-------------|--------------|------|--------|
| CREN-01 (lapse, zero-remaining, idempotent, catch-up, straddle, keyset termination, query ceiling) | `apps/credits/tests/test_lapse.py` | unit | ✅ green |
| CREN-01 (lapsed_at honoured by late commit) | `apps/credits/tests/test_consumption.py` (edit) | unit | ✅ green |
| CREN-01 (overlapping sweeps) | `apps/credits/tests/test_pg_concurrency.py` | pg_concurrency | ✅ green |
| CREN-02 (fresh month from live allocation, bonus 0) | `apps/credits/tests/test_renewal.py` | unit | ✅ green |
| CREN-03 (reap, batch, re-run, RuntimeError, Sentry, D-08 lapse-after, cross-tenant audit attribution) | `apps/credits/tests/test_reaper.py` | unit | ✅ green |
| CREN-03 / CQA-01 (reaper vs late commit; overlapping reapers; past-period) | `apps/credits/tests/test_pg_concurrency.py` | pg_concurrency | ✅ green |
| Schedules / routes / settings / model | `test_tasks.py`, `test_settings.py`, `test_models.py` | unit | ✅ green |

*Local results (31-03): pg_concurrency 16 passed / 0 skipped on a throwaway PostgreSQL 14 (3 consecutive runs); full suite 1491 passed, 18 skipped (Postgres-only tests skip on SQLite), coverage 89.57%. CI backend-pg on PG16 is still a Manual-Only item below.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] New: `test_lapse.py`, `test_reaper.py`, `test_renewal.py`, `test_tasks.py`
- [x] `apps/credits/tests/helpers.py` `age_reservation()` (base `QuerySet.update` on `created_at`)
- [x] Edits: `test_pg_concurrency.py`, `test_consumption.py`, `test_settings.py`, `test_models.py`
- [x] No framework install (no freezegun; time via `now=` and patching `periods.utc_now`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` green on PG16 | CREN-03 / CQA-01 | Needs push | `gh run view` → `backend-pg` ≥1 passed, 0 skipped |
| Beat picks up seeded schedules | CREN-01/03 | Needs running Beat | After migrate + Beat restart, Django admin → Periodic tasks shows both, enabled, UTC |
| "Lapse not done by 00:30 UTC" alert | CREN-01 | Infra outside repo | Handed off in `docs/sre/v0.9-credits-rollout.md` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** local gates green 2026-11-11 (31-03); Manual-Only rows left open for `/gsd-verify-work`

## Validation Audit 2026-11-11

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
