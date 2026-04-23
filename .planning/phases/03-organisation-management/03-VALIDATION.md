---
phase: 3
slug: organisation-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest apps/organisations/ -x -q` |
| **Full suite command** | `pytest apps/ --reuse-db -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/organisations/ -x -q`
- **After every plan wave:** Run `pytest apps/ --reuse-db -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-W0-01 | Wave 0 | 0 | ORGL-01–08 | unit | `pytest apps/organisations/tests/ -x -q` | ❌ W0 | ⬜ pending |
| 3-W0-02 | Wave 0 | 0 | CORG-01–04 | unit | `pytest apps/organisations/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-01 | 01 | 1 | ORGL-01–08 | unit | `pytest apps/organisations/tests/test_selectors.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | ORGL-08 | query-count | `pytest apps/organisations/tests/test_views.py::test_list_query_count -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | CORG-01–04 | unit | `pytest apps/organisations/tests/test_services.py::test_create_organisation -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | VORG-01–03 | unit | `pytest apps/organisations/tests/test_views.py::test_view_organisation -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | EORG-01–03 | unit | `pytest apps/organisations/tests/test_services.py::test_update_organisation -x -q` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | ENBL-01–02 | unit | `pytest apps/organisations/tests/test_services.py::test_enable_disable -x -q` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 2 | DORG-01–02 | unit | `pytest apps/organisations/tests/test_services.py::test_soft_delete -x -q` | ❌ W0 | ⬜ pending |
| 3-04-02 | 04 | 2 | STOR-01–03 | unit | `pytest apps/organisations/tests/test_services.py::test_store_allocation -x -q` | ❌ W0 | ⬜ pending |
| 3-05-01 | 05 | 3 | CORG-01–04 | integration | `pytest apps/organisations/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/organisations/tests/__init__.py` — test package init
- [ ] `apps/organisations/tests/factories.py` — OrganisationFactory, InvitationTokenFactory
- [ ] `apps/organisations/tests/test_models.py` — model field and constraint stubs
- [ ] `apps/organisations/tests/test_selectors.py` — selector stubs for ORGL-01–08
- [ ] `apps/organisations/tests/test_services.py` — service stubs for CORG-01–04, EORG-01–03, ENBL-01–02, DORG-01–02, STOR-01–03
- [ ] `apps/organisations/tests/test_views.py` — viewset stubs including query-count test (ORGL-08)
- [ ] `apps/accounts/permissions.py` — IsSuperadmin permission class (missing, blocks all tests)
- [ ] `apps/common/services/email.py` — send_transactional_email stub (missing, blocks CORG-02 create service test)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toast appears after create | CORG-03 | React toast UI, no Selenium | Create org via modal, verify "Organisation created. Invitation email sent to {email}." toast appears |
| Status badge updates without reload | ENBL-01/02 | DOM mutation, no Selenium | Toggle enable/disable, verify badge colour change with no page reload |
| Delete name-confirmation blocks wrong input | DORG-01 | Form interaction | Open delete modal, type wrong org name, verify confirm button stays disabled |
| Invitation email received | CORG-02 | External email delivery | Create org, check MailHog at localhost:8025 for invitation email |
| Search + filter combination | ORGL-04/05/06 | Multi-param GET interaction | Apply search + status filter + org type together, verify results are correct intersection |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
