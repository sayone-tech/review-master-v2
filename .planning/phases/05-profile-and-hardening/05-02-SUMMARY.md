---
phase: 05-profile-and-hardening
plan: "02"
subsystem: accounts
tags: [profile, forms, services, views, urls, password-change]
dependency_graph:
  requires:
    - 05-01
  provides:
    - update_profile_name service
    - change_password service
    - ProfileNameForm
    - ProfilePasswordChangeForm
    - update_name_view
    - change_password_view
    - /admin/profile/update-name/ URL
    - /admin/profile/change-password/ URL
  affects:
    - apps/accounts/forms.py
    - apps/accounts/services/profile.py
    - apps/accounts/views.py
    - apps/accounts/urls.py
    - apps/accounts/tests/test_views.py
tech_stack:
  added: []
  patterns:
    - Services/selectors pattern for profile update and password change
    - @login_required decorator with cast(User, request.user) for mypy strict compliance
    - update_session_auth_hash for session continuity after password change
    - xfail markers for template-dependent tests (deferred to Plan 05-03)
key_files:
  created: []
  modified:
    - apps/accounts/services/profile.py
    - apps/accounts/forms.py
    - apps/accounts/views.py
    - apps/accounts/urls.py
    - apps/accounts/tests/test_views.py
decisions:
  - "cast(User, request.user) in views for mypy strict compliance — @login_required guarantees authenticated User"
  - "Exactly 3 xfail markers on test_update_name_post_invalid, test_change_password_wrong_current, test_change_password_mismatch — template error rendering deferred to Plan 05-03"
  - "import User from apps.accounts.models in views.py for cast reference"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-24"
  tasks_completed: 2
  files_modified: 5
---

# Phase 05 Plan 02: Profile Backend Implementation Summary

**One-liner:** Profile services, forms, views, and URLs fully implemented with update_session_auth_hash session preservation and strict mypy compliance.

## Tasks Completed

### Task 1: Implement profile forms and services
- **Files:** `apps/accounts/services/profile.py`, `apps/accounts/forms.py`
- **Commit:** `b872c7a`

Replaced Plan 05-01 `NotImplementedError` stubs with working implementations:

**services/profile.py:**
- `update_profile_name`: strips whitespace, saves `update_fields=["full_name", "updated_at"]`, returns user
- `change_password`: verifies current password via `check_password`, raises `ValueError("Current password is incorrect.")` on failure, calls `set_password` + saves `update_fields=["password", "updated_at"]`

**forms.py (appended):**
- `ProfileNameForm`: single `full_name` CharField, min_length=2, max_length=100, mirrors ActivationForm error messages
- `ProfilePasswordChangeForm`: `current_password`, `new_password`, `confirm_password` fields; `clean_new_password` runs Django's `validate_password`; `clean` adds "Passwords do not match." error on mismatch

**Test result:** 6/6 test_services tests GREEN.

### Task 2: Wire views and URL patterns
- **Files:** `apps/accounts/views.py`, `apps/accounts/urls.py`, `apps/accounts/tests/test_views.py`
- **Commit:** `5b9cc0b`

**views.py additions:**
- Added `update_session_auth_hash` to auth imports
- Added `cast` to typing imports; imported `User` model for cast reference
- `update_name_view`: POST-only, validates `ProfileNameForm`, calls `update_profile_name`, queues "Name updated." success flash, redirects to `profile`
- `change_password_view`: POST-only, validates `ProfilePasswordChangeForm`, calls `svc_change_password`, catches `ValueError` to add field error, calls `update_session_auth_hash` before redirect, queues "Password updated." success flash

**urls.py additions:**
```python
path("admin/profile/update-name/", update_name_view, name="profile_update_name"),
path("admin/profile/change-password/", change_password_view, name="profile_change_password"),
```

**test_views.py:** Added `@pytest.mark.xfail(reason="Template error rendering deferred to Plan 05-03", strict=False)` to exactly 3 test methods.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy strict mode: request.user type mismatch**
- **Found during:** Task 2 pre-commit hook (mypy)
- **Issue:** `request.user` is typed as `User | AnonymousUser`; services expect `User`. Three errors: `update_profile_name`, `svc_change_password`, `update_session_auth_hash` calls
- **Fix:** Added `cast("User", request.user)` in both views (after `@login_required` guarantees authenticated user); imported `User` model and `cast` from typing
- **Files modified:** `apps/accounts/views.py`
- **Commit:** `5b9cc0b`

## Test Results

| Suite | Result |
|-------|--------|
| `test_services.py` | 6/6 passed |
| `test_views.py` (all pre-existing + new) | 44 passed, 3 xfailed |
| Django system check | 0 errors |
| mypy strict | Success: no issues found in 19 source files |

### xfail tests (deferred to Plan 05-03)

These 3 tests check for error text in rendered HTML — the stub `profile.html` does not yet include error rendering (Plan 05-03 adds the form cards):

1. `TestProfileNameUpdate::test_update_name_post_invalid` — looks for `b"at least 2"` in response
2. `TestPasswordChangeView::test_change_password_wrong_current` — looks for `b"Current password is incorrect"` in response
3. `TestPasswordChangeView::test_change_password_mismatch` — looks for `b"Passwords do not match"` in response

## Commits

| Hash | Message |
|------|---------|
| `b872c7a` | feat(05-02): implement ProfileNameForm, ProfilePasswordChangeForm, and profile services |
| `5b9cc0b` | feat(05-02): wire update_name_view and change_password_view with URL patterns |

## Self-Check: PASSED
