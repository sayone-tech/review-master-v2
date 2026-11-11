---
phase: "32"
slug: "superadmin-credit-controls"
status: complete-local
nyquist_compliant: true
wave_0_complete: true
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

| Plan-Task | Requirement | Test file(s) | Type | Status |
|-----------|-------------|--------------|------|--------|
| 32-01-T1..T3 | CRED-01 (field persist/validate/audit, create default 0, D-22 admin read-only) | `apps/organisations/tests/test_views.py`, `test_admin.py`, `apps/credits/tests/test_org_allocation.py` | API/service | ✅ green |
| 32-01-T1, T2 | CRED-06 (0→N immediate, N→M, N→0, D-18, raise zero rows, next month, idempotent, equivalence, query ceiling, rollback) | `apps/credits/tests/test_org_allocation.py` | service | ✅ green |
| 32-03-T1..T3 | CSUP-01 (list never writes, search/pagination, bonus ledger/audit, validation, 409/404, rollover) | `apps/credits/tests/test_views.py`, `test_bonus.py` | API/service | ✅ green |
| 32-01-T3, 32-03-T1..T3 | CSUP-02 (403 Org Admin/Staff/anon on every credit endpoint + PATCH field) | `apps/credits/tests/test_views.py`, `apps/organisations/tests/test_views.py` | API | ✅ green |
| 32-01-T1, 32-03-T3 | D-14/D-15/D-21 (`current_month_credit_allocation`, query ceiling unchanged) | `apps/organisations/tests/test_views.py` | API | ✅ green |
| 32-05-T1, T2 | PG races (edit vs ensure_balance, concurrent bonuses, bonus vs reserve, bonus vs 0→N); 20 passed, 0 skipped on throwaway PostgreSQL 14.20 | `apps/credits/tests/test_pg_concurrency.py` | pg_concurrency | ✅ green (local PG 14; CI PG 16 pending push) |
| 32-02-T1..T3, 32-04-T1..T3 | UI (creditHint, OrgTable column/action, Create/Edit/View modals, ManageCreditsModal incl. 409/404) | `frontend/src/widgets/org-management/*.test.ts(x)` | vitest | ✅ green (193 tests, tsc clean) |
| 32-05-T3 | Phase gate (coverage 89.88%, mypy, ruff, makemigrations --check, check --deploy, contract cross-check, no migration added) | full suite + gates | gate | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] New backend tests: `test_org_allocation.py`, `test_bonus.py`, `apps/credits/tests/test_views.py` (+ Superadmin/Staff client fixtures in credits conftest)
- [x] PG tests appended to `apps/credits/tests/test_pg_concurrency.py`
- [x] New frontend tests: `creditHint.test.ts`, `ManageCreditsModal.test.tsx`, `EditOrgModal.test.tsx`, `ViewOrgModal.test.tsx`
- [x] Update `OrgRow` fixtures in 4 existing frontend test files (or `tsc --noEmit` breaks)
- [x] No framework install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` green on PG16 | CRED-06 / CSUP-01 | Needs push | `gh run view` → `backend-pg` ≥1 passed, 0 skipped |
| Manage credits modal UX (focus, toast, 409 banner) | CSUP-01 | Visual | Superadmin → org row → Manage credits → add bonus; force month rollover via shell to see the 409 banner |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s (quick run)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** local gates signed off 2026-11-11. Still open for `/gsd-verify-work 32`: CI `backend-pg` on PostgreSQL 16 after push (expect 20 `pg_concurrency` tests, 0 skipped); Manage Credits UX walk including a forced month rollover for the 409 banner; the two 360px backstop checks.

## Validation Audit 2026-11-11

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
