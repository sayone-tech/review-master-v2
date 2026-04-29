# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- [x] **v1.0 — Superadmin Module** — 5 phases, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](.planning/milestones/v1.0-ROADMAP.md)
- [ ] **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 57 requirements (in progress)

---

## Current Milestone: v0.2-org-admin — Organisation Admin Module

**Milestone Goal:** Organisation Admins can manage their Shops, Regions, and Team — the operational layer running on top of the Superadmin control plane.

## Phases

- [ ] **Phase 6: Org Admin Shell** — Sidebar, dashboard, profile page reuse, data model migrations, and tenant security scaffold
- [ ] **Phase 7: Regions** — Full Regions CRUD with race-safe auto-ID generation and deletion guard
- [ ] **Phase 8: Shops** — Full Shops module with allocation enforcement, Google OAuth popup, and manual Place ID fallback
- [ ] **Phase 9: Team** — Team invite/manage with Manager/Staff scoping, self-protection rules, and email templates

## Phase Details

### Phase 6: Org Admin Shell
**Goal**: Org Admins have a working shell to navigate and a secure foundation that prevents all future viewsets from leaking data across tenant boundaries.
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: SHEL-01, SHEL-02, SHEL-03, SHEL-04, XMOD-05
**Success Criteria** (what must be TRUE):
  1. An Org Admin logging in lands on /admin/org/dashboard and sees a personalised "Welcome, {Name}" card with a "Create Region" setup banner when no Regions exist; other roles are redirected away.
  2. The Org Admin sidebar renders six items in the correct order — Dashboard, Shops, Regions, Team, Profile (top group), Logout (bottom-pinned) — with yellow active state on the current page.
  3. The Org Admin profile page at /admin/org/profile provides edit-in-place name update and password change with strength indicator, identical in behaviour to the Superadmin profile.
  4. A `TenantScopedViewSet` base class and `IsOrgScoped` permission class exist in `apps/common/`; a cross-tenant isolation test fixture asserts that an Org Admin from Org A receives 403 on Org B resources at the list, detail, and mutation endpoints.
  5. All Phase 2–9 data model migrations are present and reversible: Region, Shop, StaffAccessScope, User.invited_by_id / invited_at / accepted_at, InvitationToken purpose enum column (step 1 of 3-step expand-contract); `django-fernet-encrypted-fields` is installed and `FERNET_KEYS` loaded from GCP Secret Manager.

**Notes:**
- `django-sequences==3.0` smoke test (`get_next_value("test")` against Django 6 test DB) must run in this phase. If it fails, implement the 30-line `select_for_update()` fallback on a `Sequence` model before Phase 7 begins.
- Cross-Origin-Opener-Policy issue for Phase 8 OAuth popup must be scoped to the OAuth initiation view (not globally), so production.py COOP global setting of `same-origin` must NOT be changed here; instead, a per-view override point is planned.
- CI query-count ceiling assertion infrastructure (XMOD-05) established here as a shared test fixture used by all future phases.

**Plans**: 5 plans (3 waves)

Plans:
- [x] 06-01-PLAN.md — Data foundation: install django-fernet-encrypted-fields==0.4.0 + django-sequences==3.0; SALT_KEY settings; scaffold regions + shops apps; 5 ordered migrations (Region, Shop, StaffAccessScope, User extensions, InvitationToken purpose enum step 1); SequenceCounter fallback model
- [x] 06-02-PLAN.md — Tenant security scaffold: IsOrgAdmin (DRF + decorator), IsOrgScoped with mandatory has_object_permission, TenantScopedViewSet, two_orgs_two_admins + assert_query_ceiling fixtures, cross-tenant isolation scaffold, django-sequences smoke test
- [x] 06-03-PLAN.md — Org Admin navigation shell: six-item sidebar (Dashboard, Shops, Regions, Team, Profile, Logout), /admin/org/dashboard alias + 3 stub URLs (regions/shops/team) via shared org_stub_view, CustomLoginView role-based redirect
- [ ] 06-04-PLAN.md — Personalised dashboard: Welcome, {first name} card (split full_name on first space, fall back to email prefix), conditional yellow zero-regions setup banner with Create Region CTA, role-based 403 enforcement
- [ ] 06-05-PLAN.md — Org Admin profile reuse: org_profile + org_update_name_view + org_change_password_view sharing services with Superadmin profile, templates/accounts/org_profile.html (3-line diff from profile.html), three new URLs at /admin/org/profile/*

---

### Phase 7: Regions
**Goal**: Org Admins can create and manage named regions with unique auto-generated IDs, with the system blocking deletion when shops are assigned.
**Depends on**: Phase 6
**Requirements**: RGN-01, RGN-02, RGN-03, RGN-04, RGN-05, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02
**Success Criteria** (what must be TRUE):
  1. The Regions list at /admin/org/regions shows all regions in creation order with Region Name, Region ID (pill badge), Edit and Delete buttons; an empty state with a "Create your first region" CTA appears when no regions exist.
  2. Opening the Create Region modal and typing a name causes the Region ID field to auto-populate in real time (first letter per word, up to 4 letters, 3-digit zero-padded sequence); manually editing the Region ID stops auto-population; clearing a manual edit resumes it.
  3. Submitting a duplicate Region ID shows the inline error "This Region ID is already in use." and the modal stays open; two concurrent creates never produce the same Region ID (enforced by `select_for_update()` on the Organisation row inside `@transaction.atomic`).
  4. Editing a region changes the name and/or ID; typing in the name field during edit does NOT change the ID; success shows "Region updated." toast and refreshes the list.
  5. Attempting to delete a region that has one or more shops assigned shows a blocking amber popup with shop count and a "Manage Shops" link; deleting a region with no shops shows a red confirmation popup and, on confirm, permanently removes the region with a "Region '{name}' deleted." toast.

**Notes:**
- If `django-sequences` failed the Phase 6 smoke test, Region ID generation uses the `select_for_update()` fallback throughout this phase.
- `UniqueConstraint(fields=["organisation", "region_id"])` is the DB-level safety net regardless of the ID generation strategy.
- CI query-count test for the Regions list endpoint must be added in this phase (fixed ceiling, not proportional to row count).

**Plans**: TBD (estimated 3–5 plans)

Plans:
- [x] 07-01: Region services and selectors — create_region (with race-safe ID generation), update_region, delete_region (with shop-assigned guard), list_regions; full test suite
- [ ] 07-02: Region API viewset and URLs — RegionViewSet (TenantScopedViewSet), serializers, /org/regions/ URL; query-count CI test
- [x] 07-03: Regions React widget — list with empty state, Create modal (auto-ID, duplicate error), Edit modal (no ID auto-update in edit mode), Delete flow (blocking popup + confirmation popup); integration with toast system

---

### Phase 8: Shops
**Goal**: Org Admins can create and manage shops — connected via Google OAuth or manual Place ID — with allocation enforcement, connection status visibility, and key management.
**Depends on**: Phase 7 (Region FK required for Shop creation)
**Requirements**: SHOP-01, SHOP-02, SHOP-03, SHOP-04, SHOP-05, SHOP-06, SHOP-07, SHOP-08, SHOP-09, SHOP-10, SHOP-11, SHOP-12, SHOP-13, SHOP-14, SHOP-15, SHOP-16, SHOP-17, SHOP-18, SHOP-19, SHOP-20, SHOP-21, XMOD-01, XMOD-03, XMOD-04
**Success Criteria** (what must be TRUE):
  1. The Shops list at /admin/org/shops shows the allocation counter "Shops (X / Y)" and the "+ Add Shop" button is visually disabled with a tooltip when at limit; the list supports search (name, address), Status filter (All/Active/Inactive), and Region filter; pagination works with 10/25/50/100 rows-per-page selector.
  2. The Create Shop modal offers a "Connect with Google" radio that opens an OAuth popup (~600×700px); after successful OAuth, the modal shows a success row with connected listing name and "Change connection" link; popup close/deny/error/no-listings each show the correct inline message; the flow works in Safari (synchronous window.open before any async call) and falls back to polling via a 30-second Redis key when postMessage is unavailable due to COOP.
  3. The Create Shop modal "Enter manually" radio shows Google Place ID and API Key fields; both are validated against the Google Places API on submit; the OAuth refresh token and API key are never transmitted to the browser and are stored Fernet-encrypted at rest.
  4. Shop Details modal shows all fields in a read-only two-column grid with the Connection Status pill (Connected via Google / Connected via API key / Connection error / Quota exceeded) and footer action buttons; Edit modal pre-fills all editable fields; connection method and Place ID are locked in edit mode.
  5. Deactivating a shop shows an amber confirmation popup stating the slot remains used; activating shows a blue confirmation; the allocation counter updates transactionally on every create/activate/deactivate with no race condition under concurrent admin sessions (enforced via `select_for_update()`).

**Notes:**
- `Cross-Origin-Opener-Policy: same-origin-allow-popups` must be set as a scoped override on the OAuth initiation view only (the global production.py setting remains `same-origin`). Implement via a custom middleware or per-view response header.
- GBP API production approval from Google is a non-code prerequisite for Phase 8 to ship to production. The code can be fully built and tested against a sandbox/development GBP account, but production launch is gated on approval status.
- Deactivated shops are excluded from Team member scope selectors (XMOD-03 enforcement on the Shop layer: the selector used by Team modals filters `is_active=True`).
- CI query-count test for the Shops list endpoint required (fixed ceiling, not proportional to row count).

**Plans**: 7 plans (6 waves) — includes 2 gap-closure plans (08-06, 08-07)

Plans:
- [x] 08-01-PLAN.md — Google integrations layer (apps/integrations/google/: oauth.py, places.py, exceptions.py); httpx + tenacity deps; full test suite with mocked HTTP
- [x] 08-02-PLAN.md — Shop services and selectors + ShopAuditLog model/migration: create_shop (allocation enforcement with select_for_update), update_shop, activate/deactivate, reveal_api_key, rotate_api_key, reconnect_oauth, list_shops (search/filter), get_allocation_status, get_has_regions
- [x] 08-03-PLAN.md — Shop API viewset + URLs + OAuth views: ShopViewSet (TenantScopedViewSet) with custom @action endpoints, OAuth start/callback views with scoped COOP header, allocation envelope, cross-tenant + query-count CI tests
- [x] 08-04-PLAN.md — Shops list React widget: types/api/useShops hook, ConnectionStatusPill, ShopRowActionsMenu, ShopTable with search/status/region filters and pagination, Empty States A (no regions) and B (no shops), Vite + template wiring
- [x] 08-05-PLAN.md — Shop create/edit/details/action modals + OAuth popup orchestrator: synchronous window.open, postMessage with origin verification, Redis polling fallback, Deactivate/Activate confirms (amber/blue), Reveal Key (30s auto-mask + audit log), Rotate Key, Reconnect Google
- [x] 08-06-PLAN.md — Gap closure (backend): drop MANUAL ConnectionMethod + api_key field + city/state/zip_code columns; migration 0003; remove RotateKeySerializer, reveal_key/rotate_key viewset actions, reveal_api_key/rotate_api_key services; trim list_shops search; cleanup tests
- [ ] 08-07-PLAN.md — Gap closure (frontend): drop MANUAL from ConnectionMethod TS type; remove city/state/zip/api_key from types/payloads; delete RevealKeyModal/RotateKeyModal; trim CreateShopModal/EditShopModal/ShopDetailsModal/ShopTable/ShopModals; restyle Connect Google button to brand yellow primary

---

### Phase 9: Team
**Goal**: Org Admins can invite, configure, and manage team members — assigning Managers full-access or Staff scoped to specific regions and stores — with self-protection, last-manager guard, and a complete invitation acceptance flow.
**Depends on**: Phase 8 (Shops must exist for Staff scope selectors; InvitationToken purpose enum step 1 from Phase 6 must be present)
**Requirements**: TEAM-01, TEAM-02, TEAM-03, TEAM-04, TEAM-05, TEAM-06, TEAM-07, TEAM-08, TEAM-09, TEAM-10, TEAM-11, TEAM-12, TEAM-13, TEAM-14, TEAM-15, TEAM-16, TEAM-17, TEML-01, TEML-02, XMOD-03
**Success Criteria** (what must be TRUE):
  1. The Team list at /admin/org/team shows Member Name + Email, Role badge (Manager/Staff), Access chips (all-stores crown for Manager; region/store chips with "+N more" for Staff), Status badge, Invited Date, Enabled toggle, Edit and Remove buttons; three stats cards (Total Members, Managers, Active Members) show live counts; a search input and Region/Store filter dropdowns work correctly (Store dropdown narrows when a Region is selected).
  2. The Add Team Member modal accepts Name, Email, and Role; selecting Staff reveals Region multi-select and Store multi-select (only active stores appear); submitting sends a Team Invitation email with a 48-hour token and adds a Pending row to the list with a "Invitation sent to {email}." toast.
  3. Enabling/disabling a team member from the Enabled toggle works as specified — disable shows an amber confirmation popup and immediately terminates all active sessions for that user; enable is one-click with no confirmation; a disabled user attempting to log in sees "Your account has been disabled. Contact your administrator." on the login form.
  4. Removing a team member shows a red confirmation popup; on confirm, access is revoked, all sessions are terminated, and any pending invitations are invalidated; self-protection (cannot remove/disable/demote self) and last-manager guard (cannot remove last Manager) are enforced both in the UI (disabled buttons + tooltips) and at the API layer (403).
  5. The team invitation acceptance page at /invite/accept/{token}/ pre-fills Name and locks Email; on success, the account is created with the invited role, the user is auto-logged in, and redirected to /admin/org/dashboard (Manager) or a Staff welcome placeholder; both Team Invitation and Team Invitation Resent emails render correctly in HTML and plain-text with all required context (inviter name, organisation, role, assigned regions/stores for Staff).

**Notes:**
- `StaffAccessScope` prefetch must use `Prefetch('access_scopes', queryset=StaffAccessScope.objects.select_related('region', 'shop'), to_attr='prefetched_scopes')` on both FK branches; a CI query-count test asserting ≤4 queries for 20 Staff Admins with 3 scopes each is required from day one.
- InvitationToken purpose enum step 2 (backfill existing rows to `purpose=ORG_ADMIN_INVITE`, make non-null) must be completed in this phase before Staff invitation tokens can be issued.
- The invitation acceptance view (`invite_accept_view` in `apps/accounts/views.py`) must branch on `InvitationToken.purpose` to route Org Admin invitations through the existing activation flow and Staff/Manager invitations through the new Team acceptance flow.
- XMOD-03 (deactivated shops excluded from scope selectors) is enforced on the Team side by using the `list_shops(active_only=True)` selector for scope multi-selects in Add and Edit modals.

**Plans**: TBD (estimated 5–6 plans)

Plans:
- [ ] 09-01: InvitationToken purpose enum step 2 — data migration backfill + non-null constraint; UserInvitation model additions; team.py service layer (invite_member, update_member, enable_member, disable_member, remove_member, resend_invitation); full test suite
- [ ] 09-02: Team API viewset and URLs — TeamViewSet (TenantScopedViewSet), StaffAccessScope serializers, /org/team/ URL, invitation acceptance view (purpose-branching); query-count CI test
- [ ] 09-03: Team email templates — team_invitation.html + team_invitation.txt (inviter name, org, role, regions/stores for Staff); team_invitation_resent.html + team_invitation_resent.txt; send_team_invitation_email service; test assertions (recipient, subject, HTML + text bodies)
- [ ] 09-04: Team list React widget — columns (name, role badge, access chips with "+N more", status badge, invited date, enabled toggle, edit/remove buttons), stats cards, search/filter/pagination, solo-user info banner
- [ ] 09-05: Team add/edit/action modals — Add modal (role selector, dynamic scope selects, active-shops-only filter), Edit modal (role change shows/hides scopes), Disable confirmation + session termination, Remove confirmation, Resend Invitation confirmation; self-protection + last-manager guard in UI + API

---

## Progress

**Execution Order:** 6 → 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 6. Org Admin Shell | v0.2-org-admin | 3/5 | In Progress | - |
| 7. Regions | v0.2-org-admin | 0/3 | Not started | - |
| 8. Shops | v0.2-org-admin | 6/7 | In progress | - |
| 9. Team | v0.2-org-admin | 0/5 | Not started | - |

---

<details>
<summary>v1.0 — Superadmin Module (Phases 1–5) — SHIPPED 2026-04-27</summary>

5 phases, 24 plans, 52/52 requirements. Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>
