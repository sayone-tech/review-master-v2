---
phase: 05-profile-and-hardening
plan: "01"
subsystem: accounts
tags: [url-migration, services-package, tdd-red, profile, wave-0]
dependency_graph:
  requires: []
  provides:
    - path("admin/profile/", profile, name="profile") in accounts/urls.py
    - apps.accounts.services.profile module (update_profile_name, change_password stubs)
    - RED test stubs for PROF-01 and PROF-02
  affects:
    - apps/accounts/tests/test_views.py
    - apps/accounts/tests/test_services.py
    - templates/partials/sidebar.html
    - templates/partials/sidebar_org.html
    - templates/partials/topbar.html
tech_stack:
  added: []
  patterns:
    - services/selectors pattern for profile service module
    - TDD RED stubs (Wave 0 scaffolding for Plans 05-02/03)
key_files:
  created:
    - apps/accounts/services/__init__.py
    - apps/accounts/services/profile.py
    - apps/accounts/tests/test_services.py
  modified:
    - apps/accounts/urls.py
    - templates/partials/sidebar.html
    - templates/partials/sidebar_org.html
    - templates/partials/topbar.html
    - apps/accounts/tests/test_views.py
decisions:
  - Profile URL migrated to /admin/profile/ with name="profile" preserved — no template {% url 'profile' %} calls needed updating
  - services/profile.py stubs raise NotImplementedError with plan reference messages — RED by design (Plans 05-02/03 turn GREEN)
  - Test stubs left failing (not xfail) per plan decision — Wave 0 per-task CI verifies what must pass NOW
metrics:
  duration: "2 minutes"
  completed: "2026-04-24"
  tasks_completed: 2
  files_changed: 7
requirements:
  - PROF-01
  - PROF-02
---

# Phase 05 Plan 01: URL Migration and Services Scaffold Summary

Wave 0 scaffold for Phase 5. Profile URL migrated from `/profile/` to `/admin/profile/`, all sidebar/topbar partials updated, `apps/accounts/services/` package bootstrapped with stub functions, and 14 failing RED test stubs seeded for Plans 05-02/03 to implement.

## Tasks Completed

### Task 1: Migrate profile URL and update sidebar/topbar hrefs

**Commit:** 65a9735

**Changes:**

1. `apps/accounts/urls.py` — changed `path("profile/", profile, name="profile")` to `path("admin/profile/", profile, name="profile")`. URL name `"profile"` preserved so any `{% url 'profile' %}` references continue resolving.

2. `templates/partials/sidebar.html` line 39 — `href="/profile/"` → `href="/admin/profile/"` on Profile nav item.

3. `templates/partials/sidebar_org.html` line 30 — `href="/profile/"` → `href="/admin/profile/"` on Profile nav item.

4. `templates/partials/topbar.html` line 68 — `href="/profile/"` → `href="/admin/profile/"` on profile dropdown anchor.

**Verification:** `test_login_next_param` (which already expected `/admin/profile/`) continues to pass (1 passed).

### Task 2: Create services package and seed failing RED test stubs

**Commit:** 22ca50f

**Files created:**

- `apps/accounts/services/__init__.py` — empty package marker (end-of-file newline added by pre-commit fixer).

- `apps/accounts/services/profile.py` — two stub service functions decorated with `@transaction.atomic`, both raising `NotImplementedError`:
  - `update_profile_name(*, user: User, full_name: str) -> User` — "Plan 05-02 implements"
  - `change_password(*, user: User, current_password: str, new_password: str) -> User` — "Plan 05-03 implements"

- `apps/accounts/tests/test_services.py` — 6 RED test stubs:
  - `TestUpdateProfileName` (3 tests): saves trimmed value, returns user, updates timestamp
  - `TestChangePassword` (3 tests): succeeds with correct current, raises on wrong current, persists to DB

**File appended:**

- `apps/accounts/tests/test_views.py` — 8 RED test stubs appended after existing tests:
  - `TestProfileNameUpdate` (4 tests): requires login, authenticated GET 200, valid POST updates name, invalid POST shows error
  - `TestPasswordChangeView` (4 tests): valid POST redirects, wrong current 200, mismatch 200, session preserved

**Test status:**
- `test_services.py`: 6 tests collected, ALL FAIL with `NotImplementedError` (RED — expected)
- `test_views.py`: 47 tests total collected (39 existing + 8 new); new 8 FAIL (URLs not yet registered)

## Deviations from Plan

None — plan executed exactly as written.

Pre-commit hooks auto-corrected:
- `services/__init__.py`: added trailing newline (end-of-file-fixer)
- `test_services.py`: reformatted by ruff-format (minor whitespace normalization)

These are not deviations — they are expected pre-commit behaviour.

## Self-Check: PASSED

- services/__init__.py: FOUND
- services/profile.py: FOUND
- test_services.py: FOUND
- commit 65a9735: FOUND
- commit 22ca50f: FOUND
