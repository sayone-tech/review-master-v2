# Phase 9: Team - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admins can invite Managers and Staff members, configure Staff access scopes (regions +
stores), manage member lifecycle (enable/disable/remove/resend invitation), and the invitation
acceptance page allows new members to set their password and land on a role-appropriate
dashboard. Includes two email templates (initial invite + resend). Staff Admin views (their own
dashboard, scoped review access) are a separate future phase.

</domain>

<decisions>
## Implementation Decisions

### Staff scope selectors (TEAM-06, TEAM-08)
- **Independent selection** — Region multi-select and Store multi-select are fully independent.
  User can pick any combination of 0+ regions AND 0+ stores. Each selection creates its own
  `StaffAccessScope` row (`scope_type=REGION` or `scope_type=SHOP`).
- **Store list never narrows** — The Store dropdown always shows all active stores regardless of
  which regions are selected. XMOD-03 already requires deactivated shops excluded; no additional
  narrowing logic needed.
- **Validation:** At least 1 region or 1 store must be selected for Staff role. Manager role
  requires no scope selections.

### Invitation acceptance UX (TEAM-17)
- **Manager** → redirects to `/admin/org/dashboard/` after activation (full org admin shell).
- **Staff** → redirects to a simple welcome page within the org admin shell: heading
  "Welcome to {OrgName}" + body "Your account is ready. Your administrator will let you know
  when your access is set up." Minimal card body, same sidebar nav as the org admin shell.
  A placeholder URL like `/admin/org/welcome/` is acceptable for this phase.
- **Acceptance form:** Name field pre-filled from the invited user's `full_name` (set by the
  Org Admin at invite time), freely editable by the invitee. Email field displayed as locked
  (read-only). Password + confirm fields identical to existing ORG_ADMIN activation form.
- **invite_accept_view branching:** The view must check `invitation.purpose`:
  - `purpose=ORG_ADMIN` → existing `activate_account()` path → redirect `org_admin_dashboard`
  - `purpose=TEAM_MEMBER` → new `activate_team_member()` path → redirect by `invited_for_role`
  This is the "expand-contract step 2" referenced in ROADMAP.md notes.

### Row actions layout (TEAM-01, TEAM-13, TEAM-16)
- **Accepted members (Active / Disabled):** Edit (pencil icon) + Remove (trash icon) as inline
  icon buttons in the last column, always visible for eligible rows. Enabled toggle is its own
  separate column.
- **Pending members (invited but not yet accepted):** Resend (envelope icon) + Remove (trash
  icon) inline. Edit button is hidden/disabled for Pending rows — nothing meaningful to edit
  before acceptance.
- **Self-protection:** Edit and Remove buttons are disabled (with tooltip) on the Org Admin's
  own row. Enabled toggle is disabled on own row. Last-manager guard enforced at API layer.
- No three-dot dropdown menu — inline buttons only (unlike org-management RowActionsMenu).

### Solo-user banner (TEAM-05)
- **Position:** Above the table — the table always renders (even when empty), with the banner
  appearing above it as a subtle info strip.
- **Copy:** "You're the only member. Invite your team to get started." + inline
  "Add Team Member" link/button that opens the Add modal.
- **Trigger:** Banner shows when `team_member_count == 0` (i.e. the Org Admin is the only
  member). Once any invite is sent, the banner disappears.
- **Style:** Yellow info banner (same visual as the zero-regions setup banner in the org
  admin dashboard — `bg-yellow/10` strip with yellow left border or similar).

### Claude's Discretion
- Exact session termination implementation (disable/remove): Django's `is_active=False` is
  sufficient since the default authentication backend checks `is_active` on every request.
  The session records themselves can optionally be cleared from `django_session` table using
  the `User.pk` stored in session data — implement if needed for instant termination.
- `activate_team_member()` service signature and placement (`apps/accounts/services/team.py`)
- Staff welcome page URL slug and template structure
- `StaffAccessScope` bulk create/replace strategy on edit (delete all + recreate vs diff)
- Exact `+N more` truncation threshold for access chips (suggest: show 2, overflow rest)
- Query-count ceiling value for the team list (suggest: ≤5 queries for 20 members with 3 scopes)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements (MANDATORY)
- `.planning/REQUIREMENTS.md` §Team — TEAM-01 through TEAM-17 (all team requirements)
- `.planning/REQUIREMENTS.md` §Team Email Templates — TEML-01, TEML-02
- `.planning/REQUIREMENTS.md` §Cross-Module — XMOD-03 (deactivated shops excluded from scope selectors)
- `CLAUDE.md` §5 — Services/selectors pattern (all business logic in service functions)
- `CLAUDE.md` §6 — No-N+1 policy; `CaptureQueriesContext` test required for team list endpoint
- `CLAUDE.md` §12 — Transactional email via SES; `send_transactional_email` service helper
- `CLAUDE.md` §13 — pytest + factory-boy, 85% coverage minimum

### UI Design Contract (MANDATORY)
- `.planning/phases/09-team/09-UI-SPEC.md` — Full visual/interaction spec for all 7 surfaces:
  Team list, Add modal, Edit modal, Disable confirm, Remove confirm, Resend confirm, Acceptance page.
  All badge colors, chip types, spacing, typography, and component inventory are locked here.

### Data models (extend, don't recreate)
- `apps/accounts/models.py` — `User` (role, is_active, invited_by, invited_at, accepted_at),
  `InvitationToken` (purpose, invited_for_role, is_used, expires_at, hash_token()),
  `StaffAccessScope` (scope_type, region FK, shop FK, XOR constraint)
- `apps/accounts/migrations/` — latest migration is `0004_staffaccessscope.py`; Phase 9 adds
  migration to backfill existing tokens to `purpose=ORG_ADMIN` and make `purpose` non-null
  (expand-contract step 2)

### Existing invitation flow (extend, don't replace)
- `apps/accounts/views.py` — `invite_accept_view`: must be extended to branch on
  `invitation.purpose` (ORG_ADMIN continues existing path; TEAM_MEMBER routes to new path)
- `apps/organisations/services/organisations.py` — `activate_account()` for ORG_ADMIN path;
  new `activate_team_member()` analogous function needed for TEAM_MEMBER path

### Tenant security scaffold (inherit directly)
- `apps/common/viewsets.py` — `TenantScopedViewSet` base class
- `apps/common/permissions.py` — `IsOrgAdmin`, `IsOrgScoped`
- `apps/common/tests/fixtures.py` — `assert_query_ceiling`, `two_orgs_two_admins`

### Frontend canonical patterns (follow exactly)
- `frontend/src/widgets/shop-management/ShopTable.tsx` — inline action buttons, CustomEvent bus,
  row rendering, status badges via inline hex (JIT cannot generate dynamic class names)
- `frontend/src/widgets/shop-management/ShopModals.tsx` — modal orchestration, CustomEvent
  subscriptions, toast integration, state management pattern
- `frontend/src/widgets/shop-management/api.ts` — CSRF token + fetch pattern to replicate
- `frontend/src/widgets/modal/Modal.tsx` — reuse unchanged
- `frontend/src/widgets/modal/ConfirmModal.tsx` — reuse unchanged (amber/blue/red variants)
- `frontend/src/widgets/data-table/DataTable.tsx` — reuse unchanged; columns use accessor/label/rowKey API
- `frontend/src/lib/toast.ts` — `emitToast({ kind, title, msg })` API

### Phase 9 ROADMAP notes (MANDATORY — architectural constraints)
See `.planning/ROADMAP.md` Phase 9 **Notes** section for:
- `StaffAccessScope` prefetch strategy: `Prefetch('access_scopes', queryset=StaffAccessScope.objects.select_related('region', 'shop'), to_attr='prefetched_scopes')` — required from day one
- CI query-count test: ≤4 queries for 20 Staff Admins with 3 scopes each
- InvitationToken `purpose` backfill + non-null make is Phase 9 step 2 (Phase 6 was step 1)
- `invite_accept_view` must branch on `InvitationToken.purpose`
- `list_shops(active_only=True)` selector for scope multi-selects (XMOD-03 enforcement)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `User` model: all Team-required fields already exist (`role`, `is_active`, `invited_by`,
  `invited_at`, `accepted_at`, `organisation` FK)
- `InvitationToken` model: `purpose`, `invited_for_role`, `is_used`, `expires_at`, `hash_token()`
  all ready. `Purpose.TEAM_MEMBER` and `InvitedForRole.STAFF_ADMIN` / `ORG_ADMIN` already defined.
- `StaffAccessScope` model: fully defined with XOR constraint. No new fields needed.
- `Modal` + `ConfirmModal` + `DataTable` + `emitToast` — same as Phases 7 & 8, reuse as-is
- `shop-management/api.ts` — CSRF + fetch pattern: copy for `team-management/api.ts`
- `ShopTable.tsx` — inline icon button row actions and CustomEvent bus: follow exactly

### Established Patterns
- Services/selectors: all team business logic in `apps/accounts/services/team.py` (new file);
  read queries in `apps/accounts/selectors/` (check if exists; create if not)
- `transaction.atomic` required on: invite_member (create user + token), remove_member
  (revoke access + invalidate tokens), resend_invitation (invalidate old + create new),
  activate_team_member (mark token used + set accepted_at)
- React widget entrypoint follows `shop-management.tsx` pattern: reads initial data from
  Django-rendered JSON in `<script>` tags, mounts `TeamModals` + `TeamTable` into separate roots
- Inline hex for status badges and role badges (JIT cannot generate from ternary expressions)
- `CustomEvent` bus: TeamTable dispatches `team:open-edit`, `team:open-remove`,
  `team:open-disable`, `team:open-resend`; TeamModals subscribes

### Integration Points
- `apps/organisations/urls.py` `org_team` stub URL → Phase 9 replaces `org_stub_view` with
  real `team_list` Django view
- `apps/accounts/urls.py` → existing `invite_accept_view` at `/invite/accept/<token>/` gains
  purpose-based branching (same URL, extended logic)
- `apps/shops/selectors/shops.py` → `list_shops()` used for scope Store multi-select
  (must pass `active_only=True` per XMOD-03); check if `active_only` param exists or add it
- `CustomLoginView.form_valid()` — disabled user login message ("Your account has been
  disabled. Contact your administrator.") is handled by Django's existing `is_active=False`
  check in `ModelBackend.authenticate()`. TEAM-12 may only need the error message text
  customised on the login form, not a new code path.

</code_context>

<specifics>
## Specific Ideas

- Enabled toggle: wraps a checkbox or button styled as a pill toggle; must have a 44px minimum
  tap area (per UI-SPEC spacing table); disable (ON→OFF) triggers amber ConfirmModal before
  acting; enable (OFF→ON) fires immediately with no confirmation (TEAM-11)
- Access chips truncation: show up to 2 chips inline, then "+N more" overflow chip. This is a
  display-only decision — the full scope list is always stored; "+N more" is just UI truncation
- Staff welcome page copy: "Welcome to {OrgName}. Your account is ready. Your administrator
  will let you know when your access is configured." — minimal, friendly, no nav items needed
  beyond the sidebar shell
- Manager badge uses purple inline hex per UI-SPEC: `{ backgroundColor: "#F3E8FF", color: "#7C3AED" }`
- Staff badge uses existing tokens: `bg-line-soft` + `text-muted`

</specifics>

<deferred>
## Deferred Ideas

- Staff Admin views (scoped review dashboard, review list/response filtered by assigned
  regions/stores) — future phase, post-v0.2
- Audit log for team changes (who invited whom, when removed) — future phase
- Bulk invite via CSV — not in Phase 9 scope
- Staff access scope based on role type (e.g. "all future shops in a region" vs explicit list)
  — current model stores explicit FKs only; dynamic scope is a future enhancement

</deferred>

---

*Phase: 09-team*
*Context gathered: 2026-04-29*
