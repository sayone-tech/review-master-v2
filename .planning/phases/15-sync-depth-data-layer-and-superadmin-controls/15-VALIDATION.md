---
phase: 15
slug: sync-depth-data-layer-and-superadmin-controls
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest apps/organisations/tests/ apps/shops/tests/ -x -q` |
| **Full suite command** | `pytest apps/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/organisations/tests/ apps/shops/tests/ -x -q`
- **After every plan wave:** Run `pytest apps/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | SYNC-01 | unit | `pytest apps/organisations/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 1 | SYNC-01 | migration | `python manage.py migrate --check` | ✅ | ⬜ pending |
| 15-01-03 | 01 | 1 | SYNC-02 | unit | `pytest apps/shops/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 1 | SYNC-02 | migration | `python manage.py migrate --check` | ✅ | ⬜ pending |
| 15-02-01 | 02 | 1 | SYNC-01 | unit | `pytest apps/organisations/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-02 | 02 | 1 | SYNC-01 | unit | `pytest apps/organisations/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-03 | 02 | 1 | SYNC-03 | unit | `pytest apps/shops/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 2 | SDEP-02 | unit | `pytest apps/organisations/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 15-03-02 | 03 | 2 | SDEP-02 | unit | `pytest apps/organisations/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 15-03-03 | 03 | 2 | SDEP-03 | unit | `pytest apps/shops/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 15-04-01 | 04 | 2 | BKFL-01 | unit | `pytest apps/reviews/tests/test_services.py -k sync_depth -x -q` | ❌ W0 | ⬜ pending |
| 15-04-02 | 04 | 2 | BKFL-02 | unit | `pytest apps/reviews/tests/test_services.py -k sync_depth -x -q` | ❌ W0 | ⬜ pending |
| 15-04-03 | 04 | 2 | BKFL-03 | unit | `pytest apps/reviews/tests/test_services.py -k sync_depth -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/organisations/tests/test_models.py` — stubs for SYNC-01 (Organisation.allow_custom_sync_depth field tests)
- [ ] `apps/shops/tests/test_models.py` — stubs for SYNC-02 (Shop.SyncDepth choices and default tests)
- [ ] `apps/organisations/tests/test_services.py` — stubs for SYNC-01 (create_organisation and update_organisation with allow_custom_sync_depth)
- [ ] `apps/shops/tests/test_services.py` — stubs for SYNC-03 (create_shop auto-assigns sync_depth based on org flag)
- [ ] `apps/organisations/tests/test_views.py` — stubs for SDEP-02 (Superadmin create/edit org toggle)
- [ ] `apps/shops/tests/test_views.py` — stubs for SDEP-03 (shop detail shows sync_depth label)
- [ ] `apps/reviews/tests/test_services.py` — stubs for BKFL-01, BKFL-02, BKFL-03 (backfill start_date computation)

*Existing test infrastructure (pytest, factories, conftest) covers the framework — only stub files need to be created.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toggle switch renders correctly in Superadmin org create form | SDEP-02 | UI rendering requires browser | Open /organisations/create/, verify toggle appears and is interactive |
| Shop detail page shows correct sync depth label | SDEP-03 | Template rendering | Open shop detail, verify depth label matches model value |
| Toggle state persists after page reload | SDEP-02 | Full-stack UI round-trip | Create org with toggle on, reload page, verify toggle state preserved |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
