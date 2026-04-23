# Phase 4: Invitation and Activation — Research

**Researched:** 2026-04-23
**Domain:** Django secure token flows, Alpine.js form UX, React confirmation modals, Amazon SES email templates
**Confidence:** HIGH — all findings drawn from reading existing codebase directly; no speculative library choices

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Post-activation redirect:** Org Admin redirected to `/admin/org-dashboard/` (or equivalent role-gated URL). Dashboard stub shows white card: "Welcome to {OrganisationName}" heading + "Your admin panel is being set up. Check back soon." Stub has its own **Org Admin sidebar** separate from Superadmin sidebar.
- **Activation page design:** Centered white card, no sidebar (`auth_base.html` pattern from Phase 2). Heading: "Welcome to {OrganisationName}". Subtext: "Set up your account to start managing your reviews." Fields: pre-filled disabled email, Full Name (2–100 chars), Password (Alpine.js show/hide + strength indicator same as `password_reset_confirm.html`), Confirm Password. Submit: "Activate Account".
- **Token error pages:** Full-page centered card, no CTA, no sidebar.
  - Invalid/expired (ACTV-04): "This invitation link is invalid or has expired. Please contact your administrator to request a new one."
  - Already-used (ACTV-05): "This invitation has already been used."
- **Resend — token invalidation:** Mark previous `InvitationToken.is_used = True` (not delete). Preserves audit trail. Old link shows ACTV-05 after resend.
- **Resend — UX:** React confirmation modal (`ResendInvitationModal`) following `ConfirmModal` pattern. Body: "Resend invitation to **{email}** for **{OrgName}**? The previous invitation link will be invalidated." Confirm: "Resend Invitation" (yellow primary). Cancel: "Cancel". Success toast: "Invitation resent to {email}." No table refresh — `activation_status` stays "pending".
- **Email absolute URLs:** Add `SITE_URL = env("SITE_URL", default="http://localhost:8000")` to `config/settings/base.py`. Update `_build_accept_url` to `f"{settings.SITE_URL}/invite/accept/{raw_token}/"`.
- **Email CSS inlining:** No premailer. Existing templates already use fully inline styles. Continue this pattern. The "premailer deferred to Phase 4" STATE.md note is resolved — no tooling change needed.
- **Resend email template:** Same `emails/invitation.html` / `emails/invitation.txt` with `is_resend` context variable adding: "This replaces any previous invitation."

### Claude's Discretion

- Exact styling of the stub Org Admin sidebar (nav item spacing, icon choice)
- Exact copy of "Your admin panel is being set up" subtext (minor wording variations OK)
- URL pattern for Org Admin dashboard stub (`/admin/org-dashboard/` vs `/org/dashboard/`)
- Loading state on "Activate Account" button during form submission
- Whether new token and resend service are unit-tested at service level or only at view level

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 4 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INVT-01 | Superadmin can resend invitation (confirmation popup, invalidates previous token, success toast) | `resend_invitation` service + `ResendInvitationModal` React component + new DRF action |
| INVT-02 | Resend action visible only when org admin not yet activated | Already wired in `OrgTable.tsx` and `ViewOrgModal.tsx` — just replace `onOpenResend` stub |
| ACTV-01 | `/invite/accept/<token>/` — public, no sidebar, token-gated | New view + URL, extends `auth_base.html` |
| ACTV-02 | Activation form: pre-filled disabled email, Full Name, Password+strength, Confirm Password | Alpine.js pattern from `password_reset_confirm.html` reused verbatim |
| ACTV-03 | On success: token marked used, user created+linked to org, activation status → Active, user logged in | `activate_account` service wrapping `transaction.atomic` + `login()` |
| ACTV-04 | Invalid/expired token error page | View branches on `InvitationToken.is_expired` or DoesNotExist |
| ACTV-05 | Already-used token error page | View branches on `token.is_used` |
| EMAL-01 | Invitation email on org create (subject, HTML+txt, 48h expiry notice, Accept CTA, SES headers) | Already wired — `_build_accept_url` needs absolute URL fix only |
| EMAL-02 | Resend email adds "This replaces any previous invitation" note | `{% if is_resend %}` block in existing templates |
| EMAL-03 | Password reset email (subject, 1h link, plain-text, security copy) | Already complete from Phase 2 — verification only |
| EMAL-04 | All emails: Gmail/Outlook/Apple Mail compatible, max 600px, CSS inlined, plain-text fallback | Existing templates already inline all CSS — verify and confirm |
</phase_requirements>

---

## Summary

Phase 4 completes the Org Admin onboarding loop that was partially built across Phases 1–3. The `InvitationToken` model is fully implemented. The `send_transactional_email` service is wired to SES. The React frontend stubs for resend are in place (`onOpenResend` currently emits an info toast). What remains is: (1) a public Django view that validates the raw token and renders the activation form or an error card, (2) an `activate_account` service that atomically creates the user and marks the token used, (3) a `resend_invitation` service + DRF custom action, (4) a `ResendInvitationModal` React component wired into `org-management.tsx`, and (5) a minimal stub Org Admin dashboard with its own sidebar layout.

All the hard infrastructure work is done. Phase 4 is primarily glue: connecting the existing token model to real views, and wiring the frontend stubs to real API endpoints. The highest-risk area is the token lookup and validation logic in the view — specifically covering the three distinct states (valid, expired, used) cleanly in a single public view with no authentication requirement.

**Primary recommendation:** Implement the activation view as a plain Django function view (not a class-based view), branching on three token states at the top, to keep the logic easy to read and test. Use `transaction.atomic` in `activate_account` to ensure user creation and token marking happen together.

---

## Standard Stack

### Core — all already installed; no new packages needed

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.x | Token validation view, form handling, `login()` | Project-wide |
| `django.contrib.auth.login` | built-in | Log user in after activation, sets session | CLAUDE.md §9 — session auth |
| `secrets.token_urlsafe(32)` | stdlib | Generate new raw tokens for resend | Already used in `create_organisation` |
| `hashlib.sha256` | stdlib | `InvitationToken.hash_token()` already uses this | Established in Phase 1 |
| DRF `@action` decorator | installed | Resend endpoint on `OrganisationViewSet` | Follows existing PATCH/DELETE pattern |
| Alpine.js | bundled via Vite | Show/hide toggle + strength indicator on activation form | Already used in `password_reset_confirm.html` |
| React 18 + `ConfirmModal` | installed | `ResendInvitationModal` — same as `DisableConfirmModal` | Established in Phase 3 |
| `django.test.Client` + `pytest-django` | installed | All tests | CLAUDE.md §13 |

### No new dependencies required

Phase 4 introduces zero new packages. Every required library is already installed and used in earlier phases.

**Installation:** nothing to run.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
apps/
├── accounts/
│   ├── views.py              # add invite_accept_view function
│   ├── forms.py              # add ActivationForm (Full Name + Password + Confirm)
│   ├── urls.py               # add path("invite/accept/<str:token>/", ...)
│   └── tests/
│       └── test_views.py     # ACTV-01 through ACTV-05 tests
│
├── organisations/
│   ├── services/
│   │   └── organisations.py  # add resend_invitation(), update _build_accept_url()
│   ├── views.py              # add @action resend + org_admin_dashboard stub view
│   ├── urls.py               # add path("admin/org-dashboard/", ...)
│   └── tests/
│       └── test_services.py  # resend_invitation service tests
│
templates/
├── accounts/
│   ├── invite_accept.html    # activation form (extends auth_base.html)
│   └── invite_error.html     # error card (extends auth_base.html)
├── organisations/
│   └── org_dashboard.html    # stub dashboard (extends org_base.html or base_org.html)
└── (new) base_org.html       # Org Admin sidebar base template
│
emails/
│   # invitation.html + invitation.txt — add {% if is_resend %} block only
│
frontend/src/
└── widgets/org-management/
    └── ResendInvitationModal.tsx   # new, follows DisableConfirmModal.tsx pattern
```

### Pattern 1: Three-State Token Validation in a Single View

**What:** Public view at `/invite/accept/<str:token>/` looks up the token hash, then branches into three paths: invalid/expired → error template; already used → error template; valid → render activation form or process POST.

**When to use:** Any time a single public URL must serve multiple non-authenticated states.

**Example (from codebase patterns + ACTV-01 through ACTV-05):**

```python
# apps/accounts/views.py
from django.shortcuts import render
from django.contrib.auth import login
from apps.accounts.models import InvitationToken
from apps.accounts.forms import ActivationForm
from apps.organisations.services.organisations import activate_account

def invite_accept_view(request, token: str):
    token_hash = InvitationToken.hash_token(token)
    try:
        invitation = InvitationToken.objects.select_related("organisation").get(
            token_hash=token_hash
        )
    except InvitationToken.DoesNotExist:
        return render(request, "accounts/invite_error.html", {
            "message": "This invitation link is invalid or has expired. "
                       "Please contact your administrator to request a new one."
        })

    if invitation.is_used:
        return render(request, "accounts/invite_error.html", {
            "message": "This invitation has already been used."
        })

    if invitation.is_expired:
        return render(request, "accounts/invite_error.html", {
            "message": "This invitation link is invalid or has expired. "
                       "Please contact your administrator to request a new one."
        })

    org = invitation.organisation
    if request.method == "POST":
        form = ActivationForm(request.POST)
        if form.is_valid():
            user = activate_account(
                invitation=invitation,
                full_name=form.cleaned_data["full_name"],
                password=form.cleaned_data["password1"],
            )
            login(request, user)
            return redirect("org_dashboard")
    else:
        form = ActivationForm()

    return render(request, "accounts/invite_accept.html", {
        "form": form,
        "organisation": org,
        "email": org.email,
    })
```

**Critical detail:** `is_used` must be checked BEFORE `is_expired`. A used token might also be past its expiry date — the "already used" message is more accurate for audit trail clarity (locked by CONTEXT.md).

### Pattern 2: activate_account Service

**What:** Atomic service that creates the Org Admin user, links them to the org, marks the token used, and returns the user.

```python
# apps/organisations/services/organisations.py
@transaction.atomic
def activate_account(
    *,
    invitation: InvitationToken,
    full_name: str,
    password: str,
) -> User:
    """Creates Org Admin user, marks token used. Raises if token is already used (race guard)."""
    from apps.accounts.models import User
    # Re-fetch with select_for_update to guard against race conditions
    invitation = InvitationToken.objects.select_for_update().get(pk=invitation.pk)
    if invitation.is_used:
        raise ValidationError("Invitation already used.")
    user = User.objects.create_user(
        email=invitation.organisation.email,
        full_name=full_name,
        password=password,
        role=User.Role.ORG_ADMIN,
        organisation=invitation.organisation,
    )
    invitation.invited_user = user
    invitation.is_used = True
    invitation.save(update_fields=["invited_user", "is_used", "updated_at"])
    return user
```

**Key insight:** `select_for_update()` inside the atomic block prevents a double-submit race condition from creating two users.

### Pattern 3: resend_invitation Service

**What:** Marks the existing non-used token as used, creates a new token, sends the invitation email with `is_resend=True`.

```python
# apps/organisations/services/organisations.py
@transaction.atomic
def resend_invitation(*, organisation: Organisation, resent_by: User) -> str:
    """Invalidates all pending tokens, creates new 48h token, sends resend email."""
    # Mark all existing non-used tokens as used (preserves audit trail per CONTEXT.md)
    organisation.invitation_tokens.filter(is_used=False).update(is_used=True)
    raw_token = secrets.token_urlsafe(32)
    InvitationToken.objects.create(
        organisation=organisation,
        token_hash=InvitationToken.hash_token(raw_token),
    )
    send_transactional_email(
        to=[organisation.email],
        subject=f"You're invited to manage {organisation.name}",
        template_base="emails/invitation",
        context={
            "organisation": organisation,
            "accept_url": _build_accept_url(raw_token),
            "expires_in_hours": 48,
            "is_resend": True,
        },
        tags=["invitation", "resend"],
    )
    return raw_token
```

### Pattern 4: ResendInvitationModal (React)

**What:** Follows the exact same structure as `DisableConfirmModal.tsx` — uses `ConfirmModal`, calls a new `resendInvitation(id)` API function, emits a toast, calls `onClose()`. Does NOT call `onDone` with a refresh because `activation_status` remains "pending" and `last_invited_at` is not displayed in the table.

```typescript
// frontend/src/widgets/org-management/ResendInvitationModal.tsx
import { useState } from "react";
import { ConfirmModal } from "../modal";
import { resendInvitation, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
}

export function ResendInvitationModal({ org, onClose }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!org || submitting) return;
    setSubmitting(true);
    try {
      await resendInvitation(org.id);
      emitToast({ kind: "success", title: `Invitation resent to ${org.email}.` });
      onClose();
    } catch (err) {
      void (err instanceof ApiError);
      emitToast({ kind: "error", title: "Something went wrong.", msg: "Please try again." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ConfirmModal
      open={org !== null}
      onClose={onClose}
      onConfirm={handleConfirm}
      variant="default"   // yellow primary confirm button
      title="Resend Invitation"
      message={
        <>
          Resend invitation to <strong>{org?.email}</strong> for{" "}
          <strong>{org?.name}</strong>? The previous invitation link will be
          invalidated.
        </>
      }
      confirmLabel={submitting ? "Sending…" : "Resend Invitation"}
    />
  );
}
```

**Wire-up in `org-management.tsx`:** Add `resendRow` state, add `ResendInvitationModal`, replace `onOpenResend` stub with `(r) => setResendRow(r)`.

### Pattern 5: DRF Custom Action for Resend

**What:** `@action(detail=True, methods=["post"])` on `OrganisationViewSet` at `/api/v1/organisations/{id}/resend_invitation/`.

```python
# apps/organisations/views.py
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.organisations.services.organisations import resend_invitation

class OrganisationViewSet(viewsets.ModelViewSet[Organisation]):
    # ... existing code ...

    @action(detail=True, methods=["post"], url_path="resend-invitation")
    def resend_invitation(self, request, pk=None):
        org = self.get_object()  # applies IsSuperadmin permission
        resend_invitation(organisation=org, resent_by=request.user)
        return Response({"detail": "Invitation resent."}, status=200)
```

**Permission:** `get_object()` already applies the viewset's `[IsAuthenticated, IsSuperadmin]` permission classes — no extra guard needed.

### Pattern 6: ActivationForm (Django Form)

**What:** Standard Django `Form` with `full_name`, `password1`, `password2` fields. Reuse Django's built-in `SetPasswordForm`-style validation rather than re-implementing password validators.

```python
# apps/accounts/forms.py (add to existing file)
from django import forms
from django.contrib.auth.password_validation import validate_password

class ActivationForm(forms.Form):
    full_name = forms.CharField(min_length=2, max_length=100)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_password1(self):
        pw = self.cleaned_data["password1"]
        validate_password(pw)   # runs AUTH_PASSWORD_VALIDATORS
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned
```

### Pattern 7: Org Admin Sidebar Base Template

**What:** New `base_org.html` that mirrors `base.html`'s shell structure but uses a role-scoped sidebar. The existing `base.html` uses `partials/shell_open.html` which includes the Superadmin nav. The Org Admin base needs its own sidebar partial.

```
templates/
├── base.html               # Superadmin — uses partials/shell_open.html
├── base_org.html           # Org Admin — uses partials/shell_org_open.html (new)
├── auth_base.html          # No sidebar — activation page extends this
└── partials/
    ├── shell_open.html     # Superadmin sidebar
    └── shell_org_open.html # Org Admin sidebar (new, minimal: "Dashboard" nav item)
```

The stub dashboard template: `{% extends "base_org.html" %}`.

### Anti-Patterns to Avoid

- **Do not delete InvitationToken on resend** — mark `is_used=True` to preserve the audit trail. Old link correctly shows ACTV-05 "already used" (CONTEXT.md locked).
- **Do not check `is_expired` before `is_used`** — a used-and-expired token should show "already used", not "expired".
- **Do not put activation logic in the view** — service function with `transaction.atomic` and `select_for_update`.
- **Do not add `@login_required` to `invite_accept_view`** — it's a public endpoint (ACTV-01).
- **Do not use `update()` on `invitation.is_used`** — use `save(update_fields=...)` after setting `invited_user` FK so both fields change atomically.
- **Do not use a new React entrypoint for ResendInvitationModal** — mount it inside existing `OrgModals` in `org-management.tsx`.
- **Do not call `onDone()` (table refresh) after resend confirm** — `activation_status` stays "pending" and `last_invited_at` is not in the table columns, so a refresh is wasted.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password validation | Custom regex checks | `validate_password(pw)` (Django built-in) | Runs all `AUTH_PASSWORD_VALIDATORS` from settings |
| Session after activation | Manual cookie setting | `django.contrib.auth.login(request, user)` | Sets session correctly, handles backend selection |
| Token lookup | Custom token table scan | `InvitationToken.hash_token(raw_token)` → `get(token_hash=...)` | SHA-256 already implemented; unique DB index already present |
| Confirmation modal | Custom dialog | `ConfirmModal` from `../modal` | Already built with focus trap, ARIA, keyboard nav (Phase 3) |
| Race condition guard | Application-level lock | `select_for_update()` inside `transaction.atomic` | Prevents double-submit creating two users |
| CSRF protection on resend API | Manual header | DRF `SessionAuthentication` + `getCsrfToken()` in `api.ts` | Already wired in existing `headers()` function |

**Key insight:** Every hard problem in this phase has an existing solution in the codebase. The task is assembly, not invention.

---

## Common Pitfalls

### Pitfall 1: Token State Order

**What goes wrong:** Checking `is_expired` before `is_used` causes a used-and-expired token to show the "expired" error instead of "already used."

**Why it happens:** Both `is_used` and `is_expired` can be true simultaneously (resend invalidates via `is_used=True`, but the original `expires_at` is unchanged).

**How to avoid:** Always check `is_used` first. The CONTEXT.md decision explicitly documents: "If the recipient clicks the old link after resend, they see ACTV-05: 'This invitation has already been used.'"

**Warning signs:** A test that resends and then clicks the old link gets ACTV-04 copy instead of ACTV-05 copy.

### Pitfall 2: Relative Accept URL in Emails

**What goes wrong:** `_build_accept_url` currently returns `/invite/accept/{token}/` (relative path). This works for form actions but email clients need an absolute URL.

**Why it happens:** The stub left a comment: "Phase 4 upgrades to absolute URL using `settings.SITE_URL`."

**How to avoid:** Update `_build_accept_url` to `f"{settings.SITE_URL}/invite/accept/{raw_token}/"`. Add `SITE_URL = env("SITE_URL", default="http://localhost:8000")` to `config/settings/base.py`. This is the single fix for EMAL-01.

**Warning signs:** Email test asserting `accept_url` starts with `http` fails.

### Pitfall 3: LOGIN_REDIRECT_URL Points to Superadmin After Activation

**What goes wrong:** After `login(request, user)`, if code does `redirect(settings.LOGIN_REDIRECT_URL)`, Org Admins land on `/admin/organisations/` which is Superadmin-only.

**Why it happens:** `LOGIN_REDIRECT_URL = "/admin/organisations/"` is set in `base.py` for Superadmin use.

**How to avoid:** In `invite_accept_view`, after `login()`, explicitly `redirect("org_dashboard")` (or whatever URL name is chosen). Do NOT use `settings.LOGIN_REDIRECT_URL`. This is the correct pattern per Django docs: the redirect after `login()` should be explicit in the view when the destination is role-determined.

**Warning signs:** Activated Org Admin sees a 403 or the Superadmin organisations list.

### Pitfall 4: mypy Strict Mode on Service Functions

**What goes wrong:** `activate_account` returns `User` but the import is inside `TYPE_CHECKING` block; `select_for_update()` return type may not satisfy strict mypy.

**Why it happens:** `apps/organisations/services/organisations.py` already uses `if TYPE_CHECKING: from apps.accounts.models import User` pattern to avoid circular import. The new `activate_account` function needs the same pattern.

**How to avoid:** Keep `User` under `TYPE_CHECKING` for annotations; use `from apps.accounts.models import User` inside the function body for the actual `objects.create_user()` call. Follow the existing `create_organisation` pattern exactly.

**Warning signs:** `mypy` reports `Cannot find implementation or library stub for module named 'apps.accounts.models'` or `Name 'User' is not defined`.

### Pitfall 5: ResendInvitationModal Not Getting the Row Object

**What goes wrong:** `onOpenResend` in `org-management.tsx` currently has signature `() => void` (no row argument). The new handler needs `(r: OrgRow) => void`.

**Why it happens:** The Phase 3 stub was `onOpenResend: () => emitToast(...)`. The `_orgModalHandlers` type definition also uses `onOpenResend: () => void`.

**How to avoid:** Update `_orgModalHandlers` type in `org-management.tsx` to `onOpenResend: (r: OrgRow) => void`. Update `OrgTableWidget`'s `onOpenResend: (_r) => getHandlers()?.onOpenResend()` to pass `r`. The `OrgTableHandlers` interface in `OrgTable.tsx` already has `onOpenResend: (row: OrgRow) => void` — the stub was the mismatch.

**Warning signs:** TypeScript error: "Expected 0 arguments, but got 1."

### Pitfall 6: ActivationForm Not Running AUTH_PASSWORD_VALIDATORS

**What goes wrong:** Password meets `min_length=10` check in the form field but doesn't go through Django's validator chain (CommonPasswordValidator, NumericPasswordValidator, etc.).

**Why it happens:** Forgetting to call `validate_password(pw)` in `clean_password1`.

**How to avoid:** Always call `validate_password(pw)` in the `clean_password1` method. This calls all validators configured in `AUTH_PASSWORD_VALIDATORS`. This is the same approach Django's own `SetPasswordForm` uses.

**Warning signs:** `password1 = "password123456"` is accepted by the form despite CommonPasswordValidator.

### Pitfall 7: Double-Submit Race on Activation

**What goes wrong:** Two concurrent POSTs to the activation form both pass the `is_used` check before either commits, resulting in two `User` objects with the same email — violating the `unique=True` constraint on `User.email`.

**Why it happens:** Without a database-level lock, both requests read `is_used=False` before either writes `is_used=True`.

**How to avoid:** Use `select_for_update()` inside `transaction.atomic` in `activate_account`. The unique constraint on `User.email` is also a safety net but `select_for_update` prevents the duplicate attempt.

**Warning signs:** Intermittent `IntegrityError: UNIQUE constraint failed: accounts_user.email` in production logs.

---

## Code Examples

### Verified Pattern: Token Hash Lookup (from existing `InvitationToken`)

```python
# From apps/accounts/models.py — already implemented
@classmethod
def hash_token(cls, raw_token: str) -> str:
    """SHA-256 hex digest of the signed token string (stored, never the raw token)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
```

**Lookup pattern:**
```python
token_hash = InvitationToken.hash_token(raw_token_from_url)
invitation = InvitationToken.objects.select_related("organisation").get(
    token_hash=token_hash
)
# DB index: token_hash is unique + db_index=True — single-query lookup
```

### Verified Pattern: Alpine.js Strength Indicator (from `password_reset_confirm.html`)

The activation form reuses this verbatim — already battle-tested in Phase 2:

```html
<!-- From templates/accounts/password_reset_confirm.html -->
<form x-data="{
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
}" ...>
```

### Verified Pattern: ConfirmModal Usage (from `DisableConfirmModal.tsx`)

```typescript
// Pattern for ResendInvitationModal — mirrors DisableConfirmModal structure
<ConfirmModal
  open={org !== null}
  onClose={onClose}
  onConfirm={handleConfirm}
  variant="amber"  // or "default" for yellow primary
  title="Resend Invitation"
  message={<>Resend invitation to <strong>{org?.email}</strong>...</>}
  confirmLabel={submitting ? "Sending…" : "Resend Invitation"}
/>
```

### Verified Pattern: API fetch with CSRF (from `api.ts`)

```typescript
// Add to frontend/src/widgets/org-management/api.ts
export async function resendInvitation(id: number): Promise<void> {
  const resp = await fetch(`${BASE}${id}/resend-invitation/`, {
    method: "POST",
    headers: headers("POST"),   // includes X-CSRFToken
    credentials: "same-origin",
  });
  await handle(resp);
}
```

### Verified Pattern: `is_resend` conditional in email template

```html
<!-- Add to templates/emails/invitation.html before the footer row -->
{% if is_resend %}
<tr>
  <td style="padding:0 32px 0 32px;">
    <p style="margin:0 0 16px 0;font-size:12px;line-height:1.5;color:#71717A;font-style:italic;">
      This replaces any previous invitation.
    </p>
  </td>
</tr>
{% endif %}
```

```
{# Add to templates/emails/invitation.txt before expiry line #}
{% if is_resend %}This replaces any previous invitation.

{% endif %}
```

### Verified Pattern: `activate_account` in org settings (from `create_organisation`)

```python
# Follows same @transaction.atomic decorator pattern already in organisations.py
@transaction.atomic
def activate_account(*, invitation: InvitationToken, full_name: str, password: str) -> "User":
    from apps.accounts.models import User
    locked = InvitationToken.objects.select_for_update().get(pk=invitation.pk)
    if locked.is_used:
        raise ValidationError("Invitation already used.")
    user = User.objects.create_user(
        email=locked.organisation.email,
        full_name=full_name,
        password=password,
        role=User.Role.ORG_ADMIN,
        organisation=locked.organisation,
    )
    locked.invited_user = user
    locked.is_used = True
    locked.save(update_fields=["invited_user", "is_used", "updated_at"])
    return user
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_build_accept_url` returns relative path | Phase 4 adds `settings.SITE_URL` prefix | Phase 4 (now) | Emails become clickable from any mail client |
| `onOpenResend` emits info toast (stub) | `ResendInvitationModal` + real API call | Phase 4 (now) | INVT-01 and INVT-02 become functional |
| Invitation email sent on org create only | Also sent on explicit resend | Phase 4 (now) | EMAL-02 complete |
| Org Admin has no landing page | Stub dashboard at `/admin/org-dashboard/` | Phase 4 (now) | Post-activation redirect target exists |

**Deprecated/outdated:**

- `_build_accept_url` comment "Phase 4 registers the real URL" — this comment should be removed and the function updated in the same commit.
- `onOpenResend: () => emitToast(...)` stubs in `org-management.tsx` and `ViewOrgModal.tsx` — replaced by real modal dispatch.

---

## Open Questions

1. **`ConfirmModal` `variant` prop for yellow primary confirm button**
   - What we know: `DisableConfirmModal` uses `variant="amber"`, `DeleteConfirmModal` uses `variant="red"`, `EnableConfirmModal` likely uses `"green"`.
   - What's unclear: Does `ConfirmModal` support a `"default"` or `"primary"` variant that produces a yellow button? Need to check `frontend/src/widgets/modal.tsx`.
   - Recommendation: Read `modal.tsx` before implementing `ResendInvitationModal`. If no yellow variant exists, check `EnableConfirmModal` for the pattern — or add a `"primary"` variant mapping to the yellow button class.

2. **`UserManager.create_user` signature**
   - What we know: `User` uses a custom `UserManager` in `apps/accounts/managers.py`. `create_organisation` doesn't call it directly.
   - What's unclear: Whether `create_user` accepts `role` and `organisation` as keyword args, or whether those must be set manually after creation.
   - Recommendation: Read `apps/accounts/managers.py` before writing `activate_account`. If `create_user` doesn't accept these fields, set them and call `user.save()` before the `select_for_update` block ends.

3. **`base_org.html` sidebar nav URL names**
   - What we know: The Org Admin sidebar can be minimal (one "Dashboard" item per CONTEXT.md). URL name for the dashboard view is Claude's discretion.
   - What's unclear: Should the Org Admin sidebar use Alpine.js `$store.nav` for mobile drawer (same as Superadmin sidebar), or a simpler static sidebar since Phase 5 will rebuild it?
   - Recommendation: Reuse the existing Alpine.js `$store.nav` pattern for consistency — the sidebar infrastructure is already in place and it's simpler than maintaining two mobile menu systems.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (installed) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest apps/accounts/tests/ apps/organisations/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INVT-01 | Resend: invalidates old token, creates new, sends email | unit (service) | `pytest apps/organisations/tests/test_services.py -k resend -x` | ❌ Wave 0 |
| INVT-01 | Resend endpoint returns 200 for Superadmin | integration (view) | `pytest apps/organisations/tests/test_views.py -k resend -x` | ❌ Wave 0 |
| INVT-01 | Resend endpoint returns 403 for non-Superadmin | integration (view) | `pytest apps/organisations/tests/test_views.py -k resend_forbidden -x` | ❌ Wave 0 |
| INVT-02 | Resend visible only when activation_status != active | unit (React) | `npx vitest run src/widgets/org-management/ResendInvitationModal.test.tsx` | ❌ Wave 0 |
| ACTV-01 | GET valid token → 200 with form | integration | `pytest apps/accounts/tests/test_views.py -k invite_accept_valid -x` | ❌ Wave 0 |
| ACTV-02 | Form renders pre-filled disabled email, required fields | integration | `pytest apps/accounts/tests/test_views.py -k invite_accept_fields -x` | ❌ Wave 0 |
| ACTV-03 | POST valid form → user created, token used, login, redirect | integration | `pytest apps/accounts/tests/test_views.py -k invite_accept_submit -x` | ❌ Wave 0 |
| ACTV-04 | GET invalid/expired token → error page with correct copy | integration | `pytest apps/accounts/tests/test_views.py -k invite_accept_expired -x` | ❌ Wave 0 |
| ACTV-05 | GET already-used token → error page with correct copy | integration | `pytest apps/accounts/tests/test_views.py -k invite_accept_used -x` | ❌ Wave 0 |
| EMAL-01 | Invitation email sends with absolute URL on org create | unit (service) | `pytest apps/organisations/tests/test_services.py -k invitation_email_absolute -x` | ❌ Wave 0 |
| EMAL-02 | Resend email contains "This replaces any previous invitation" | unit (service) | `pytest apps/organisations/tests/test_services.py -k resend_email_note -x` | ❌ Wave 0 |
| EMAL-03 | Password reset email already tested in Phase 2 | — | `pytest apps/accounts/tests/test_views.py -k password_reset -x` | ✅ Exists |
| EMAL-04 | Email templates: max-width 600px, inline CSS, plain-text present | manual | Visual check in MailHog | N/A — manual only |

### Sampling Rate

- **Per task commit:** `pytest apps/accounts/tests/ apps/organisations/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/accounts/tests/test_views.py` — add `invite_accept_*` test functions (ACTV-01 through ACTV-05)
- [ ] `apps/organisations/tests/test_services.py` — add `test_resend_invitation_*` functions (INVT-01, EMAL-01, EMAL-02)
- [ ] `apps/organisations/tests/test_views.py` — add `test_resend_invitation_endpoint_*` functions (INVT-01 endpoint)
- [ ] `frontend/src/widgets/org-management/ResendInvitationModal.test.tsx` — new file for INVT-02 React test

*(Existing test files for these modules already exist — only new test functions are needed, no new file scaffolding for Django tests.)*

---

## Sources

### Primary (HIGH confidence)

- Direct reading of `apps/accounts/models.py` — `InvitationToken` model, `hash_token`, `is_expired`, `is_used` fields
- Direct reading of `apps/organisations/services/organisations.py` — `create_organisation`, `_build_accept_url` stub, `InvitationToken.objects.create` pattern
- Direct reading of `apps/common/services/email.py` — `send_transactional_email` signature and SES header handling
- Direct reading of `templates/accounts/password_reset_confirm.html` — Alpine.js strength indicator pattern, show/hide toggle, `auth_base.html` extension
- Direct reading of `templates/auth_base.html` — centered-card no-sidebar layout for activation and error pages
- Direct reading of `frontend/src/widgets/org-management/DisableConfirmModal.tsx` — `ConfirmModal` usage pattern for `ResendInvitationModal`
- Direct reading of `frontend/src/entrypoints/org-management.tsx` — `onOpenResend` stub location, `_orgModalHandlers` type, wiring pattern
- Direct reading of `frontend/src/widgets/org-management/OrgTable.tsx` — `onOpenResend` already passes `OrgRow` to handler
- Direct reading of `frontend/src/widgets/org-management/api.ts` — `getCsrfToken`, `headers()`, `ApiError` reuse for `resendInvitation`
- Direct reading of `apps/organisations/selectors/organisations.py` — `activation_status_for` logic confirming `is_used` = active state
- Direct reading of `CLAUDE.md §9` — `login()` usage, session auth, `LOGIN_REDIRECT_URL` warning
- Direct reading of `.planning/REQUIREMENTS.md` — exact locked copy for ACTV-04, ACTV-05 error messages
- Direct reading of `04-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- `select_for_update()` race condition prevention: standard Django ORM pattern, documented in Django 6.0 official docs; consistent with CLAUDE.md §6.12

### Tertiary (LOW confidence)

- None — all findings are directly verifiable from existing codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; all libraries verified as installed and in use
- Architecture: HIGH — all patterns derived directly from existing codebase files
- Pitfalls: HIGH — derived from direct code analysis (token state ordering, URL absoluteness, redirect target, mypy patterns)
- Open questions: MEDIUM — two require reading one additional file (`modal.tsx`, `managers.py`) before implementation

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable stack — no fast-moving dependencies)
