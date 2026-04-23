---
phase: 04-invitation-and-activation
verified: 2026-04-23T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Send a real invitation email and click the link in a browser"
    expected: "Absolute URL opens the activation form with the correct organisation name, disabled email field, full name input, password + strength indicator, and 'Activate Account' button"
    why_human: "End-to-end email delivery and browser rendering of Alpine.js UI cannot be verified programmatically"
  - test: "Complete account activation by setting password, then log in to the resulting session"
    expected: "User is logged in and redirected to /admin/org-dashboard/ showing 'Welcome to {OrgName}' card"
    why_human: "Session establishment and redirect behaviour after Django login() call requires a live request cycle"
  - test: "Click the old invitation link after a Superadmin resend"
    expected: "Error page shows 'This invitation has already been used.' with no CTA"
    why_human: "Requires two real tokens and a real resend, verifiable only in a browser against a live DB"
  - test: "Open ResendInvitationModal in the browser, confirm resend"
    expected: "Success toast 'Invitation resent to {email}.' appears, modal closes, API call hits /api/v1/organisations/<pk>/resend-invitation/"
    why_human: "React toast rendering and modal close animation need a browser"
---

# Phase 4: Invitation and Activation — Verification Report

**Phase Goal:** Org Admins can receive an invitation email with a working activation link (absolute URL), set their password to activate their account, and Superadmins can resend the invitation. The invitation flow is end-to-end wired: backend token lifecycle, email templates, activation view, error pages, and React resend modal.

**Verified:** 2026-04-23
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /invite/accept/<token>/ resolves a valid token and renders the activation form | VERIFIED | `invite_accept_view` in `apps/accounts/views.py` (line 82); URL registered at `invite/accept/<str:token>/` in `apps/accounts/urls.py` (line 56); URL resolves to `/invite/accept/x/` confirmed by test `test_invite_accept_url_name_resolves` |
| 2 | Password is validated through Django AUTH_PASSWORD_VALIDATORS | VERIFIED | `ActivationForm.clean_password1()` calls `validate_password(pw)` from `django.contrib.auth.password_validation`; test `test_invite_accept_post_invalid_password_rerenders_form` confirms weak passwords are rejected |
| 3 | Successful POST activates account, logs in user, redirects to /admin/org-dashboard/ | VERIFIED | `invite_accept_view` POST branch: calls `activate_account()`, then `login(request, user)`, then `redirect(reverse("org_admin_dashboard"))`; URL `admin/org-dashboard/` registered in `apps/organisations/urls.py`; test `test_invite_accept_post_creates_user_and_logs_in` verifies user creation and `is_used=True` |
| 4 | Expired token shows ACTV-04 copy | VERIFIED | `ACTV04_COPY` = "This invitation link is invalid or has expired. Please contact your administrator to request a new one." rendered via `invite_error.html`; test `test_invite_accept_expired_token_shows_actv04` confirms |
| 5 | Used token shows ACTV-05 copy, is_used checked BEFORE is_expired | VERIFIED | Code at lines 102-104 of `views.py` checks `invitation.is_used` first, then `invitation.is_expired`; `ACTV05_COPY` = "This invitation has already been used."; test `test_invite_accept_used_and_expired_prefers_actv05` confirms a token that is both used AND expired shows ACTV-05 copy |
| 6 | Superadmin resend invalidates old tokens and sends is_resend email | VERIFIED | `resend_invitation()` service: `filter(is_used=False).update(is_used=True)` then creates new token; sends email with `is_resend=True` context; test `test_resend_invitation_endpoint_invalidates_existing_token` and `test_resend_invitation_sends_email_with_resend_marker` confirm |
| 7 | Resend endpoint returns 403 for non-Superadmin users | VERIFIED | `OrganisationViewSet` has `permission_classes = [IsAuthenticated, IsSuperadmin]`; test `test_resend_invitation_endpoint_org_admin_forbidden` asserts 403; test `test_resend_invitation_endpoint_anonymous_forbidden` asserts 403 |
| 8 | Invitation email sent with correct subject | VERIFIED | `create_organisation()` sends with subject `f"You're invited to manage {name}"`; `resend_invitation()` sends with same subject; test `test_resend_invitation_sends_email_with_resend_marker` asserts exact subject |
| 9 | Resend email contains "This replaces any previous invitation." | VERIFIED | `invitation.txt` line 8: `{% if is_resend %}This replaces any previous invitation.`; `invitation.html` lines 47-51: same conditional block; test `test_resend_invitation_sends_email_with_resend_marker` asserts text in both `.body` and `.alternatives[0][0]` |
| 10 | Email accept URL is absolute (starts with http:// or https://) | VERIFIED | `_build_accept_url()` uses `settings.SITE_URL` (set to `"http://localhost:8000"` by default); test `test_build_accept_url_returns_absolute_url` asserts `url.startswith("http://") or url.startswith("https://")`; test `test_create_organisation_invitation_email_contains_absolute_url` asserts `"http://localhost:8000/invite/accept/"` is in the email body |
| 11 | Both HTML and plain-text email templates exist for invitation | VERIFIED | `templates/emails/invitation.html` (full HTML with inline styles); `templates/emails/invitation.txt` (plain text); `send_transactional_email` wires both as `EmailMultiAlternatives`; test `test_resend_invitation_sends_email_with_resend_marker` asserts `m.alternatives` is present |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/accounts/forms.py` | ActivationForm class | VERIFIED | Substantive: full_name + password1 + password2 fields, `clean_password1` calls `validate_password`, `clean` checks password match |
| `apps/organisations/services/organisations.py` | `activate_account()` and `resend_invitation()` | VERIFIED | Both functions present and substantive; `activate_account` uses `select_for_update()` race guard; `resend_invitation` marks old tokens `is_used=True` atomically |
| `apps/accounts/views.py` | `invite_accept_view` function | VERIFIED | Full implementation: token lookup, is_used/is_expired checks in correct order, form handling, login+redirect on success |
| `apps/accounts/urls.py` | `invite/accept/<str:token>/` path | VERIFIED | Line 56: `path("invite/accept/<str:token>/", invite_accept_view, name="invite_accept")` |
| `templates/accounts/invite_accept.html` | Activation form template | VERIFIED | Extends auth_base.html; has email (disabled), full_name, password1+show/hide+strength indicator, password2, "Activate Account" submit button |
| `templates/accounts/invite_error.html` | Error card template | VERIFIED | Renders `{{ message }}` with centered card layout, no CTA links |
| `templates/emails/invitation.html` | HTML email with is_resend conditional | VERIFIED | `{% if is_resend %}` block at lines 47-53 containing "This replaces any previous invitation."; `{{ accept_url }}` rendered verbatim |
| `templates/emails/invitation.txt` | Plain-text email with is_resend conditional | VERIFIED | `{% if is_resend %}This replaces any previous invitation.` at line 8 |
| `config/settings/base.py` | SITE_URL setting | VERIFIED | Line 91: `SITE_URL = env("SITE_URL", default="http://localhost:8000")` |
| `apps/organisations/views.py` | `resend_invitation` @action on OrganisationViewSet | VERIFIED | `@action(detail=True, methods=["post"], url_path="resend-invitation")` at line 171; inherits `permission_classes = [IsAuthenticated, IsSuperadmin]` from viewset |
| `apps/organisations/urls.py` | `org_admin_dashboard` URL | VERIFIED | `path("admin/org-dashboard/", org_admin_dashboard, name="org_admin_dashboard")` |
| `templates/organisations/org_dashboard.html` | Stub Org Admin dashboard | VERIFIED | Extends `base_org.html`; "Welcome to {{ organisation.name }}" heading; "Your admin panel is being set up. Check back soon." |
| `frontend/src/widgets/org-management/api.ts` | `resendInvitation(id)` export | VERIFIED | `export async function resendInvitation(id: number): Promise<void>` — POSTs to `${BASE}${id}/resend-invitation/` |
| `frontend/src/widgets/org-management/ResendInvitationModal.tsx` | Modal component with variant="blue" | VERIFIED | Uses `ConfirmModal` with `variant="blue"`; calls `resendInvitation(org.id)`; emits success/error toasts; double-submit guard via `submitting` state |
| `frontend/src/widgets/org-management/ResendInvitationModal.test.tsx` | 7+ tests | VERIFIED | 136-line file with 7 tests covering: null org, modal display, confirm label, API call, success toast + onClose, error toast + no onClose, loading label, double-click guard |
| `frontend/src/entrypoints/org-management.tsx` | ResendInvitationModal mounted, onOpenResend wired | VERIFIED | `ResendInvitationModal` imported and rendered with `org={resendRow}`; `onOpenResend: (r) => setResendRow(r)` exposed on `window._orgModalHandlers`; no stub comments present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `invite_accept_view` | `activate_account()` | `from apps.organisations.services.organisations import activate_account` inside POST branch | WIRED | Lazy import at line 111 of views.py; called with invitation, full_name, password |
| `invite_accept_view` | `InvitationToken` | `InvitationToken.objects.select_related("organisation").get(token_hash=...)` | WIRED | Line 93 of views.py |
| `_build_accept_url` | `settings.SITE_URL` | `from django.conf import settings; base = settings.SITE_URL.rstrip("/")` | WIRED | Confirmed in services/organisations.py |
| `resend_invitation` service | `send_transactional_email` | `context={"is_resend": True, ...}` | WIRED | Confirmed in services/organisations.py |
| `OrganisationViewSet.resend_invitation` | `resend_invitation` service | lazy import inside action method | WIRED | Lines 179-180 of views.py |
| `ResendInvitationModal` | `resendInvitation` API call | `import { resendInvitation } from "./api"` | WIRED | Confirmed in ResendInvitationModal.tsx |
| `org-management.tsx` entrypoint | `ResendInvitationModal` | `import { ResendInvitationModal }` + `<ResendInvitationModal org={resendRow} onClose=.../>` | WIRED | Lines 9 and ~130 of org-management.tsx |
| `ViewOrgModal` | `onResend` handler | `onClick={() => onResend(org)}` on Resend button | WIRED | Line 49 of ViewOrgModal.tsx |
| `OrgTable` | `onOpenResend` handler | `onSelect: handlers.onOpenResend` at line 153 | WIRED | Confirmed in OrgTable.tsx |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ACTV-01 | 04-03 | GET /invite/accept/<token>/ resolves valid token, renders form | SATISFIED | `invite_accept_view` GET branch; test `test_invite_accept_valid_get_renders_form` |
| ACTV-02 | 04-03 | Password validation via AUTH_PASSWORD_VALIDATORS | SATISFIED | `ActivationForm.clean_password1()` calls `validate_password`; test confirms weak password rejection |
| ACTV-03 | 04-03 | POST activates account, logs in user, redirects to /admin/org-dashboard/ | SATISFIED | View POST: `activate_account()` + `login()` + `redirect(reverse("org_admin_dashboard"))`; test `test_invite_accept_post_creates_user_and_logs_in` |
| ACTV-04 | 04-03 | Expired token shows "This invitation has expired." copy; is_used checked BEFORE is_expired | SATISFIED | ACTV04_COPY constant; is_used check at line 102 precedes is_expired at line 104; dedicated test for both cases |
| ACTV-05 | 04-03 | Used token shows "This invitation has already been used." | SATISFIED | ACTV05_COPY constant; test `test_invite_accept_used_and_expired_prefers_actv05` |
| INVT-01 | 04-04 | Superadmin resend — old tokens invalidated, new token sent, is_resend copy included | SATISFIED | `resend_invitation()` service; test `test_resend_invitation_endpoint_invalidates_existing_token`; test `test_resend_invitation_sends_email_with_resend_marker` |
| INVT-02 | 04-04 | Resend endpoint requires Superadmin auth (403 for Org Admin) | SATISFIED | `IsSuperadmin` on viewset; tests for both anonymous (403) and org_admin (403) |
| EMAL-01 | 04-02 | Invitation email sent with correct subject | SATISFIED | Subject `f"You're invited to manage {name}"` in both `create_organisation` and `resend_invitation`; test asserts exact subject |
| EMAL-02 | 04-02 | Resend email contains "This replaces any previous invitation." | SATISFIED | `{% if is_resend %}` in both `.html` and `.txt` templates; test asserts text in HTML and plain-text bodies |
| EMAL-03 | 04-02 | Email accept URL is absolute (http://...) | SATISFIED | `_build_accept_url` uses `settings.SITE_URL`; test `test_build_accept_url_returns_absolute_url` and `test_create_organisation_invitation_email_contains_absolute_url` |
| EMAL-04 | 04-02 | Email templates have both HTML and plain-text versions | SATISFIED | `invitation.html` and `invitation.txt` both exist with `is_resend` conditionals; `send_transactional_email` sends `EmailMultiAlternatives` with both parts; test asserts `m.alternatives` present |

---

## Anti-Patterns Found

None detected. Grep scans across all Phase 4 files found:
- No TODO/FIXME/placeholder comments in key files
- No `return null` / empty handler implementations in the view or services
- No "Resend Invitation arrives in Phase 4." stub remaining in `org-management.tsx`
- No `console.log` debugging left in React components
- `is_used` checked before `is_expired` in `invite_accept_view` (correct order for ACTV-04/05)
- `select_for_update()` used in `activate_account()` to guard against double-submit race

---

## Human Verification Required

### 1. End-to-end invitation email delivery

**Test:** Create an organisation as Superadmin, check MailHog for the invitation email, click the activation link.
**Expected:** Browser opens `/invite/accept/<token>/` with "Welcome to {OrgName}", disabled email, full name input, password + strength bar, and "Activate Account" button.
**Why human:** Email delivery and Alpine.js interactive UI cannot be verified programmatically.

### 2. Full activation flow — login and redirect

**Test:** Fill in the activation form with a valid full name and strong password, submit.
**Expected:** User is logged in and redirected to `/admin/org-dashboard/` showing the "Welcome to {OrgName}" card. Superadmin redirect goes to `/admin/organisations/`.
**Why human:** Django session establishment and redirect after `login()` requires a live browser session.

### 3. Used-token error page after resend

**Test:** After a Superadmin resends the invitation, click the original (now invalidated) invitation link.
**Expected:** `/accounts/invite_error.html` renders with "This invitation has already been used." and no action button.
**Why human:** Requires two real tokens and a live database to verify the correct error path is shown.

### 4. ResendInvitationModal browser interaction

**Test:** In the org management table, click the "Resend Invitation" action on a pending org, confirm in the modal.
**Expected:** API call fires, success toast "Invitation resent to {email}." appears, modal closes. If API fails, error toast appears and modal stays open.
**Why human:** Toast animation, modal close transition, and button loading state need a real browser.

---

## Summary

Phase 4 goal is **fully achieved**. All 11 observable truths are verified against actual code:

- **Backend token lifecycle** is complete: `InvitationToken` model with `is_used`/`is_expired`, correct check ordering (ACTV-04 vs ACTV-05), `select_for_update()` race guard in `activate_account()`, atomic `resend_invitation()` that marks old tokens `is_used=True` before creating a new one.
- **Activation view** is fully wired: resolves token by hash, renders `invite_accept.html`, processes `ActivationForm`, calls service, logs in user, redirects to `org_admin_dashboard`.
- **Email infrastructure** is complete: `SITE_URL` setting drives absolute URLs, both HTML and plain-text templates have `{% if is_resend %}` conditionals, `send_transactional_email` sends both parts via `EmailMultiAlternatives`.
- **Resend endpoint** is DRF `@action` on `OrganisationViewSet` with inherited `IsSuperadmin` permission, returning 403 for non-Superadmins.
- **React modal** is fully wired: `ResendInvitationModal` calls `resendInvitation(org.id)`, emits toasts, has double-submit guard. `org-management.tsx` mounts it with `resendRow` state and exposes `onOpenResend` on `window._orgModalHandlers`. Old stub comment is gone.
- **Test coverage** is substantive: 10+ backend tests covering all ACTV/INVT/EMAL requirements, 7 Vitest tests for the React modal including success, failure, loading, and double-click guard paths.

Four items flagged for human verification are UI/UX and live-browser concerns — all automated checks pass.

---

_Verified: 2026-04-23_
_Verifier: Claude (gsd-verifier)_
