---
phase: 02-authentication
verified: 2026-04-23T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Load /login/ in a browser and verify visual rendering"
    expected: "Centered white card, yellow logo mark, 'Sign in to your account' heading, email field, password field with show/hide toggle, 'Forgot password?' inline link, 'Remember me for 30 days' checkbox, full-width yellow 'Sign in' button — no sidebar or topbar"
    why_human: "Visual accuracy of auth_base + login card against UI-SPEC cannot be verified programmatically"
  - test: "Load /password-reset/ and complete the full reset flow in a real browser (using MailHog)"
    expected: "Forgot-password form renders, reset email arrives in MailHog with 'Reset your password' subject and yellow CTA button, /password-reset/confirm/ form shows 4-bar Alpine.js strength indicator animating as you type, success redirects to /login/ with 'Password updated. Please sign in.' flash banner visible"
    why_human: "Alpine.js reactivity, password strength animation, email rendering in MailHog all require a live browser session"
  - test: "Trigger rate-limit: submit POST /login/ 11 times with wrong password in < 15 minutes"
    expected: "11th attempt returns a page (or plain-text 429) with 'Too many sign-in attempts. Please try again in 15 minutes.' — first 10 return the normal error banner"
    why_human: "Redis rate-limit state accumulation across real HTTP requests requires a live server"
---

# Phase 2: Authentication Verification Report

**Phase Goal:** Superadmin can securely log in, log out, and recover their password — every authenticated page is behind this gate
**Verified:** 2026-04-23
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Superadmin can log in with email and password at /login/ and is redirected to /admin/organisations/ | VERIFIED | `CustomLoginView` at `path("login/", ...)`, `LOGIN_REDIRECT_URL="/admin/organisations/"`, `CustomAuthenticationForm` with generic error; 5 login tests pass |
| 2 | Superadmin can log out from any page and their server-side session is immediately invalidated | VERIFIED | `auth_views.LogoutView.as_view(next_page="/login/")` at `path("logout/", ...)`, `test_logout` and `test_logout_get_rejected` both pass |
| 3 | Superadmin can request a password reset email via "Forgot password?" and receive it within 60 seconds | VERIFIED | `PasswordResetView` wired at `/password-reset/`, email templates exist (`emails/password_reset.html`, `emails/password_reset.txt`, `emails/password_reset_subject.txt`), `test_password_reset_email_sent` passes |
| 4 | Superadmin can reset their password via the emailed link (expires after 1 hour, single-use) | VERIFIED | `CustomPasswordResetConfirmView` with `success_url=reverse_lazy("login")` and `messages.success(…, "Password updated. Please sign in.")`, `PASSWORD_RESET_TIMEOUT=3600`, `test_password_reset_confirm`, `test_password_reset_expired`, `test_password_reset_flow` all pass |
| 5 | Superadmin's authenticated session persists after a browser refresh without re-login | VERIFIED | `SESSION_COOKIE_AGE=86400`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=False`, remember-me path sets 30d, `test_session_persists`, `test_login_remember_me`, `test_login_no_remember_me` pass |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/settings/base.py` | LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL, SESSION_COOKIE_AGE, PASSWORD_RESET_TIMEOUT, CACHES["throttle"], DEFAULT_THROTTLE_RATES["login"] | VERIFIED | All values confirmed at runtime: `/login/`, `/admin/organisations/`, `/login/`, 86400, 3600, Redis DB 1 in base (locmem in test), `10/15min` |
| `apps/accounts/throttling.py` | LoginRateThrottle class with scope="login", cache=caches["throttle"] | VERIFIED | Class exists, uses `caches["throttle"]`, overrides `parse_rate` to handle `10/15min` multi-unit format, `get_cache_key` is IP-based |
| `apps/accounts/forms.py` | CustomAuthenticationForm with generic error message | VERIFIED | `error_messages["invalid_login"] == "Invalid email or password."` confirmed |
| `apps/accounts/views.py` | CustomLoginView (rate-limit + remember-me) + CustomPasswordResetConfirmView (flash + /login/ redirect) | VERIFIED | Both classes present, `throttle.allow_request` called in `post()`, `set_expiry` branching in `form_valid`, flash message exactly `"Password updated. Please sign in."` |
| `apps/accounts/urls.py` | 6 named URLs: login, logout, password_reset, password_reset_done, password_reset_confirm, password_reset_complete | VERIFIED | All 6 paths present; `CustomPasswordResetConfirmView.as_view()` on confirm path; no `app_name` namespace |
| `templates/auth_base.html` | Centered card layout, no sidebar, extends nothing | VERIFIED | Does not extend `base.html`; contains `{% block card %}`; no `<aside>` or sidebar include |
| `templates/accounts/login.html` | Login form extending auth_base, all required fields | VERIFIED | Extends `auth_base.html`; contains `Sign in to your account`, `name="remember_me"`, `{% url 'password_reset' %}`, `data-testid="login-error-banner"` |
| `templates/accounts/password_reset.html` | Forgot-password form | VERIFIED | `Forgot your password?`, `Send reset link`, `Back to sign in` link |
| `templates/accounts/password_reset_done.html` | Check-your-email confirmation | VERIFIED | `Check your email`, `data-lucide="mail-check"` icon |
| `templates/accounts/password_reset_confirm.html` | New-password form with validlink branch + strength indicator | VERIFIED | `{% if validlink %}`, `This link has expired`, `name="new_password1"`, `data-testid="strength-indicator"`, `aria-live="polite"` |
| `templates/accounts/password_reset_complete.html` | Fallback completion page | VERIFIED | Extends auth_base, `Password updated. Please sign in.` copy |
| `templates/emails/password_reset.html` | HTML email, 600px, inline CSS, yellow CTA | VERIFIED | `max-width:600px`, `background-color:#FACC15`, `{% url 'password_reset_confirm' ... %}` present twice |
| `templates/emails/password_reset.txt` | Plain-text email with reset link | VERIFIED | Contains `{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' ... %}`, `1 hour` expiry copy |
| `templates/emails/password_reset_subject.txt` | Subject "Reset your password" | VERIFIED | File content: `Reset your password` |
| `apps/accounts/tests/test_views.py` | 21 tests covering AUTH-01..AUTH-05 | VERIFIED | 21 test functions, all pass (0 failures) |
| `apps/accounts/tests/conftest.py` | superadmin, client_logged_in, anon_client fixtures + throttle cache clearing | VERIFIED | 4 fixtures including `clear_throttle_cache` autouse |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/accounts/views.py CustomLoginView.post` | `LoginRateThrottle` | `throttle.allow_request(request, self)` | WIRED | `LoginRateThrottle()` instantiated, `allow_request` called before `super().post()` |
| `apps/accounts/views.py CustomLoginView.form_valid` | `request.session.set_expiry` | conditional 30d vs 24h on `remember_me` | WIRED | Both `set_expiry(SESSION_AGE_30D)` and `set_expiry(SESSION_AGE_24H)` branches present |
| `config/urls.py` | `apps.accounts.urls` | `include("apps.accounts.urls")` | WIRED | Present in urlpatterns; `apps.organisations.urls` is also included which provides the `@login_required` guarded `/admin/organisations/` target |
| `templates/accounts/login.html` | `templates/auth_base.html` | `{% extends "auth_base.html" %}` | WIRED | First line of login.html |
| `templates/accounts/login.html` | URL name `password_reset` | `{% url 'password_reset' %}` | WIRED | Present at forgot-password link; URL resolves to `/password-reset/` |
| `apps/accounts/urls.py` | `CustomPasswordResetConfirmView` | Replace of `auth_views.PasswordResetConfirmView` | WIRED | `CustomPasswordResetConfirmView.as_view()` on the confirm path; `auth_views.PasswordResetConfirmView` is gone from that entry |
| `CustomPasswordResetConfirmView.form_valid` | `messages.success(request, ...)` | Flash before return | WIRED | `messages.success(self.request, "Password updated. Please sign in.")` present |
| `apps/accounts/throttling.py` | `CACHES["throttle"]` | `cache = caches["throttle"]` | WIRED | Class-level attribute override confirmed; test settings provide locmem backend under the same key |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-01 | 02-01, 02-02 | User can log in with email and password via the /login page | SATISFIED | `CustomLoginView` at `/login/`, `CustomAuthenticationForm`, tests `test_login_get`, `test_login_post_valid`, `test_login_success`, `test_login_invalid`, `test_login_no_enumeration` all pass |
| AUTH-02 | 02-02 | User can log out and have their server-side session invalidated | SATISFIED | `LogoutView` at `/logout/` (POST-only per Django 5+); `test_logout` verifies session invalidation and redirect to `/login/` |
| AUTH-03 | 02-03 | User can request a password reset email via "Forgot password?" link | SATISFIED | `PasswordResetView` at `/password-reset/`, email templates wired, `test_password_reset_email_sent` and `test_password_reset_no_enumeration` pass |
| AUTH-04 | 02-01, 02-03 | User can reset their password via a secure, time-limited email link (1-hour expiry) | SATISFIED | `PASSWORD_RESET_TIMEOUT=3600`, `CustomPasswordResetConfirmView` with flash redirect, `test_password_reset_confirm`, `test_password_reset_expired`, `test_password_reset_flow` pass |
| AUTH-05 | 02-01, 02-02 | User session persists across browser refresh | SATISFIED | `SESSION_COOKIE_AGE=86400`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=False`, remember-me 30d override, `test_session_persists` confirms Max-Age cookie is set |

All 5 requirements in scope for Phase 2 are SATISFIED.

---

### Anti-Patterns Found

No blocker or warning anti-patterns found.

Notable observations (informational only):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/accounts/views.py` | 33 | `# type: ignore[arg-type]` on `throttle.allow_request` | Info | DRF/Django CBV type mismatch; intentional per research notes. Does not affect runtime behaviour. |
| `apps/accounts/views.py` | 39 | `# type: ignore[override]` on `CustomLoginView.form_valid` | Info | Mypy strict limitation with FormView MRO; intentional. Does not affect runtime. |
| `templates/emails/password_reset.html` | — | CSS is hand-inlined (no premailer) | Info | Intentional deviation documented in 02-03-PLAN.md and SUMMARY. Premailer integration deferred to Phase 4 per CLAUDE.md §12.11 note. |
| `config/urls.py` | 5 | `apps.organisations.urls` included before `apps.accounts.urls` | Info | Organisations URLs were added in Phase 1 but accounts URLs now take logical priority for auth. No functional conflict since URL patterns are non-overlapping. |

---

### Human Verification Required

#### 1. Login Page Visual Rendering

**Test:** Open `http://localhost:8000/login/` in a browser after `make up`
**Expected:** Centered white card on gray background, yellow "R" logo mark + "Review Master" text, "Sign in to your account" heading, email field with autofocus, password field with show/hide eye toggle, inline "Forgot password?" link right-aligned next to "Password" label, "Remember me for 30 days" checkbox, full-width yellow "Sign in" button — no sidebar or topbar anywhere on the page
**Why human:** CSS class rendering, Alpine.js eye-toggle behaviour, and visual alignment against UI-SPEC require a live browser

#### 2. Full Password Reset Flow in MailHog

**Test:** Submit `/password-reset/` with a valid superadmin email, check MailHog at `http://localhost:8025`, click the reset link in the email
**Expected:** Email arrives with subject "Reset your password", has yellow CTA button, `/password-reset/confirm/` shows "Set a new password" form with 4-bar strength indicator that updates as you type, successful submit redirects to `/login/` with green flash "Password updated. Please sign in."
**Why human:** Email HTML rendering in MailHog, Alpine.js strength bar animation, and flash message banner display require a live browser session

#### 3. Rate-Limit Behaviour

**Test:** Submit 11 failed POST requests to `/login/` within 15 minutes from the same IP
**Expected:** First 10 return 200 with "Invalid email or password." banner; 11th returns either 429 plain-text or a rate-limit error page with "Too many sign-in attempts. Please try again in 15 minutes."
**Why human:** Redis rate-limit state accumulation across real HTTP round-trips requires a running server; automated test uses locmem cache

---

### Gaps Summary

No gaps. All automated checks pass, all 21 tests are green, all artifacts are substantive and wired. The three items listed under Human Verification are visual/UX checks that cannot be verified programmatically — they do not indicate missing implementation.

One implementation note worth tracking forward: `premailer` CSS inlining for email templates is deliberately deferred to Phase 4 per the plan. Hand-inlined styles are currently used in `templates/emails/password_reset.html`. This is documented and intentional — not a gap.

---

*Verified: 2026-04-23*
*Verifier: Claude (gsd-verifier)*
