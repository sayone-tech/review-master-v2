---
phase: 7
slug: regions
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-28
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django 8.3.3 (backend) · vitest (frontend) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/regions/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Frontend quick command** | `cd frontend && npm run test -- region-management` |
| **Estimated runtime** | ~30 seconds (backend) · ~10 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/regions/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Frontend tasks:** Run `cd frontend && npm run test -- region-management` after each frontend commit
- **Before `/gsd:verify-work`:** Full suite must be green + `cd frontend && npm run test`
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | RGN-01–11 | unit | `pytest apps/regions/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | RGN-01–11 | unit | `pytest apps/regions/tests/test_selectors.py -x -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | RGN-01,06,07 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_list -x` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | RGN-03,06 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_create_validation -x` | ❌ W0 | ⬜ pending |
| 7-02-03 | 02 | 1 | RGN-06 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_create_duplicate_id -x` | ❌ W0 | ⬜ pending |
| 7-02-04 | 02 | 1 | RGN-08,09 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_patch -x` | ❌ W0 | ⬜ pending |
| 7-02-05 | 02 | 1 | RGN-10,11,XMOD-02 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_delete_blocked -x` | ❌ W0 | ⬜ pending |
| 7-02-06 | 02 | 1 | XMOD-05 | performance | `pytest apps/regions/tests/test_views.py::test_regions_list_query_count_ceiling -x` | ❌ W0 | ⬜ pending |
| 7-02-07 | 02 | 1 | cross-tenant | security | `pytest apps/regions/tests/test_views.py::test_regions_cross_tenant_isolation -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 2 | RGN-04,05 | unit (frontend) | `cd frontend && npm run test -- region-management` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 2 | RGN-01,02,07,09,11 | unit (frontend) | `cd frontend && npm run test -- region-management` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/regions/tests/test_services.py` — stubs for create_region, update_region, delete_region, RegionHasShopsError
- [ ] `apps/regions/tests/test_selectors.py` — stubs for list_regions ordering
- [ ] `apps/regions/tests/test_views.py` — stubs for all API endpoints + template view + query ceiling + cross-tenant
- [ ] `apps/regions/serializers.py` — must exist before test imports compile
- [ ] `apps/regions/services/__init__.py` + `apps/regions/services/regions.py` — service layer
- [ ] `apps/regions/selectors/__init__.py` + `apps/regions/selectors/regions.py` — selector layer
- [ ] `apps/regions/exceptions.py` — `RegionHasShopsError`
- [ ] `apps/regions/views.py` — `region_list` template view + `RegionViewSet`
- [ ] `apps/regions/urls.py` — URL patterns
- [ ] Update `apps/regions/tests/factories.py` — fix `region_id` from `f"RGN-{n:03d}"` to `f"RGN{n:03d}"`
- [ ] `templates/regions/region_list.html` — Django template
- [ ] `frontend/src/widgets/region-management/` — widget directory
- [ ] `frontend/src/entrypoints/region-management.tsx` — entrypoint
- [ ] `vite.config.ts` — add `"region-management"` to `rollupOptions.input`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Region ID pill renders in monospace font with subtle border | RGN-01 | Visual/CSS rendering requires browser | Visit /admin/org/regions/ with regions present; confirm pill badge uses `font-mono` and has a border |
| Empty state Map icon renders correctly | RGN-02 | Icon rendering requires browser | Visit /admin/org/regions/ with no regions; confirm MapPin icon visible with correct color |
| Auto-ID populates in real time as user types | RGN-04 | Real-time input behavior requires browser | Open Create modal, type "North East" — confirm ID field shows "NE001" without delay |
| Clearing auto-resumed ID when field was manually edited | RGN-05 | Complex state machine requires browser | In Create modal: type name → manually edit ID → clear ID field → type more name → confirm auto-population resumes |
| Amber popup shows shop count + Manage Shops link | RGN-10 | Popup content requires browser | Attempt to delete a region with shops assigned; confirm amber popup shows correct shop count and link |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
