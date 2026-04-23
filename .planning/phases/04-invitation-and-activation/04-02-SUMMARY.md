---
phase: 04-invitation-and-activation
plan: "02"
subsystem: email
tags: [django, email, ses, invitation, templates, settings]

# Dependency graph
requires:
  - phase: 04-01
    provides: org admin layout and shell partials
  - phase: 03-organisation-management
    provides: create_organisation service with email sending via send_transactional_email

provides:
  - "SITE_URL env setting in base.py (default http://localhost:8000)"
  - "_build_accept_url returns absolute URL using settings.SITE_URL with trailing-slash guard"
  - "invitation.html has {% if is_resend %} conditional block with grey italic resend notice"
  - "invitation.txt has {% if is_resend %} conditional block before expiry line"
  - "EMAL-01/03/04 compliance verified via automated tests for both invitation and password_reset templates"

affects: [04-04-resend-invitation, future-email-services]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SITE_URL env var pattern for absolute URL construction in services"
    - "settings.SITE_URL.rstrip('/') guard to prevent double-slash from operator error"
    - "Django template {% if context_var %} conditional for optional email content"

key-files:
  created: []
  modified:
    - config/settings/base.py
    - apps/organisations/services/organisations.py
    - templates/emails/invitation.html
    - templates/emails/invitation.txt
    - apps/organisations/tests/test_services.py
    - apps/accounts/tests/test_views.py

key-decisions:
  - "SITE_URL stored in settings (not hardcoded) so Cloud Run can inject production domain via env var"
  - "_build_accept_url uses function-local import of settings (not module-level) — acceptable pattern, no perf cost"
  - "rstrip('/') guard applied to SITE_URL before concatenation to protect against trailing-slash operator error"
  - "{% if is_resend %} block placed after CTA row and before footer border row in invitation.html — Plan 04 resend service passes is_resend=True"

patterns-established:
  - "Template conditional pattern: {% if context_var %}...{% endif %} for optional email content — used by resend flow"
  - "EMAL compliance audit pattern: read template file via Path(settings.BASE_DIR) and assert string presence in tests"

requirements-completed: [EMAL-01, EMAL-02, EMAL-03, EMAL-04]

# Metrics
duration: 6min
completed: "2026-04-23"
---

# Phase 04 Plan 02: Email Production Readiness — Absolute URLs, Resend Conditional, EMAL Compliance Summary

**Invitation emails now use absolute URLs from SITE_URL env var; invitation templates conditionally render "This replaces any previous invitation." when is_resend=True; password reset email verified EMAL-03/04 compliant with 13 new passing tests**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-23T12:25:21Z
- **Completed:** 2026-04-23T12:31:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `SITE_URL` env setting to `config/settings/base.py` (default `http://localhost:8000`); `_build_accept_url` now returns absolute URLs with `.rstrip("/")` guard against operator trailing-slash errors
- Added `{% if is_resend %}` conditional to both `invitation.html` (grey italic paragraph row) and `invitation.txt` (standalone line before expiry notice) — Plan 04 resend service will call with `is_resend=True`
- Verified EMAL-01/03/04 compliance: invitation and password reset templates confirmed to use inline styles only, max-width:600px, plain-text siblings present, password reset subject is "Reset your password", 1-hour expiry copy present

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SITE_URL setting + make _build_accept_url return absolute URL** - `f50a1f3` (feat)
2. **Task 2: Add is_resend conditional to invitation templates + EMAL-04 audit tests** - `30b850f` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks have RED → GREEN flow; Task 1 had 4 tests, Task 2 had 9 service tests + 1 view test_

## Files Created/Modified

- `config/settings/base.py` - Added `SITE_URL = env("SITE_URL", default="http://localhost:8000")`
- `apps/organisations/services/organisations.py` - Updated `_build_accept_url` to use `settings.SITE_URL.rstrip("/")`
- `templates/emails/invitation.html` - Added `{% if is_resend %}` row with grey italic paragraph after CTA
- `templates/emails/invitation.txt` - Added `{% if is_resend %}` block before expiry notice line
- `apps/organisations/tests/test_services.py` - Added 13 tests: 4 absolute URL tests + 5 is_resend conditional tests + 4 EMAL compliance tests
- `apps/accounts/tests/test_views.py` - Added 1 EMAL-03 password reset compliance test

## Decisions Made

- `SITE_URL` stored in settings (not hardcoded) so Cloud Run can inject production domain via env var without code changes
- `_build_accept_url` uses function-local `from django.conf import settings` import — acceptable pattern, no performance cost, avoids circular import risk
- `.rstrip("/")` applied to `SITE_URL` to guard against operator misconfiguration with trailing slash
- `{% if is_resend %}` block placed after CTA row and before the footer border row in `invitation.html` — aligns with Plan 04 resend service which passes `is_resend=True` in email context

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff PT018 assertion style violations**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Two `assert p.exists() and p.stat().st_size > 0` compound assertions violated ruff PT018 rule
- **Fix:** Split each compound assertion into two separate `assert` statements
- **Files modified:** `apps/organisations/tests/test_services.py`
- **Verification:** `ruff check` passes in subsequent commit attempt
- **Committed in:** `30b850f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - ruff linting)
**Impact on plan:** Trivial code style fix; no logic change. No scope creep.

## Issues Encountered

- DjHTML pre-commit hook reformatted `invitation.html` indentation inside the `{% if %}` block on first commit attempt. Re-added files and recommitted; content semantically identical, tests still pass.

## User Setup Required

None - no external service configuration required. `SITE_URL` defaults to `http://localhost:8000` for local dev; production Cloud Run sets this via env var.

## Next Phase Readiness

- Plan 04 (resend invitation service) can now call `create_organisation` / resend service with `is_resend=True` context and the template will render the replacement notice correctly
- `SITE_URL` is wired and tested; any service building invite/activation URLs should use `settings.SITE_URL`
- All EMAL-01 through EMAL-04 requirements are now verified by automated tests

---
*Phase: 04-invitation-and-activation*
*Completed: 2026-04-23*
