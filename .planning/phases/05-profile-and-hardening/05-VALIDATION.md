---
phase: 5
slug: profile-and-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/accounts/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85 -q` |
| **Estimated runtime** | ~15 seconds (quick) / ~45 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/accounts/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85 -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | PROF-01 | unit | `pytest apps/accounts/tests/test_services.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | PROF-01 | unit | `pytest apps/accounts/tests/test_services.py::TestUpdateProfileName -x -q` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | PROF-01 | integration | `pytest apps/accounts/tests/test_views.py::TestProfileNameUpdate -x -q` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 0 | PROF-02 | unit | `pytest apps/accounts/tests/test_services.py::TestChangePassword -x -q` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | PROF-02 | unit | `pytest apps/accounts/tests/test_services.py::TestChangePassword -x -q` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | PROF-02 | integration | `pytest apps/accounts/tests/test_views.py::TestPasswordChangeView -x -q` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 1 | — | integration | `python manage.py check --deploy 2>&1 \| grep -c "System check"` | ✅ | ⬜ pending |
| 05-03-02 | 03 | 1 | — | lint | `pre-commit run --all-files` | ✅ | ⬜ pending |
| 05-04-01 | 04 | 2 | — | CI | `cat .github/workflows/ci.yml \| grep "pytest --cov"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/tests/test_services.py` — stub test classes `TestUpdateProfileName`, `TestChangePassword` (failing RED stubs)
- [ ] `apps/accounts/tests/test_views.py` — stub test classes `TestProfileNameUpdate`, `TestPasswordChangeView` (failing RED stubs)
- [ ] `apps/accounts/services/__init__.py` — create empty package (directory doesn't exist yet)
- [ ] `apps/accounts/services/profile.py` — create stub with `update_profile_name()` and `change_password()` raising `NotImplementedError`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alpine.js edit-on-click toggle renders correctly | PROF-01 | Browser interaction, no Selenium | Load `/admin/profile/`, click Edit, verify input appears; click Cancel, verify text returns |
| 4-bar strength indicator responds to typing | PROF-02 | Alpine.js reactivity in browser | Load `/admin/profile/`, type in New password, verify bar count changes at weak/fair/good/strong thresholds |
| Show/hide toggle works on all 3 password fields | PROF-02 | Browser interaction | Toggle each eye icon; verify plaintext/masked toggles correctly |
| Success toast appears after name save | PROF-01 | Browser visual check | Submit name change; verify yellow toast appears at top-right |
| Success toast appears after password change | PROF-02 | Browser visual check | Submit password change; verify toast appears; session stays active |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
