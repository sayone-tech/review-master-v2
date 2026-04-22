# Feature Landscape

**Domain:** Superadmin module — multi-tenant SaaS platform (Phase 1)
**Researched:** 2026-04-22
**Confidence:** MEDIUM-HIGH

---

## Table Stakes

Features superadmins expect. Missing = product feels incomplete or unprofessional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Secure login with session management | Every admin panel; prerequisite for all other features | Low | Django session auth; rate-limit login attempts |
| Logout with server-side session invalidation | Security baseline; clearing only cookie leaves session replayable | Low | Invalidate server-side session; redirect to login |
| Forgot-password / reset flow | ~100% of SaaS tools have this | Low | TimestampSigner link, 1-hour expiry |
| Organisations list — searchable, filterable, paginated | Primary daily surface; unusable without search/filter | Medium | Search by name/email; filter status+type; server-side pagination |
| Organisation status badge on list | Assess tenant health at a glance | Low | Colour-coded pill (Active / Inactive / Pending) |
| Create organisation form with inline validation | Core data-entry task | Medium | Required: name, type, email, address, store allocation |
| View organisation detail | Audit, support, and edit starting point | Low | Read-only summary + action buttons; show invitation status |
| Edit organisation | Organisations change name, address, type | Medium | Same fields as create; email disabled post-create |
| Enable / disable organisation | Suspend tenant without data loss | Low | Single-click + confirmation modal |
| Delete organisation with type-to-confirm | Destructive action; industry standard requires name typing | Medium | Disabled confirm button until exact name match |
| Store allocation management per organisation | Core capacity concept | Medium | Show "used / allocated"; enforce active ≤ allocation |
| Org Admin invitation email on org create | Every multi-tenant SaaS sends setup email on provisioning | Medium | SES; HTML + plain text; signed token URL; 48hr expiry |
| Resend Org Admin invitation | Tokens expire; admins request resends | Low | Invalidate prior token; rate-limit at 5/hour |
| Org Admin account activation page (token-gated) | Org Admin must set password when accepting invitation | Medium | Token validation; password form; mark token used |
| Superadmin profile page (name + password change) | Basic account management in every dashboard | Low | Current-password-required for password change |
| Left sidebar navigation with active state | Standard SaaS admin layout | Medium | Collapses on mobile; active link highlighted |
| Responsive layout (mobile-usable) | Superadmins may check on mobile | Medium | Sidebar collapses to hamburger below md breakpoint |
| Empty states for all list views | Blank table looks like a loading bug | Low | Icon + CTA ("Create your first organisation") |
| Loading and error states on data fetch | Network latency and API errors are realities | Low | Skeleton loaders; error banner with retry |
| CSRF protection on all form submissions | Security baseline | Low | Never disable CSRF; Django 6 CSP middleware |

---

## Differentiators

Features that elevate the product. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Invitation status badge on org detail | "Invitation sent · Expires in 38h / Accepted / Expired" eliminates "did they get the email?" support question | Low | Derive from invitation record + created_at |
| Token expiry countdown on resend UI | Tells superadmin if resend is actually needed | Low | "Resend (expires in 12h)" vs "Resend (expired)" |
| Keyboard-accessible confirmation dialogs | Power-user and accessibility win; Tab/Enter/Esc | Low | Native focus trap; no external library |
| Password strength meter on activation page | Reduces weak-password support tickets | Low | zxcvbn or native constraint validation; frontend only |
| Session timeout warning with extend option | Prevents silent logout mid-task | Medium | JS countdown + /session/extend/ endpoint |
| Superadmin impersonation (view as Org Admin) | Reduces "I can see it, they can't" support tickets | High | Recommend Phase 2+; significant security surface |

---

## Anti-Features

Features to deliberately NOT build in Phase 1.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Public / self-service organisation signup | Bypasses the Superadmin control model | Superadmin creates all orgs; Org Admin enters via invitation only |
| Email address change without verification loop | Can lock Superadmin out or take over another account | Defer email change to a later phase |
| Hard-delete of organisations in Phase 1 | Permanent, unrecoverable data loss | Soft-delete; schedule hard-purge job for a future phase |
| Inline row editing on the organisations list | Accidental edits; breaks keyboard navigation | Dedicated Edit modal triggered by Edit button |
| CSV batch import of organisations | Parsing, validation, rollback add significant complexity | Build single-create solidly first |
| Dynamic role creation / custom RBAC | Roles are fixed; dynamic config delays Phase 1 | Hardcode roles as enum |
| Two-factor authentication for superadmin | TOTP setup + backup codes + recovery flow delays Phase 1 | Enforce strong password now; add 2FA in security hardening phase |
| Activity log / audit trail UI | Separate bounded context; non-trivial | Log to structured JSON in production; surface UI in a future phase |
| Dashboard analytics / charts | No meaningful data until orgs/stores live for weeks | Simple text stat summary (total orgs, active orgs, pending invitations) |
| In-app notification centre | Explicitly out of scope | Email only via SES in Phase 1 |

---

## Feature Dependencies

```
Login / auth
  └→ All authenticated views (prerequisite)

Create organisation
  └→ Org Admin invitation email (sent immediately on create)
  └→ Store allocation (set on create form)

Org Admin invitation email
  └→ Amazon SES configured
  └→ Invitation token (TimestampSigner)
  └→ Org Admin activation page (token consumed here)

Org Admin activation page
  └→ Valid, unexpired, single-use invitation token
  └→ Password set form
  └→ Org Admin user record (activated on token redemption)

Resend invitation
  └→ Org must exist + prior token invalidated + SES configured

Delete organisation
  └→ Type-to-confirm modal + soft-delete on model

Left sidebar layout
  └→ Wraps all authenticated views

Superadmin profile
  └→ Login (must be authenticated)
```

---

## MVP Sequencing

### Must-have — build in this order

1. Auth (login, logout, forgot password) — prerequisite
2. Left sidebar layout + design system — all views depend on this shell
3. Organisations list (search, filter, pagination, empty state)
4. Create organisation + invitation email (core provisioning flow)
5. View organisation detail + status badge + invitation status
6. Edit organisation
7. Enable / disable with confirmation modal
8. Delete with type-to-confirm
9. Store allocation management (on create + edit + detail)
10. Resend invitation with expiry display
11. Org Admin activation page (token-gated)
12. Superadmin profile (name + password change)

### Low-complexity differentiators worth including in Phase 1

- Invitation status badge on org detail (Low, high operational value)
- Token expiry display on resend button (Low, prevents unnecessary resends)
- Keyboard-accessible dialogs (Low, accessibility)
- Password strength meter on activation page (Low, good first impression)

---

## UX Patterns Catalogue

### Type-to-Confirm (Delete)

Industry references: GitHub repo deletion, Vercel project deletion, Heroku app deletion.
- Input placeholder: "Type the organisation name to confirm"
- Confirm button disabled until exact match (case-insensitive)
- The typing friction communicates irreversibility; prevents muscle-memory clicks

### Status Badges

| Status | Classes (Tailwind) | Label |
|--------|-------------------|-------|
| Active | `bg-green-100 text-green-800` | Active |
| Inactive | `bg-gray-100 text-gray-600` | Inactive |
| Pending invite | `bg-yellow-100 text-yellow-800` | Pending |

Never use colour alone — always include a text label (WCAG).

### Organisation List Column Order

Name | Type | Status | Stores (used/allocated) | Org Admin email | Created | Actions

Actions column: kebab menu (View Details, Edit, Adjust Store Count, Enable/Disable, Resend Invitation, Delete). Delete always last, visually separated, in red.

### Search / Filter Bar

- Debounce search input at 300ms; clear (×) button when non-empty
- Status and Type as `<select>` dropdowns (simpler on mobile)
- "No results for 'xyz'" message with clear-filters button

---

## Open Questions

- **Login lockout policy:** How many failed attempts trigger lockout? Time-based or manual unlock?
- **Org Admin email uniqueness:** Can the same email be Org Admin across multiple organisations?
- **Store allocation reduction:** If allocation set below current active stores, block or warn-only?
- **Soft-delete visibility:** Should deleted orgs appear in list with a filter, or be fully invisible?
