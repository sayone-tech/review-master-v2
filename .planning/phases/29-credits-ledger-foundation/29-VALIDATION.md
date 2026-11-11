---
phase: "29"
slug: "credits-ledger-foundation"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-11"
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `29-RESEARCH.md` § Validation Architecture (requirement → test map lives there).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 + factory-boy 3.3.3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (add `markers` for `pg_concurrency`) |
| **Quick run command** | `.venv/bin/pytest apps/credits -x -q --no-cov` |
| **Full suite command** | `.venv/bin/pytest --cov=apps --cov-fail-under=85` |
| **Postgres race command** | `make test-pg` (or `REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs`) |
| **Estimated runtime** | ~20 seconds (credits quick run) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest apps/credits -x -q --no-cov`
- **After every plan wave:** Run `.venv/bin/pytest apps/credits apps/organisations apps/shops -q --no-cov` + `mypy apps/credits` + `makemigrations --check --dry-run`
- **Before `/gsd-verify-work`:** Full suite green AND `backend-pg` CI job green (tests passed, not skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner/executor from PLAN.md task IDs. Requirement → test-file mapping (from RESEARCH.md):

| Requirement | Test file | Test Type | Automated Command | File Exists | Status |
|-------------|-----------|-----------|-------------------|-------------|--------|
| CRED-02 | `apps/credits/tests/test_models.py`, `test_allocation.py` | unit/DB | `.venv/bin/pytest apps/credits/tests/test_models.py apps/credits/tests/test_allocation.py -x` | ❌ W0 | ⬜ pending |
| CRED-02 / CQA-01 | `apps/credits/tests/test_pg_concurrency.py` | pg_concurrency | `make test-pg` | ❌ W0 | ⬜ pending |
| CRED-03 | `apps/credits/tests/test_append_only.py`, `test_admin.py`, `test_models.py` | unit/integration | `.venv/bin/pytest apps/credits/tests/test_append_only.py apps/credits/tests/test_admin.py -x` | ❌ W0 | ⬜ pending |
| CRED-04 | `apps/credits/tests/test_credit_cost.py`, `test_settings.py`, `test_periods.py` | unit | `.venv/bin/pytest apps/credits/tests/test_credit_cost.py apps/credits/tests/test_settings.py apps/credits/tests/test_periods.py -x` | ❌ W0 | ⬜ pending |
| CRED-05 | `apps/credits/tests/test_selectors.py` | unit + query-count | `.venv/bin/pytest apps/credits/tests/test_selectors.py -x` | ❌ W0 | ⬜ pending |
| CQA-01 | `conftest.py` hook, `config/settings/test_pg.py`, `.github/workflows/ci.yml` | infra/CI | `REQUIRE_PG=1 .venv/bin/pytest apps/credits -q` exits non-zero on SQLite; `backend-pg` job green | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/credits/` skeleton + `apps/credits/tests/factories.py`
- [ ] `pyproject.toml` `markers`, root `conftest.py` skip hook + `REQUIRE_PG` guard, `config/settings/test_pg.py`, `ci.yml` `backend-pg`, `Makefile` `test-pg`
- [ ] `apps/credits/tests/conftest.py` re-exporting `assert_query_ceiling`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` runs on Postgres 16 in GitHub Actions | CQA-01 | Needs a pushed branch | Push branch; `gh run view` → `backend-pg` green with ≥1 passed (not skipped) |
| Migrations reversible | CRED-02/03 | One-off on scratch PG | `manage.py migrate credits zero && manage.py migrate organisations <prev>` succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
