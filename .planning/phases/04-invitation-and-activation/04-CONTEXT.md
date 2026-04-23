# Phase 4: Invitation and Activation - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admin recipients accept invitations and activate their accounts via a secure, time-limited token link. Superadmins can resend invitations when needed. All transactional email templates (invitation, resend, password reset) are finalized for cross-client rendering compliance (EMAL-04). A stub Org Admin dashboard is built as the post-activation landing page.

Requirements: INVT-01, INVT-02, ACTV-01, ACTV-02, ACTV-03, ACTV-04, ACTV-05, EMAL-01, EMAL-02, EMAL-03, EMAL-04.

The Org Admin full dashboard (stores, reviews, analytics) is Phase 5+. This phase builds only the authentication/activation path and the stub landing page.

</domain>

<decisions>
## Implementation Decisions

### Post-activation redirect
- After successful activation, Org Admin is logged in and redirected to a new stub Org Admin dashboard at `/admin/org-dashboard/` (or equivalent role-gated URL).
- Dashboard stub shows a white card with "Welcome to {OrganisationName}" heading + brief copy: "Your admin panel is being set up. Check back soon."
- The stub page has its own **separate Org Admin sidebar** — distinct from the Superadmin sidebar. Even as a placeholder, it establishes the correct role-based layout boundary that Phase 5 will fill in.
- The Org Admin sidebar nav can be minimal (e.g., a single "Dashboard" item) — the important thing is the sidebar renders and is role-scoped.

### Activation page design
- Follows the **centered white card, no sidebar** pattern established in Phase 2 for auth pages (login, password reset).
- Above-form content: heading "Welcome to {OrganisationName}" + one line of subtext: "Set up your account to start managing your reviews."
- Form fields (per ACTV-02, already locked): pre-filled disabled email, Full Name (required 2–100 chars), Password with Alpine.js show/hide toggle and strength indicator, Confirm Password.
- Submit button label: **"Activate Account"**.
- Password strength indicator: Alpine.js, same pattern as Phase 2's password reset and the future PROF-02 — consistent across all password-setting screens.

### Token error pages
- Invalid/expired token (ACTV-04): full-page centered card, **error message only, no CTA**. Copy (locked by requirements): "This invitation link is invalid or has expired. Please contact your administrator to request a new one."
- Already-used token (ACTV-05): same page style, **no CTA**. Copy: "This invitation has already been used."
- Both error pages: same centered-card, no-sidebar treatment as the activation form page.

### Resend invitation — token invalidation
- When Superadmin resends: **mark the previous `InvitationToken.is_used = True`** (not delete, not expire). Preserves audit trail.
- If the recipient clicks the old link after resend, they see ACTV-05: "This invitation has already been used." (accurate and clear).
- A new `InvitationToken` is created with a fresh 48-hour expiry and a new `raw_token`.

### Resend invitation — UX flow
- **Confirmation popup** (React modal, consistent with existing modal patterns):
  - Body: "Resend invitation to **{email}** for **{OrgName}**? The previous invitation link will be invalidated."
  - Confirm button: "Resend Invitation" (primary yellow)
  - Cancel button: "Cancel" (secondary)
- **After confirmation**: modal closes + success toast: "Invitation resent to {email}."
- No table refresh required — `activation_status` remains "pending"; only `last_invited_at` changes which is not displayed in the table.
- "Resend Invitation" action visible when `activation_status !== 'active'` — already implemented in frontend stubs (`OrgTable.tsx` and `ViewOrgModal.tsx`). Phase 4 wires the real handler.

### Email — absolute URLs
- Add `SITE_URL = env("SITE_URL", default="http://localhost:8000")` to `config/settings/base.py`.
- `_build_accept_url(raw_token)` in `apps/organisations/services/organisations.py` updated to: `f"{settings.SITE_URL}/invite/accept/{raw_token}/"`.
- This is the single change needed — the template already renders `{{ accept_url }}` verbatim.

### Email — CSS inlining
- **No premailer** — existing `invitation.html` and `password_reset.html` already use fully inline styles throughout. Continue this pattern for all Phase 4 templates.
- The STATE.md note "premailer deferred to Phase 4" is resolved: manually inlined styles already satisfy EMAL-04. No tooling change needed.

### Email — resend invitation template
- **Same template as original** (`emails/invitation.html` and `emails/invitation.txt`) with an `is_resend` context variable.
- When `is_resend=True`, a note is added: "This replaces any previous invitation."
  - HTML: `{% if is_resend %}<p style="...">This replaces any previous invitation.</p>{% endif %}`
  - TXT: `{% if is_resend %}This replaces any previous invitation.\n\n{% endif %}`
- `send_transactional_email` called with `context={"is_resend": True, ...}` for resend flow.

### Claude's Discretion
- Exact styling of the stub Org Admin sidebar (nav item spacing, icon choice)
- Exact copy of "Your admin panel is being set up" subtext (minor wording variations OK)
- URL pattern for the Org Admin dashboard stub (e.g., `/admin/org-dashboard/` vs `/org/dashboard/`)
- Loading state on the "Activate Account" button during form submission
- Whether the new token and resend service are unit-tested at service level or only at view level

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & constraints
- `CLAUDE.md` — Full architectural constraints: services/selectors pattern (§5), DRF conventions (§8), session auth (§9), Amazon SES via django-ses (§12), security checklist (§19), pre-commit hooks (§14).
- `CLAUDE.md §12` — `send_transactional_email` service in `apps/common/services/email.py`; SES backend; template rendering pattern; email template location under `templates/emails/`.
- `CLAUDE.md §9` — Authentication: `AUTH_USER_MODEL`, `login()` after activation, `LoginRequiredMixin`, `LOGIN_REDIRECT_URL`.

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 4 requirements: INVT-01, INVT-02, ACTV-01 through ACTV-05, EMAL-01 through EMAL-04. Exact copy for error messages and success toasts is specified here.

### Prior phase decisions
- `.planning/phases/02-authentication/02-CONTEXT.md` — Centered card auth page pattern, Alpine.js show/hide toggle, strength indicator, password-related UX conventions that carry forward to activation form.
- `.planning/phases/03-organisation-management/03-CONTEXT.md` — React modal patterns (focus trap, ARIA, confirmation popup structure), `activation_status` serializer field, frontend stubs for resend.

### Existing code (Phase 4 must read before modifying)
- `apps/accounts/models.py` — `InvitationToken` model: `is_used`, `expires_at`, `invited_user`, `token_hash`, `is_expired` property, `hash_token()` classmethod.
- `apps/organisations/services/organisations.py` — `create_organisation`, `_build_accept_url` (stub returning relative path — Phase 4 upgrades to absolute URL using `settings.SITE_URL`).
- `apps/common/services/email.py` — `send_transactional_email` service; already wired to SES backend.
- `templates/emails/invitation.html` + `templates/emails/invitation.txt` — Existing invitation email templates; Phase 4 adds `is_resend` conditional block.
- `templates/emails/password_reset.html` + `templates/emails/password_reset.txt` — Password reset email templates (already complete from Phase 2; EMAL-03 may just need verification).
- `frontend/src/entrypoints/org-management.tsx` — `onOpenResend` stub (line ~82): "Resend Invitation arrives in Phase 4." — Phase 4 wires real handler.
- `frontend/src/widgets/org-management/ViewOrgModal.tsx` — "Resend Invitation" button already rendered when `activation_status !== 'active'`.
- `frontend/src/widgets/org-management/OrgTable.tsx` — "Resend Invitation" row action already conditionally visible.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `InvitationToken` model: fully built with `is_used`, `expires_at`, `hash_token()`, `is_expired`. No schema changes needed.
- `send_transactional_email`: ready; just needs `is_resend` flag added to invitation context.
- `invitation.html/txt`: existing templates need only the `{% if is_resend %}` block added.
- `password_reset.html/txt`: already complete from Phase 2 — likely just needs EMAL-03 compliance verification.
- `activation_status_for()` selector: already returns "pending" | "active" | "expired" per org.
- Frontend `onOpenResend` stubs: in place in `org-management.tsx`, `OrgTable.tsx`, `ViewOrgModal.tsx` — Phase 4 replaces stub behavior with a real `ResendInvitationModal` component.
- Phase 2 password reset form: show/hide toggle + strength indicator pattern established in Alpine.js — activation form reuses this pattern.

### Established Patterns
- Services/selectors: resend invitation logic → `apps/organisations/services/organisations.py` (or `apps/accounts/services/invitations.py` if separated).
- React confirmation modals: follow the `ConfirmModal` pattern established in Phase 3 (enable/disable/delete/store allocation). `ResendInvitationModal` follows the same structure.
- Auth page template: extends a no-sidebar base (not `base.html`) — activation page follows this. New `base_auth.html` or existing pattern from Phase 2.
- Org admin dashboard: new Django template view at `/admin/org-dashboard/` protected by `login_required` + role check for `ORG_ADMIN`.

### Integration Points
- `apps/accounts/urls.py` — Add `path("invite/accept/<str:token>/", invite_accept_view, name="invite_accept")`.
- `apps/organisations/views.py` or `apps/accounts/views.py` — New `invite_accept` view (public, token-gated, no `@login_required`).
- `config/urls.py` — Register the activation URL. Also add Org Admin dashboard URL.
- `config/settings/base.py` — Add `SITE_URL = env("SITE_URL", default="http://localhost:8000")`.
- `apps/organisations/services/organisations.py` — Update `_build_accept_url` + add `resend_invitation` service function.
- Frontend: `org-management.tsx` → replace `onOpenResend` stub with real modal dispatch; add `ResendInvitationModal` component.

</code_context>

<specifics>
## Specific Ideas

- "Resend Invitation" confirmation modal body: "Resend invitation to **{email}** for **{OrgName}**? The previous invitation link will be invalidated." — confirm as "Resend Invitation" (yellow primary), cancel as "Cancel" (secondary).
- Success toast after resend: "Invitation resent to {email}."
- Activation page submit button: "Activate Account" (not "Register", not "Sign Up").
- Post-activation redirect to stub Org Admin dashboard at a role-gated URL.
- Error pages: no CTA — just the exact copy from REQUIREMENTS.md. No button, no link.
- `is_resend` template variable added to invitation.html/txt for the "This replaces any previous invitation." note per EMAL-02.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 4 scope.

</deferred>

---

*Phase: 04-invitation-and-activation*
*Context gathered: 2026-04-23*
