# Phase 5: Profile and Hardening - Research

**Researched:** 2026-04-24
**Domain:** Django profile views, Django auth password change, GitHub Actions CI, security settings hardening
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Profile page layout:**
- Two separate cards stacked vertically under `max-w-[640px]`
- Card 1 — "Your profile": name (editable) + email (read-only) + role (read-only)
- Card 2 — "Change password": current password + new password (with strength indicator) + confirm new password
- Both forms use full page POST — no HTMX, no partial updates

**Name edit UX:**
- Edit-on-click pattern: name displays as static text with an Edit button beside it
- Clicking Edit renders an `<input>` in place of the text, with Save and Cancel buttons
- Cancel reverts to original value (Alpine.js `x-data` holding the original)
- Save: `POST /admin/profile/update-name/` → redirect back to `/admin/profile` → success toast via Django messages
- Full page reload on success is acceptable

**Password change section:**
- Three fields: Current password, New password, Confirm new password
- Current password required — reject with validation error if wrong
- Alpine.js 4-bar strength indicator on New password field — reuse exact pattern from `templates/accounts/invite_accept.html`
- Show/hide toggle on all three fields — reuse same pattern as existing auth templates
- Submit: `POST /admin/profile/change-password/` → on success, use Django's `update_session_auth_hash` to keep logged in, show success toast
- Use Django's `check_password()` to validate current password server-side

**GitHub Actions CI:**
- Triggers: push to `main` + pull_request targeting `main`
- Steps in order:
  1. `pre-commit run --all-files`
  2. `mypy`
  3. `pytest --cov=apps --cov-fail-under=85`
  4. `python manage.py makemigrations --check --dry-run`
  5. `python manage.py check --deploy` (uses production settings)
- No deploy step in this phase — CI only

**Pre-commit config:**
- `.pre-commit-config.yaml` already exists with hooks from CLAUDE.md §14 — verify and add any missing hooks only
- django-upgrade target-version MUST remain "5.1" (not "6.0") — django-upgrade 1.22.2 does not support 6.0 (locked project decision from STATE.md)

**Security settings hardening:**
- All additions go in `config/settings/production.py`
- Required settings to add: `SECURE_BROWSER_XSS_FILTER = True`, `X_FRAME_OPTIONS = "DENY"`
- Already present: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_PROXY_SSL_HEADER`
- Django 6 CSP middleware enabled in MIDDLEWARE (confirm django.middleware.security.SecurityMiddleware is present)

### Claude's Discretion

- Exact Alpine.js code for the name Edit/Cancel toggle (follow the established show/hide pattern)
- Session message vs query-param toast delivery mechanism for success toasts
- URL structure for the two profile POST endpoints (can be one view with action discrimination or two separate views)
- Ruff `pyproject.toml` config (already exists — check before adding)

### Deferred Ideas (OUT OF SCOPE)

- Password reset / forgot password — already implemented in Phase 2
- Deploy workflow (`.github/workflows/deploy.yml`) — out of scope for this phase (CI only)
- HTMX partial name update — not worth the complexity for a single field
- Org Admin profile page — only Superadmin profile is in scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROF-01 | Superadmin can update their full name from /admin/profile; success toast on save | Django form POST pattern, `update_profile_name()` service function, Django messages framework for toast delivery, profile stub template at `templates/accounts/profile.html` ready to extend |
| PROF-02 | Superadmin can change their password (requires current password, new password with strength indicator, confirm); success toast on save | Django `check_password()` + `set_password()` + `update_session_auth_hash()` pattern, Alpine.js strength indicator from `invite_accept.html`, `PasswordChangeForm` alternative vs custom form |
</phase_requirements>

---

## Summary

Phase 5 completes the Superadmin feature set with a profile edit page and locks down the project with CI, coverage enforcement, and production security hardening. The codebase is mature: four prior phases have established all the patterns, templates, and infrastructure this phase relies on.

The profile page (`templates/accounts/profile.html`) is already a read-only stub at `/profile/`. This phase extends it to `/admin/profile/` with two functional cards. The URL **must move** from `profile/` to `admin/profile/` to match the locked spec — the current registration at `path("profile/", ...)` is in `apps/accounts/urls.py` and must be changed. Sidebar and topbar templates use hardcoded `/profile/` hrefs that also need updating.

The GitHub Actions CI workflow does not exist yet (no `.github/workflows/` directory). The `.pre-commit-config.yaml` is fully wired already, so CI simply needs to invoke `pre-commit run --all-files`. Coverage is already configured in `pyproject.toml` (`fail_under = 85`); CI just needs to pass `--cov-fail-under=85`. The `manage.py check --deploy` step needs stub env vars for the production settings to not crash during CI (specifically `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECRET_KEY`, `AWS_SES_FROM_EMAIL`).

**Primary recommendation:** Implement profile views first (two plan tasks: backend services + views, then template), then wire CI (one task), then verify security settings audit (one task). Reuse the Alpine.js patterns from `invite_accept.html` verbatim — do not reinvent.

## Standard Stack

### Core (already in pyproject.toml — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.2 | Profile views, password change utilities, messages framework | Project's web framework |
| pytest + pytest-django | 8.3.3 / 4.9.0 | Test suite for profile service and view tests | Project test framework |
| Alpine.js | (bundled via Vite) | Edit-in-place toggle, password show/hide, strength indicator | Already used throughout for interactive UI |

### Supporting (already present)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `django.contrib.messages` | built-in | Success toast delivery after POST-redirect | Used for all full-page form success feedback |
| `django.contrib.auth.update_session_auth_hash` | built-in | Keep session alive after password change | Called immediately after `set_password()` + `save()` |
| `django.contrib.auth.password_validation.validate_password` | built-in | Validate new password against AUTH_PASSWORD_VALIDATORS | Already used in `ActivationForm` |
| `factory-boy` | 3.3.3 | `UserFactory` in tests — already has full_name and password setup | Profile service tests |

### No New Dependencies

This phase introduces zero new Python dependencies. All functionality is available through Django builtins and existing project libraries.

**Installation:** None required.

## Architecture Patterns

### Recommended Project Structure for This Phase

```
apps/accounts/
├── services/                   # CREATE THIS DIRECTORY
│   ├── __init__.py
│   └── profile.py              # update_profile_name(), change_password()
├── forms.py                    # ADD: ProfileNameForm, PasswordChangeForm
├── views.py                    # ADD: update_name_view(), change_password_view()
└── urls.py                     # MODIFY: add two POST endpoints, move profile to /admin/profile/

templates/accounts/
└── profile.html                # MODIFY: extend stub with two cards, Alpine.js patterns

.github/
└── workflows/
    └── ci.yml                  # CREATE: 5-step CI pipeline

config/settings/
└── production.py               # MODIFY: add missing security headers
```

### Pattern 1: Profile Service Functions

**What:** Two thin service functions in `apps/accounts/services/profile.py`. No business logic in views.
**When to use:** Any state-mutating operation on the User model.

```python
# apps/accounts/services/profile.py
from __future__ import annotations
from django.db import transaction
from apps.accounts.models import User


@transaction.atomic
def update_profile_name(*, user: User, full_name: str) -> User:
    """Update Superadmin's full name. Validates min/max length before save."""
    user.full_name = full_name.strip()
    user.save(update_fields=["full_name", "updated_at"])
    return user


@transaction.atomic
def change_password(*, user: User, current_password: str, new_password: str) -> User:
    """Change password after verifying current password.
    Raises ValueError if current_password does not match.
    Caller must call update_session_auth_hash() after this returns.
    """
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    return user
```

### Pattern 2: Profile Views (POST-redirect-GET with Django messages)

**What:** The profile page renders the GET. Two separate POST-only views handle name update and password change. On success, both redirect back to `/admin/profile/` and queue a Django message. On failure, both redirect back with the form errors stored in the session (or re-render with error context).
**When to use:** Full page POST pattern, consistent with all other form pages in this project.

```python
# apps/accounts/views.py (additions)
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from apps.accounts.services.profile import update_profile_name, change_password as svc_change_password

@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/profile.html")

@login_required
def update_name_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("profile")
    form = ProfileNameForm(request.POST)
    if form.is_valid():
        update_profile_name(user=request.user, full_name=form.cleaned_data["full_name"])
        messages.success(request, "Name updated.")
        return redirect("profile")
    # re-render profile with name form errors in context
    return render(request, "accounts/profile.html", {"name_form": form})

@login_required
def change_password_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("profile")
    form = PasswordChangeForm(request.POST)
    if form.is_valid():
        try:
            user = svc_change_password(
                user=request.user,
                current_password=form.cleaned_data["current_password"],
                new_password=form.cleaned_data["new_password"],
            )
            update_session_auth_hash(request, user)  # keep session alive
            messages.success(request, "Password updated.")
        except ValueError:
            form.add_error("current_password", "Current password is incorrect.")
            return render(request, "accounts/profile.html", {"pw_form": form})
    else:
        return render(request, "accounts/profile.html", {"pw_form": form})
    return redirect("profile")
```

### Pattern 3: Alpine.js Edit-in-Place for Name

**What:** Alpine `x-data` holds the original name and an `editing` boolean. Clicking Edit shows the input and Save/Cancel buttons. Cancel reverts to original without a page load. Save triggers the form POST.
**When to use:** Single-field inline edit with a cancel path.

```html
{# In profile.html name row — Alpine.js edit-in-place pattern #}
<div x-data="{ editing: false, orig: '{{ user.full_name|escapejs }}', val: '{{ user.full_name|escapejs }}' }"
     class="flex items-center gap-2">
  {# Static display #}
  <span x-show="!editing" class="text-ink font-medium" x-text="val || '—'"></span>
  <button x-show="!editing" type="button" @click="editing = true"
          class="text-[12px] text-subtle hover:text-ink">Edit</button>

  {# Editable form #}
  <form x-show="editing" method="post" action="{% url 'profile_update_name' %}" class="flex items-center gap-2">
    {% csrf_token %}
    <input type="text" name="full_name" :value="val"
           x-model="val" minlength="2" maxlength="100" required
           class="px-2 py-1 text-[13.5px] border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06]">
    <button type="submit" class="text-[12px] text-yellow hover:text-yellow-hover font-medium">Save</button>
    <button type="button" @click="editing = false; val = orig"
            class="text-[12px] text-subtle hover:text-ink">Cancel</button>
  </form>
</div>
```

### Pattern 4: Toast Delivery via Django Messages

**What:** The toast component in `templates/components/toasts.html` already seeds from Django messages on page render. After redirect, the queued message renders as a toast automatically. No extra work needed.
**How it works:** The `<script type="application/json" id="django-messages-seed">` block in `toasts.html` is read on DOMContentLoaded and fires `app:toast` CustomEvents. The tag value of `messages.success(request, "...")` maps to the toast `kind` field.

The tag for `messages.success()` is `"success"` — which maps to the green icon in the toast component. Use `messages.success(request, "Name updated.")` and `messages.success(request, "Password updated.")`.

**Verification:** Confirmed by reading `templates/components/toasts.html` — the seed script iterates `{% for message in messages %}` and emits `{ "kind": "{{ message.tags }}", "title": "{{ message|escapejs }}", "msg": "" }`. The `messages.success()` tag string is `"success"`.

### Pattern 5: URL Migration from /profile/ to /admin/profile/

**What:** The profile page is currently registered at `path("profile/", ...)` but the spec requires `/admin/profile/`. The sidebar and topbar also hardcode `/profile/`.
**Changes needed:**
1. In `apps/accounts/urls.py`: change `path("profile/", ...)` to `path("admin/profile/", ...)`
2. Add two new POST endpoints: `path("admin/profile/update-name/", ...)` and `path("admin/profile/change-password/", ...)`
3. In `templates/partials/sidebar.html`: update href from `/profile/` to `/admin/profile/`
4. In `templates/partials/sidebar_org.html`: same update
5. In `templates/partials/topbar.html`: update href from `/profile/` to `/admin/profile/`

**Note:** The existing test at line 91-95 of `test_views.py` already expects `/admin/profile/` in the `next` parameter redirect — this confirms the URL must be `/admin/profile/`. The existing stub registration at `/profile/` was always a placeholder.

### Pattern 6: GitHub Actions CI Workflow

**What:** `.github/workflows/ci.yml` running 5 sequential steps on Python 3.12 with uv. Uses `astral-sh/setup-uv` for fast dependency installation.
**When to use:** Every PR and push to main.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: reviewmaster
          POSTGRES_USER: app
          POSTGRES_PASSWORD: app
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 3
        ports:
          - 6379:6379

    env:
      DJANGO_SETTINGS_MODULE: config.settings.test
      DJANGO_SECRET_KEY: ci-insecure-secret
      DJANGO_ALLOWED_HOSTS: localhost

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          version: "0.4.29"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: pre-commit
        run: uv run pre-commit run --all-files

      - name: mypy
        run: uv run mypy .

      - name: pytest
        run: uv run pytest --cov=apps --cov-fail-under=85

      - name: Check migrations
        run: uv run python manage.py makemigrations --check --dry-run

      - name: Deploy check
        env:
          DJANGO_SETTINGS_MODULE: config.settings.production
          DJANGO_SECRET_KEY: ci-deploy-check-secret
          DJANGO_ALLOWED_HOSTS: localhost
          AWS_SES_FROM_EMAIL: noreply@example.com
          DEFAULT_FROM_EMAIL: noreply@example.com
          DEFAULT_REPLY_TO: support@example.com
          DATABASE_URL: postgres://app:app@localhost:5432/reviewmaster
          REDIS_URL: redis://localhost:6379
        run: uv run python manage.py check --deploy
```

**Key CI insight:** Steps 1-4 use `config.settings.test` (SQLite in-memory, no external services needed). Step 5 (`check --deploy`) uses `config.settings.production` and needs the production env vars stubbed — specifically `DJANGO_ALLOWED_HOSTS` and `DJANGO_SECRET_KEY` (required by production.py) and `AWS_SES_FROM_EMAIL` (required by production.py `env("AWS_SES_FROM_EMAIL")`). The deploy check does NOT run tests, just validates settings configuration.

### Anti-Patterns to Avoid

- **Calling `user.save()` without `update_fields`**: Always use `update_fields=["full_name", "updated_at"]` to avoid overwriting unrelated fields and triggering unnecessary DB writes.
- **Putting password validation in the view**: All validation belongs in the form (`clean_new_password()`) and current-password verification in the service.
- **Re-rendering without populating both forms**: The profile template renders two cards. When one form fails validation, the other card must still render correctly. Pass both `name_form` and `pw_form` to the context (using `None` for the one not being submitted).
- **Skipping `update_session_auth_hash`**: After `set_password()`, the session auth hash changes and the user gets logged out. `update_session_auth_hash(request, user)` regenerates the session with the new hash. This is a Django builtin at `django.contrib.auth`.
- **Using `save()` then `update_session_auth_hash` in wrong order**: Save the user first, then call `update_session_auth_hash`. The function reads `user.password` from the saved object.
- **Hardcoding `/profile/` in templates**: Use `{% url 'profile' %}` to avoid link rot when URL changes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password strength scoring | Custom JS strength algorithm | Alpine.js pattern from `invite_accept.html` (verbatim copy) | Already implemented, tested visually, consistent UX |
| Show/hide password toggle | Custom toggle widget | Alpine `x-data="{ show: false }"` pattern from `invite_accept.html` | Same pattern works across all password fields |
| Current password verification | Custom hash comparison | `user.check_password(current_password)` | Django handles hash algorithm, timing safety |
| Session update after password change | Manual session key update | `update_session_auth_hash(request, user)` | Django builtin handles session regeneration correctly |
| Password validation | Custom rules | `validate_password(pw)` from `django.contrib.auth.password_validation` | Already used in `ActivationForm`, respects `AUTH_PASSWORD_VALIDATORS` |
| Toast notification display | Custom notification system | Django messages framework + existing `toasts.html` seed script | Already wired — `messages.success()` renders as green toast |
| CI dependency caching | Custom cache key | `astral-sh/setup-uv@v5` | uv caches faster than pip; `--frozen` ensures reproducibility |

**Key insight:** Every hard part of this phase is already solved. The Alpine.js patterns exist in `invite_accept.html` as verbatim source. The toast delivery mechanism is wired in `toasts.html`. The test infrastructure is set up. This phase is about assembly, not invention.

## Common Pitfalls

### Pitfall 1: Profile URL Mismatch — `/profile/` vs `/admin/profile/`

**What goes wrong:** The current `urls.py` registers the profile at `path("profile/", ...)` which serves it at `/profile/`. The CONTEXT.md spec requires `/admin/profile/`. The sidebar and topbar hardcode `/profile/` hrefs. Forgetting to update any of these causes broken links or 404s.
**Why it happens:** The profile was stubbed in Phase 1 at `/profile/` as a placeholder; the final URL was always intended to be `/admin/profile/`.
**How to avoid:** Change `path("profile/", ...)` to `path("admin/profile/", ...)` in `apps/accounts/urls.py`. Update all three template files: `sidebar.html`, `sidebar_org.html`, `topbar.html` (change hardcoded `/profile/` to `/admin/profile/`). Use `{% url 'profile' %}` in the profile template itself.
**Warning signs:** Test `test_login_next_param` in `test_views.py` already expects `resp.url == "/admin/profile/"` — if profile stays at `/profile/`, this test fails.

### Pitfall 2: Django Messages Tag Mismatch

**What goes wrong:** `messages.success(request, "...")` produces tag `"success"`. The toast component reads `message.tags`. If you use `messages.add_message(request, messages.INFO, "...")`, the tag would be `"info"` which maps to a blue icon — not the green success icon expected.
**Why it happens:** `messages.success()` produces tag `"success"`, `messages.info()` produces `"info"`, `messages.warning()` produces `"warning"`, `messages.error()` produces `"error"`. The toast component uses these to colour the indicator icon.
**How to avoid:** Always use `messages.success(request, "...")` for success feedback in this phase.

### Pitfall 3: `manage.py check --deploy` Fails in CI on Missing Env Vars

**What goes wrong:** `config/settings/production.py` calls `env("AWS_SES_FROM_EMAIL")` (no default) and `env.list("DJANGO_ALLOWED_HOSTS")` (no default). If these are not set in the CI environment when the deploy check runs, the settings module raises `django.core.exceptions.ImproperlyConfigured`.
**Why it happens:** Production settings intentionally fail loudly for missing secrets.
**How to avoid:** The CI step for deploy check must set env vars:
  - `DJANGO_SECRET_KEY` — any non-empty string
  - `DJANGO_ALLOWED_HOSTS` — `localhost` is enough
  - `AWS_SES_FROM_EMAIL` — any email address string
  - `DATABASE_URL` — must be reachable; use the postgres service from the CI job
  - `REDIS_URL` — must be reachable; use the redis service
**Warning signs:** CI step fails with `django.core.exceptions.ImproperlyConfigured: Set the AWS_SES_FROM_EMAIL environment variable`.

### Pitfall 4: Session Invalidation After Password Change

**What goes wrong:** After `user.set_password(new_password); user.save()`, the session's `_auth_user_hash` no longer matches the user's new password hash. On the next request, Django logs the user out silently. The redirect to `/admin/profile/` appears to work but the next page load hits the login wall.
**Why it happens:** Django session auth uses `get_session_auth_hash()` which is derived from the password hash. Changing the password invalidates the old hash.
**How to avoid:** Always call `update_session_auth_hash(request, user)` immediately after saving the user with the new password. From `django.contrib.auth`.

### Pitfall 5: Pre-commit `gitleaks` Blocking CI Secrets

**What goes wrong:** If stub secrets in the CI YAML file (e.g., `DJANGO_SECRET_KEY: ci-insecure-secret`) are detected by gitleaks as "real secrets", pre-commit step fails.
**Why it happens:** gitleaks uses entropy analysis and patterns to detect potential secrets.
**How to avoid:** Use obviously fake values like `ci-insecure-secret` or `ci-deploy-check-secret` — gitleaks recognises common test/CI key patterns. Do NOT use values that look like real AWS keys or Django production secrets. If gitleaks still flags it, use `--gitleaks-ignore` annotation comment on the specific line.

### Pitfall 6: Two-Form Page Re-render Loses Context

**What goes wrong:** When the name form fails validation and the view re-renders `profile.html`, the password form card renders with no bound form object — causing AttributeErrors in the template if it references `pw_form.errors` or similar.
**Why it happens:** The view only passes `name_form` when the name form fails. The template references both forms.
**How to avoid:** Always pass both forms to the template context. When only one form is active, pass the other as its unbound default:
```python
# In update_name_view on validation failure:
return render(request, "accounts/profile.html", {
    "name_form": form,          # bound, has errors
    "pw_form": PasswordChangeForm(),  # unbound, clean
})
```
The template guards `{% if name_form.errors %}` before rendering field errors.

### Pitfall 7: `update_fields` Must Include Timestamp

**What goes wrong:** `user.save(update_fields=["full_name"])` works but does not update `updated_at`, leading to a stale timestamp in the sidebar user display.
**Why it happens:** `update_fields` bypasses auto_now behavior for excluded fields unless `TimeStampedModel` uses `auto_now=True`.
**How to avoid:** Check `apps/common/models.py` for `TimeStampedModel`. If `updated_at` uses `auto_now=True`, Django updates it regardless of `update_fields`. If it uses a signal or pre-save hook, include it in `update_fields`. Confirm before writing the service.

## Code Examples

### Django `update_session_auth_hash` Usage

```python
# Source: Django docs https://docs.djangoproject.com/en/6.0/topics/auth/default/#django.contrib.auth.update_session_auth_hash
from django.contrib.auth import update_session_auth_hash

# After changing password and saving user:
user.set_password(new_password)
user.save()
update_session_auth_hash(request, user)  # keeps user logged in
messages.success(request, "Password updated.")
return redirect("profile")
```

### Django `check_password` Usage

```python
# Source: Django docs — AbstractBaseUser.check_password
if not user.check_password(current_password):
    raise ValueError("Current password is incorrect.")
```

### Alpine.js Strength Indicator (from `invite_accept.html` — copy verbatim)

```html
{# Attach to the form wrapper — binds 'pw', 'score', 'label', 'barClass' #}
x-data="{
    pw: '',
    get score() {
        let s = 0;
        if (this.pw.length >= 10) s++;
        if (/[A-Z]/.test(this.pw)) s++;
        if (/[0-9]/.test(this.pw)) s++;
        if (/[^A-Za-z0-9]/.test(this.pw)) s++;
        return s;
    },
    get label() { return ['Too short','Weak','Fair','Good','Strong'][this.score]; },
    get barClass() { return ['bg-line','bg-red','bg-amber','bg-yellow','bg-green'][this.score]; }
}"

{# Password input: #}
<input x-model="pw" :type="show ? 'text' : 'password'" ...>

{# Strength bars: #}
<div class="flex gap-1">
    <template x-for="i in 4" :key="i">
        <div class="h-1 rounded-full flex-1" :class="i <= score ? barClass : 'bg-line'"></div>
    </template>
</div>
<div class="mt-1 text-[12px] text-subtle text-right" x-text="label">&nbsp;</div>
```

### Show/Hide Toggle (from `invite_accept.html` — copy verbatim)

```html
{# Wrap the input in: #}
<div x-data="{ show: false }" class="relative">
    <input :type="show ? 'text' : 'password'" ...>
    <button type="button" tabindex="-1" @click="show = !show"
            class="absolute right-2 top-1/2 -translate-y-1/2 w-[30px] h-[30px] rounded-sm text-subtle hover:bg-line-soft flex items-center justify-center"
            :aria-label="show ? 'Hide password' : 'Show password'">
        <span class="w-4 h-4" aria-hidden="true" :data-lucide="show ? 'eye-off' : 'eye'" data-lucide="eye"></span>
    </button>
</div>
```

### ProfileNameForm

```python
# apps/accounts/forms.py (addition)
class ProfileNameForm(forms.Form):
    full_name = forms.CharField(
        min_length=2,
        max_length=100,
        strip=True,
        error_messages={
            "min_length": "Name must be at least 2 characters.",
            "max_length": "Name must be at most 100 characters.",
            "required": "Name is required.",
        },
    )
```

### PasswordChangeForm (custom, not Django's built-in)

```python
# apps/accounts/forms.py (addition)
class ProfilePasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Current password is required."},
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "New password is required."},
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        error_messages={"required": "Please confirm your new password."},
    )

    def clean_new_password(self) -> str:
        pw: str = self.cleaned_data["new_password"]
        try:
            validate_password(pw)
        except ValidationError as exc:
            raise forms.ValidationError(list(exc.messages)) from exc
        return pw

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned
```

**Note:** Do NOT use Django's built-in `PasswordChangeForm` — it expects a `user` argument at instantiation and has different field names (`old_password`, `new_password1`, `new_password2`). A custom form following the `ActivationForm` pattern is simpler and consistent.

### Security Settings to Add to production.py

```python
# config/settings/production.py — ADD these (not already present):
SECURE_BROWSER_XSS_FILTER = True     # X-XSS-Protection header
X_FRAME_OPTIONS = "DENY"             # Clickjacking protection (base.py has middleware, not the setting)

# ALREADY PRESENT (verified by reading production.py):
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SECURE_CONTENT_TYPE_NOSNIFF = True
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

**CSP note:** Django 6 includes `django.middleware.security.SecurityMiddleware` which enables basic security headers. Full CSP via `django.middleware.csp` requires `CSP_*` settings. For Phase 5, the CONTEXT.md specifies confirming `SecurityMiddleware` is in MIDDLEWARE (it is — verified in `base.py` line 31) and enabling CSP. A minimal permissive CSP that doesn't break Vite assets + CDN Alpine.js is needed. Research shows `manage.py check --deploy` will warn if CSP is not configured but won't fail.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install` in CI | `uv sync --frozen` | 2024 | 10x faster installs, reproducible lockfile |
| `actions/setup-python` + pip | `astral-sh/setup-uv` + uv | 2024 | Unified tool, no pip needed |
| Django's built-in `PasswordChangeForm` | Custom form following project `ActivationForm` pattern | Project decision | Consistent with existing form architecture |
| Polling for coverage | `--cov-fail-under=85` as a CI gate | Always | Hard fail rather than gradual drift |

**Not deprecated in this project:**
- `django-upgrade` target 5.1: The project intentionally uses 5.1 (not 6.0) because django-upgrade 1.22.2 does not support 6.0 as a target-version argument. **Do not change this.**
- `uv` version 0.4.29: Pinned in Dockerfile and Makefile — use same version in CI for consistency.

## Open Questions

1. **CSP middleware configuration scope**
   - What we know: `django.middleware.security.SecurityMiddleware` is in MIDDLEWARE. Django 6 supports `CSP_*` settings natively via this middleware.
   - What's unclear: The CONTEXT.md mentions "CSP middleware enabled" but doesn't specify CSP directives. A restrictive CSP could break Alpine.js CDN or Vite-loaded scripts.
   - Recommendation: Add a permissive initial CSP that allows `'self'` and `'unsafe-inline'` for scripts (Vite bundles inline scripts in dev mode). Log violations in report-only mode first. This is low risk given `check --deploy` won't fail on CSP gaps.

2. **`TimeStampedModel.updated_at` field type (auto_now vs default)**
   - What we know: `User` inherits from `TimeStampedModel` in `apps/common/models.py`. Service pattern uses `update_fields`.
   - What's unclear: Whether `updated_at` uses `auto_now=True` (auto-updates) or `auto_now_add=True` (set once) or a custom default.
   - Recommendation: Read `apps/common/models.py` before writing the service to determine if `updated_at` needs to be in `update_fields`.

3. **Profile URL redirect for Org Admins**
   - What we know: The sidebar and topbar are shared (with role-based nav items). Both link to `/profile/` which will move to `/admin/profile/`. Org Admins also have a profile link in their sidebar.
   - What's unclear: Phase 5 is Superadmin-only per CONTEXT.md. The `/admin/profile/` endpoint should check `@login_required` — but should it also check `IsSuperadmin`? If an Org Admin hits `/admin/profile/`, what happens?
   - Recommendation: The profile view should use `@login_required` only (not `@superadmin_required`). The URL prefix `/admin/` is a naming convention in this project, not DRF API — it doesn't enforce role. For now, allow any authenticated user to see and edit their own profile at `/admin/profile/` since the Org Admin phase is deferred. Add an `IsSuperadmin` guard only if CONTEXT.md explicitly requires it (it does not).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest apps/accounts/tests/ -x -q` |
| Full suite command | `uv run pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | GET /admin/profile/ renders profile page | view | `pytest apps/accounts/tests/test_views.py -k "profile" -x` | ❌ Wave 0 |
| PROF-01 | POST /admin/profile/update-name/ with valid name → redirect + toast | view | `pytest apps/accounts/tests/test_views.py -k "update_name" -x` | ❌ Wave 0 |
| PROF-01 | POST /admin/profile/update-name/ with invalid name → re-renders errors | view | `pytest apps/accounts/tests/test_views.py -k "update_name" -x` | ❌ Wave 0 |
| PROF-01 | update_profile_name() saves full_name correctly | unit | `pytest apps/accounts/tests/test_services.py -k "profile_name" -x` | ❌ Wave 0 |
| PROF-01 | Unauthenticated GET /admin/profile/ redirects to /login/ | view | `pytest apps/accounts/tests/test_views.py -k "profile_auth" -x` | ❌ Wave 0 |
| PROF-02 | POST /admin/profile/change-password/ with correct current password → success | view | `pytest apps/accounts/tests/test_views.py -k "change_password" -x` | ❌ Wave 0 |
| PROF-02 | POST /admin/profile/change-password/ with wrong current password → validation error | view | `pytest apps/accounts/tests/test_views.py -k "change_password" -x` | ❌ Wave 0 |
| PROF-02 | POST /admin/profile/change-password/ with mismatched passwords → validation error | view | `pytest apps/accounts/tests/test_views.py -k "change_password" -x` | ❌ Wave 0 |
| PROF-02 | Password change keeps session alive (update_session_auth_hash) | view | `pytest apps/accounts/tests/test_views.py -k "session_alive" -x` | ❌ Wave 0 |
| PROF-02 | change_password() service raises ValueError on wrong current password | unit | `pytest apps/accounts/tests/test_services.py -k "change_password" -x` | ❌ Wave 0 |
| CI | pytest --cov-fail-under=85 passes in CI | integration | `uv run pytest --cov=apps --cov-fail-under=85` | ❌ Wave 0 (file) |

### Sampling Rate

- **Per task commit:** `uv run pytest apps/accounts/tests/ -x -q`
- **Per wave merge:** `uv run pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/accounts/tests/test_services.py` — does not exist yet; covers PROF-01 and PROF-02 service functions
- [ ] `apps/accounts/services/__init__.py` — services directory does not exist
- [ ] `apps/accounts/services/profile.py` — profile service functions
- [ ] `.github/workflows/ci.yml` — CI workflow file
- [ ] `.github/workflows/` directory — does not exist

*(Existing `apps/accounts/tests/test_views.py` is the target for profile view tests — add to existing file.)*

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `apps/accounts/views.py`, `apps/accounts/urls.py`, `apps/accounts/forms.py`, `apps/accounts/models.py` — current state verified
- Direct codebase inspection: `config/settings/production.py` — security settings already present vs missing confirmed
- Direct codebase inspection: `templates/accounts/invite_accept.html` — Alpine.js strength indicator and show/hide patterns
- Direct codebase inspection: `templates/components/toasts.html` — Django messages seed script mechanism
- Direct codebase inspection: `.pre-commit-config.yaml` — existing hook configuration confirmed
- Direct codebase inspection: `pyproject.toml` — coverage config `fail_under = 85` confirmed
- Django 6 official docs: `update_session_auth_hash`, `check_password`, `messages` framework — standard API
- `.planning/STATE.md` — django-upgrade 5.1 decision locked

### Secondary (MEDIUM confidence)

- `astral-sh/setup-uv@v5` — GitHub Actions action for uv; current version at time of research (April 2026)
- `actions/checkout@v4` — current stable GitHub Actions checkout action

### Tertiary (LOW confidence)

- GitHub Actions postgres/redis service container configuration — from prior project knowledge; standard pattern, verify against current GHA docs if workflow fails

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies are existing project libraries; zero new additions
- Architecture: HIGH — patterns copied directly from existing, working project code
- Profile views: HIGH — Django pattern thoroughly understood, existing `ActivationForm` provides direct template
- CI workflow: MEDIUM — astral-sh/setup-uv version and exact GHA syntax may have minor updates; functional pattern is well established
- Security settings: HIGH — production.py read directly; missing settings identified with certainty
- Pitfalls: HIGH — derived from direct code inspection, not assumptions

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — stable Django patterns)
