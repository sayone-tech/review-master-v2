# Phase 2: Authentication - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Superadmin login, logout, and password recovery — every authenticated `/admin/*` page is
behind this gate. Creating users and the invitation/activation flow are separate phases.

Requirements: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05.

</domain>

<decisions>
## Implementation Decisions

### Login page design
- Centered white card (~400–480px wide) on Background Gray (`#FAFAFA`) canvas — no sidebar shell
- Logo + app name at the top of the card (above the form heading)
- Password field has show/hide toggle (Alpine.js, consistent with activation and reset forms)
- "Forgot password?" link is right-aligned inline next to the Password label (not below the button)
- Same centered-card template used for forgot-password and reset-password pages

### Login error & security
- Error message: generic "Invalid email or password" (does not reveal whether email exists)
- Error displayed as a top-of-form alert banner (red, above the form fields)
- Rate limiting: DRF throttle on the login endpoint — 10 attempts per 15 minutes per IP, backed by Redis; 429 response with a clear user-facing message on breach
- "Remember me" checkbox: present on the login form; when checked, session cookie persists for 30 days; when unchecked, session expires after 24 hours

### Password reset flow
- Use Django's built-in `PasswordResetView` / `PasswordResetDoneView` / `PasswordResetConfirmView` / `PasswordResetCompleteView` — Django handles HMAC token generation, 1-hour expiry, and single-use enforcement
- Forgot-password page always shows "Check your email" after submission (never confirms whether email exists)
- Password reset email sent via Amazon SES (`django-ses` backend) — template matches EMAL-03 spec
- New-password field on the reset page includes the Alpine.js strength indicator (consistent across reset, activation ACTV-02, and profile change PROF-02)
- After successful reset: redirect to `/login` with a success message ("Password updated. Please sign in.")

### Session & redirect policy
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & constraints
- `CLAUDE.md` — Full architectural constraints: services/selectors pattern, Redis usage (DB 1 for throttling), pre-commit hooks, settings structure. Single most important reference.
- `CLAUDE.md §7.5` — Rate limiting via DRF throttle classes backed by Redis DB 1; `DEFAULT_THROTTLE_RATES` config
- `CLAUDE.md §9` — Authentication & authorization: session auth, `AUTH_USER_MODEL`, `LOGIN_URL`, `LoginRequiredMixin` enforcement
- `CLAUDE.md §12` — Amazon SES via `django-ses`; `send_transactional_email` service in `apps/common/services/email.py`; EMAL-03 template spec
- `CLAUDE.md §19` — Security checklist: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`

### Requirements
- `.planning/REQUIREMENTS.md` — AUTH-01 through AUTH-05, EMAL-03; exact success criteria
- `docs/Requirements_Phase1_Superadmin.docx` — Original requirements document (v1.0, April 2026); contains design detail for auth pages

### Prior phase decisions
- `.planning/phases/01-foundation/01-CONTEXT.md` — Design system tokens, Alpine.js patterns, React vs template boundary, component patterns (show/hide toggle, strength indicator)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/accounts/models.py` — `User` model with `email` as `USERNAME_FIELD`, `role` enum, `is_active` boolean. Django auth backends will work with this directly.
- `templates/base.html` — Shell layout (sidebar + topbar). Auth pages must NOT extend this; they need a separate auth base template (no sidebar).
- `templates/components/` — Button, form input, badge components established in Phase 1; reuse for auth forms.
- `config/settings/base.py` — Redis cache at DB 0; DRF throttle via DB 1; `EMAIL_BACKEND = django_ses.SESBackend`.

### Established Patterns
- Alpine.js for all template interactivity (sidebar, dropdowns, toasts) — show/hide password toggle follows this pattern.
- Services/selectors pattern: any login-adjacent business logic (e.g., rate-limit check, session setup) goes in `apps/accounts/services/`.
- Brand tokens: primary yellow `#FACC15`, primary black `#0A0A0A`, background gray `#FAFAFA` — auth pages use same tokens.

### Integration Points
- `config/urls.py` — Auth URLs (`/login/`, `/logout/`, `/password-reset/`, etc.) need to be added here.
- `config/settings/base.py` — `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, `SESSION_COOKIE_AGE`, `SESSION_EXPIRE_AT_BROWSER_CLOSE` need to be set.
- `apps/accounts/` — Views, forms, and URL patterns live here.
- `apps/common/services/email.py` — Password reset email uses the `send_transactional_email` service; password reset template goes in `templates/emails/`.

</code_context>

<specifics>
## Specific Ideas

- Login card should feel like Linear's / Vercel's login — clean, minimal, centered, no clutter.
- "Forgot password?" link positioned inline (right-aligned) next to the Password label — matches the Gmail/Linear/Vercel pattern.
- Rate limit: 10 attempts / 15 min per IP. On breach: "Too many sign-in attempts. Please try again in 15 minutes."
- Password reset success: redirect to `/login` with a Django messages flash: "Your password has been updated. Please sign in."

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-authentication*
*Context gathered: 2026-04-22*
