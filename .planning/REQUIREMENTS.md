# Requirements: Multi-Tenant Review Management Platform

**Defined:** 2026-04-27
**Source:** `docs/Requirements_Phase2_OrgAdmin.docx` (v1.0, April 2026)
**Core Value:** Organisation Admins can manage their Shops, Regions, and Team — the operational layer that runs on top of the Superadmin control plane.

---

## v2 Requirements (Milestone v0.2-org-admin)

### Organisation Admin Shell

- [x] **SHEL-01**: Organisation Admin sidebar shows six items in order — Dashboard, Shops, Regions, Team, Profile (top group) and Logout (bottom-pinned) — with correct icons and yellow active state
- [x] **SHEL-02**: Organisation Admin lands on /admin/org/dashboard after login with a "Welcome, {Name}" placeholder card
- [x] **SHEL-03**: Dashboard displays a yellow info banner "Get started by creating your first region…" with a "Create Region" CTA when the organisation has zero Regions
- [x] **SHEL-04**: Profile page at /admin/org/profile reuses the Phase 1 two-card layout (name edit-in-place, password change with strength indicator, same toasts)

### Regions

- [x] **RGN-01**: Org Admin sees a list of all regions (creation order) with columns: Region Name, Region ID (pill badge, monospace), and Edit + Delete direct icon buttons (no three-dot menu)
- [x] **RGN-02**: Regions list shows an empty state (Map icon, "No regions yet", "Create your first region" CTA) when no regions exist
- [x] **RGN-03**: Org Admin can open a "Create Region" modal from the list page; modal accepts Region Name (2–60 chars, required) and Region ID (uppercase letters + digits, 2–10 chars, unique within organisation, required)
- [x] **RGN-04**: As the user types in Region Name, Region ID auto-populates in real time (first letter per word, up to 4 letters, plus 3-digit zero-padded sequence number); auto-population stops once the user manually edits the Region ID field
- [x] **RGN-05**: If the user clears a manually-edited Region ID, auto-population resumes
- [x] **RGN-06**: Submitting a duplicate Region ID shows an inline field error "This Region ID is already in use."
- [x] **RGN-07**: Successful region create closes the modal, shows toast "Region '{name}' created.", and refreshes the list
- [x] **RGN-08**: Org Admin can open an Edit Region modal; Region Name is editable; Region ID is editable; typing in Region Name does NOT auto-update Region ID in edit mode
- [x] **RGN-09**: Successful region edit shows toast "Region updated." and refreshes the list
- [x] **RGN-10**: Attempting to delete a Region that has one or more Shops assigned shows a blocking info popup (amber Warning icon, "Cannot delete region", shop count, "Manage Shops" link to Shops page pre-filtered by this region)
- [x] **RGN-11**: Deleting a Region with no Shops shows a red confirmation popup; on confirm, the region is permanently deleted and a toast "Region '{name}' deleted." appears

### Shops

- [x] **SHOP-01**: Shops page header shows a live allocation counter "Shops (X / Y)" where X is current shop count and Y is the Superadmin-set allocation
- [x] **SHOP-02**: "+ Add Shop" button is visually disabled with a tooltip "Shop limit reached." when the organisation is at allocation; clicking it shows a toast "You've reached your shop limit…" — the Create modal does not open
- [x] **SHOP-03**: Shops list has a search input (searches Name + Street Address), a Status filter (All / Active / Inactive), and a Region filter (All / per-region)
- [x] **SHOP-04**: Shops list shows columns: Shop Name (bold, clickable), Location (address + city/state/zip), Region badge, Contact (phone), Google Place ID (truncated monospace), API Key (masked, manual fallback only), Status badge (Active / Inactive), Connection Status pill, Created Date, Actions (three-dot menu)
- [x] **SHOP-05**: Connection Status pill shows one of four states: "Connected via Google" (green dot), "Connected via API key" (blue dot), "Connection error" (red dot), "Quota exceeded" (amber dot)
- [x] **SHOP-06**: Shops list is paginated (rows-per-page selector: 10/25/50/100, default 10) with "Showing X–Y of Z" display
- [x] **SHOP-07**: Empty State A (no Regions exist) shows "Create a region first" with a "Go to Regions" CTA; Empty State B (Regions exist but no Shops) shows "No shops yet" with "Add your first shop" CTA
- [x] **SHOP-08**: Create Shop modal has a connection method radio (Connect with Google / Enter manually), common fields (Shop Name 2–100 chars required; Phone optional E.164; Region dropdown required; Street Address required; City required; State/ZIP optional)
- [x] **SHOP-09**: When "Connect with Google" is selected, a "Connect Google Business Profile" button opens an OAuth popup (~600×700px); after successful connection, the button is replaced with a success row showing the connected listing name and address and a "Change connection" link
- [~] **SHOP-10** (RETIRED 2026-04-29 — see `.planning/phases/08-shops/08-CONTEXT.md` `<deferred>` section): When "Enter manually" is selected, Google Place ID (starts with 'ChIJ' or valid prefix, 20–256 chars) and Google Places API Key (masked, show/hide toggle) fields appear; both are validated against the Google Places API on submit
- [x] **SHOP-11**: Google OAuth popup flow: popup opens to /oauth/google/start/, user authenticates and grants permissions, callback page at /oauth/google/callback/ exchanges code for refresh token, presents listing picker if multiple listings, calls window.opener.postMessage with listing details and auto-closes; parent modal listens (origin verified) and shows success row
- [x] **SHOP-12**: OAuth popup edge cases handled correctly: user closes popup → "Connection cancelled. Please try again."; user denies consent → "Permission was not granted."; Google error → "Could not complete connection."; no listings → "No business listings found in this Google account."
- [x] **SHOP-13**: OAuth refresh token (Google) and manual API key are both encrypted at rest before persisting; they are never transmitted to the browser
- [x] **SHOP-14**: Successful shop create closes modal, shows toast "Shop '{name}' created.", refreshes list with new row at top, increments allocation counter
- [x] **SHOP-15**: Shop Details modal (triggered by clicking shop name or "View Details") shows all fields in a read-only two-column grid, including Connection Status pill, and has footer buttons: Reconnect Google (OAuth error only), Edit, Activate/Deactivate, Close
- [x] **SHOP-16**: Edit Shop modal mirrors Create modal with current values pre-filled; connection method radio and Google Place ID are locked; all other fields (Name, Phone, Region, Address fields, API Key via Rotate Key) are editable
- [x] **SHOP-17**: Deactivate Shop shows amber confirmation popup ("allocated store slot remains used"); success toast "Shop '{name}' deactivated."; deactivation does NOT free an allocation slot
- [x] **SHOP-18**: Activate Shop shows blue confirmation popup; success toast "Shop '{name}' activated."
- [~] **SHOP-19** (RETIRED 2026-04-29 — see `.planning/phases/08-shops/08-CONTEXT.md` `<deferred>` section): Reveal API Key action (manual fallback only) requires confirmation popup; shows the full key for 30 seconds then auto-masks; writes an audit log entry shop.api_key.revealed
- [~] **SHOP-20** (RETIRED 2026-04-29 — see `.planning/phases/08-shops/08-CONTEXT.md` `<deferred>` section): Rotate Key action opens a Rotate Key modal with a new API Key field; server validates the new key against the Google Places API, then replaces the old key atomically; success toast "API key rotated for '{name}'."; writes audit log entry shop.api_key.rotated
- [x] **SHOP-21**: Reconnect Google action (OAuth-connected shops with Connection error) restarts the OAuth popup flow; on success, the new refresh token replaces the old one and Connection Status returns to healthy

### Team

- [ ] **TEAM-01**: Team list shows columns: Member Name + Email, Role badge (purple "Manager" or gray "Staff"), Access chips (all-stores crown for Manager; region/store chips for Staff with "+N more" truncation), Status badge (Active/Pending), Invited Date, Enabled toggle, Edit + Remove icon buttons
- [ ] **TEAM-02**: Team list has a search input (Name + Email) and filter dropdowns for Region and Store (Store narrows when a Region is selected)
- [ ] **TEAM-03**: Team list is paginated (10/25/50/100, default 10)
- [ ] **TEAM-04**: Three stats cards below the table show live counts: Total Members, Managers, Active Members
- [ ] **TEAM-05**: When only the Org Admin exists (no other team members), a subtle info banner appears above the table with an "+ Add Team Member" inline action
- [x] **TEAM-06**: Add Team Member modal accepts: Name (2–100 chars), Email (valid, unique across platform), Role (Manager / Staff); when Role = Manager, no extra fields appear; when Role = Staff, Region multi-select and Store multi-select appear (at least one Region or Store selection required)
- [x] **TEAM-07**: Sending an invite refreshes the Team list with a new Pending row, shows toast "Invitation sent to {email}.", and sends the Team Invitation email with a 48-hour token
- [ ] **TEAM-08**: Edit Team Member modal (disabled for own row): Name, Role, Regions, Stores editable; Email is locked; changing role between Manager and Staff dynamically shows/hides scope selectors
- [ ] **TEAM-09**: Successful team member edit shows toast "Team member updated." and refreshes the list with updated access chips
- [x] **TEAM-10**: Enabled toggle disable (ON → OFF): amber confirmation popup; on confirm, all active sessions for the user are terminated immediately; success toast "{Name} disabled."
- [x] **TEAM-11**: Enabled toggle enable (OFF → ON): one-click, no confirmation; success toast "{Name} enabled."
- [x] **TEAM-12**: Disabled user attempting to log in sees "Your account has been disabled. Contact your administrator." on the login form
- [x] **TEAM-13**: Remove Team Member shows red confirmation popup; on confirm, access is revoked, all sessions are terminated, any pending invitations are invalidated; success toast "{Name} removed from team."
- [ ] **TEAM-14**: Self-protection rules enforced in UI (disabled buttons + tooltips) AND at API layer (403): Org Admin cannot remove self, disable self, or demote self to Staff
- [x] **TEAM-15**: Last-Manager rule enforced at API layer: removing the last Manager from an organisation returns an error "Cannot remove the last Manager."
- [x] **TEAM-16**: Pending team members have a Resend Invitation action; blue confirmation popup; previous token invalidated; new Team Invitation email sent; toast "Invitation resent to {email}."
- [x] **TEAM-17**: Team invitation acceptance page (/invite/accept/<token>/) pre-fills Name (editable by invitee) and Email (locked); on success, account is created with the invited role, user is auto-logged in and redirected to role-appropriate dashboard (Manager → /admin/org/dashboard; Staff → placeholder welcome page)

### Team Email Templates

- [x] **TEML-01**: Team Invitation email: addressed to invitee by name; mentions inviter name, organisation, and role; for Staff role includes comma-separated list of assigned regions/stores; primary CTA "Accept Invitation"; 48-hour expiry notice; plain-text fallback
- [x] **TEML-02**: Team Invitation Resent email: same structure as original plus "This replaces any previous invitation. The earlier link is no longer valid."; subject "New invitation link for {OrganisationName}"

### Cross-Module

- [x] **XMOD-01**: A Shop cannot be created without selecting a Region; Region dropdown is disabled with a link to /admin/org/regions when no Regions exist in the organisation
- [x] **XMOD-02**: Region deletion is blocked (info popup with shop count and "Manage Shops" link) when the Region has one or more Shops assigned
- [x] **XMOD-03**: Deactivated Shops are excluded from the "Select Stores" list in Add and Edit Team Member modals
- [x] **XMOD-04**: Shop allocation counter updates transactionally on shop create/activate/deactivate with no race conditions under concurrent admin sessions
- [x] **XMOD-05**: All Phase 2 list endpoints render within the query-count ceilings asserted in CI tests (no N+1 regardless of result size)

---

## Future Requirements (Deferred)

### Deferred from v0.2

- **STAF-01**: Staff Admin dashboard and store-level review views — Phase 3
- **REVW-01**: Google review fetching, storage, and response interface — Phase 4
- **ANLT-01**: Analytics dashboards and reporting — Phase 4
- **BILL-01**: Billing, subscriptions, and plan management — Phase 5
- **SHOP-DELET**: Shop hard-delete / freeing an allocation slot on deletion — future phase
- **NOTF-02**: In-app notifications for team events — future
- **2FA-02**: Two-factor authentication for Org Admins — future security hardening

---

## Out of Scope (v0.2)

| Feature | Reason |
|---------|--------|
| Staff Admin dashboard | Phase 3 — no review data exists yet |
| Google review fetching and response | Phase 4 |
| Shop hard-delete | Deactivate + future scheduled purge; consistent with Phase 1 org soft-delete pattern |
| Email address change flow | Requires verification loop; deferred |
| Shop deletion freeing allocation slots | Deliberate to prevent over-allocation churn |
| Org Admin self-service account deletion | High-risk, deferred |
| Bulk region / shop actions | Not needed until tenant count grows significantly |
| Region hierarchy beyond one level | Anti-feature for v0.2 scope |
| Direct Staff Admin login dashboard | Staff module content deferred to Phase 3 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHEL-01 | Phase 6 — Org Admin Shell | Complete |
| SHEL-02 | Phase 6 — Org Admin Shell | Complete |
| SHEL-03 | Phase 6 — Org Admin Shell | Complete |
| SHEL-04 | Phase 6 — Org Admin Shell | Complete |
| RGN-01 | Phase 7 — Regions | Complete |
| RGN-02 | Phase 7 — Regions | Complete |
| RGN-03 | Phase 7 — Regions | Complete |
| RGN-04 | Phase 7 — Regions | Complete |
| RGN-05 | Phase 7 — Regions | Complete |
| RGN-06 | Phase 7 — Regions | Complete |
| RGN-07 | Phase 7 — Regions | Complete |
| RGN-08 | Phase 7 — Regions | Complete |
| RGN-09 | Phase 7 — Regions | Complete |
| RGN-10 | Phase 7 — Regions | Complete |
| RGN-11 | Phase 7 — Regions | Complete |
| SHOP-01 | Phase 8 — Shops | Complete |
| SHOP-02 | Phase 8 — Shops | Complete |
| SHOP-03 | Phase 8 — Shops | Complete |
| SHOP-04 | Phase 8 — Shops | Complete |
| SHOP-05 | Phase 8 — Shops | Complete |
| SHOP-06 | Phase 8 — Shops | Complete |
| SHOP-07 | Phase 8 — Shops | Complete |
| SHOP-08 | Phase 8 — Shops | Complete |
| SHOP-09 | Phase 8 — Shops | Complete |
| SHOP-10 | Phase 8 — Shops | Retired (2026-04-29) |
| SHOP-11 | Phase 8 — Shops | Complete |
| SHOP-12 | Phase 8 — Shops | Complete |
| SHOP-13 | Phase 8 — Shops | Complete |
| SHOP-14 | Phase 8 — Shops | Complete |
| SHOP-15 | Phase 8 — Shops | Complete |
| SHOP-16 | Phase 8 — Shops | Complete |
| SHOP-17 | Phase 8 — Shops | Complete |
| SHOP-18 | Phase 8 — Shops | Complete |
| SHOP-19 | Phase 8 — Shops | Retired (2026-04-29) |
| SHOP-20 | Phase 8 — Shops | Retired (2026-04-29) |
| SHOP-21 | Phase 8 — Shops | Complete |
| TEAM-01 | Phase 9 — Team | Pending |
| TEAM-02 | Phase 9 — Team | Pending |
| TEAM-03 | Phase 9 — Team | Pending |
| TEAM-04 | Phase 9 — Team | Pending |
| TEAM-05 | Phase 9 — Team | Pending |
| TEAM-06 | Phase 9 — Team | Complete |
| TEAM-07 | Phase 9 — Team | Complete |
| TEAM-08 | Phase 9 — Team | Pending |
| TEAM-09 | Phase 9 — Team | Pending |
| TEAM-10 | Phase 9 — Team | Complete |
| TEAM-11 | Phase 9 — Team | Complete |
| TEAM-12 | Phase 9 — Team | Complete |
| TEAM-13 | Phase 9 — Team | Complete |
| TEAM-14 | Phase 9 — Team | Pending |
| TEAM-15 | Phase 9 — Team | Complete |
| TEAM-16 | Phase 9 — Team | Complete |
| TEAM-17 | Phase 9 — Team | Complete |
| TEML-01 | Phase 9 — Team | Complete |
| TEML-02 | Phase 9 — Team | Complete |
| XMOD-01 | Phase 8 — Shops | Complete |
| XMOD-02 | Phase 7 — Regions | Complete |
| XMOD-03 | Phase 9 — Team | Complete |
| XMOD-04 | Phase 8 — Shops | Complete |
| XMOD-05 | Phase 6–9 (all) | Complete |

**Coverage:**
- v2 requirements: 57 total
- Mapped to phases: 57
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-27*
*Source: docs/Requirements_Phase2_OrgAdmin.docx v1.0*
