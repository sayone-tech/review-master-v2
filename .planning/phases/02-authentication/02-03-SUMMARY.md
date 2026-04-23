---
phase: 02-authentication
plan: 03
subsystem: auth
tags: [django, password-reset, email, alpine.js, tailwind, ses]

# Dependency graph
requires:
  - phase: 02-authentication-02
    provides: auth_base.html template, URL skeleton with password_reset URLs, stub templates
  - phase: 02-authentication-01
    provides: PASSWORD_RESET_TIMEOUT=3600 setting, test fixtures, test_views.py with AUTH-03/04 tests

provides:
  - CustomPasswordResetConfirmView with flash-to-login redirect
  - Four complete password-reset UI templates (password_reset, _done, _confirm, _complete)
  - Three email templates (HTML 600px hand-inlined + plain-text + subject)
  - All 21 AUTH tests green including AUTH-03 and AUTH-04

affects: [04-email-infrastructure, phase-3-organizations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Django PasswordResetConfirmView subclass with form_valid flash + redirect to /login/
    - Hand-inlined CSS email templates (premailer deferred to Phase 4)
    - Alpine.js x-data password strength indicator (4-bar, aria-live polite)
    - Django _now() mocking for token expiry in tests

key-files:
  created:
    - templates/accounts/password_reset.html
    - templates/accounts/password_reset_done.html
    - templates/accounts/password_reset_confirm.html
    - templates/accounts/password_reset_complete.html
    - templates/emails/password_reset.html
    - templates/emails/password_reset.txt
    - templates/emails/password_reset_subject.txt
  modified:
    - apps/accounts/views.py
    - apps/accounts/urls.py
    - apps/accounts/tests/test_views.py

key-decisions:
  - "CustomPasswordResetConfirmView.form_valid adds flash AFTER super().form_valid so token is invalidated first, then message queued"
  - "Flash message is EXACTLY 'Password updated. Please sign in.' per CONTEXT.md locked copy — do not paraphrase"
  - "Hand-inlined CSS in password_reset.html email — premailer integration deferred to Phase 4 (send_transactional_email service)"
  - "test_password_reset_expired mocks default_token_generator._now() +1s — Django documents _now() as designed for mocking"

patterns-established:
  - "Pattern: Django built-in PasswordResetConfirmView subclassed for project customization (flash + redirect) without hand-rolling HMAC"
  - "Pattern: Token expiry test uses patch.object(generator, '_now', return_value=future) not sleep/timeout manipulation"
  - "Pattern: Email templates use hand-inlined styles in Phase 2; Phase 4 will introduce premailer via send_transactional_email"

requirements-completed: [AUTH-03, AUTH-04]

# Metrics
duration: 6min
completed: 2026-04-23
---

# Phase 02 Plan 03: Password Reset Flow Summary

**Complete password reset flow with CustomPasswordResetConfirmView, 4 UI templates, multipart email (600px hand-inlined HTML + plain text), Alpine.js strength indicator, and all 21 AUTH tests green**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-23T04:55:04Z
- **Completed:** 2026-04-23T05:01:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- `CustomPasswordResetConfirmView` added to `apps/accounts/views.py` — subclasses Django's built-in, redirects to `/login/` with exact flash "Password updated. Please sign in."
- Four account-facing password-reset templates replacing Plan 02 stubs: forgot-password form, check-your-email confirmation, new-password form with 4-bar Alpine.js strength indicator + expired-link branch, fallback complete page
- Three email templates: subject "Reset your password", plain-text body with reset link + 1-hour expiry notice, HTML with hand-inlined 600px-max yellow CTA (premailer deferred to Phase 4)
- All 21 tests in `apps/accounts/tests/test_views.py` pass (AUTH-01 through AUTH-05)

## Password Reset URL Map

| URL name | Resolved path |
|---|---|
| `password_reset` | `/password-reset/` |
| `password_reset_done` | `/password-reset/done/` |
| `password_reset_confirm` | `/password-reset/confirm/<uidb64>/<token>/` |
| `password_reset_complete` | `/password-reset/complete/` |
| `login` (success_url) | `/login/` |
| `logout` | `/logout/` |

## Email Template Paths

| File | Purpose |
|---|---|
| `templates/emails/password_reset_subject.txt` | Subject "Reset your password" — referenced by `subject_template_name` in `PasswordResetView.as_view()` |
| `templates/emails/password_reset.txt` | Plain-text body with `{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' … %}` |
| `templates/emails/password_reset.html` | HTML body, hand-inlined CSS, 600px max-width table, `background-color:#FACC15` CTA |

The `PasswordResetView` URL entry in `apps/accounts/urls.py` references all three via `email_template_name`, `html_email_template_name`, and `subject_template_name` kwargs.

## Flash Message (CONTEXT.md Locked Copy)

`CustomPasswordResetConfirmView.form_valid` queues exactly:

```
"Password updated. Please sign in."
```

This is asserted verbatim by `test_password_reset_flow` via `get_messages(r2.wsgi_request)`.

## Test Suite Status

All 21 tests in `apps/accounts/tests/test_views.py` pass:

| Test | AUTH | Status |
|---|---|---|
| test_login_get | AUTH-01 | PASS |
| test_login_post_valid | AUTH-01 | PASS |
| test_login_success | AUTH-01 | PASS |
| test_login_invalid | AUTH-01 | PASS |
| test_login_no_enumeration | AUTH-01 | PASS |
| test_login_rate_limit | AUTH-01 | PASS |
| test_login_remember_me | AUTH-01 | PASS |
| test_login_no_remember_me | AUTH-01 | PASS |
| test_remember_me | AUTH-05 | PASS |
| test_login_next_param | AUTH-01 | PASS |
| test_logout | AUTH-02 | PASS |
| test_logout_get_rejected | AUTH-02 | PASS |
| test_password_reset_email_sent | AUTH-03 | PASS |
| test_password_reset_no_enumeration | AUTH-03 | PASS |
| test_password_reset_confirm | AUTH-04 | PASS |
| test_password_reset_expired | AUTH-04 | PASS |
| test_password_reset_redirect | AUTH-04 | PASS |
| test_password_reset_flow | AUTH-04 | PASS |
| test_session_persists | AUTH-05 | PASS |
| test_login_required_redirect | AUTH-05 | PASS |
| test_redirect_unauthenticated | AUTH-05 | PASS |

## Task Commits

1. **Task 1: Add CustomPasswordResetConfirmView and rewire confirm URL** - `07cfde7` (feat)
2. **Task 2: Replace four account-facing password-reset templates with real UI** - `f829c14` (feat)
3. **Task 3: Create password reset email templates and fix expired token test** - `1fcc2a1` (feat)

## Files Created/Modified

- `apps/accounts/views.py` — Added `CustomPasswordResetConfirmView` class, merged imports
- `apps/accounts/urls.py` — Swapped `auth_views.PasswordResetConfirmView` for custom view, updated import
- `apps/accounts/tests/test_views.py` — Fixed `test_password_reset_expired`: mock `_now()` +1s for deterministic expiry
- `templates/accounts/password_reset.html` — Forgot-password form with email field, "Send reset link" button, "Back to sign in" link
- `templates/accounts/password_reset_done.html` — "Check your email" confirmation with mail-check icon
- `templates/accounts/password_reset_confirm.html` — New-password form with Alpine.js 4-bar strength indicator + expired-link branch
- `templates/accounts/password_reset_complete.html` — Fallback complete page with locked flash copy
- `templates/emails/password_reset_subject.txt` — Subject line
- `templates/emails/password_reset.txt` — Plain-text body
- `templates/emails/password_reset.html` — HTML email body (hand-inlined CSS, 600px, yellow CTA)

## Decisions Made

1. **CustomPasswordResetConfirmView.form_valid**: Calls `super().form_valid(form)` first (which saves the password and invalidates the token), then queues the flash message. This ordering is correct — token invalidation happens before the message is queued.

2. **Flash message string**: Exactly `"Password updated. Please sign in."` per CONTEXT.md locked copy. The test asserts this literal string.

3. **Hand-inlined CSS for email**: CLAUDE.md §12.5 mandates premailer, but `PasswordResetView` renders templates directly via `render_to_string` with no wrapper to hook premailer into. Hand-inlined styles applied for full Gmail/Outlook/Apple Mail compatibility. Premailer integration deferred to Phase 4 when `send_transactional_email` service is built.

4. **Token expiry test fix**: `test_password_reset_expired` used `PASSWORD_RESET_TIMEOUT=0` but `(now - ts) > 0` is False when token is freshly created (age=0). Fixed by mocking `default_token_generator._now()` to return `datetime.now() + timedelta(seconds=1)`. Django's own codebase has the comment "Used for mocking in tests" on `_now()`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_password_reset_expired: PASSWORD_RESET_TIMEOUT=0 edge case**
- **Found during:** Task 3 (Create email templates — test verification run)
- **Issue:** `PASSWORD_RESET_TIMEOUT=0` with a freshly-created token: Django's check is `(now - ts) > 0`. Since `now=ts` at creation, `0 > 0` is False → token is NOT expired. Test expected expired behavior but got valid-link page.
- **Fix:** Added `patch.object(default_token_generator, "_now", return_value=datetime.now() + timedelta(seconds=1))` so the age appears as 1 second, making `1 > 0` → expired.
- **Files modified:** `apps/accounts/tests/test_views.py`
- **Verification:** `test_password_reset_expired` passes, all 21 tests pass
- **Committed in:** `1fcc2a1` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test expiry mechanism)
**Impact on plan:** Fix necessary for test correctness. No scope creep. Django documents `_now()` as "Used for mocking in tests".

## Issues Encountered

DjHTML pre-commit hook reformatted `templates/accounts/password_reset_confirm.html` and `templates/emails/password_reset.html` on first commit attempt. Re-staged and re-committed after each reformatting. No functional impact.

## Premailer Note (Phase 4 Deferred)

CLAUDE.md §12.5 mandates `premailer` for CSS inlining. Phase 2's email rendering path (`PasswordResetView` → `render_to_string` → `send_mail`) has no hook for a premailer transform. Styles are hand-inlined in `templates/emails/password_reset.html`. Phase 4 will introduce `apps/common/services/email.py::send_transactional_email` and route all transactional emails (including password reset) through it, where `premailer.transform()` will be called at send time. No test change will be needed since rendered output is equivalent.

## Sidebar/Login Compatibility

- `{% url 'logout' %}` in `sidebar.html` → resolves to `/logout/` (LogoutView unchanged)
- `{% url 'password_reset' %}` in `templates/accounts/login.html` → resolves to `/password-reset/` (URL entry unchanged)
- `{% url 'login' %}` in all four reset templates → resolves to `/login/` (CustomLoginView unchanged)

## Next Phase Readiness

Phase 02 authentication is complete. All 21 AUTH tests pass. The full login/logout/password-reset flow is functional with Django templates + Tailwind + Alpine.js. Phase 03 (Organisations) can proceed.

---
*Phase: 02-authentication*
*Completed: 2026-04-23*
