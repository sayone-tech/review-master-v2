# Requirements: Multi-Tenant Review Management Platform

**Defined:** 2026-04-22
**Source:** `docs/Requirements_Phase1_Superadmin.docx` (v1.0, April 2026)
**Core Value:** Superadmins can provision and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.

---

## v1 Requirements (Phase 1 — Superadmin Module)

### Authentication

- [ ] **AUTH-01**: User can log in with email and password via the /login page
- [ ] **AUTH-02**: User can log out and have their server-side session invalidated
- [ ] **AUTH-03**: User can request a password reset email via "Forgot password?" link
- [ ] **AUTH-04**: User can reset their password via a secure, time-limited email link (1-hour expiry)
- [ ] **AUTH-05**: User session persists across browser refresh

### Design System and Layout

- [x] **DSYS-01**: All authenticated pages render within a fixed left sidebar layout (Primary Black background, ~240px wide on desktop)
- [ ] **DSYS-02**: Sidebar displays role-specific navigation with white text, yellow active state, yellow hover state, and bottom-pinned logout item
- [ ] **DSYS-03**: Top bar shows current page title/breadcrumb (left) and notification bell + profile avatar dropdown (right)
- [x] **DSYS-04**: Main content area uses Background Gray (#FAFAFA) canvas with white content cards
- [ ] **DSYS-05**: Layout is fully responsive — sidebar collapses to collapsible icon rail on tablet (768–1023px) and hamburger drawer on mobile (<768px)
- [ ] **DSYS-06**: Tables scroll horizontally on tablet; transform into stacked cards on mobile
- [ ] **DSYS-07**: Reusable component set implemented: Primary/Secondary/Danger/Ghost buttons, form inputs with label+helper+error, modal dialogs, confirmation popups, toast notifications (success/error/warning/info), data tables with sticky headers and row actions, status badges, empty states, loading skeletons
- [ ] **DSYS-08**: Full keyboard navigation, visible focus states, ARIA labels on icon-only buttons, focus trap in modals, WCAG AA contrast compliance, logical heading hierarchy

### Organisations List

- [ ] **ORGL-01**: Superadmin sees organisations list as the default landing page after login (/admin/organisations)
- [ ] **ORGL-02**: Organisations list displays columns: Name (bold, clickable), Type (badge), Email, # Stores (used/allocated), Status (badge), Created Date, Actions (three-dot menu)
- [ ] **ORGL-03**: User can search organisations by name or email (real-time, debounced)
- [ ] **ORGL-04**: User can filter organisations by status (All / Active / Disabled)
- [ ] **ORGL-05**: User can filter organisations by type (All / Retail / Restaurant / Pharmacy / Supermarket)
- [ ] **ORGL-06**: List is paginated with rows-per-page selector (10/25/50/100, default 10) and page navigation controls showing "Showing X–Y of Z"
- [ ] **ORGL-07**: List shows skeleton loading state while data loads and an empty state with CTA when no organisations exist
- [ ] **ORGL-08**: List renders with a fixed number of SQL queries regardless of result size (CI query-count ceiling asserted)

### Create Organisation

- [ ] **CORG-01**: User can open a "Create Organisation" modal from the list page header
- [ ] **CORG-02**: Create form accepts: Organisation Name (2–100 chars, required), Organisation Type (dropdown, required), Address (textarea, max 500 chars, optional), Email (valid, unique across orgs, required), Number of Stores (integer 1–1000, required)
- [ ] **CORG-03**: On successful create, modal closes, success toast appears ("Organisation created. Invitation email sent to {email}."), and list refreshes
- [ ] **CORG-04**: System generates a secure invitation token (48-hour expiry, single-use) and sends an activation email to the organisation's contact email address immediately on create

### View Organisation

- [ ] **VORG-01**: User can open an Organisation Details modal by clicking the organisation name or selecting "View Details" from the row actions menu
- [ ] **VORG-02**: Details modal shows: Name, Type (badge), Address, Email, Stores (X used of Y allocated), Status (badge), Created Date, Org Admin activation status (Pending invite / Active / Invitation expired), timestamp of last invitation sent
- [ ] **VORG-03**: Details modal shows "Resend Invitation" button only when Org Admin has not yet activated the account

### Edit Organisation

- [ ] **EORG-01**: User can open an Edit Organisation modal (reuses create form layout, all fields pre-filled)
- [ ] **EORG-02**: Email field is disabled in edit mode — cannot be changed after creation
- [ ] **EORG-03**: On successful save, modal closes, toast shows "Organisation updated.", and view refreshes

### Enable / Disable Organisation

- [ ] **ENBL-01**: User can disable an active organisation via the row actions menu, after confirming a popup (icon: Warning amber; message includes org name; buttons: Cancel / Disable red; success toast on confirm)
- [ ] **ENBL-02**: User can enable a disabled organisation via the row actions menu, after confirming a popup (icon: Info blue; buttons: Cancel / Enable primary; success toast on confirm)

### Delete Organisation

- [ ] **DORG-01**: User can delete an organisation via the row actions menu, after a confirmation popup that requires typing the exact organisation name into an input before the Delete button is enabled (icon: Alert red; success toast on confirm)
- [ ] **DORG-02**: Delete performs a soft-delete (status change); permanent purge is handled by a future scheduled job

### Store Allocation

- [ ] **STOR-01**: User can adjust a store allocation via "Adjust Store Count" from the row actions menu; input shows "Currently using X of Y stores" with helper text showing the minimum allowed value
- [ ] **STOR-02**: Entering a value below the current in-use count shows an inline amber warning; the Update button remains blocked until the value is valid
- [ ] **STOR-03**: Clicking Update shows a confirmation popup (icon: Info blue; shows old and new count; buttons: Cancel / Update primary); success toast on confirm

### Invitation System

- [ ] **INVT-01**: Superadmin can resend an invitation from the row actions menu or Organisation Details modal (confirmation popup with org name and target email; invalidates previous token; success toast on confirm)
- [ ] **INVT-02**: Resend Invitation action is visible only when the Org Admin has not yet activated their account

### Account Activation Page

- [ ] **ACTV-01**: Invitation recipient lands on /invite/accept/<token>/ — a public, token-gated page with no sidebar
- [ ] **ACTV-02**: Activation page shows "Welcome to {OrganisationName}" and a form with: pre-filled disabled Email, Full Name (required, 2–100 chars), Password (with show/hide toggle, Django validators, strength indicator), Confirm Password (must match)
- [ ] **ACTV-03**: On successful activation, invitation token is marked used (single-use), Org Admin user is created and associated with the organisation, activation status updates to Active, user is logged in and redirected
- [ ] **ACTV-04**: Invalid or expired token shows a full-page error: "This invitation link is invalid or has expired. Please contact your administrator to request a new one."
- [ ] **ACTV-05**: Already-accepted token shows: "This invitation has already been used."

### Superadmin Profile

- [ ] **PROF-01**: Superadmin can update their full name from the Profile page (/admin/profile); success toast on save
- [ ] **PROF-02**: Superadmin can change their password (requires current password, new password with strength indicator, confirm); success toast on save

### Email Templates

- [ ] **EMAL-01**: Invitation email sends on new organisation create (subject: "You're invited to manage {OrganisationName}"; HTML + plain text; 48-hour expiry notice; Accept Invitation CTA; SES configuration set headers)
- [ ] **EMAL-02**: Resent invitation email sends with same structure as original plus "This replaces any previous invitation" note
- [ ] **EMAL-03**: Password reset email sends on forgot-password request (subject: "Reset your password"; 1-hour link; plain-text fallback; security advisory copy)
- [ ] **EMAL-04**: All emails render correctly across Gmail, Outlook, and Apple Mail; max 600px width; CSS inlined; plain-text fallback always present

---

## v2 Requirements (Deferred)

### Future Phases

- **Phase 2**: Organisation Admin dashboard, store creation, Google Business Profile OAuth per store, Staff Admin invitation
- **Phase 3**: Staff Admin dashboard, review listing and response interface
- **Phase 4**: Scheduled Google review fetching, review storage, analytics dashboards
- **Phase 5**: Billing, Stripe integration, plan selection

### Deferred from Phase 1

- **NOTF-01**: In-app notification centre — email-only in Phase 1
- **AUDIT-01**: Audit log UI — structured JSON logs are captured in production; UI deferred
- **2FA-01**: Two-factor authentication for Superadmin — security hardening phase
- **IMPR-01**: Superadmin impersonation (view as Org Admin) — Phase 2+
- **BULK-01**: Bulk enable/disable organisations — when tenant count regularly exceeds ~50

---

## Out of Scope (Phase 1)

| Feature | Reason |
|---------|--------|
| Organisation Admin dashboard and store management | Phase 2 |
| Staff Admin role and dashboard | Phase 3 |
| Google Business Profile OAuth connection | Phase 2+ |
| Review fetching, storage, and analytics | Phase 4 |
| Billing and subscription | Phase 5 |
| Public / self-service organisation signup | Bypasses Superadmin control model by design |
| Email address change after org creation | Requires verification loop; deferred |
| Hard-delete in Phase 1 | Soft-delete + future scheduled purge |
| CSV batch import of organisations | Single-create solidly first |
| Dark mode | Polish phase |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DSYS-01 | Phase 1 — Foundation | Complete |
| DSYS-02 | Phase 1 — Foundation | Pending |
| DSYS-03 | Phase 1 — Foundation | Pending |
| DSYS-04 | Phase 1 — Foundation | Complete |
| DSYS-05 | Phase 1 — Foundation | Pending |
| DSYS-06 | Phase 1 — Foundation | Pending |
| DSYS-07 | Phase 1 — Foundation | Pending |
| DSYS-08 | Phase 1 — Foundation | Pending |
| AUTH-01 | Phase 2 — Authentication | Pending |
| AUTH-02 | Phase 2 — Authentication | Pending |
| AUTH-03 | Phase 2 — Authentication | Pending |
| AUTH-04 | Phase 2 — Authentication | Pending |
| AUTH-05 | Phase 2 — Authentication | Pending |
| ORGL-01 | Phase 3 — Organisation Management | Pending |
| ORGL-02 | Phase 3 — Organisation Management | Pending |
| ORGL-03 | Phase 3 — Organisation Management | Pending |
| ORGL-04 | Phase 3 — Organisation Management | Pending |
| ORGL-05 | Phase 3 — Organisation Management | Pending |
| ORGL-06 | Phase 3 — Organisation Management | Pending |
| ORGL-07 | Phase 3 — Organisation Management | Pending |
| ORGL-08 | Phase 3 — Organisation Management | Pending |
| CORG-01 | Phase 3 — Organisation Management | Pending |
| CORG-02 | Phase 3 — Organisation Management | Pending |
| CORG-03 | Phase 3 — Organisation Management | Pending |
| CORG-04 | Phase 3 — Organisation Management | Pending |
| VORG-01 | Phase 3 — Organisation Management | Pending |
| VORG-02 | Phase 3 — Organisation Management | Pending |
| VORG-03 | Phase 3 — Organisation Management | Pending |
| EORG-01 | Phase 3 — Organisation Management | Pending |
| EORG-02 | Phase 3 — Organisation Management | Pending |
| EORG-03 | Phase 3 — Organisation Management | Pending |
| ENBL-01 | Phase 3 — Organisation Management | Pending |
| ENBL-02 | Phase 3 — Organisation Management | Pending |
| DORG-01 | Phase 3 — Organisation Management | Pending |
| DORG-02 | Phase 3 — Organisation Management | Pending |
| STOR-01 | Phase 3 — Organisation Management | Pending |
| STOR-02 | Phase 3 — Organisation Management | Pending |
| STOR-03 | Phase 3 — Organisation Management | Pending |
| INVT-01 | Phase 4 — Invitation and Activation | Pending |
| INVT-02 | Phase 4 — Invitation and Activation | Pending |
| ACTV-01 | Phase 4 — Invitation and Activation | Pending |
| ACTV-02 | Phase 4 — Invitation and Activation | Pending |
| ACTV-03 | Phase 4 — Invitation and Activation | Pending |
| ACTV-04 | Phase 4 — Invitation and Activation | Pending |
| ACTV-05 | Phase 4 — Invitation and Activation | Pending |
| EMAL-01 | Phase 4 — Invitation and Activation | Pending |
| EMAL-02 | Phase 4 — Invitation and Activation | Pending |
| EMAL-03 | Phase 4 — Invitation and Activation | Pending |
| EMAL-04 | Phase 4 — Invitation and Activation | Pending |
| PROF-01 | Phase 5 — Profile and Hardening | Pending |
| PROF-02 | Phase 5 — Profile and Hardening | Pending |

**Coverage:**
- v1 requirements: 50 total
- Mapped to phases: 50
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-22*
*Last updated: 2026-04-22 — traceability updated with 5-phase roadmap assignments*
