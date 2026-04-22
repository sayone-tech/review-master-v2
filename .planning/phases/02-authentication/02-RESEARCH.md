# Phase 2: Authentication - Research

**Researched:** 2026-04-22
**Domain:** Django built-in authentication views, session management, DRF throttling, Amazon SES email
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Login page design:**
- Centered white card (~400–480px wide) on Background Gray (`#FAFAFA`) canvas — no sidebar shell
- Logo + app name at the top of the card (above the form heading)
- Password field has show/hide toggle (Alpine.js, consistent with activation and reset forms)
- "Forgot password?" link is right-aligned inline next to the Password label (not below the button)
- Same centered-card template used for forgot-password and reset-password pages

**Login error & security:**
- Error message: generic "Invalid email or password" (does not reveal whether email exists)
- Error displayed as a top-of-form alert banner (red, above the form fields)
- Rate limiting: DRF throttle on the login endpoint — 10 attempts per 15 minutes per IP, backed by Redis; 429 response with a clear user-facing message on breach
- "Remember me" checkbox: present on the login form; when checked, session cookie persists for 30 days; when unchecked, session expires after 24 hours

**Password reset flow:**
- Use Django's built-in `PasswordResetView` / `PasswordResetDoneView` / `PasswordResetConfirmView` / `PasswordResetCompleteView` — Django handles HMAC token generation, 1-hour expiry, and single-use enforcement
- Forgot-password page always shows "Check your email" after submission (never confirms whether email exists)
- Password reset email sent via Amazon SES (`django-ses` backend) — template matches EMAL-03 spec
- New-password field on the reset page includes the Alpine.js strength indicator (consistent across reset, activation ACTV-02, and profile change PROF-02)
- After successful reset: redirect to `/login` with a success message ("Password updated. Please sign in.")

**Session & redirect policy:**
- Default session lifetime: 24 hours (persistent cookie, regardless of remember-me)
- "Remember me" extends to 30 days
- `/login` respects `?next=` parameter for post-login redirect; Django validates `next` is a relative URL (open-redirect protection)
- Unauthenticated access to any `/admin/*` URL: redirect to `/login?next=<url>` (standard `login_required` / `LoginRequiredMixin` behaviour)
- After logout: redirect to `/login` (no confirmation message, clean slate)
- `LOGIN_URL` set to `/login/` in settings; `LOGIN_REDIRECT_URL` set to `/admin/organisations/`

### Claude's Discretion
- Exact login card padding, shadow, and border-radius (consistent with design system established in Phase 1)
- Loading / spinner state on the sign-in button during form submission
- Exact copy for rate-limit exceeded message
- 404 / 500 error page design (out of scope for this phase — can be minimal)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | User can log in with email and password via the /login page | Django LoginView with custom authentication_form + custom template; `email` as USERNAME_FIELD already set on User model |
| AUTH-02 | User can log out and have their server-side session invalidated | Django LogoutView with next_page='/login/'; POST-only for CSRF protection; replaces logout_stub in apps/common/urls.py |
| AUTH-03 | User can request a password reset email via "Forgot password?" link | Django PasswordResetView with custom template + email templates; always shows done page regardless of email existence |
| AUTH-04 | User can reset their password via a secure, time-limited email link (1-hour expiry) | Django PasswordResetConfirmView; HMAC token expires in PASSWORD_RESET_TIMEOUT (default 3 days, set to 3600s = 1 hour); single-use enforced by Django natively |
| AUTH-05 | User session persists across browser refresh | SESSION_COOKIE_AGE=86400 (24h), SESSION_EXPIRE_AT_BROWSER_CLOSE=False; set_expiry(2592000) for remember-me (30 days) |
</phase_requirements>

---

## Summary

This phase implements the authentication gate for the entire platform: login, logout, and password reset for the Superadmin role. All functionality builds directly on Django's built-in auth views (`django.contrib.auth.views`), which provide CSRF protection, HMAC token generation, single-use enforcement, and redirect validation out of the box. No custom token system is needed for password reset — Django already handles it correctly.

The main implementation work is: (1) custom `LoginView` subclass to add remember-me session logic and per-IP rate limiting via a new DRF-backed throttle class; (2) four auth templates using the existing design system's centered-card layout (a new `auth_base.html`, separate from `base.html`); (3) wiring Django's password-reset chain to the Amazon SES backend and EMAL-03 email template; (4) settings additions (`LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, `SESSION_COOKIE_AGE`, `PASSWORD_RESET_TIMEOUT`).

The rate-limiting decision (DRF throttle on the login endpoint) requires care: `LoginView` is a Django template view, not a DRF APIView. The cleanest approach consistent with the existing codebase is a thin custom `LoginView` subclass that manually invokes DRF's `SimpleRateThrottle` (using Redis DB 1) on POST requests before calling `super().post()`. This keeps rate-limit logic in `apps/accounts/throttling.py`, Redis-backed, and consistent with the project's existing throttle patterns in `apps/common/throttling.py`.

**Primary recommendation:** Subclass Django's built-in auth views with minimal overrides; add a custom `LoginRateThrottle` using Redis; create a new `auth_base.html` that does not extend `base.html` (no sidebar); use `PasswordResetView.html_email_template_name` to send HTML+text multipart reset emails via SES.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `django.contrib.auth.views` | Django 6.0.x (built-in) | LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetCompleteView | Ships with Django; handles CSRF, HMAC tokens, single-use, open-redirect protection |
| `django-ses` | ^4.3.0 (already in pyproject.toml per CLAUDE.md §12.11) | SES email backend | Already chosen; plugs into Django's email API transparently |
| `djangorestframework` | already installed | SimpleRateThrottle for login rate limiting | Already in project; Redis-backed cache key throttling |
| `django-redis` | already installed | Redis cache backend (DB 1 for throttle) | Already configured in base.py |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `premailer` | ^3.10.0 (per CLAUDE.md §12.11) | CSS inlining for email templates | Used in `send_transactional_email` service for EMAL-03 password reset email |
| Alpine.js | already bundled via Vite | Show/hide password toggle, submit button loading state | Already established pattern — form_fields.html password component uses it |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DRF SimpleRateThrottle manually invoked | `django-ratelimit` decorator | django-ratelimit is simpler for template views but adds a new dependency; project already uses DRF throttle infrastructure |
| Django's built-in PasswordResetView | Custom token + TimestampSigner | InvitationToken already uses TimestampSigner; but password reset has additional Django integration benefits (invalidation on password change, SetPasswordForm validation) — don't duplicate |
| Custom `auth_base.html` | Extending `base.html` with sidebar conditionally hidden | Conditional sidebar is fragile; auth pages structurally differ (no sidebar, no topbar); separate base template is cleaner |

**Installation:** No new dependencies required for Phase 2. `django-ses`, `boto3`, and `premailer` are already specified in `CLAUDE.md §12.11` as Phase 1 requirements; verify they are in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

```
apps/accounts/
├── views.py              # CustomLoginView, stub logout replaced by LogoutView wiring
├── forms.py              # CustomAuthenticationForm (generic error message)
├── throttling.py         # LoginRateThrottle (new — IP-based, Redis DB 1)
├── urls.py               # /login/, /logout/, /password-reset/*, /password-reset/confirm/
└── tests/
    ├── factories.py      # already exists
    ├── test_views.py     # new — login, logout, password reset tests

templates/
├── auth_base.html        # new — centered card layout, no sidebar
└── accounts/
    ├── login.html
    ├── password_reset.html
    ├── password_reset_done.html
    ├── password_reset_confirm.html
    └── password_reset_complete.html

templates/emails/
├── password_reset.html   # HTML version — EMAL-03
└── password_reset.txt    # plain-text version — EMAL-03

apps/common/services/
└── email.py              # send_transactional_email — already planned in CLAUDE.md §12.4
```

### Pattern 1: Custom LoginView with Remember-Me and Rate Limiting

**What:** Subclass `LoginView` to add per-IP rate limiting before authentication, and call `request.session.set_expiry()` based on the "remember me" checkbox value in `form_valid()`.

**When to use:** Whenever you need to augment built-in auth views without replacing them. Django's `form_valid()` is the canonical hook after successful validation.

**Example:**
```python
# Source: https://docs.djangoproject.com/en/6.0/topics/auth/default/
# apps/accounts/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.urls import reverse_lazy

from apps.accounts.forms import CustomAuthenticationForm
from apps.accounts.throttling import LoginRateThrottle


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        throttle = LoginRateThrottle()
        if not throttle.allow_request(request, self):
            from django.http import HttpResponse as HR
            return HR("Too many sign-in attempts. Please try again in 15 minutes.", status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: CustomAuthenticationForm) -> HttpResponse:
        remember = self.request.POST.get("remember_me")
        response = super().form_valid(form)
        if remember:
            self.request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
        else:
            self.request.session.set_expiry(60 * 60 * 24)  # 24 hours
        return response
```

### Pattern 2: Generic Login Error Message (No Email Enumeration)

**What:** Subclass `AuthenticationForm` and override `error_messages` to replace the default message with the generic "Invalid email or password."

**When to use:** Any login form where user existence must not be revealed.

**Example:**
```python
# apps/accounts/forms.py
from django.contrib.auth.forms import AuthenticationForm


class CustomAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }
```

### Pattern 3: IP-Based Login Rate Throttle

**What:** Subclass `SimpleRateThrottle` for use outside DRF APIViews. Override `get_cache_key()` to use the request IP. Call `throttle.allow_request(request, view)` manually inside `LoginView.post()`.

**When to use:** Rate limiting non-DRF views while keeping Redis throttle backend consistent with existing project patterns.

**Example:**
```python
# apps/accounts/throttling.py
from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """10 POST attempts per 15 minutes per IP on the login endpoint."""
    scope = "login"

    def get_cache_key(self, request, view):  # type: ignore[override]
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
```

Add to `DEFAULT_THROTTLE_RATES` in `base.py`:
```python
"login": "10/15min",
```

Note: DRF `SimpleRateThrottle` stores keys in the cache configured for `DEFAULT_CACHE_ALIAS`. The project's Redis is DB 0 for the default cache. CLAUDE.md §7.5 states DB 1 is for DRF throttling. To use DB 1, set a separate cache alias `"throttle"` on DB 1 and set `cache = caches["throttle"]` on the throttle class.

### Pattern 4: PasswordResetView with HTML Email

**What:** Use `PasswordResetView.html_email_template_name` to send an HTML+text multipart reset email. Django's `PasswordResetForm.save()` automatically uses `html_email_template_name` when specified, creating an `EmailMultiAlternatives` with both parts.

**When to use:** Any time password reset email must render in HTML (EMAL-03 requirement).

**Example:**
```python
# apps/accounts/urls.py (excerpt)
from django.contrib.auth import views as auth_views
from django.urls import path

urlpatterns = [
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="emails/password_reset.txt",
        html_email_template_name="emails/password_reset.html",
        subject_template_name="emails/password_reset_subject.txt",
        success_url="/password-reset/done/",
        extra_email_context={"site_name": "Review Master"},
    ), name="password_reset"),
    ...
]
```

**Critical:** `PasswordResetView` checks `html_email_template_name` when present and sends multipart. The plain-text `email_template_name` is still required as the fallback body.

### Pattern 5: PasswordResetConfirmView → Redirect to /login with Flash

**What:** After successful password reset, redirect to `/login` with a Django messages success flash.

**When to use:** Consistent UX pattern — user resets password then must sign in fresh.

**Example:**
```python
# apps/accounts/views.py
from django.contrib import messages
from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import reverse_lazy


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Your password has been updated. Please sign in.",
        )
        return response
```

### Pattern 6: Auth Base Template (No Sidebar)

**What:** A new `auth_base.html` that renders the centered card layout without sidebar or topbar. Auth pages extend this, NOT `base.html`.

**When to use:** All pages without authenticated shell: login, forgot-password, reset-password, activation (Phase 4).

**Example structure:**
```html
{# templates/auth_base.html #}
<!DOCTYPE html>
<html lang="en">
  <head>{% include "partials/head.html" %}</head>
  <body class="bg-bg font-sans min-h-screen flex items-center justify-center">
    <div class="w-full max-w-[480px] px-4">
      {% block card %}{% endblock %}
    </div>
    {% include "components/toasts.html" %}
  </body>
</html>
```

### Anti-Patterns to Avoid

- **Extending `base.html` for auth pages:** `base.html` includes sidebar and topbar — auth pages must use a separate `auth_base.html`.
- **Calling `logout_stub` from Phase 1 as the real logout:** Replace `logout_stub` in `apps/common/urls.py`; move to `apps/accounts/urls.py` using `LogoutView`.
- **Using `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` globally:** This overrides all sessions. Instead, keep `SESSION_EXPIRE_AT_BROWSER_CLOSE = False` globally and use `set_expiry(0)` per-request only when needed (Phase 2 does not use browser-close expiry; 24h is the minimum).
- **Storing remember-me preference in the DB:** `set_expiry()` on the session object is the correct approach — no model change needed.
- **Confirming email existence on forgot-password:** `PasswordResetView` already does this correctly by default (sends to valid emails silently, always redirects to done page). Don't override this behavior.
- **Putting business logic in `form_valid()`:** `form_valid()` is a view hook; keep logic minimal — session setting is acceptable here, but multi-step writes go to services.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC password reset tokens (1-hour expiry, single-use) | Custom token generation + DB storage | Django's `PasswordResetView` + `PasswordResetConfirmView` | Django uses `default_token_generator` (HMAC of user PK + password hash + timestamp); single-use via password hash invalidation; no extra DB table |
| CSRF protection on login/logout | Manual token checking | Django's `CsrfViewMiddleware` (already in MIDDLEWARE) + `{% csrf_token %}` | Already in the middleware stack |
| Open-redirect protection on `?next=` | Manual URL validation | `LoginView` built-in `is_safe_url` validation | Django validates `next` is a safe relative URL automatically |
| Session invalidation on logout | Manual `session.flush()` | `LogoutView` | `LogoutView` calls `logout(request)` which flushes session and regenerates CSRF token |
| Email delivery to SES | Direct boto3 calls | `django-ses` backend + `send_mail()` / `EmailMultiAlternatives` | Already configured; `PasswordResetView.from_email` uses `DEFAULT_FROM_EMAIL` which routes through SES backend |

**Key insight:** Django's auth views encode years of security best-practice. The correct approach is thin subclassing for project-specific overrides, not replacement.

---

## Common Pitfalls

### Pitfall 1: Rate Throttle Bypass — POST vs GET

**What goes wrong:** `LoginView` handles both GET (render form) and POST (authenticate). A naive throttle applied at the class level throttles form renders too. An IP-based throttle should only apply to POST.

**Why it happens:** Overriding `dispatch()` runs before method routing; overriding `post()` is the correct hook.

**How to avoid:** Override `post()` in `CustomLoginView`; call `throttle.allow_request()` there, then call `super().post()` only on success.

**Warning signs:** GET requests to `/login/` returning 429 when the throttle is hit.

### Pitfall 2: `logout` URL Name Conflict

**What goes wrong:** Phase 1 registered `logout_stub` with `name='logout'` in `apps/common/urls.py`. Phase 2 must move this to `apps/accounts/urls.py` using Django's real `LogoutView`. If both registrations exist simultaneously, Django picks the first matching URL pattern.

**Why it happens:** URL names are global in Django; duplicate names silently win by first-registered order.

**How to avoid:** Remove `path("logout/", logout_stub, name="logout")` from `apps/common/urls.py` in the same plan wave that adds it to `apps/accounts/urls.py`. STATE.md documents: "logout_stub registered as name='logout' in Phase 1; Phase 2 swaps view body, URL name is stable."

**Warning signs:** `{% url 'logout' %}` resolving to the stub after Phase 2 migration.

### Pitfall 3: `PASSWORD_RESET_TIMEOUT` Default Is Too Long

**What goes wrong:** Django's default `PASSWORD_RESET_TIMEOUT` is 259200 seconds (3 days). AUTH-04 requires 1-hour expiry.

**Why it happens:** Django's default is conservative for usability; the requirement overrides it.

**How to avoid:** Set `PASSWORD_RESET_TIMEOUT = 3600` in `config/settings/base.py`.

**Warning signs:** Password reset links still working after 1 hour in testing.

### Pitfall 4: LogoutView Requires POST in Django 5+

**What goes wrong:** Since Django 5.0, `LogoutView` only accepts POST requests (GET logout was removed for CSRF security). Templates that send logout as a `<a href="/logout/">` link will silently fail or show the logged-out template without actually logging out.

**Why it happens:** Django 5.0 security hardening removed GET-based logout.

**How to avoid:** The sidebar logout item must be a `<form method="post" action="{% url 'logout' %}">` with `{% csrf_token %}`, not a bare anchor tag. Check `templates/partials/sidebar.html` — update if it uses an anchor.

**Warning signs:** User still authenticated after clicking logout.

### Pitfall 5: Session Cookie Not Secure in Production

**What goes wrong:** `SESSION_COOKIE_SECURE` defaults to False; sessions transmitted over HTTP are vulnerable to interception.

**Why it happens:** Production settings need explicit security flags.

**How to avoid:** Set in `config/settings/production.py`:
```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True  # already Django default
```
These are listed in CLAUDE.md §19 security checklist.

### Pitfall 6: DRF Throttle Cache Key Collision with Default Cache (DB 0)

**What goes wrong:** `SimpleRateThrottle` by default uses Django's `default` cache (Redis DB 0). CLAUDE.md §7 specifies DB 1 for DRF throttling.

**Why it happens:** DRF `SimpleRateThrottle` uses `default_cache` unless overridden.

**How to avoid:** Add a `throttle` cache alias for Redis DB 1 in `base.py`:
```python
CACHES = {
    "default": { ... "/0" ... },
    "throttle": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379") + "/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "throttle",
        "TIMEOUT": 900,
    }
}
```
Then set `cache = caches["throttle"]` on `LoginRateThrottle` (and optionally set `REST_FRAMEWORK["DEFAULT_THROTTLE_BACKEND"] = "throttle"` for DRF-wide throttle cache isolation).

### Pitfall 7: `redirect_authenticated_user = True` Information Leakage

**What goes wrong:** Django docs warn: "Enabling redirect_authenticated_user may result in an information leak as third-party sites can determine whether their visitors are authenticated on your site" (e.g., via image loading timing).

**Why it happens:** Feature works by redirecting authenticated users, which is observable externally.

**How to avoid:** Set `redirect_authenticated_user = True` anyway for UX (locks Superadmin out of /login/ if already logged in), but be aware of the nuance. For a Superadmin-only tool with no external exposure, this risk is acceptable.

---

## Code Examples

### Settings additions (config/settings/base.py)

```python
# Source: https://docs.djangoproject.com/en/6.0/topics/auth/default/
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/admin/organisations/"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_COOKIE_AGE = 60 * 60 * 24        # 24 hours (default; remember-me overrides per-request)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False   # persist cookie across browser restart
SESSION_SAVE_EVERY_REQUEST = False        # don't reset clock on every request

PASSWORD_RESET_TIMEOUT = 3600            # 1 hour (AUTH-04)
```

### URL wiring (apps/accounts/urls.py)

```python
# Source: https://docs.djangoproject.com/en/6.0/topics/auth/default/
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import CustomLoginView, CustomPasswordResetConfirmView

app_name = "accounts"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="emails/password_reset.txt",
        html_email_template_name="emails/password_reset.html",
        subject_template_name="emails/password_reset_subject.txt",
        success_url="/password-reset/done/",
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/confirm/<uidb64>/<token>/",
         CustomPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
```

Include in `config/urls.py`:
```python
path("", include("apps.accounts.urls")),
```
Remove `path("logout/", logout_stub, name="logout")` from `apps/common/urls.py` in the same wave.

### Email context variables available in password_reset.html template

```
# Source: https://docs.djangoproject.com/en/6.0/topics/auth/default/
# Template context provided by PasswordResetForm.save():
# {{ email }}     — recipient email
# {{ user }}      — User instance
# {{ domain }}    — request domain (e.g. app.reviewmaster.io)
# {{ protocol }} — "https" in production
# {{ uid }}       — base64-encoded user PK
# {{ token }}     — HMAC reset token
# {{ site_name }} — via extra_email_context

# Reset link construction:
{{ protocol }}://{{ domain }}{% url 'accounts:password_reset_confirm' uidb64=uid token=token %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GET-based logout (`<a href="/logout/">`) | POST-only `LogoutView` | Django 5.0 | Sidebar logout must be a form with CSRF token |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` for "no remember me" | `request.session.set_expiry(seconds)` per-request | Django 1.0+ | Per-session control without global setting changes |
| Separate password-reset token DB table | Django's `default_token_generator` (HMAC-based, stateless) | Django 1.0+ | No DB table needed; token invalidated when password changes |
| HTML-only reset emails | `html_email_template_name` + plain-text fallback | Django 1.7+ | SES penalises HTML-only; always ship both |

**Deprecated/outdated:**
- `django.contrib.auth.urls` include path: Still works but gives less control over URL paths and names; prefer explicit registration as shown above.
- GET logout: Removed in Django 5.0. Do not use `<a href="{% url 'logout' %}">` anchors.

---

## Open Questions

1. **`apps/common/services/email.py` — Does it exist yet?**
   - What we know: CLAUDE.md §12.4 specifies `send_transactional_email` should live there; Phase 1 did not appear to create it (no `services/` subdirectory found in `apps/common/`).
   - What's unclear: Whether Phase 2 should create it as part of this phase (needed for the password reset email to use the standard service) or whether `PasswordResetView`'s built-in email mechanism is sufficient.
   - Recommendation: For this phase, use `PasswordResetView`'s built-in email sending (via `html_email_template_name`). Create `apps/common/services/email.py` in Phase 4 (invitation emails), which is the first phase that actually calls `send_transactional_email`. This avoids creating empty infrastructure.

2. **`throttle` Redis cache alias — Is it already configured?**
   - What we know: `base.py` only configures the `default` cache (DB 0). CLAUDE.md §7.5 says throttle goes to DB 1 but no `throttle` alias exists yet.
   - What's unclear: Was the throttle cache alias expected to be set up in Phase 1?
   - Recommendation: Add the `throttle` cache alias in this phase's settings plan. The `LoginRateThrottle` must explicitly reference it.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (already configured) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| Quick run command | `pytest apps/accounts/tests/test_views.py -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Login with valid credentials redirects to /admin/organisations/ | integration | `pytest apps/accounts/tests/test_views.py::test_login_success -x` | ❌ Wave 0 |
| AUTH-01 | Login with invalid credentials shows generic error (not email enumeration) | integration | `pytest apps/accounts/tests/test_views.py::test_login_invalid -x` | ❌ Wave 0 |
| AUTH-01 | Login with nonexistent email shows same error as wrong password | integration | `pytest apps/accounts/tests/test_views.py::test_login_no_enumeration -x` | ❌ Wave 0 |
| AUTH-01 | Rate limit blocks IP after 10 failed attempts in 15 minutes (429) | integration | `pytest apps/accounts/tests/test_views.py::test_login_rate_limit -x` | ❌ Wave 0 |
| AUTH-01 | "Remember me" checked: session expires in 30 days | integration | `pytest apps/accounts/tests/test_views.py::test_login_remember_me -x` | ❌ Wave 0 |
| AUTH-01 | "Remember me" unchecked: session expires in 24 hours | integration | `pytest apps/accounts/tests/test_views.py::test_login_no_remember_me -x` | ❌ Wave 0 |
| AUTH-01 | ?next= redirect works; rejects absolute URLs (open-redirect) | integration | `pytest apps/accounts/tests/test_views.py::test_login_next_param -x` | ❌ Wave 0 |
| AUTH-02 | POST to /logout/ invalidates session and redirects to /login/ | integration | `pytest apps/accounts/tests/test_views.py::test_logout -x` | ❌ Wave 0 |
| AUTH-02 | GET to /logout/ is rejected or redirects safely (Django 5+ behavior) | integration | `pytest apps/accounts/tests/test_views.py::test_logout_get_rejected -x` | ❌ Wave 0 |
| AUTH-03 | Forgot-password POST with valid email sends reset email (check mail.outbox) | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_email_sent -x` | ❌ Wave 0 |
| AUTH-03 | Forgot-password POST with nonexistent email shows done page, no email sent | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_no_enumeration -x` | ❌ Wave 0 |
| AUTH-04 | Valid reset link allows password change; link invalid after use | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_confirm -x` | ❌ Wave 0 |
| AUTH-04 | Expired reset link (>1 hour) shows invalid-link page | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_expired -x` | ❌ Wave 0 |
| AUTH-04 | After reset, redirect to /login/ with flash message | integration | `pytest apps/accounts/tests/test_views.py::test_password_reset_redirect -x` | ❌ Wave 0 |
| AUTH-05 | Authenticated user accessing /admin/* after browser-simulated restart still authenticated | integration | `pytest apps/accounts/tests/test_views.py::test_session_persists -x` | ❌ Wave 0 |
| AUTH-05 | Unauthenticated access to /admin/* redirects to /login?next= | integration | `pytest apps/accounts/tests/test_views.py::test_login_required_redirect -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/accounts/tests/test_views.py -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `apps/accounts/tests/test_views.py` — all AUTH-01 through AUTH-05 tests
- [ ] `apps/accounts/tests/factories.py` — already exists; verify `UserFactory` creates superadmin with usable password

*(No new test infrastructure files needed — pytest, pytest-django, factory-boy all configured)*

---

## Sources

### Primary (HIGH confidence)
- Django 6.0 official docs — https://docs.djangoproject.com/en/6.0/topics/auth/default/ — LoginView, LogoutView, PasswordResetView*, form attributes, session set_expiry(), PASSWORD_RESET_TIMEOUT
- Django 6.0 ref — https://docs.djangoproject.com/en/6.0/ref/contrib/auth/ — auth view attributes verified
- CLAUDE.md (project) — Sessions, Redis DB assignment, DRF throttle configuration, SES email backend, security checklist

### Secondary (MEDIUM confidence)
- WebSearch (multiple sources) — Django 5.0 GET logout removal; `set_expiry()` pattern for remember-me; `SimpleRateThrottle` manual invocation pattern
- DRF docs — https://www.django-rest-framework.org/api-guide/throttling/ — `SimpleRateThrottle.get_cache_key()` override

### Tertiary (LOW confidence)
- None — all critical claims verified against official Django 6.0 docs or project files

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; Django auth views verified against 6.0 docs
- Architecture: HIGH — patterns verified against official docs; project conventions confirmed from existing code
- Pitfalls: HIGH — POST-only logout and PASSWORD_RESET_TIMEOUT defaults verified from Django 5.0/6.0 docs; Redis DB separation from CLAUDE.md

**Research date:** 2026-04-22
**Valid until:** 2026-07-22 (stable domain — Django auth views change rarely)
