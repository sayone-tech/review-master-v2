---
phase: 09-team
plan: "02"
subsystem: accounts
tags:
  - team-management
  - drf
  - viewset
  - serializers
  - templates
  - invitation-flow
dependency_graph:
  requires:
    - "09-01"  # team services, selectors, models
    - "08-01"  # shops app
    - "07-01"  # regions app
  provides:
    - "TeamViewSet at /api/v1/team/"
    - "invite_accept_view purpose-branching (TEAM_MEMBER vs ORG_ADMIN)"
    - "Django template views: team_list, org_welcome"
    - "Template seeding contract for Plans 04/05 React widgets"
  affects:
    - "09-03"  # email templates
    - "09-04"  # React team-management widget
    - "09-05"  # React modals
tech_stack:
  added:
    - "apps/accounts/api_urls.py — DRF SimpleRouter for TeamViewSet"
    - "apps/accounts/serializers.py — 4 new serializer classes"
  patterns:
    - "TenantScopedViewSet with IsOrgAdmin + IsOrgScoped permission stack"
    - "N+1-safe prefetched_scopes to_attr in TeamMemberReadSerializer"
    - "Self-protection guards inline in TeamViewSet (no custom exception)"
    - "Last-manager guard inline in destroy + _do_update"
    - "Purpose-branching in invite_accept_view for TEAM_MEMBER vs ORG_ADMIN"
key_files:
  created:
    - apps/accounts/serializers.py
    - apps/accounts/api_urls.py
    - apps/accounts/tests/test_serializers.py
    - apps/accounts/tests/test_views_team.py
    - templates/team/team_list.html
    - templates/accounts/team_invite_accept.html
    - templates/organisations/team_welcome.html
  modified:
    - apps/accounts/views.py
    - apps/organisations/views.py
    - apps/organisations/urls.py
    - config/urls.py
decisions:
  - "Tasks 1+2 committed as one atomic commit — organisations/urls.py imports team_list/org_welcome from organisations/views.py (unstaged), so pre-commit hook failed when staged separately"
  - "TeamViewSet uses IsOrgAdmin permission (not IsOrgScoped alone) — matches existing ShopViewSet pattern; STAFF_ADMIN cannot manage team"
  - "get_queryset() converts region_id/shop_id string query params to int before passing to selector (mypy strict compliance)"
  - "team_list + org_welcome moved to organisations/views.py (plan spec) but org_welcome uses @login_required not @org_admin_required — Staff (non-ORG_ADMIN) needs to reach /admin/org/welcome/ after activation"
metrics:
  duration_minutes: 21
  completed_date: "2026-04-29"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 11
---

# Phase 9 Plan 02: Team API + Templates Summary

Build the Team API and invitation acceptance flow. TeamViewSet operational at `/api/v1/team/` with self-protection, last-manager guards, and purpose-branched invite_accept_view.

## TeamViewSet Endpoint Inventory

| Method | URL | Action | Permission |
|--------|-----|--------|------------|
| GET | `/api/v1/team/` | list | IsOrgAdmin |
| POST | `/api/v1/team/` | create (invite) | IsOrgAdmin |
| GET | `/api/v1/team/{id}/` | retrieve | IsOrgAdmin |
| PATCH | `/api/v1/team/{id}/` | partial_update | IsOrgAdmin |
| PUT | `/api/v1/team/{id}/` | update | IsOrgAdmin |
| DELETE | `/api/v1/team/{id}/` | destroy | IsOrgAdmin |
| POST | `/api/v1/team/{id}/disable/` | disable | IsOrgAdmin |
| POST | `/api/v1/team/{id}/enable/` | enable | IsOrgAdmin |
| POST | `/api/v1/team/{id}/resend/` | resend | IsOrgAdmin |
| GET | `/api/v1/team/stats/` | stats | IsOrgAdmin |

## Self-Protection and Last-Manager Guard Policy

**Self-protection (HTTP 403):**
- `DELETE /api/v1/team/{own_pk}/` → `"You cannot remove yourself."`
- `POST /api/v1/team/{own_pk}/disable/` → `"You cannot disable yourself."`
- `PATCH /api/v1/team/{own_pk}/` with `role=STAFF_ADMIN` → `"You cannot demote yourself."`

**Last-manager guard (HTTP 403):**
- `DELETE /api/v1/team/{id}/` on only active ORG_ADMIN → `"Cannot remove the last Manager."`
- `PATCH /api/v1/team/{id}/` demoting only active ORG_ADMIN → `"Cannot remove the last Manager."`

Both guards are enforced at the view layer (inline in TeamViewSet methods). Self-guard is checked first; last-manager guard is checked after self-guard passes.

## invite_accept_view Purpose-Branching

**Before (ORG_ADMIN only flow):**
```python
# All tokens: activate_account() → redirect org_admin_dashboard
```

**After (purpose-branched):**
```python
if invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER:
    activate_team_member(invitation, full_name, password)
    if user.role == STAFF_ADMIN:
        redirect("org_welcome")  # /admin/org/welcome/
    else:
        redirect("org_admin_dashboard")  # /admin/org-dashboard/
else:
    # ORG_ADMIN path — unchanged
    activate_account(invitation, full_name, password)
    redirect("org_admin_dashboard")
```

**Template selection:**
- `Purpose.TEAM_MEMBER` → `accounts/team_invite_accept.html` (with role-context banner)
- `Purpose.ORG_ADMIN` → `accounts/invite_accept.html` (unchanged)

## Template Seeding Contract (for Plans 04/05)

The `/admin/org/team/` view renders `templates/team/team_list.html` with:

| `json_script` id | Content | Source |
|-----------------|---------|--------|
| `team-data` | `initial_members_json` | `TeamMemberReadSerializer` (first 10) |
| `team-regions-data` | `regions_json` | `RegionReadSerializer` (all org regions) |
| `team-active-shops-data` | `active_shops_json` | `ShopReadSerializer` (active only, XMOD-03) |
| `team-stats-data` | `stats` | `get_team_stats()` |

**DOM mount attributes:**
- `#team-table-root` — `data-current-user-id`, `data-manager-count`
- `#team-modals-root` — `data-current-user-id`, `data-manager-count`

React entrypoint: `src/entrypoints/team-management.tsx` (Plan 04 creates this)

## XMOD-03 Enforcement

`list_shops(organisation_id=org.pk, active_only=True)` used in `team_list` view to seed active shops for scope selectors.

## Deviations from Plan

**1. [Rule 3 - Blocking] Tasks 1+2 committed atomically**
- **Found during:** Task 1 commit attempt
- **Issue:** Pre-commit `missing-migrations` hook ran `manage.py` which imported `organisations.urls`; organisations/urls.py imported `team_list` and `org_welcome` from organisations/views.py (Task 2 output, unstaged). ImportError during the hook caused commit failure.
- **Fix:** Added all Task 1+2 files to the same commit. Both tasks are functionally interdependent.
- **Commit:** 985183c

## Self-Check: PASSED
