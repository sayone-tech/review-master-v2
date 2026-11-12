---
phase: "33"
slug: "credit-visibility-staff-scoping"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: true) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
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

Results from the 33-07 gate run (full backend suite 1650 passed / 22 skipped, 90.34% coverage; frontend 349 passed; tsc, mypy, ruff clean; 85 backend tests re-run green on throwaway PostgreSQL with `config.settings.test_pg`).

| Task ID | Plan | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|-------------|----------|-----------|-------------------|-------------|--------|
| 33-01-T1, 33-01-T2 | 01 | SCOPE-01, CVIS-02 | `list_shops` Staff scope matrix, Staff retrieve 404 (D-17), `get_accessible_shop_for_credits`, one credit annotation, query count 1 vs 20 | selector/API | `.venv/bin/pytest apps/shops/tests/test_selectors.py apps/shops/tests/test_views.py --no-cov -q` | ✅ | ✅ green |
| 33-01-T3 | 01 | CVIS-04 | Shops page `credit-contact` bootstrap | API | `.venv/bin/pytest apps/shops/tests/test_views.py --no-cov -q` | ✅ | ✅ green |
| 33-02-T1, 33-02-T2 | 02 | CVIS-05 | Org Admin sees credit audit rows; Staff never; `shop_name` org-bounded; query ceiling | selector/API | `.venv/bin/pytest apps/common/tests/test_audit_log_selectors.py apps/common/tests/test_audit_log_api.py --no-cov -q` | ✅ | ✅ green (also on PostgreSQL) |
| 33-02-T3 | 02 | CVIS-05 | Activity Log labels, Credits pill, shop-name cell | vitest | `cd frontend && npx vitest run src/widgets/audit-log` | ✅ | ✅ green |
| 33-03-T1, 33-03-T2 | 03 | CVIS-04 | Buy More modal: focus trap, Esc, backdrop, encoded mailto, no payment | vitest | `cd frontend && npx vitest run src/widgets/credits` | ✅ | ✅ green |
| 33-03-T3 | 03 | CVIS-01, CVIS-02 | Band helper, UTC date formatters, shop-keyed store | vitest | `cd frontend && npx vitest run src/widgets/credits` | ✅ | ✅ green |
| 33-04-T1, 33-04-T2 | 04 | CVIS-01, SCOPE-01 | Credits GET: virtual balance, no writes, `period_label`, `renews_on`, `no-store`, not enabled, 404 | API | `.venv/bin/pytest apps/credits/tests/test_shop_credits_view.py apps/credits/tests/test_periods.py --no-cov -q` | ✅ | ✅ green (also on PostgreSQL) |
| 33-04-T3 | 04 | SCOPE-01 | Table-driven negative sweep plus route-coverage guard | API | `.venv/bin/pytest apps/credits/tests/test_scope_sweep.py --no-cov -q` | ✅ | ✅ green |
| 33-05-T1 | 05 | CVIS-03, CVIS-04 | Reviews page bootstrap; composer shows server cost and remaining | API/vitest | `.venv/bin/pytest apps/reviews/tests/test_views.py -k CreditContact --no-cov -q` ; `cd frontend && npx vitest run src/widgets/review-management` | ✅ | ✅ green |
| 33-05-T2, 33-05-T3 | 05 | CVIS-03 | Composer disabled states, 402/409/422/502 handling, tone-pill cost | vitest | `cd frontend && npx vitest run src/widgets/review-management` | ✅ | ✅ green |
| 33-06-T1, 33-06-T2 | 06 | CVIS-01, CVIS-04 | Credits card states, stacked Buy More flow | vitest | `cd frontend && npx vitest run src/widgets/credits src/widgets/shop-management` | ✅ | ✅ green |
| 33-06-T3 | 06 | CVIS-02 | Badge states, store seeding, Staff empty state | vitest | `cd frontend && npx vitest run src/widgets/shop-management src/widgets/credits` | ✅ | ✅ green |
| 33-07-T1 | 07 | CVIS-01..05, SCOPE-01 | Whole-phase walk-through across Org Admin, Superadmin and Staff; frontend/backend contract keys | API | `.venv/bin/pytest apps/credits/tests/test_phase33_flow.py --no-cov -q` | ✅ | ✅ green (also on PostgreSQL) |
| 33-07-T2 | 07 | SCOPE-01, CVIS-05 | Four section 27 reviews dispositioned; runbook and CLAUDE.md match shipped behaviour | review/docs | PostgreSQL run of audit, Shops selector and credits view tests | ✅ | ✅ green |
| 33-07-T3 | 07 | all | Full gates: coverage >= 85, mypy, ruff, makemigrations --check, check --deploy, frontend suite, tsc | gates | see Full suite command | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Note: the draft referenced `apps/credits/tests/test_access_selector.py`; Plan 33-01 placed `get_accessible_shop_for_credits` in `apps/shops`, so its tests live in `apps/shops/tests/test_selectors.py` (keeps `apps/credits` free of `apps.reviews` imports).

---

## Wave 0 Requirements

- [x] `apps/credits/tests/test_shop_credits_view.py`, `test_scope_sweep.py`, `test_phase33_flow.py` (selector tests live in `apps/shops/tests/test_selectors.py`)
- [x] Credit + Staff cases in `apps/shops/tests/test_selectors.py`, `test_views.py`; audit cases in `apps/common/tests/`
- [x] `frontend/src/widgets/credits/*.test.ts(x)` and `frontend/src/widgets/review-management/ReplyComposer.test.tsx`
- Framework install: none.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Colour bands read correctly in the real UI and dark/light contexts | CVIS-01, CVIS-02 | Visual check | Open Shops list + Shop Details for shops at 100%, 20%, 3%, 0, not enabled |
| Mailto opens the OS mail client with the expected subject/body | CVIS-04 | Depends on OS mail handler | Click Contact Admin from card, badge and composer |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** automated rows validated by Plan 33-07 on 2026-11-12. Still open for `/gsd-verify-work` (manual / UI-SPEC backstop): colour bands in the real UI, OS mail client opening from card, badge and composer, two 360px composer checks, the 200-character / emoji mailto check, and the two-Escape ordering over stacked modals. CI `backend-pg` (pg_concurrency) remains authoritative after push.

## Validation Audit 2026-11-11

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
