---
phase: 8
slug: shops
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| **Quick run command** | `pytest apps/shops/ apps/integrations/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Frontend test command** | `cd frontend && npm test` |
| **Estimated runtime** | ~30 seconds (quick), ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/shops/ apps/integrations/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | SHOP-11 | unit | `pytest apps/integrations/google/tests/ -x -q` | ❌ Wave 0 | ⬜ pending |
| 08-01-02 | 01 | 1 | SHOP-10 | unit | `pytest apps/integrations/google/tests/test_places.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-02-01 | 02 | 1 | SHOP-02, XMOD-04 | integration | `pytest apps/shops/tests/test_services.py::TestCreateShopAllocation -x` | ❌ Wave 0 | ⬜ pending |
| 08-02-02 | 02 | 1 | SHOP-19 | unit | `pytest apps/shops/tests/test_services.py::TestRevealApiKey -x` | ❌ Wave 0 | ⬜ pending |
| 08-02-03 | 02 | 1 | SHOP-20 | unit | `pytest apps/shops/tests/test_services.py::TestRotateApiKey -x` | ❌ Wave 0 | ⬜ pending |
| 08-02-04 | 02 | 1 | SHOP-03 | unit | `pytest apps/shops/tests/test_selectors.py::TestListShopsFilters -x` | ❌ Wave 0 | ⬜ pending |
| 08-03-01 | 03 | 2 | SHOP-01 | unit | `pytest apps/shops/tests/test_views.py::TestShopsListAllocation -x` | ❌ Wave 0 | ⬜ pending |
| 08-03-02 | 03 | 2 | SHOP-11 COOP | unit | `pytest apps/shops/tests/test_views.py::TestOAuthStartView -x` | ❌ Wave 0 | ⬜ pending |
| 08-03-03 | 03 | 2 | SHOP-13 | unit | `pytest apps/shops/tests/test_views.py::TestShopSerializerFields -x` | ❌ Wave 0 | ⬜ pending |
| 08-03-04 | 03 | 2 | XMOD-04 | integration | `pytest apps/shops/tests/test_views.py::test_shops_list_query_count_ceiling -x` | ❌ Wave 0 | ⬜ pending |
| 08-03-05 | 03 | 2 | cross-tenant | integration | `pytest apps/shops/tests/test_views.py::test_shops_cross_tenant_isolation -x` | ❌ Wave 0 | ⬜ pending |
| 08-04-01 | 04 | 2 | SHOP-04, SHOP-05 | manual | see Manual Verifications | N/A | ⬜ pending |
| 08-05-01 | 05 | 3 | SHOP-09, SHOP-11 | manual | see Manual Verifications | N/A | ⬜ pending |
| 08-05-02 | 05 | 3 | SHOP-12 | manual | see Manual Verifications | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All files below must be created (as stubs or full implementations) before automated tests can run:

- [ ] `apps/integrations/__init__.py` — package root
- [ ] `apps/integrations/google/__init__.py` — google integration package
- [ ] `apps/integrations/google/tests/__init__.py` — test directory
- [ ] `apps/shops/tests/conftest.py` — re-export `assert_query_ceiling`, `two_orgs_two_admins` (mirror `apps/regions/tests/conftest.py`)
- [ ] `apps/shops/services/__init__.py` + `apps/shops/services/shops.py` — service layer stubs
- [ ] `apps/shops/selectors/__init__.py` + `apps/shops/selectors/shops.py` — selector layer stubs
- [ ] `apps/shops/exceptions.py` — `ShopAtLimitError` and other domain exceptions
- [ ] `apps/shops/serializers.py` — read/create/update serializer stubs
- [ ] `apps/shops/views.py` — `ShopViewSet`, `shop_list` template view, OAuth views
- [ ] `apps/shops/migrations/0002_shop_audit_log.py` — `ShopAuditLog` migration
- [ ] `apps/shops/tests/test_services.py` — service test stubs
- [ ] `apps/shops/tests/test_selectors.py` — selector test stubs
- [ ] `apps/shops/tests/test_views.py` — DRF + template view test stubs
- [ ] Frontend: `frontend/src/entrypoints/shop-management.tsx`
- [ ] Frontend: `frontend/src/widgets/shop-management/` directory + component files
- [ ] Vite: add `shop-management` entrypoint to `rollupOptions.input` in `vite.config.ts`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Allocation counter "Shops (X / Y)" in page header updates after shop create | SHOP-01 | DOM visual; no browser in CI | Open /admin/org/shops/, count X matches shop count, create a shop, verify counter increments |
| "+ Add Shop" button disabled with tooltip at allocation limit | SHOP-02 | Tooltip visibility + disabled state | Set org.number_of_stores == shop count, reload Shops page, hover button, verify tooltip text "Shop limit reached." |
| OAuth popup opens ~600×700px, COOP allows cross-origin postMessage | SHOP-11 | Requires browser + Google OAuth | Click "Connect with Google", verify popup opens, complete OAuth flow, verify success row appears in modal |
| Popup edge cases: close/deny/error/no-listings | SHOP-12 | Browser interaction + OAuth states | Manually trigger each edge case, verify correct inline message in parent modal |
| Connection Status pill variants (4 states) render correctly | SHOP-05 | Visual; needs shop rows with each status | Create shops with each ConnectionStatus, verify correct colour dot and label in table |
| 30-second auto-mask after Reveal API Key | SHOP-19 | Timer-based UI; not unit-testable | Click Reveal, verify key shown, wait 30s, verify it re-masks |
| Safari synchronous window.open (no async before open) | SHOP-11 | Safari browser required | Test in Safari; popup must open without being blocked |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
