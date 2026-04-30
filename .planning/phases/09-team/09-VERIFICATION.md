---
phase: 09-team
verified: 2026-04-30T10:30:00Z
status: passed
score: 20/20 must-haves verified
gaps: []
human_verification:
  - test: "Visit /admin/org/team/ in a running dev server with an Org Admin login"
    expected: "Team list renders with stats cards, search input, region/store filter dropdowns, paginated table rows with RoleBadge, AccessChips, EnabledToggle, Edit and Remove icon buttons"
    why_human: "React widget visual rendering and interactive filtering require a live browser"
  - test: "Click '+ Add Team Member', fill in Staff role, select a region, submit"
    expected: "Pending row appears in the table, toast 'Invitation sent to {email}.', MailHog shows the team invitation email with yellow CTA, region name in the email body"
    why_human: "End-to-end invite flow combining API, email send, toast, and list refresh cannot be verified programmatically"
  - test: "Click the Enabled toggle ON for a non-self Staff member"
    expected: "Amber confirmation modal appears; on confirm the member row shows Disabled status and toast '{Name} disabled.'"
    why_human: "Modal interaction and toast display require browser"
  - test: "On a Pending row click the Resend (mail icon), confirm the blue modal"
    expected: "Old token invalidated, new invitation email in MailHog, toast 'Invitation resent to {email}.'"
    why_human: "Resend flow end-to-end requires live server + MailHog"
  - test: "Accept a TEAM_MEMBER invitation via /invite/accept/{token}/ as a Staff invitee"
    expected: "Role banner shows 'You're joining as Staff.', form pre-fills name, on submit user is logged in and redirected to /admin/org/welcome/"
    why_human: "Template rendering and redirect flow require browser"
---

# Phase 9: Team Management Verification Report

**Phase Goal:** Team Management — Org Admin can invite Staff Admins, manage their access (enable/disable/remove), and resend invitations via a React-powered team list UI.
**Verified:** 2026-04-30T10:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Migration 0005 backfills purpose=ORG_ADMIN (NOT NULL) before adding constraint | VERIFIED | `apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py`: RunPython at line 21 runs before AlterField at lines 22 and 31 |
| 2 | `invite_member()` creates User(is_active=False) + InvitationToken(TEAM_MEMBER) + StaffAccessScope rows atomically | VERIFIED | `services/team.py` line 49: `@transaction.atomic`; line 87: `purpose=InvitationToken.Purpose.TEAM_MEMBER`; lines 95-107: bulk_create scopes |
| 3 | `activate_team_member()` updates existing User (is_active=True, password, accepted_at) + marks token used with race guard | VERIFIED | `services/team.py` lines 114-145: `@transaction.atomic`, `select_for_update()` at line 126 |
| 4 | `resend_team_invitation()` nulls out old token's invited_user before creating new token (avoids OneToOne uniqueness) | VERIFIED | `services/team.py` line 249: `old_token.invited_user = None`; new token created at line 264 |
| 5 | `disable_member` / `remove_member` set is_active=False; `remove_member` raises LastManagerError for last active ORG_ADMIN | VERIFIED | `services/team.py` line 221: `raise LastManagerError`; lines 192-202: disable; lines 203-237: remove with guard |
| 6 | `send_team_invitation_email()` sends email with correct subject, recipient, both HTML and text variants | VERIFIED | `services/team.py` lines 271-320: context dict built, `send_transactional_email` called; confirmed by 6 passing tests in `test_team_emails.py` |
| 7 | `list_team_members()` uses N+1-safe Prefetch with to_attr='prefetched_scopes' meeting ≤4 query ceiling | VERIFIED | `selectors/team.py` line 34: `to_attr="prefetched_scopes"`; line 33: `select_related("region", "shop")`; confirmed by `test_list_team_members_query_count` asserting `max_queries=4` |
| 8 | Disabled user login shows "Your account has been disabled. Contact your administrator." | VERIFIED | `apps/accounts/forms.py` line 19: exact copy present |
| 9 | GET /api/v1/team/ returns paginated list with role, status, access_scopes via prefetch | VERIFIED | `views.py` line 104: `list_team_members()` called; `serializers.py` line 73: `getattr(instance, "prefetched_scopes", None)` |
| 10 | POST /api/v1/team/ creates invitation, sends email, returns Pending row | VERIFIED | `views.py` lines 112-135: `invite_member()` then `send_team_invitation_email()` then returns 201 |
| 11 | PATCH /api/v1/team/{id}/ updates name/role/scopes; Email field is locked at serializer layer | VERIFIED | `serializers.py` TeamMemberUpdateSerializer (lines 108-124) has no `email` field; `views.py` line 151: demotion guard inline |
| 12 | Self-protection: own row returns 403 for remove/disable/demote | VERIFIED | `views.py` lines 151, 188, 201: three 403 guards with exact error strings |
| 13 | Last-manager guard: removing/demoting last ORG_ADMIN returns 403 | VERIFIED | `views.py` lines 166-173: peer_managers count + 403 return; `services/team.py` line 221: LastManagerError |
| 14 | GET /api/v1/team/stats/ returns {total_members, managers, active_members} | VERIFIED | `views.py` stats action returns `get_team_stats()` result |
| 15 | /admin/org/team/ Django view renders React widget with seeded JSON (members, regions, active_shops, stats, current_user_id, manager_count) | VERIFIED | `organisations/views.py` line 172: `team_list`; `templates/team/team_list.html` lines 21-33: all 5 json_script IDs and data-* attrs present; `active_only=True` at line 195 (XMOD-03) |
| 16 | /invite/accept/{token}/ branches on purpose: TEAM_MEMBER → activate_team_member → role-based redirect | VERIFIED | `views.py` lines 336-380: purpose branching, STAFF_ADMIN redirects to `org_welcome`, ORG_ADMIN to `org_admin_dashboard` |
| 17 | /admin/org/welcome/ renders Staff welcome page with "Your account is ready" | VERIFIED | `templates/organisations/team_welcome.html` line 9 |
| 18 | TeamTable renders all required columns, CustomEvent bus, self-protection/last-manager UI guards | VERIFIED | `TeamTable.tsx`: DataTable at line 260; events dispatched at lines 134/153/163/178; guard tooltips at lines 190/192 |
| 19 | TeamModals orchestrator subscribes to all team:open-* events; confirm modals have correct amber/red/blue variants | VERIFIED | `TeamModals.tsx` lines 62-67: all 6 event subscriptions; inline enable at line 47; `DisableMemberModal` amber, `RemoveMemberModal` red, `ResendMemberInviteModal` blue |
| 20 | Email templates: team_invitation.html/txt + team_invitation_resent.html/txt have correct content, 600px max-width, brand yellow CTA, scope conditionals | VERIFIED | Templates confirmed: `Accept Invitation` CTA, `{{ accept_url }}`, `is_staff_role` conditional, `assigned_region_names/shop_names`, `#FACC15`, `width="600"`, `max-width:600px`; resent template has "earlier link is no longer valid" |

**Score:** 20/20 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py` | Data migration (RunPython + AlterField) | VERIFIED | 40 lines; RunPython before AlterField |
| `apps/accounts/services/team.py` | 8 team service functions | VERIFIED | 317 lines; all 8 functions present |
| `apps/accounts/selectors/team.py` | list_team_members + get_team_stats | VERIFIED | 74 lines; Prefetch to_attr='prefetched_scopes' present |
| `apps/accounts/exceptions.py` | LastManagerError only | VERIFIED | LastManagerError present; SelfProtectionError absent |
| `apps/accounts/serializers.py` | 4 serializer classes | VERIFIED | 124 lines; TeamMemberReadSerializer, Create, Update, StaffAccessScopeSerializer |
| `apps/accounts/views.py` | TeamViewSet + extended invite_accept_view | VERIFIED | 516 lines; TeamViewSet + purpose-branching present |
| `apps/accounts/api_urls.py` | DRF router for TeamViewSet | VERIFIED | `router.register(r"team", TeamViewSet, basename="team")` |
| `apps/accounts/forms.py` | Updated inactive copy | VERIFIED | Line 19: correct TEAM-12 message |
| `templates/team/team_list.html` | React mount template with JSON seeds | VERIFIED | All 5 json_script IDs and data-* attrs |
| `templates/accounts/team_invite_accept.html` | TEAM_MEMBER acceptance form with role banner | VERIFIED | "You're joining as" present |
| `templates/organisations/team_welcome.html` | Staff welcome page | VERIFIED | "Your account is ready" present |
| `templates/emails/team_invitation.html` | Initial invitation email | VERIFIED | Accept Invitation, scope conditionals, #FACC15, 600px |
| `templates/emails/team_invitation.txt` | Plain-text fallback | VERIFIED | `{{ accept_url }}` present |
| `templates/emails/team_invitation_resent.html` | Resend invitation email | VERIFIED | Resend notice present |
| `templates/emails/team_invitation_resent.txt` | Resend plain-text fallback | VERIFIED | `{{ accept_url }}` present |
| `frontend/src/widgets/team-management/types.ts` | TeamMemberRow, AccessScopeRow, TeamStats, TeamFilterParams | VERIFIED | All interfaces exported |
| `frontend/src/widgets/team-management/api.ts` | 8 API functions + CSRF + /api/v1/team/ | VERIFIED | All functions present; X-CSRFToken header |
| `frontend/src/widgets/team-management/useTeam.ts` | Filter hook with setSearch/setRegion/setShop/setPage | VERIFIED | All setters exported |
| `frontend/src/widgets/team-management/RoleBadge.tsx` | Manager/Staff role badges | VERIFIED | #F3E8FF inline hex present |
| `frontend/src/widgets/team-management/AccessChips.tsx` | Crown/All stores for Manager; chips + overflow for Staff | VERIFIED | Crown icon + "All stores" |
| `frontend/src/widgets/team-management/EnabledToggle.tsx` | Controlled switch with role="switch" | VERIFIED | `role="switch"` at line 26 |
| `frontend/src/widgets/team-management/TeamStatsCards.tsx` | 3 stats cards | VERIFIED | File exists, substantive |
| `frontend/src/widgets/team-management/SoloMemberBanner.tsx` | Solo member banner | VERIFIED | File exists, substantive |
| `frontend/src/widgets/team-management/TeamEmptyState.tsx` | Empty state | VERIFIED | File exists, substantive |
| `frontend/src/widgets/team-management/TeamTable.tsx` | Main grid with DataTable, CustomEvent bus, guards | VERIFIED | 308 lines; DataTable, events, guards all present |
| `frontend/src/widgets/team-management/ScopeSection.tsx` | Region + store checkbox multi-select | VERIFIED | activeShops prop used; validation error text present |
| `frontend/src/widgets/team-management/AddTeamMemberModal.tsx` | Add modal with createTeamMember + team:member-added | VERIFIED | createTeamMember, team:member-added, "Send Invitation" |
| `frontend/src/widgets/team-management/EditTeamMemberModal.tsx` | Edit modal with updateTeamMember + email readOnly | VERIFIED | updateTeamMember, readOnly, "Save Changes" |
| `frontend/src/widgets/team-management/DisableMemberModal.tsx` | Amber ConfirmModal + disableTeamMember | VERIFIED | variant="amber", "Disable Member", team:member-toggled |
| `frontend/src/widgets/team-management/RemoveMemberModal.tsx` | Red ConfirmModal + removeTeamMember | VERIFIED | variant="red", "Remove Member", team:member-removed |
| `frontend/src/widgets/team-management/ResendMemberInviteModal.tsx` | Blue ConfirmModal + resendTeamInvitation | VERIFIED | variant="blue", "Resend Invitation", team:member-toggled |
| `frontend/src/widgets/team-management/TeamModals.tsx` | Orchestrator subscribing to all team:open-* events | VERIFIED | 120 lines; all 6 event subscriptions; inline enable; open-add-team-member button wired |
| `frontend/src/entrypoints/team-management.tsx` | Vite entrypoint mounting two roots | VERIFIED | createRoot, team-data, team-active-shops-data, dataset.currentUserId |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `services/team.py:invite_member` | `models.py:InvitationToken` | `purpose=InvitationToken.Purpose.TEAM_MEMBER` | WIRED | Line 87 |
| `services/team.py:resend_team_invitation` | `models.py:InvitationToken` | `old_token.invited_user = None` before new token | WIRED | Line 249 |
| `selectors/team.py:list_team_members` | `models.py:StaffAccessScope` | `Prefetch(to_attr='prefetched_scopes', select_related('region','shop'))` | WIRED | Lines 32-35 |
| `organisations/services/organisations.py:create_organisation` | `models.py:InvitationToken` | `purpose=InvitationToken.Purpose.ORG_ADMIN` | WIRED | Lines 55 and 98 |
| `views.py:TeamViewSet` | `selectors/team.py:list_team_members` | `get_queryset()` returns `list_team_members(...)` | WIRED | Line 104 |
| `views.py:invite_accept_view` | `services/team.py:activate_team_member` | `if invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER` | WIRED | Lines 336-345 |
| `views.py:TeamViewSet.create` | `services/team.py:invite_member + send_team_invitation_email` | `perform_create` calls both | WIRED | Lines 112-135 |
| `views.py:TeamViewSet` | `shops/selectors/shops.py:list_shops(active_only=True)` | `organisations/views.py:team_list` seeds `active_only=True` | WIRED | `organisations/views.py` line 195 |
| `organisations/urls.py` | `organisations/views.py:team_list` | `path("admin/org/team/", team_list, name="org_team")` | WIRED | urls.py line 39 |
| `api.ts:/api/v1/team/` | Backend TeamViewSet | `fetch("/api/v1/team/", {credentials: "same-origin"})` | WIRED | `api.ts` line 53 |
| `TeamTable.tsx` | `DataTable.tsx` | `DataTable<TeamMemberRow>` with columns array | WIRED | `TeamTable.tsx` line 260 |
| `TeamModals.tsx` | `AddTeamMemberModal` | subscribes to `team:open-add` CustomEvent | WIRED | `TeamModals.tsx` line 62 |
| `AddTeamMemberModal.tsx` | `api.ts:createTeamMember` | form submit handler | WIRED | `AddTeamMemberModal.tsx` line 82 |
| `RemoveMemberModal.tsx` | `api.ts:removeTeamMember` | ConfirmModal onConfirm | WIRED | `RemoveMemberModal.tsx` line 19 |
| `ScopeSection.tsx` | `activeShops` prop (XMOD-03) | checkbox list iterates `activeShops` | WIRED | `ScopeSection.tsx` line 74 |
| `entrypoints/team-management.tsx` | `templates/team/team_list.html` | `parseJson("team-data")`, `parseJson("team-active-shops-data")`, `dataset.currentUserId` | WIRED | Entrypoint lines 17-28 |
| `config/urls.py` | `apps/accounts/api_urls.py` | `path("api/v1/", include("apps.accounts.api_urls"))` | WIRED | `config/urls.py` line 19 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| TEAM-01 | 09-02, 09-04 | Team list columns: Member, Role badge, Access chips, Status badge, Invited date, Enabled toggle, Edit+Remove | SATISFIED | TeamTable.tsx columns array; RoleBadge, AccessChips, EnabledToggle sub-components |
| TEAM-02 | 09-02, 09-04 | Search (Name+Email) + Region and Store filter dropdowns; Store narrows on Region select | SATISFIED | TeamTable.tsx search input + region/store selects; filteredShops derived from selectedRegion |
| TEAM-03 | 09-02, 09-04 | Pagination with 10/25/50/100, default 10 | SATISFIED | TeamTable.tsx pagination controls; `TeamPagination(page_size=10)` in views.py |
| TEAM-04 | 09-02, 09-04 | Three stats cards: Total Members, Managers, Active Members | SATISFIED | TeamStatsCards.tsx; GET /api/v1/team/stats/ endpoint |
| TEAM-05 | 09-04 | Solo member banner when org admin is only member | SATISFIED | SoloMemberBanner.tsx; `isSoloAdmin = stats.total_members === 1` in TeamTable.tsx |
| TEAM-06 | 09-01, 09-05 | Add modal: Name/Email/Role; Staff reveals scope section with at-least-one validation | SATISFIED | AddTeamMemberModal.tsx; ScopeSection.tsx; `invite_member()` service |
| TEAM-07 | 09-01, 09-02, 09-05 | Invite sends email, Pending row appears, toast "Invitation sent to {email}." | SATISFIED | `send_team_invitation_email()` called from TeamViewSet.create; AddTeamMemberModal dispatches team:member-added |
| TEAM-08 | 09-02, 09-05 | Edit modal: Name/Role editable, Email locked, role change shows/hides scopes | SATISFIED | EditTeamMemberModal.tsx: `readOnly` on email; TeamMemberUpdateSerializer has no email field |
| TEAM-09 | 09-02, 09-05 | Edit success toast "Team member updated." + list refresh | SATISFIED | EditTeamMemberModal.tsx: `emitToast(…"Team member updated.")` + dispatches team:member-updated |
| TEAM-10 | 09-01, 09-05 | Disable: amber confirmation; sessions terminated; toast "{Name} disabled." | SATISFIED | DisableMemberModal.tsx amber variant; `disable_member()` calls `_flush_user_sessions()` |
| TEAM-11 | 09-01, 09-05 | Enable: one-click, no confirmation; toast "{Name} enabled." | SATISFIED | TeamModals.tsx inline enable handler; `enable_member()` service |
| TEAM-12 | 09-01 | Disabled user login shows exact error copy | SATISFIED | `forms.py` line 19: "Your account has been disabled. Contact your administrator." |
| TEAM-13 | 09-01, 09-05 | Remove: red confirmation; access revoked; tokens invalidated; sessions terminated; toast | SATISFIED | RemoveMemberModal.tsx red variant; `remove_member()` invalidates tokens, flushes sessions |
| TEAM-14 | 09-02, 09-04 | Self-protection in UI (disabled buttons + tooltips) AND API (403) | SATISFIED | `views.py` lines 151/188/201: three 403 guards; TeamTable.tsx: isOwnRow guards on buttons |
| TEAM-15 | 09-01, 09-02, 09-04 | Last-manager guard enforced at API (403) and UI (disabled Remove button) | SATISFIED | `services/team.py` LastManagerError; `views.py` 403; TeamTable.tsx: isLastManager guard |
| TEAM-16 | 09-01, 09-02, 09-05 | Resend: blue confirmation; old token invalidated; new invite email; toast "Invitation resent to {email}." | SATISFIED | ResendMemberInviteModal.tsx; `resend_team_invitation()` nulls invited_user; toast confirmed |
| TEAM-17 | 09-02 | Acceptance page /invite/accept/{token}/: Name pre-filled, Email locked, auto-login, role redirect | SATISFIED | `views.py` purpose-branching; STAFF_ADMIN → org_welcome; ORG_ADMIN → org_admin_dashboard |
| TEML-01 | 09-01, 09-03 | Team invitation email: invitee/inviter names, org, role, scopes for Staff, Accept CTA, 48h expiry, plain-text fallback | SATISFIED | `team_invitation.html/txt`; scope conditionals; 6 tests in test_team_emails.py |
| TEML-02 | 09-01, 09-03 | Resent email: same as TEML-01 plus replaces-previous notice; alternate subject | SATISFIED | `team_invitation_resent.html/txt`; "earlier link is no longer valid"; subject "New invitation link for {org}" |
| XMOD-03 | 09-02, 09-05 | Deactivated shops excluded from scope selectors | SATISFIED | `organisations/views.py` line 195: `active_only=True`; entrypoint seeds `team-active-shops-data` |

---

## Anti-Patterns Found

No blockers or warnings found. Scans of `services/team.py`, `selectors/team.py`, `serializers.py`, `views.py`, `TeamTable.tsx`, and `TeamModals.tsx` found:
- No TODO/FIXME/PLACEHOLDER comments
- No empty implementations (`return null`, `return {}`, `return []`)
- No remaining `pytest.skip` stubs in test files
- No `console.log` debugging in production paths
- `TeamModals.tsx` is the real 120-line orchestrator, not the Plan 04 stub

---

## Human Verification Required

### 1. Team List Page Rendering

**Test:** Log in as an Org Admin, visit /admin/org/team/
**Expected:** Stats cards show correct counts; table renders with all 7 column headers (MEMBER, ROLE, ACCESS, STATUS, INVITED, ENABLED, and actions); search input and filter dropdowns are visible
**Why human:** React widget visual rendering cannot be verified with grep

### 2. Add Team Member — Staff role invite flow

**Test:** Click "+ Add Team Member", select Role = Staff, check a region, submit
**Expected:** Pending row appears in table, toast "Invitation sent to {email}.", MailHog shows invitation email with "Accept Invitation" yellow CTA and the selected region name in the body
**Why human:** End-to-end modal → API → email → table refresh flow requires live browser + MailHog

### 3. Disable/Enable toggle confirmation

**Test:** Click the green Enabled toggle for a non-self active Staff member
**Expected:** Amber confirmation modal appears with "Disable Member" button; on confirm the row status changes to Disabled and toast "{Name} disabled." appears
**Why human:** Modal interaction and toast display require browser

### 4. Resend invitation

**Test:** On a Pending row, click the Mail icon (Resend), confirm the blue modal
**Expected:** Toast "Invitation resent to {email}.", MailHog shows second invitation email with "This replaces any previous invitation" notice
**Why human:** Resend flow requires live server, MailHog, and visual inspection of the email

### 5. TEAM_MEMBER invitation acceptance

**Test:** Accept a Staff team member invitation by visiting /invite/accept/{token}/
**Expected:** Role banner shows "You're joining as Staff."; name field is pre-filled; on submit the user is logged in and redirected to /admin/org/welcome/ showing "Your account is ready."
**Why human:** Acceptance form pre-fill, banner styling, and redirect require browser

---

## Gaps Summary

No gaps found. All 20 observable truths verified, all required artifacts exist and are substantive, all key links are wired, all 20 requirement IDs (TEAM-01 through TEAM-17, TEML-01, TEML-02, XMOD-03) are satisfied.

---

_Verified: 2026-04-30T10:30:00Z_
_Verifier: Claude (gsd-verifier)_
