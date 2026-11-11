---
phase: "32"
slug: "superadmin-credit-controls"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-11"
---

# Phase 32 — Validation Strategy

> Per-phase validation contract. Requirement → test map: `32-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 8.3.3 + pytest-django + factory-boy. Frontend: vitest 2.1.8 + @testing-library/react (jsdom) |
| **Config file** | `pyproject.toml`, root `conftest.py`, `frontend/vitest.config.ts` |
| **Quick run command** | `.venv/bin/pytest apps/credits apps/organisations --no-cov -q` ; `cd frontend && npx vitest run src/widgets/org-management` |
| **Full suite command** | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` ; `cd frontend && npm test && npx tsc --noEmit` |
| **Postgres command** | `make test-pg` or throwaway PG `REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` (CI `backend-pg` authoritative) |
| **Extra gates** | `makemigrations --check --dry-run` (no model change expected), `mypy .`, `ruff`, `spectacular --validate` |
| **Estimated runtime** | ~60 seconds quick run |

---

## Sampling Rate

- **After every task commit:** quick-run commands (plus `npx tsc --noEmit` when `types.ts` changes)
- **After every plan wave:** `.venv/bin/pytest apps/credits apps/organisations apps/common --no-cov -q` + `cd frontend && npm test && npx tsc --noEmit`
- **Before `/gsd-verify-work`:** full suite + gates green; `backend-pg` CI green; tenant-security-auditor + orm-performance-auditor + code-reviewer dispositions recorded
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled by the planner from PLAN.md task IDs.

| Requirement | Test file(s) | Type | Status |
|-------------|--------------|------|--------|
| CRED-01 (field persist/validate/audit, create default 0, D-22 admin read-only) | `apps/organisations/tests/test_views.py`, `test_services.py`, admin test | API/service | ⬜ pending |
| CRED-06 (0→N immediate, N→M, N→0, D-18, raise zero rows, next month, idempotent, equivalence, query ceiling, rollback) | `apps/credits/tests/test_org_allocation.py` | service | ⬜ pending |
| CSUP-01 (list never writes, search/pagination, bonus ledger/audit, validation, 409/404, rollover) | `apps/credits/tests/test_views.py`, `test_bonus.py` | API/service | ⬜ pending |
| CSUP-02 (403 Org Admin/Staff/anon on every credit endpoint + PATCH field) | `apps/credits/tests/test_views.py`, `apps/organisations/tests/test_views.py` | API | ⬜ pending |
| D-14/D-15/D-21 (`current_month_credit_allocation`, query ceiling unchanged) | `apps/organisations/tests/test_views.py` | API | ⬜ pending |
| PG races (edit vs ensure_balance, concurrent bonuses, bonus vs reserve, bonus vs 0→N) | `apps/credits/tests/test_pg_concurrency.py` | pg_concurrency | ⬜ pending |
| UI (creditHint, OrgTable column/action, Create/Edit/View modals, ManageCreditsModal incl. 409/404) | `frontend/src/widgets/org-management/*.test.ts(x)` | vitest | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New backend tests: `test_org_allocation.py`, `test_bonus.py`, `apps/credits/tests/test_views.py` (+ Superadmin/Staff client fixtures in credits conftest)
- [ ] PG tests appended to `apps/credits/tests/test_pg_concurrency.py`
- [ ] New frontend tests: `creditHint.test.ts`, `ManageCreditsModal.test.tsx`, `EditOrgModal.test.tsx`, `ViewOrgModal.test.tsx`
- [ ] Update `OrgRow` fixtures in 4 existing frontend test files (or `tsc --noEmit` breaks)
- [ ] No framework install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` green on PG16 | CRED-06 / CSUP-01 | Needs push | `gh run view` → `backend-pg` ≥1 passed, 0 skipped |
| Manage credits modal UX (focus, toast, 409 banner) | CSUP-01 | Visual | Superadmin → org row → Manage credits → add bonus; force month rollover via shell to see the 409 banner |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
