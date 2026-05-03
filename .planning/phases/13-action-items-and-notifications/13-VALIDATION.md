---
phase: 13
slug: action-items-and-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-03
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-django |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/action_items/ apps/notifications/ -x -q` |
| **Full suite command** | `pytest apps/ -q --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/action_items/ apps/notifications/ -x -q`
- **After every plan wave:** Run `pytest apps/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-xx-01 | models | 1 | ACTN-01 | unit | `pytest apps/action_items/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-02 | services | 1 | ACTN-02,ACTN-03 | unit | `pytest apps/action_items/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-03 | selectors | 1 | ACTN-12 | unit+query | `pytest apps/action_items/tests/test_selectors.py -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-04 | api views | 2 | ACTN-04,ACTN-05 | integration | `pytest apps/action_items/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-05 | staff scoping | 2 | ACTN-06,ACTN-07 | integration | `pytest apps/action_items/tests/test_views.py -k staff -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-06 | notifications | 3 | NOTF-01,NOTF-02 | unit | `pytest apps/notifications/tests/ -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-07 | bell endpoint | 3 | NOTF-03,NOTF-04 | integration | `pytest apps/notifications/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 13-xx-08 | query count | 2 | ACTN-12 | query-count | `pytest apps/action_items/tests/test_selectors.py -k query_count -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/action_items/__init__.py` — app package
- [ ] `apps/action_items/apps.py` — AppConfig
- [ ] `apps/action_items/tests/__init__.py`
- [ ] `apps/action_items/tests/factories.py` — ActionItem, AuditLog factories
- [ ] `apps/action_items/tests/test_models.py` — stubs for ACTN-01
- [ ] `apps/action_items/tests/test_services.py` — stubs for ACTN-02, ACTN-03
- [ ] `apps/action_items/tests/test_selectors.py` — stubs for ACTN-12 query count
- [ ] `apps/action_items/tests/test_views.py` — stubs for ACTN-04–ACTN-11
- [ ] `apps/notifications/__init__.py` — app package
- [ ] `apps/notifications/apps.py` — AppConfig
- [ ] `apps/notifications/tests/__init__.py`
- [ ] `apps/notifications/tests/factories.py` — Notification factory
- [ ] `apps/notifications/tests/test_services.py` — stubs for NOTF-01, NOTF-02
- [ ] `apps/notifications/tests/test_views.py` — stubs for NOTF-03, NOTF-04, NOTF-05

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Notification bell popover renders and dismisses | NOTF-03 | Browser DOM interaction | Open `/admin/org/action-items/`, verify bell icon shows count, click to open popover with ≤10 items, click item to navigate and mark read |
| Staff user cannot see brand-scoped items via UI | ACTN-06 | Role-dependent UI rendering | Log in as Staff, navigate to action items, confirm no brand-scope filter UI and no brand items in list |
| Action item creation modal flow | ACTN-03 | Multi-step form interaction | As Org Admin, click "Create", fill all fields, submit, verify item appears in list with correct data |
| Status transition audit trail | ACTN-08 | UI + database consistency | Transition item to each status, verify audit log entries in detail modal |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
