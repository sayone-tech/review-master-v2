# Feature Landscape

**Domain:** Organisation Admin Module — multi-tenant SaaS review management platform (v0.2-org-admin milestone)
**Researched:** 2026-04-27
**Confidence:** MEDIUM-HIGH

This document covers the feature landscape for four new capability areas being added on top of the existing Superadmin control plane: Shell, Regions, Shops, and Team. It answers three targeted questions: (a) production-grade Google Business Profile OAuth popup flow, (b) hierarchical access scopes (region → shop) for team members, and (c) resource allocation enforcement UX.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features Org Admins expect from day one. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Org Admin sidebar shell with role-aware navigation | Every SaaS has a role-specific sidebar; Org Admins must not see Superadmin pages | LOW | Reuse existing sidebar component; swap nav items by role. Already scaffolded in v1.0 activation redirect |
| Dashboard landing page with welcome + setup state | Users need orientation on first login; "what do I do next?" is a universal SaaS problem | LOW | Static Django template; show setup checklist banner until first shop created; no API call required |
| Profile page (name change + password change) | Basic account hygiene; every dashboard has it | LOW | Reuse existing Superadmin profile views/services; only permission class differs |
| Regions list — searchable, paginated | Grouping entities are useless without a browsable list | LOW | Server-side pagination; search by name/ID; empty state with CTA |
| Create region with auto-generated ID | Users expect the system to assign a stable, human-readable code (e.g. REG-001); manual ID entry is error-prone | LOW | Prefix + zero-padded sequential counter scoped per org; see ID generation notes below |
| Edit region name | Names change; editing is table stakes | LOW | Modal reusing create form; ID is read-only after creation |
| Delete region (blocked when shops assigned) | Prevents orphaned shops; referential integrity feedback is expected | LOW | Backend enforces block; frontend shows inline explanation: "Remove all shops from this region first" |
| Shops list — searchable, filterable, paginated with allocation counter | Primary daily surface for Org Admins managing locations | MEDIUM | Show "X of Y shops used" header counter; filter by status (Active/Inactive) and region; server-side |
| Create shop via Google Business Profile OAuth | Connecting a real location to GBP is the core value proposition | HIGH | Full OAuth popup flow — see OAuth section below |
| Create shop via manual Place ID entry | Fallback for users who cannot complete OAuth; or for testing | MEDIUM | Validate Place ID format; show preview of resolved business name before save |
| View / edit shop details | Users need to update shop names, regions, metadata | LOW | Modal or detail page; Google connection status shown prominently |
| Activate / deactivate shop | Temporarily suspend a location without deleting it | LOW | Confirmation popup; deactivated shops do not count toward Google sync |
| Google reconnect (re-auth) per shop | Tokens expire or are revoked; reconnect is expected | MEDIUM | Same OAuth popup flow; preserves existing shop data; does not create new shop record |
| Shop allocation counter enforcement | Org Admin must not create shops beyond their Superadmin-allocated limit | MEDIUM | Hard block at backend; UI disables "Add Shop" button and shows "X of Y used — contact your administrator to increase your limit" banner |
| Invite team member (Manager or Staff) | Every SaaS with team features has invitations | MEDIUM | Reuse Phase 1 invitation token infrastructure; new invitation purpose enum value |
| Assign Manager role (full org access) | Managers need to act on behalf of the Org Admin | LOW | No scope selection needed; Manager = full access within the organisation |
| Assign Staff role with region/shop scope | Staff restricted to specific locations is the operational model for multi-location businesses | MEDIUM | Multi-select of regions and/or individual shops at invite time; stored in StaffAccessScope junction table |
| Team list — searchable, with status badges | Admins need to see who's active and who's still pending | LOW | Status: Active / Pending / Disabled; search by name/email |
| Edit team member scope and role | Scope changes as staff responsibilities evolve | MEDIUM | Existing scope rows replaced atomically; cannot change role from Manager to Staff if they are the last Manager |
| Enable / disable team member | Suspend without removing | LOW | Confirmation popup; disabled users cannot log in |
| Remove team member | Permanently remove access | LOW | Confirmation; last-manager guard must prevent removing the last active Manager |
| Resend invitation to pending team member | Invitation tokens expire after 48h; resend is expected | LOW | Invalidates prior token; rate-limited at 5/hour (reuse existing throttle) |
| Team invitation email and acceptance page | User must receive email and be able to set password | MEDIUM | New email template (team invitation); acceptance page reuses Phase 1 activation view with purpose-aware routing |
| Self-protection: cannot disable or remove yourself | Universal SaaS rule | LOW | Permission check: `request.user != target_user` |
| Last-manager guard | Cannot leave organisation with zero active Managers | LOW | Backend check before disable/remove/role-change operations |

---

### Differentiators (Competitive Advantage)

Features that elevate the product above baseline. Not universally expected, but meaningfully improve day-to-day operations.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Google Business Profile name preview during shop creation | Before saving, show resolved business name and address from the Place ID / OAuth account — "Is this the right location?" reduces wrong-shop errors | MEDIUM | Requires a pre-save API call to GBP or Places API to resolve the Place ID; show in modal before final "Create" |
| OAuth popup with non-blocking parent modal | User can start shop creation in a modal, trigger OAuth in a popup, and return to the same modal state — no page navigation | HIGH | postMessage from callback page to parent window; modal remains open during OAuth; see OAuth UX section for edge cases |
| Connection status badge per shop | "Connected · Syncing" / "Token expired — Reconnect" / "Manual (no OAuth)" gives instant health visibility | LOW | Derive from stored token state; no extra API call needed |
| Inline region filter on shop list | Staff users are region-scoped; Org Admins want to view by region quickly | LOW | Region dropdown on list filter bar; pre-filtered when navigated from Region detail |
| Region detail page showing assigned shops | Navigating from a region to its shops is a natural mental model for multi-location admins | LOW | Simple filtered shop list view; reuse shop list component |
| Invitation context-aware acceptance page | "You've been invited by [Org Admin Name] to join [Org Name] as a [Manager / Staff]" reduces confusion | LOW | Pass role and inviter name in email template and in activation view context |
| Shop API key display + regenerate | Some integrations require per-shop API keys for external use | MEDIUM | UUID generated at shop create; regenerate action with confirmation; show once, then mask |
| Last-seen sync timestamp per shop | Tells admin whether Google reviews are actually being fetched | LOW | `last_synced_at` field on Shop; displayed on shop detail/list |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features to deliberately NOT build in this milestone.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Attribute-based or custom role creation | Power admins want fine-grained control | Designing a general-purpose permission builder is a separate product; the Manager/Staff split covers 95% of real use cases at this stage | Two hardcoded roles with region/shop scope cover the use case |
| Real-time review dashboard in this milestone | Org Admins want to see reviews | Reviews require GBP sync jobs (Phase 3+); building the UI before the data pipeline creates a useless empty page | Defer to reviews module; show "reviews coming soon" placeholder on dashboard |
| Bulk shop import via CSV | Power admins at large chains request this | Parsing, validation, rollback, OAuth-per-row, and partial failure handling add weeks of complexity | Build single-shop create solidly first; batch import is a v2 feature |
| Staff Admin dashboard in this milestone | Staff members need their own view | Staff Admin dashboard requires understanding what Staff can actually do with reviews; that depends on the reviews module | Block out the role; show "coming soon" after login |
| Google-side user management (add location admins via API) | Admins want to manage GBP access from the app | GBP API does not expose location admin management to third-party apps | OAuth per-location is the correct model; document this limitation |
| Automatic token refresh in background during OAuth popup | Simplify the reconnect experience | Background token refresh creates security surface; OAuth popup is explicit consent by design | Explicit reconnect flow on `invalid_grant`; notify Org Admin by email and in-app status badge |
| Nested region hierarchy (regions within regions) | Large chains have districts, areas, regions | A three-level hierarchy adds query complexity, scope evaluation complexity, and UI complexity with marginal real-world benefit at this stage | Two-level flat model (Region → Shop) is sufficient for the majority of use cases |
| Inline row editing on team or shop lists | Power users like editing in place | Accidental edits; breaks keyboard navigation; harder to validate | Dedicated edit modal triggered by action menu |
| Email address change for team members | Admin wants to fix a typo | Email is the identity; changing it without a verification loop creates account takeover risk | Disable the field post-creation; document that the member must be removed and re-invited |

---

## Feature Dependencies

```
Org Admin Shell (sidebar + layout)
  └──requires──> Existing design system (v1.0 global components) [ALREADY BUILT]
  └──requires──> IsOrgAdmin permission class [ALREADY BUILT]
  └──enables──>  All Org Admin views (regions, shops, team, profile)

Regions Module (list, create, edit, delete)
  └──requires──> Org Admin Shell
  └──requires──> Region model + migration
  └──blocks──>   Shop creation (shops must belong to a region)

Shops Module
  └──requires──> Regions Module (region FK on Shop, region filter on list)
  └──requires──> Google OAuth infrastructure (apps/integrations/google/oauth.py)
  └──requires──> Allocation counter enforcement (Organisation.number_of_stores already set by Superadmin)
  └──enables──>  Google review sync (Phase 3)
  └──enables──>  Staff scope assignment (StaffAccessScope references shops)

Google OAuth Popup Flow
  └──requires──> GCP OAuth credentials configured (client_id, client_secret, redirect URI)
  └──requires──> /integrations/google/oauth/callback/ endpoint (receives auth code)
  └──requires──> Encrypted refresh token storage (django-cryptography or Fernet)
  └──delivers──> Connected Shop record with valid tokens

Team Module (invite, manage)
  └──requires──> Org Admin Shell
  └──requires──> Invitation token infrastructure [ALREADY BUILT — extend with purpose enum]
  └──requires──> Regions Module (for scope multi-select at invite time)
  └──requires──> Shops Module (for individual shop scope at invite time)
  └──requires──> StaffAccessScope model + migration
  └──soft-requires──> Staff Admin dashboard (invited Staff members need somewhere to land)

Team Invitation Email + Acceptance
  └──requires──> send_transactional_email() helper [ALREADY BUILT]
  └──requires──> New email template: emails/team_invitation.html + .txt
  └──requires──> UserInvitation model (rename/extend OrganisationInvitation with purpose enum)
  └──requires──> Activation view extended to route by invitation purpose

Profile Page
  └──requires──> Existing Superadmin profile services [ALREADY BUILT — no changes needed]
  └──requires──> Org Admin Shell (for correct sidebar)
```

---

## MVP Sequencing

### Must-have — build in this order

Phase ordering is dictated by the dependency graph above.

1. **Org Admin Shell** — sidebar, layout, dashboard placeholder. All subsequent pages need this container. LOW complexity. No blockers.
2. **Regions module** — list, create (auto-ID), edit, delete. Required by shops for the region FK and by team for scope selection. LOW-MEDIUM complexity.
3. **Shops module (without OAuth first)** — list with allocation counter, create via manual Place ID, activate/deactivate, edit. Unblocks Staff scope assignment. MEDIUM complexity. Build OAuth popup as a separate sub-phase.
4. **Google Business Profile OAuth popup** — full popup flow, postMessage, token storage, connection status badge, reconnect. HIGH complexity. Treated as its own work unit.
5. **Team module** — invite (Manager + Staff scope), list, edit scope, enable/disable, remove, resend. Depends on regions and shops being live so scope multi-selects are populated. MEDIUM complexity.
6. **Team invitation email + acceptance** — new email template, purpose-aware activation view extension. Depends on UserInvitation model changes. MEDIUM complexity.
7. **Org Admin profile page** — reuses existing services; just a permission class swap and sidebar context change. LOW complexity. Can be built in any phase.

### Low-complexity differentiators worth including in this milestone

- Connection status badge per shop (LOW, high operational value, required for reconnect UX)
- Last-seen sync timestamp on shop list (LOW, useful as soon as Phase 3 sync exists)
- Invitation context-aware acceptance page copy (LOW, single template change)
- Self-protection + last-manager guard (LOW, always paired with invite/enable/disable implementation)

### Defer to future milestones

- Staff Admin dashboard — needs reviews module to be meaningful (Phase 3+)
- Google Business Profile name preview during shop creation — valuable but requires a secondary API call; can ship after initial OAuth is stable
- Region detail page showing assigned shops — useful quality-of-life addition; not blocking for launch
- Bulk shop import via CSV — post-PMF feature

---

## Detailed UX Pattern Notes

### (a) Google Business Profile OAuth Popup Flow

**Production-grade pattern (recommended):**

1. Org Admin clicks "Connect via Google" inside the Create Shop modal (or Reconnect button on shop detail).
2. Parent page calls `window.open(oauthStartUrl, "gbp_oauth", "width=600,height=700")`. The popup URL is a Django view (`/integrations/google/oauth/start/?shop_id=<id>&state=<csrf_state_token>`) that immediately redirects to Google's authorization endpoint.
3. Google shows the OAuth consent screen inside the popup. The user grants access.
4. Google redirects to the registered callback URL: `/integrations/google/oauth/callback/?code=<auth_code>&state=<state>`.
5. The Django callback view: (a) validates the state token against session, (b) exchanges the auth code for access + refresh tokens, (c) encrypts and stores the refresh token on the Shop record, (d) closes itself by rendering a minimal HTML page that calls `window.opener.postMessage({status: "success", shopId: "<id>"}, window.location.origin)` then `window.close()`.
6. Parent page has a `window.addEventListener("message", handler)` that listens for this postMessage, validates origin (must equal `window.location.origin`), and on success refreshes the shop list / updates the shop record's connection status badge.

**Critical edge cases to handle:**

| Edge Case | Cause | Handling |
|-----------|-------|---------|
| Popup blocked by browser | User has popup blocker or first-time browser prompt | Detect `window.open()` returning null; show fallback message: "Popup was blocked. Please allow popups for this site and try again." |
| COOP header breaks `window.opener` | Google's OAuth pages sometimes send `Cross-Origin-Opener-Policy: same-origin`, which severs `window.opener` | Use polling fallback: after opening popup, poll `/integrations/google/oauth/status/?shop_id=<id>` every 2s until status changes or popup is detected closed (via `popup.closed`). Server-side, the callback view writes status to a short-lived Redis key (30s TTL) that the status endpoint reads. |
| User closes popup without completing OAuth | Browser `window.closed` polling detects closure | Cancel polling loop; show informational message: "Authorization cancelled. Your shop was not connected." |
| `invalid_grant` on first token exchange | Stale auth code, clock skew, or reuse | Return error to popup; popup postMessages `{status: "error", reason: "auth_failed"}`; parent shows inline error in modal |
| `invalid_grant` on subsequent token refresh (background sync) | Token revoked by user, password change, or 6-month inactivity | Mark shop `connection_status = EXPIRED`; do not retry; notify Org Admin via email + show reconnect badge on shop list |
| OAuth app in "Testing" status | Tokens expire in 7 days | Move app to "Production" published state in GCP before launch; add pre-launch checklist item |
| User grants access with wrong Google account | OAuth succeeds but Place ID doesn't match | After token exchange, verify the authorized account has access to the expected location; if not, set connection to ERROR and prompt reconnect with correct account |

**Google Business Profile OAuth scopes:**
The current required scope is `https://www.googleapis.com/auth/business.manage`. The older `plus.business.manage` scope is deprecated. Request `offline` access (to get a refresh token) and `prompt=consent` to force the refresh token to be issued even if the user has previously granted access (important for reconnect flows).

**Token storage:**
Refresh tokens must be encrypted at rest. Use Fernet symmetric encryption with a key stored in GCP Secret Manager. Never store raw tokens in the database. `access_token` does not need to be stored — it can be re-fetched from the refresh token on demand.

---

### (b) Hierarchical Access Scopes (Region → Shop) for Team Members

**The two-role, two-scope model (recommended for this milestone):**

| Role | Access | Scope Model |
|------|--------|-------------|
| Manager | Full access to all shops, all regions, all team features within the organisation | No scope record needed; role alone grants access |
| Staff | Scoped read access (future: review reply) to specific regions and/or individual shops | `StaffAccessScope` rows: one per (user, region) or (user, shop) |

**How scope evaluation works in practice:**

When a Staff user makes an API request, the `TenantScopedViewSet` base class already enforces `organisation_id`. An additional `StaffScopedMixin` further filters:

```
queryset.filter(
    Q(region_id__in=user.staff_scopes.filter(scope_type="REGION").values("region_id")) |
    Q(id__in=user.staff_scopes.filter(scope_type="SHOP").values("shop_id"))
)
```

**Scope assignment UX at invite time:**

- Invite modal shows a two-section scope picker: "By Region" (checkboxes for each region) and "By Individual Shop" (checkboxes for shops not covered by a selected region).
- If a region is selected, all current and future shops in that region are implicitly included — this is the expected behaviour in location-management SaaS.
- At least one scope item must be selected for Staff role. Manager role disables the scope picker.

**Scope change on edit:**

- Editing a Staff member's scope replaces all existing `StaffAccessScope` rows atomically inside `@transaction.atomic`.
- If a region is removed from scope and the user had explicit individual shop scopes within that region, those shop scopes are also removed (region supersedes individual shop; removing the region removes all its children from scope).

**Industry pattern context:**

The "administrative units" / "data-level RBAC" pattern where scope = set of allowed resources is standard across location-management SaaS (franchise management, retail operations tools). Three tiers (org → region → shop) with role × scope is the dominant pattern. Deeper nesting (district → area → region → shop) is deferred to later milestones per the anti-features rationale.

---

### (c) Resource Allocation Enforcement (Shop Limits)

**What Superadmins control:** The `Organisation.number_of_stores` field (already implemented in v1.0) defines how many active shops an Org Admin can create.

**Hard limit enforcement (recommended pattern):**

- Backend: `create_shop()` service checks `active_shop_count < org.number_of_stores` before creating. If at limit, raises a validation error (HTTP 400) with a structured error body: `{code: "SHOP_LIMIT_REACHED", limit: 5, current: 5}`.
- The check must use `select_for_update()` inside a transaction to prevent race conditions when two simultaneous creation requests race against the same counter.

**Frontend enforcement (UX patterns from research):**

| State | UI Behaviour |
|-------|-------------|
| Under limit | "Add Shop" button enabled; header shows "3 of 5 shops used" |
| At limit (0 remaining) | "Add Shop" button is visually disabled (greyed out, cursor: not-allowed); counter turns amber: "5 of 5 shops used — contact your administrator to increase your limit"; clicking the disabled button shows a tooltip explaining the limit |
| Over limit (if allocation is reduced retroactively) | Existing shops remain; no new shops can be created; banner shown at top of shops list: "Your shop limit has been reduced. You are currently over your limit. New shops cannot be added." |

**Do NOT soft-block (warn but allow):** Soft-blocking erodes trust in the limit concept and creates billing disputes. Hard block is the industry standard. The UX explains the situation and points the user to the resolution action (contact administrator).

**Counter source of truth:** Always count `Shop.objects.filter(organisation=org, is_active=True).count()` at creation time — do not store a denormalised counter that could drift. Annotating the Organisation queryset with `active_shop_count` via `annotate()` is correct for list display; the `select_for_update` check at creation time is the authoritative gate.

---

### Auto-Generated Region IDs

The industry pattern (pioneered by Stripe, now widespread) is a type-prefixed, sequential, human-readable ID. For Regions:

- Format: `REG-{org_short_code}-{zero_padded_sequence}` — e.g., `REG-ACME-001`
- Or simpler: `REG-{sequential_number_per_org}` — e.g., `REG-001`, `REG-002`
- The ID is generated at create time, stored as a separate string field (not the database PK), is immutable after creation, and is used for display and reference only.
- Implementation: use `F()` expressions + annotation or a custom manager method to get the next sequence number per organisation inside a `select_for_update()` guard.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Org Admin Shell (sidebar + layout) | HIGH | LOW | P1 |
| Regions — full CRUD | HIGH | LOW | P1 |
| Shops — list + manual create + edit | HIGH | MEDIUM | P1 |
| Shop allocation counter enforcement | HIGH | MEDIUM | P1 |
| Google OAuth popup flow | HIGH | HIGH | P1 |
| Google token reconnect flow | HIGH | MEDIUM | P1 |
| Team invite (Manager + Staff scope) | HIGH | MEDIUM | P1 |
| Team list + enable/disable/remove | HIGH | LOW | P1 |
| Team invitation email + acceptance | HIGH | MEDIUM | P1 |
| Self-protection + last-manager guard | HIGH | LOW | P1 |
| Connection status badge per shop | MEDIUM | LOW | P1 (pairs with OAuth) |
| Profile page reuse | MEDIUM | LOW | P1 |
| Popup blocked fallback (polling) | HIGH | MEDIUM | P1 (required for OAuth reliability) |
| Region detail → shops drill-down | MEDIUM | LOW | P2 |
| GBP name preview before shop save | MEDIUM | MEDIUM | P2 |
| Last-seen sync timestamp on shop list | LOW | LOW | P2 |
| Shop API key management | LOW | MEDIUM | P3 |
| Bulk shop import CSV | LOW | HIGH | Defer |
| Staff Admin dashboard | HIGH | HIGH | Defer (needs reviews module) |

---

## Open Questions

- **Staff Admin landing page:** What page does an accepted Staff invitation redirect to? A "reviews coming soon" placeholder is needed if the Staff Admin dashboard is deferred.
- **Manual Place ID validation:** Should the create-shop flow validate the Place ID against the Google Places API immediately, or accept it unvalidated and fail later during sync? Immediate validation gives better UX; requires Places API to be enabled and adds a network call to the create path.
- **Region ID format:** Confirm whether the org short code should be embedded in the Region ID (e.g. `REG-ACME-001`) or just a scoped sequence (e.g. `REG-001`). The former is more readable in external references; the latter is simpler to generate.
- **Manager can manage team:** Clarify whether Managers can invite/edit/remove Staff members, or only Org Admins can. This determines the permission classes on Team viewset endpoints.
- **OAuth app approval status:** The GBP OAuth app may require Google verification for production access (especially for sensitive scopes). This can take 4–6 weeks. Must be initiated well before launch.
- **Shop deactivation and active count:** Does deactivating a shop free up a slot in the allocation counter? Confirm the business rule (deactivated shops counting against limit is common to prevent quota gaming).

---

## Sources

- Google Business Profile OAuth implementation: [Implement OAuth with Business Profile APIs](https://developers.google.com/my-business/content/implement-oauth), [OAuth setup](https://developers.google.com/my-business/content/oauth-setup)
- Google OAuth scopes: [OAuth 2.0 Scopes for Google APIs](https://developers.google.com/identity/protocols/oauth2/scopes)
- Google API deprecation schedule: [Deprecation schedule](https://developers.google.com/my-business/content/sunset-dates)
- OAuth popup + postMessage pattern: [How we use a popup for Google and Outlook OAuth — DEV Community](https://dev.to/dinkydani21/how-we-use-a-popup-for-google-and-outlook-oauth-oci), [Leave Me Alone blog](https://leavemealone.com/blog/how-to-oauth-popup/)
- COOP header and OAuth popups: [Chrome for Developers — restrict-properties](https://developer.chrome.com/blog/coop-restrict-properties), [Next.js Discussion #51135](https://github.com/vercel/next.js/discussions/51135), [MDN COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Opener-Policy)
- `invalid_grant` handling: [Nango Blog — Google OAuth invalid_grant](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked/)
- Multi-tenant RBAC and scope patterns: [EnterpriseReady RBAC Guide](https://www.enterpriseready.io/features/role-based-access-control/), [Frontegg Roles and Permissions](https://frontegg.com/guides/roles-and-permissions-handling-in-saas-applications), [WorkOS multi-tenant architecture](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture)
- Quota enforcement UX patterns: [Indie Hackers — how to handle limits](https://www.indiehackers.com/post/how-do-you-handle-limits-in-your-saas-plans-3c4f7c692c), [SaaS Upgrade Prompt Examples](https://www.saasframe.io/patterns/upgrade-prompt)
- Human-readable ID patterns: [Designing APIs for humans: Object IDs](https://dev.to/4thzoa/designing-apis-for-humans-object-ids-3o5a)
- Team invitation flow: [How to onboard invited users — Userpilot](https://userpilot.com/blog/onboard-invited-users-saas/), [Designing an intuitive user flow for inviting teammates — PageFlows](https://pageflows.com/resources/invite-teammates-user-flow/)

---

*Feature research for: Organisation Admin Module (v0.2-org-admin)*
*Researched: 2026-04-27*
