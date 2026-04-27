---
phase: 06-org-admin-shell
plan: 05
subsystem: accounts
tags: [profile, org-admin, views, urls, templates, tdd]
dependency_graph:
  requires: [06-02]
  provides: [org_profile_views, org_profile_urls, org_profile_template]
  affects: [apps/accounts/views.py, apps/accounts/urls.py, templates/accounts/org_profile.html]
tech_stack:
  patterns: [services-selectors, org_admin_required-decorator, shared-services-reuse]
key_files:
  created:
    - templates/accounts/org_profile.html
  modified:
    - apps/accounts/views.py
    - apps/accounts/urls.py
    - apps/accounts/tests/test_views.py
decisions:
  - "@org_admin_required alone used — does not stack with @login_required (decorator already wraps it internally)"
  - "profile.html and org_profile.html differ in exactly 3 lines: {% extends %} + 2 {% url %} tags"
  - "No business logic duplicated — both profile families call update_profile_name and change_password from apps.accounts.services.profile"
metrics:
  duration: 8m 23s
  completed: 2026-04-27
  tasks_completed: 1
  files_changed: 4
---

# Phase 6 Plan 05: Org Admin Profile Views Summary

Org Admin profile page (`/admin/org/profile/`) using the org sidebar shell, sharing the same services and forms as the Superadmin `/admin/profile/` flow.

## What Was Built

Three new view functions added to `apps/accounts/views.py`:

- `org_profile` — GET renders `accounts/org_profile.html`
- `org_update_name_view` — POST-only, calls `update_profile_name` service, redirects to `org_profile`
- `org_change_password_view` — POST-only, calls `change_password` service, calls `update_session_auth_hash`, redirects to `org_profile`

All three decorated with `@org_admin_required` which returns 403 for SUPERADMIN, STAFF_ADMIN, and org-less ORG_ADMIN. Anonymous users get the standard login redirect.

Three new URL patterns added to `apps/accounts/urls.py`:

| URL | Name |
|-----|------|
| `/admin/org/profile/` | `org_profile` |
| `/admin/org/profile/update-name/` | `org_profile_update_name` |
| `/admin/org/profile/change-password/` | `org_profile_change_password` |

One new template `templates/accounts/org_profile.html` created. It is a copy of `templates/accounts/profile.html` with **exactly 3 lines changed**:
- Line 1: `{% extends "base.html" %}` → `{% extends "base_org.html" %}`
- Name form action: `{% url 'profile_update_name' %}` → `{% url 'org_profile_update_name' %}`
- Password form action: `{% url 'profile_change_password' %}` → `{% url 'org_profile_change_password' %}`

Confirmed via `diff templates/accounts/profile.html templates/accounts/org_profile.html | grep -c "^[<>]"` = 6 (3 changed lines × 2 diff sides).

## Shared Service Functions (NOT Modified)

Both profile flows call the same services from `apps/accounts/services/profile.py`:
- `update_profile_name(*, user: User, full_name: str) -> User`
- `change_password(*, user: User, current_password: str, new_password: str) -> User`

Neither function was touched. Any future changes to these services will propagate to both Superadmin and Org Admin profiles automatically.

## Decorator Stack

`@org_admin_required` only — NOT `@login_required` + `@org_admin_required`. The `org_admin_required` decorator in `apps/accounts/permissions.py` already wraps `@login_required` internally. Stacking both would be redundant.

## Test Coverage

10 new tests added to `apps/accounts/tests/test_views.py`:

| Test | Covers |
|------|--------|
| `test_org_profile_get_returns_200_with_two_cards` | Happy path: 200, both card headings, email visible |
| `test_org_profile_renders_inside_base_org_shell` | `data-testid="sidebar"` present (base_org.html renders sidebar_org.html) |
| `test_org_profile_returns_403_for_superadmin` | Role rejection |
| `test_org_profile_returns_403_for_staff_admin` | Role rejection |
| `test_org_profile_returns_403_for_org_admin_without_organisation` | Org-less ORG_ADMIN gets 403 |
| `test_org_profile_update_name_success` | 302 redirect, DB updated |
| `test_org_profile_update_name_invalid_renders_form_with_error` | 200, name unchanged |
| `test_org_profile_change_password_success` | 302 redirect, new password authenticates |
| `test_org_profile_change_password_wrong_current_shows_error` | 200, error message, old password still works |
| `test_existing_superadmin_profile_url_still_works` | No regression: /admin/profile/ returns 200 |
| `test_org_profile_url_names_resolve_correctly` | URL reverse() checks |

All 64 tests in `apps/accounts/tests/test_views.py` pass.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- templates/accounts/org_profile.html: FOUND
- apps/accounts/views.py: FOUND
- Commit 21ce171: FOUND
- All 64 tests pass
