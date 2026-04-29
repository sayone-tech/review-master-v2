---
phase: 9
slug: team
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (existing) |
| **Config file** | `pyproject.toml` (existing `[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/accounts/tests/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/accounts/tests/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | Migration | migration | `pytest apps/accounts/tests/test_migrations.py -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | TEAM-06 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_invite_member -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | TEAM-07 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_invite_member_sends_email -x` | ❌ W0 | ⬜ pending |
| 09-01-04 | 01 | 1 | TEAM-10 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_disable_member -x` | ❌ W0 | ⬜ pending |
| 09-01-05 | 01 | 1 | TEAM-13 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_remove_member -x` | ❌ W0 | ⬜ pending |
| 09-01-06 | 01 | 1 | TEAM-17 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_activate_team_member -x` | ❌ W0 | ⬜ pending |
| 09-01-07 | 01 | 1 | TEML-01 | unit (service) | `pytest apps/accounts/tests/test_services_team.py::test_team_invitation_email -x` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | TEAM-01 | unit (serializer) | `pytest apps/accounts/tests/test_serializers.py -x` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 2 | TEAM-14 | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_cannot_remove_self -x` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 2 | TEAM-15 | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_last_manager_guard -x` | ❌ W0 | ⬜ pending |
| 09-02-04 | 02 | 2 | XMOD-05 | integration (viewset) | `pytest apps/accounts/tests/test_views_team.py::test_team_list_query_count -x` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | TEML-01 | unit (email) | `pytest apps/accounts/tests/test_services_team.py::test_team_invitation_email -x` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 2 | TEML-02 | unit (email) | `pytest apps/accounts/tests/test_services_team.py::test_team_invitation_resent_email -x` | ❌ W0 | ⬜ pending |
| 09-04-01 | 04 | 3 | TEAM-01 | manual | Browser: /admin/org/team/ shows all columns + stats cards | N/A | ⬜ pending |
| 09-04-02 | 04 | 3 | TEAM-02 | manual | Browser: search/filter work; store filter narrows when region selected | N/A | ⬜ pending |
| 09-05-01 | 05 | 3 | TEAM-06 | manual | Browser: Add modal role toggle shows/hides scope selects | N/A | ⬜ pending |
| 09-05-02 | 05 | 3 | TEAM-14 | manual | Browser: own row buttons disabled with tooltip | N/A | ⬜ pending |
| XMOD-03 | 01 | 1 | XMOD-03 | unit (selector) | `pytest apps/shops/tests/test_selectors.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/selectors/` directory — create `__init__.py` + `team.py` (list_team_members selector with N+1-safe prefetch)
- [ ] `apps/accounts/tests/test_services_team.py` — stubs covering TEAM-06, TEAM-07, TEAM-10, TEAM-13, TEAM-16, TEAM-17, TEML-01, TEML-02
- [ ] `apps/accounts/tests/test_views_team.py` — stubs covering TEAM-14, TEAM-15, XMOD-05 (query count)
- [ ] `apps/accounts/tests/test_serializers.py` — stub covering TEAM-01 (access_scopes prefetch read path)
- [ ] `apps/accounts/tests/test_migrations.py` — stub for migration 0005 backfill test
- [ ] `apps/accounts/tests/conftest.py` — verify exists; if not, create following `apps/shops/tests/conftest.py` re-export pattern for `assert_query_ceiling` and `two_orgs_two_admins`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Team list renders all columns with correct badges and chips | TEAM-01 | React widget visual output | Load /admin/org/team/ in browser; verify Name+Email, Role badge, Access chips, Status badge, Invited Date, Enabled toggle, Edit+Remove buttons all present |
| Search + filter dropdowns work | TEAM-02 | Browser interaction | Type in search box; select Region; verify Store dropdown narrows to that region's shops |
| Solo-user banner visible when alone | TEAM-05 | Org with one member | Log in as Org Admin in org with no team; verify banner appears above empty table |
| Add modal role toggle shows/hides scope selects | TEAM-06 | React dynamic UI | Open Add modal; select Manager — scope selects hidden; select Staff — Region+Store selects appear |
| Enabled toggle disable shows amber confirm | TEAM-10 | React interaction | Click toggle ON→OFF on any active member; amber confirm modal must appear |
| Disabled user login message | TEAM-12 | Auth flow | Disable a member; log in as them; verify "Your account has been disabled. Contact your administrator." on login form |
| Invitation acceptance form UX | TEAM-17 | Multi-step auth flow | Use invite link; verify Name pre-filled+editable, Email locked; submit; verify redirect by role |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
