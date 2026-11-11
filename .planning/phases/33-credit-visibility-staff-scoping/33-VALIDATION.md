---
phase: "33"
slug: "credit-visibility-staff-scoping"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-11"
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Backend: pytest 8.3.3 + pytest-django 4.9.0 + factory-boy. Frontend: vitest 2.1.8 + @testing-library/react 16.1.0 (jsdom) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`), `frontend/vitest.config.ts` |
| **Quick run command** | `.venv/bin/pytest apps/credits apps/shops apps/common apps/reviews/tests/test_views.py --no-cov -q` ; `cd frontend && npx vitest run src/widgets/credits src/widgets/shop-management src/widgets/review-management src/widgets/audit-log` |
| **Full suite command** | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` ; `cd frontend && npm test && npx tsc --noEmit` |
| **Estimated runtime** | ~60s quick, ~300s full |

---

## Sampling Rate

- **After every task commit:** Run the quick command scoped to the touched app or widget (plus `npx tsc --noEmit` when `types.ts` changes)
- **After every plan wave:** `.venv/bin/pytest apps/credits apps/shops apps/common apps/reviews --no-cov -q` + `cd frontend && npm test && npx tsc --noEmit`
- **Before `/gsd-verify-work`:** Full suite + `makemigrations --check --dry-run` + mypy + ruff green; `tenant-security-auditor` and `orm-performance-auditor` dispositions recorded
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled in from the PLAN files (task IDs are assigned by the planner). Requirement → test map from RESEARCH.md:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| CVIS-01 | Credits GET: virtual balance, no writes, `period_label`, `renews_on`, `no-store`, total 0 → not enabled | API | `.venv/bin/pytest apps/credits/tests/test_shop_credits_view.py -x --no-cov` | ❌ W0 | ⬜ pending |
| CVIS-01 | Credits card states, bands, no divide-by-zero, UTC dates | vitest | `cd frontend && npx vitest run src/widgets/credits` | ❌ W0 | ⬜ pending |
| CVIS-02 | `list_shops(with_credits=True)` one annotation; fixed query count 1 vs 20 | selector/API | `.venv/bin/pytest apps/shops/tests/test_selectors.py apps/shops/tests/test_views.py -k credit -x --no-cov` | ✅ (new cases) | ⬜ pending |
| CVIS-02 | Badge text/aria for all states | vitest | `cd frontend && npx vitest run src/widgets/shop-management src/widgets/credits` | partial | ⬜ pending |
| CVIS-03 | Composer state machine, 402 handling, pills disabled while generating | vitest | `cd frontend && npx vitest run src/widgets/review-management` | ❌ W0 | ⬜ pending |
| CVIS-04 | Buy More modal: focus trap, Esc, backdrop, encoded mailto, no payment | vitest | `cd frontend && npx vitest run src/widgets/credits` | ❌ W0 | ⬜ pending |
| CVIS-05 | Org Admin sees credit audit rows; Staff never; `shop_name` org-bounded; query ceiling | selector/API | `.venv/bin/pytest apps/common/tests/test_audit_log_selectors.py apps/common/tests/test_audit_log_api.py -x --no-cov` | ✅ (new cases) | ⬜ pending |
| SCOPE-01 | Staff list/credits GET scoped; out-of-scope 404; cross-org 404; Superadmin endpoints refuse Staff | API | `.venv/bin/pytest apps/credits/tests/test_access_selector.py apps/credits/tests/test_scope_sweep.py apps/shops/tests -k staff -x --no-cov` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/credits/tests/test_shop_credits_view.py`, `test_access_selector.py`, `test_scope_sweep.py`
- [ ] Credit + Staff cases in `apps/shops/tests/test_selectors.py`, `test_views.py`; audit cases in `apps/common/tests/`
- [ ] `frontend/src/widgets/credits/*.test.ts(x)` and `frontend/src/widgets/review-management/ReplyComposer.test.tsx`
- Framework install: none.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Colour bands read correctly in the real UI and dark/light contexts | CVIS-01, CVIS-02 | Visual check | Open Shops list + Shop Details for shops at 100%, 20%, 3%, 0, not enabled |
| Mailto opens the OS mail client with the expected subject/body | CVIS-04 | Depends on OS mail handler | Click Contact Admin from card, badge and composer |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
