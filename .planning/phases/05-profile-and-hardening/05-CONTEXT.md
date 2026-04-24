# Phase 5: Profile and Hardening - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Superadmin can manage their own profile (name update, password change), and the project is production-ready with a GitHub Actions CI pipeline, finalized pre-commit config, and security headers in production settings. Test coverage of 85%+ enforced in CI on every PR. 85%+ coverage is already configured in `pyproject.toml` (`fail_under = 85`); this phase wires it into CI so it's actually enforced.

</domain>

<decisions>
## Implementation Decisions

### Profile page layout
- Two separate cards stacked vertically under `max-w-[640px]`
- Card 1 — **"Your profile"**: name (editable) + email (read-only) + role (read-only)
- Card 2 — **"Change password"**: current password + new password (with strength indicator) + confirm new password
- Both forms use full page POST — no HTMX, no partial updates

### Name edit UX
- Edit-on-click pattern: name displays as static text with an **Edit** button beside it
- Clicking Edit renders an `<input>` in place of the text, with **Save** and **Cancel** buttons
- Cancel reverts to original value (Alpine.js `x-data` holding the original, or server re-render)
- Save: `POST /admin/profile/update-name/` → redirect back to `/admin/profile` → success toast via `?toast=...` query param or standard session message
- Full page reload on success is acceptable

### Password change section
- Three fields: **Current password**, **New password**, **Confirm new password**
- Current password required — reject with validation error if wrong
- Alpine.js 4-bar strength indicator on **New password** field — reuse the exact pattern from `templates/accounts/invite_accept.html`
- Show/hide toggle on all three fields — reuse same pattern as existing auth templates
- Submit: `POST /admin/profile/change-password/` → on success, log user out (Django's `update_session_auth_hash` to keep them logged in) and show success toast
- Use Django's `check_password()` to validate current password server-side

### GitHub Actions CI
- Triggers: push to `main` + pull_request targeting `main`
- Steps in order:
  1. `pre-commit run --all-files`
  2. `mypy`
  3. `pytest --cov=apps --cov-fail-under=85`
  4. `python manage.py makemigrations --check --dry-run`
  5. `python manage.py check --deploy` (uses production settings)
- No deploy step in this phase — CI only

### Pre-commit config
- Add `.pre-commit-config.yaml` with hooks from CLAUDE.md §14 exactly:
  - `pre-commit-hooks` (trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files, debug-statements, detect-private-key)
  - `ruff-pre-commit` (ruff-check --fix, ruff-format)
  - `django-upgrade` (--target-version 5.1 — django-upgrade 1.22.2 does not support 6.0; STATE.md locks this at 5.1)
  - `mirrors-mypy` with django-stubs + drf-stubs
  - `bandit`
  - `djhtml` (djhtml + djcss)
  - `gitleaks`
  - Local hook: `missing-migrations` via `makemigrations --check --dry-run`

### Security settings hardening
- All additions go in `config/settings/production.py`
- Required settings:
  - `SECURE_SSL_REDIRECT = True`
  - `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`, `SECURE_HSTS_PRELOAD = True`
  - `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
  - `SECURE_BROWSER_XSS_FILTER = True`
  - `SECURE_CONTENT_TYPE_NOSNIFF = True`
  - `X_FRAME_OPTIONS = "DENY"`
  - `ALLOWED_HOSTS` read from env (already should exist — confirm it does)
  - Minimal permissive CSP: add `django-csp` (or Django 6 built-in SecurityMiddleware CSP config) with `CSP_DEFAULT_SRC = ("'self'",)` and `CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")` to avoid breaking Vite-bundled assets
- `manage.py check --deploy` step in CI catches future regressions

### Claude's Discretion
- Exact Alpine.js code for the name Edit/Cancel toggle (follow the established show/hide pattern)
- Session message vs query-param toast delivery mechanism for success toasts
- URL structure for the two profile POST endpoints (can be one view with action discrimination or two separate views)
- Ruff `pyproject.toml` config (already exists — check before adding)

</decisions>

<specifics>
## Specific Ideas

- Strength indicator and show/hide: copy exact Alpine.js pattern from `templates/accounts/invite_accept.html` — don't reinvent
- `update_session_auth_hash(request, user)` must be called after password change to keep the session alive (Django built-in)
- CI `check --deploy` step must use `DJANGO_SETTINGS_MODULE=config.settings.production` with enough env vars stubbed so it doesn't crash on missing secrets

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Profile forms and views
- `templates/accounts/profile.html` — existing read-only profile stub that this phase extends
- `apps/accounts/views.py` — profile view stub at line ~24; name-update and password-change views go in this file
- `config/urls.py` + `apps/accounts/urls.py` — URL wiring for the two new POST endpoints

### Alpine.js patterns to reuse
- `templates/accounts/invite_accept.html` — canonical source for 4-bar strength indicator AND show/hide toggle pattern; copy verbatim into password change card

### CI/CD spec
- `CLAUDE.md §16` — GitHub Actions workflow requirements (ci.yml steps, deploy.yml structure)
- `CLAUDE.md §14` — Full pre-commit config with exact hook revisions and ruff/mypy config

### Security settings
- `CLAUDE.md §19` — Security checklist; every item there is a target for production.py
- `config/settings/production.py` — Existing production settings file; add secure headers here

### Coverage enforcement
- `pyproject.toml` — Already has `[tool.coverage.report] fail_under = 85`; CI just needs to pass `--cov-fail-under=85` to pytest

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `templates/accounts/invite_accept.html`: Alpine.js 4-bar strength indicator + show/hide toggle — copy directly into password change card template
- `apps/accounts/forms.py` `ActivationForm`: Has password1/password2 with Django validators — similar structure needed for password change form
- Toast system: `app:toast` CustomEvent `{ kind, title, msg }` — available but profile pages use Django template flow (full page POST), so success toasts should use Django messages framework or redirect-with-toast convention

### Established Patterns
- Services/selectors pattern: name update and password change logic go in `apps/accounts/services/` (e.g., `update_profile_name()`, `change_password()`)
- Full page POST + redirect: consistent with how the rest of the Django template pages work in this project
- `@transaction.atomic` on any service that touches the User model

### Integration Points
- `apps/accounts/views.py` `profile_view` (stub) — expand to handle GET and delegate POST to two new views
- `apps/accounts/urls.py` — add two new URL patterns for name update and password change
- `config/settings/production.py` — add security headers; must not break the existing settings structure

</code_context>

<deferred>
## Deferred Ideas

- Password reset / forgot password — already implemented in Phase 2
- Deploy workflow (`.github/workflows/deploy.yml`) — out of scope for this phase (CI only)
- HTMX partial name update — not worth the complexity for a single field
- Org Admin profile page — only Superadmin profile is in scope; Org Admin gets their own phase or backlog item

</deferred>

---

*Phase: 05-profile-and-hardening*
*Context gathered: 2026-04-24*
