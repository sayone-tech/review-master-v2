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
| **Full suite command** | `pytest --reuse-db -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/accounts/tests/ -x -q`
- **After every plan wave:** Run `pytest --reuse-db -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | AUTH-01 | unit | `pytest apps/accounts/tests/test_views.py::test_login_get -xq` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | AUTH-01 | integration | `pytest apps/accounts/tests/test_views.py::test_login_post_valid -xq` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | AUTH-02 | integration | `pytest apps/accounts/tests/test_views.py::test_login_rate_limit -xq` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 1 | AUTH-03 | integration | `pytest apps/accounts/tests/test_views.py::test_remember_me -xq` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 2 | AUTH-04 | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_flow -xq` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 2 | AUTH-04 | unit | `pytest apps/accounts/tests/test_views.py::test_password_reset_email_sent -xq` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 3 | AUTH-05 | unit | `pytest apps/accounts/tests/test_views.py::test_logout -xq` | ❌ W0 | ⬜ pending |
| 2-03-02 | 03 | 3 | AUTH-05 | integration | `pytest apps/accounts/tests/test_views.py::test_redirect_unauthenticated -xq` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/tests/test_views.py` — stubs for AUTH-01 through AUTH-05
- [ ] `apps/accounts/tests/conftest.py` — shared fixtures (UserFactory, client, auth helpers)
- [ ] Confirm `pytest-django` and `factory-boy` installed (already in pyproject.toml)

*Existing infrastructure covers the framework — Wave 0 only needs test stubs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Show/hide password toggle renders & toggles | AUTH-01 | Alpine.js DOM interaction | Open `/login/`, click eye icon, verify input type toggles `password`↔`text` |
| "Remember me" persists session 30 days | AUTH-03 | Requires browser cookie inspection | Check `Set-Cookie` header after login with remember-me checked for `Max-Age=2592000` |
| Rate-limit 429 renders user-facing message | AUTH-02 | Requires 10 actual requests | Submit invalid login 10× in quick succession; confirm red banner with rate-limit message appears |
| Password-reset email renders correctly | AUTH-04 | HTML email rendering | Trigger reset in dev; view in Mailhog at `localhost:8025`; verify brand, link validity |
| ?next= redirect after login | AUTH-01 | Browser redirect chain | Visit `/organisations/` unauthenticated; confirm redirect to `/login/?next=/organisations/`; login; confirm lands at `/organisations/` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
