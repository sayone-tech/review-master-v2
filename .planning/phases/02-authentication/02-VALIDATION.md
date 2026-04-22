---
phase: 2
slug: authentication
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/accounts/tests/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85 -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/accounts/tests/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85 -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | AUTH-01 | integration | `pytest apps/accounts/tests/test_views.py::TestLoginView -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | AUTH-02 | integration | `pytest apps/accounts/tests/test_views.py::TestLogoutView -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | AUTH-03 | integration | `pytest apps/accounts/tests/test_views.py::TestPasswordResetView -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 1 | AUTH-04 | integration | `pytest apps/accounts/tests/test_views.py::TestPasswordResetConfirmView -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | AUTH-05 | integration | `pytest apps/accounts/tests/test_views.py::TestSessionPersistence -x -q` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 2 | AUTH-01 | query-count | `pytest apps/accounts/tests/test_views.py::TestLoginQueryCount -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/tests/test_views.py` — stubs for AUTH-01 through AUTH-05 view tests
- [ ] `apps/accounts/tests/factories.py` — SuperadminFactory (already exists; verify it has `role=SUPERADMIN`)
- [ ] `apps/accounts/tests/conftest.py` — `superadmin_client` fixture (authenticated APIClient)

*Existing infrastructure covers pytest, pytest-django, factory-boy — no new framework installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Password reset email delivered within 60 seconds | AUTH-03 | Requires live SES or MailHog; E2E timing assertion | 1. Start docker-compose, 2. Submit forgot-password form, 3. Open MailHog at :8025, 4. Verify email arrives within 60s |
| Login card renders correctly (logo, layout, brand) | AUTH-01 | Visual/rendering check | 1. `make up`, 2. Navigate to /login, 3. Verify centered card, logo, yellow CTA button |
| "Remember me" session persists across browser restart | AUTH-05 | Browser cookie behaviour | 1. Login with "Remember me" checked, 2. Close browser completely, 3. Re-open and navigate to /admin/organisations, 4. Verify still authenticated |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
