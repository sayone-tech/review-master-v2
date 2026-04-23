---
phase: 02-authentication
plan: "02"
subsystem: accounts/templates/urls
tags: [auth, login, logout, templates, url-wiring, rate-limiting, session, wave-2]
dependency_graph:
  requires:
    - apps/accounts/throttling.py:LoginRateThrottle (Plan 02-01)
    - config/settings/base.py:LOGIN_URL,LOGIN_REDIRECT_URL,SESSION_EXPIRE_AT_BROWSER_CLOSE (Plan 02-01)
    - config/settings/test.py:CACHES.throttle (Plan 02-01)
  provides:
    - templates/auth_base.html:centered-card layout for all auth pages
    - templates/accounts/login.html:login form with remember-me, forgot-password
    - apps/accounts/forms.py:CustomAuthenticationForm
    - apps/accounts/views.py:CustomLoginView
    - apps/accounts/urls.py:login,logout,password_reset,password_reset_done,password_reset_confirm,password_reset_complete
    - templates/accounts/password_reset*.html:stub templates (Plan 03 replaces)
    - apps/organisations/views.py:organisation_list placeholder (Plan 03 replaces with real view)
  affects:
    - Plan 02-03 (password reset views depend on these URL names and stub templates)
tech_stack:
  added: []
  patterns:
    - Django LoginView subclass with DRF throttle hook (allow_request on POST only)
    - Session expiry branching on remember_me POST value
    - auth_base.html standalone layout (does not extend base.html) for auth pages
    - URL registration before Django admin to prevent admin from catching /admin/* paths
key_files:
  created:
    - templates/auth_base.html
    - templates/accounts/login.html
    - templates/accounts/password_reset.html
    - templates/accounts/password_reset_done.html
    - templates/accounts/password_reset_confirm.html
    - templates/accounts/password_reset_complete.html
    - apps/accounts/forms.py
    - apps/accounts/views.py
    - apps/accounts/urls.py
    - apps/organisations/views.py
    - apps/organisations/urls.py
  modified:
    - templates/registration/login.html (replaced dark Phase-1 stub with backward-compat alias)
    - apps/common/urls.py (removed logout_stub)
    - apps/common/views.py (removed logout_stub function)
    - config/urls.py (replaced django.contrib.auth.urls with apps.accounts.urls)
    - apps/accounts/tests/conftest.py (added autouse fixture to clear throttle cache)
decisions:
  - "Email field inlined in login.html (not via form_fields.html component) because UI-SPEC requires the label row to contain the inline Forgot password? link with right-alignment — the component does not support extra_attrs for autocomplete/autofocus"
  - "organisations/views.py placeholder added with @login_required before Django admin in URL order so test_login_required_redirect passes (GET /admin/organisations/ redirects to /login/ not /admin/login/)"
  - "conftest.py clear_throttle_cache autouse fixture added — LocMemCache persists between tests, causing rate-limit bleed from test_login_rate_limit into subsequent tests"
  - "apps.organisations.urls included in config/urls.py BEFORE admin/ to prevent Django admin from catching /admin/organisations/ before the login_required view resolves it"
metrics:
  duration: ~8 min
  completed_date: "2026-04-23"
  tasks: 3
  files: 15
---

# Phase 02 Plan 02: Login + Logout Templates, Form, View, URL Wiring Summary

Login/logout implementation: auth_base.html card layout, CustomLoginView with rate limiting and remember-me, URL wiring replacing Phase-1 shims, stub reset templates, all AUTH-01/02/05 tests green.

## What Was Built

### Task 1 — auth_base.html + accounts/login.html Templates

Created `templates/auth_base.html` as a standalone layout (does NOT extend base.html) with:
- Centered card at 480px max-width, white background, border, shadow
- Yellow "R" lettermark logo + "Review Master" wordmark
- `{% block card %}` for page-specific content
- Includes `components/toasts.html` for flash messages

Created `templates/accounts/login.html` extending auth_base with:
- "Sign in to your account" heading + subtitle
- Red alert banner pattern (`data-testid="login-error-banner"`) for non_field_errors
- Email field: type="email", autocomplete="email", autofocus (inlined — see Deviations)
- Password field: label row with right-aligned "Forgot password?" link to `{% url 'password_reset' %}`, Alpine.js show/hide toggle, autocomplete="current-password"
- "Remember me for 30 days" checkbox (`name="remember_me"`)
- Full-width yellow primary submit button with Alpine.js loading state

Replaced dark Phase-1 `templates/registration/login.html` stub with single-line backward-compat alias.

### Task 2 — CustomAuthenticationForm + CustomLoginView

`apps/accounts/forms.py`:
- `CustomAuthenticationForm(AuthenticationForm)` — overrides error_messages["invalid_login"] to "Invalid email or password." (no email enumeration)

`apps/accounts/views.py`:
- `CustomLoginView(LoginView)` with:
  - `template_name = "accounts/login.html"`
  - `authentication_form = CustomAuthenticationForm`
  - `redirect_authenticated_user = True`
  - `post()` override: calls `LoginRateThrottle().allow_request(request, self)` before delegating to Django; returns HTTP 429 plain-text on rejection
  - `form_valid()` override: reads `remember_me` from POST, calls `set_expiry(SESSION_AGE_30D)` or `set_expiry(SESSION_AGE_24H)`

### Task 3 — URL Wiring + Cleanup

**Final URL table:**

| URL name | Path |
|---|---|
| login | /login/ |
| logout | /logout/ |
| password_reset | /password-reset/ |
| password_reset_done | /password-reset/done/ |
| password_reset_confirm | /password-reset/confirm/<uidb64>/<token>/ |
| password_reset_complete | /password-reset/complete/ |
| organisation_list | /admin/organisations/ |

**Where remember_me is read and session expiry is set:**
- File: `apps/accounts/views.py`
- Method: `CustomLoginView.form_valid()`
- Line: `remember = self.request.POST.get("remember_me")`
- Branch: `if remember: set_expiry(2592000)` else `set_expiry(86400)`

**Removed:**
- `logout_stub` function from `apps/common/views.py`
- `path("logout/", logout_stub, ...)` from `apps/common/urls.py`
- `path("accounts/", include("django.contrib.auth.urls"))` from `config/urls.py`

**Stub templates created** (Plan 03 Task 2 replaces all four):
- `templates/accounts/password_reset.html`
- `templates/accounts/password_reset_done.html`
- `templates/accounts/password_reset_confirm.html`
- `templates/accounts/password_reset_complete.html`

Each contains exactly: `{% extends "auth_base.html" %}{% block card %}{% endblock %}`

## Auth Gates

None — fully autonomous execution.

## Test Results

**GREEN (AUTH-01/02/05):** All 15 targeted tests pass:
- test_login_get, test_login_post_valid, test_login_success, test_login_invalid, test_login_no_enumeration
- test_login_rate_limit, test_login_remember_me, test_login_no_remember_me, test_remember_me, test_login_next_param
- test_logout, test_logout_get_rejected
- test_session_persists, test_login_required_redirect, test_redirect_unauthenticated

**RED (AUTH-03/04 — expected):** 4 password-reset tests fail (TemplateDoesNotExist for email templates + missing CustomPasswordResetConfirmView). Plan 03 addresses these.

## sidebar.html compatibility

`templates/partials/sidebar.html` already uses `{% url 'logout' %}`. This still resolves correctly — the URL name "logout" is now served by `LogoutView.as_view(next_page="/login/")` in `apps/accounts/urls.py`. No template change was needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Email field autocomplete attribute not rendered via form_fields.html include**
- **Found during:** Task 1
- **Issue:** `form_fields.html` component has no `extra_attrs` variable, so `autocomplete="email"` and `autofocus` would not render when using the include approach
- **Fix:** Inlined the email field directly in `login.html`, mirroring the component's visual tokens exactly
- **Files modified:** `templates/accounts/login.html`
- **Commit:** 21c1595

**2. [Rule 1 - Bug] test_login_required_redirect fails — Django admin catches /admin/organisations/**
- **Found during:** Task 3
- **Issue:** `/admin/organisations/` resolves to Django admin's `app_index` view, which redirects to `/admin/login/` not `/login/`; the test expects `/login/` since LOGIN_URL is set
- **Fix:** Added minimal `@login_required` placeholder view in `apps/organisations/views.py` + `apps/organisations/urls.py`, registered BEFORE Django admin in `config/urls.py`
- **Files modified:** `apps/organisations/views.py`, `apps/organisations/urls.py`, `config/urls.py`
- **Commit:** 155f632

**3. [Rule 1 - Bug] Rate-limit cache bleeding between tests**
- **Found during:** Task 3 (test run)
- **Issue:** `LocMemCache` persists between tests in the same process; `test_login_rate_limit` runs 11 POST attempts that fill the IP's throttle bucket; subsequent tests hit the 429 wall
- **Fix:** Added `autouse=True` fixture `clear_throttle_cache()` in `conftest.py` that calls `caches["throttle"].clear()` before every test
- **Files modified:** `apps/accounts/tests/conftest.py`
- **Commit:** 155f632

## Self-Check: PASSED

All files confirmed on disk:
- templates/auth_base.html: FOUND
- templates/accounts/login.html: FOUND
- apps/accounts/forms.py: FOUND
- apps/accounts/views.py: FOUND
- apps/accounts/urls.py: FOUND

All commits confirmed in git:
- 21c1595 (Task 1 templates): FOUND
- 7c28818 (Task 2 form/view): FOUND
- 155f632 (Task 3 URL wiring): FOUND
