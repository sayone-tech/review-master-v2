# Phase 6: Org Admin Shell - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admins get a working navigation shell (sidebar with 6 items, personalised dashboard, profile
page reuse) + a secure tenant isolation foundation (IsOrgAdmin, IsOrgScoped, TenantScopedViewSet,
cross-tenant test fixture, CI query-count ceiling fixture) + all v0.2 data model migrations
(Region, Shop, StaffAccessScope, User extensions, InvitationToken purpose column step 1) +
django-fernet-encrypted-fields installed with FERNET_KEYS wired. Shops, Regions, and Team module
logic are separate phases (7, 8, 9).

</domain>

<decisions>
## Implementation Decisions

### Dashboard welcome card
- Heading: **"Welcome, {first name}"** — split `user.full_name` on first space for first name;
  fall back to the part before `@` in `user.email` if full_name is blank
- Supporting text below heading (when regions exist):
  org name displayed as subtitle + "Manage your shops, regions and team from here."
- Both rendered in a single white card, max-w-[560px], matching the existing stub card shell

### Zero-regions setup banner (SHEL-03)
- Yellow info banner — appears **only when the organisation has zero Regions** (dynamic check:
  `Region.objects.filter(organisation=user.organisation).count() == 0` in the view, passed as
  `show_setup_banner=True` in template context)
- Banner copy: "Get started by creating your first region…" + **"Create Region" CTA**
- CTA links to `/admin/org/regions/` (stub page in Phase 6; becomes real Regions list in Phase 7)
- Once org has ≥1 Region the banner is gone; no user-dismissal required

### URL structure
- All new Org Admin pages use the `/admin/org/*` prefix namespace
- **Alias approach** for dashboard URL: register both `/admin/org-dashboard/` (existing name
  `org_admin_dashboard`) **and** `/admin/org/dashboard/` pointing to the same view.
  `invite_accept_view` continues to call `reverse("org_admin_dashboard")` → unchanged.
  All new links (sidebar, login redirect) use `/admin/org/dashboard/`.
- **Separate profile URL**: `/admin/org/profile/` for Org Admin; Superadmin keeps `/admin/profile/`.
  Both reuse the same profile services (`update_profile_name`, `change_password`).
  Org Admin profile view extends `base_org.html`; Superadmin profile view extends `base.html`.
- Final stub URLs registered in Phase 6 (Phase 7–9 replace views behind same URLs):
  - `/admin/org/regions/` (name: `org_regions`)
  - `/admin/org/shops/` (name: `org_shops`)
  - `/admin/org/team/` (name: `org_team`)

### Sidebar (SHEL-01)
- Update `templates/partials/sidebar_org.html` to six items in order:
  **Dashboard, Shops, Regions, Team, Profile** (top nav group) + **Logout** (bottom-pinned)
- Icons: layout-dashboard, store, map-pin, users, user, log-out (Lucide)
- Yellow active state on current page — reuse existing `_nav_item.html` active-state logic
- Sidebar structure (HTML, Alpine.js, mobile drawer) is already complete — only nav items change

### Stub pages for Shops / Regions / Team
- **One shared stub view** `org_stub_view(request, section: str)` in `apps/organisations/views.py`
- Renders `organisations/org_stub.html` extending `base_org.html`; template receives `section`
  as a display title (e.g., "Shops", "Regions", "Team")
- Uses the existing `components/empty_state.html` component: icon + "{section}" heading +
  "This section is coming soon." subtext
- Three URL patterns registered pointing to this view:
  `/admin/org/regions/`, `/admin/org/shops/`, `/admin/org/team/`
  (Phase 7/8/9 replace the view behind each URL; no link changes needed)

### Login redirect for direct logins
- `CustomLoginView.form_valid()` overridden: after successful authentication check `user.role`
  and redirect accordingly:
  - `SUPERADMIN` → `/admin/organisations/`
  - `ORG_ADMIN` → `/admin/org/dashboard/`
  - Anything else (including `STAFF_ADMIN`) → `settings.LOGIN_REDIRECT_URL` (fallback)
- `LOGIN_REDIRECT_URL` in `config/settings/base.py` remains `/dashboard/` as ultimate fallback

### Permission classes
- **`IsOrgAdmin`** (new, `apps/accounts/permissions.py`): rejects non-ORG_ADMIN roles with 403
- **`IsOrgScoped`** (new, `apps/common/permissions.py`): rejects requests where
  `user.organisation_id` doesn't match the queryset tenant scope; returns 403 (not redirect)
- Both Org Admin template views AND DRF viewsets enforce `IsOrgAdmin` + `IsOrgScoped`
- Staff Admins hitting Org Admin-only pages → 403

### TenantScopedViewSet
- Base class in `apps/common/viewsets.py`; overrides `get_queryset()` to filter by
  `organisation_id=self.request.user.organisation_id`
- All Phase 7–9 DRF viewsets inherit from this
- Cross-tenant isolation test fixture lives in `apps/common/tests/fixtures.py`:
  asserts Org Admin from Org A receives 403 on Org B resources at list, detail, and mutation

### CI query-count ceiling fixture (XMOD-05)
- Shared pytest fixture `assert_query_ceiling(response, max_queries)` in
  `apps/common/tests/fixtures.py` (or `conftest.py`)
- Every Phase 7–9 list endpoint test imports this fixture and asserts a fixed ceiling regardless
  of result size

### Profile page reuse (SHEL-04)
- New view `org_profile_view` in `apps/accounts/views.py` (or `apps/organisations/views.py`):
  same logic as existing `profile` view but:
  - Requires `IsOrgAdmin` permission
  - Renders `accounts/org_profile.html` extending `base_org.html`
- Template: copy the two-card layout from `templates/accounts/profile.html` verbatim;
  change `{% extends "base.html" %}` to `{% extends "base_org.html" %}`
- Same form classes (`ProfileNameForm`, `ProfilePasswordChangeForm`), same services,
  same Alpine.js strength indicator pattern from `invite_accept.html`

### Claude's Discretion
- Exact migration file names (follow project naming convention — descriptive, not auto-generated)
- django-sequences Django 6 smoke test implementation (simple management command or pytest
  autouse fixture that calls `get_next_value("test")` and fails fast if it errors)
- FERNET_KEYS settings loading pattern (env var in local, GCP Secret Manager in production)
- `StaffAccessScope` model detail (scope_type enum values, nullable fields) — follows research notes
- Exact `InvitationToken.purpose` enum values for step 1 of expand-contract (PENDING/ORG_ADMIN
  per research, but Claude may refine based on Phase 9 team-invite requirements read from REQUIREMENTS.md)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `CLAUDE.md` — Full architectural constraints: §3 folder structure, §5 services/selectors,
  §6 no-N+1 + query-count tests, §9 auth/RBAC, §14 pre-commit, §19 security checklist.
  Most important reference for all implementation decisions.
- `.planning/REQUIREMENTS.md` — SHEL-01–04 and XMOD-05 requirements (Phase 6 scope)

### Existing org shell (to extend, not recreate)
- `templates/partials/sidebar_org.html` — existing org sidebar with Dashboard + Profile + Logout;
  add Shops, Regions, Team items in the correct position
- `templates/base_org.html` — existing org shell layout wrapper
- `templates/partials/shell_org_open.html` — includes sidebar_org + topbar
- `templates/organisations/org_dashboard.html` — existing stub dashboard; extend to add
  personalised welcome + conditional setup banner

### Views and URLs to extend
- `apps/organisations/views.py` lines 95–115 — `org_admin_dashboard` view; extend with
  personalisation + setup banner logic
- `apps/organisations/urls.py` — add `/admin/org/dashboard/` alias + stub URLs
- `apps/accounts/views.py` — `CustomLoginView.form_valid()` override; `profile` view pattern;
  `invite_accept_view` (DO NOT change the reverse("org_admin_dashboard") call here)
- `apps/accounts/urls.py` — add `/admin/org/profile/` URL
- `config/urls.py` — confirm org app includes are already wired

### Permission patterns to replicate
- `apps/accounts/permissions.py` — `IsSuperadmin` class; mirror for `IsOrgAdmin`
- `apps/common/` — TenantScopedViewSet and `IsOrgScoped` go here (keep common/ for truly
  shared code per CLAUDE.md §3)

### Profile reuse patterns
- `templates/accounts/profile.html` — two-card layout to copy for `accounts/org_profile.html`
- `templates/accounts/invite_accept.html` — canonical Alpine.js strength indicator + show/hide
  toggle pattern (copy verbatim per Phase 5 decision)
- `apps/accounts/services/profile.py` — `update_profile_name()` and `change_password()` reused
  as-is by org profile view

### Data model research
- `.planning/research/STACK.md` — django-fernet-encrypted-fields 0.3.1, django-sequences 3.0
  smoke test requirement, google-auth packages
- `.planning/research/ARCHITECTURE.md` — StaffAccessScope in apps/accounts to avoid circular
  imports; IsOrgScoped placement; existing URL preservation notes
- `.planning/research/PITFALLS.md` — InvitationToken expand-contract 3-step plan;
  django-sequences fallback; has_object_permission gap on list endpoints

### Design system components
- `templates/components/empty_state.html` — reuse for stub pages
- `templates/partials/_nav_item.html` — nav item with active state logic (reuse in sidebar update)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sidebar_org.html`: already has correct structure (collapsed/mobile Alpine.js, logout bottom-pinned,
  user avatar) — only the `<ul>` nav items section needs updating (add Shops, Regions, Team)
- `org_dashboard.html`: stub card shell exists — extend with template variables, don't rewrite
- `profile.html` + services: two-card layout and all profile logic ships and tested — copy template,
  wire same services for org profile view
- `invite_accept.html`: strength indicator Alpine.js — copy block verbatim
- `empty_state.html` + `_nav_item.html`: shared components ready to use

### Established Patterns
- Services/selectors: all business logic in `apps/<app>/services/`, queries in `selectors/`;
  views call these functions only
- `@login_required` + `IsSuperadmin` pattern in `apps/accounts/permissions.py` is the model
  for `IsOrgAdmin` and `IsOrgScoped`
- Full page POST + Django messages for profile forms (per Phase 5 decision)
- `transaction.atomic` on all multi-step service functions

### Integration Points
- `CustomLoginView.form_valid()` in `apps/accounts/views.py` — override here for role-based
  post-login redirect; call `super().form_valid()` first then redirect by role
- `config/settings/base.py` `LOGIN_REDIRECT_URL` — keep as fallback; don't remove
- `apps/common/` — add `viewsets.py` (TenantScopedViewSet) and `permissions.py` (IsOrgScoped);
  add `tests/fixtures.py` for shared test utilities

</code_context>

<specifics>
## Specific Ideas

- The zero-regions banner must use the yellow brand colour (`bg-yellow` / `text-black`) —
  consistent with Phase 5 hardening which uses yellow ring for focus states and yellow CTA
- `invite_accept_view` reverse("org_admin_dashboard") must NOT be changed — the alias approach
  keeps both URLs alive and avoids breaking the activation flow
- django-sequences smoke test: fail Phase 6 fast if Django 6 incompatibility is found;
  the select_for_update() fallback is already described in research pitfalls

</specifics>

<deferred>
## Deferred Ideas

- Staff Admin dashboard and login redirect — Phase 9
- Hard delete for org admin profile — not in scope
- HTMX partial updates for profile name — deferred (Phase 5 decision carried forward)

</deferred>

---

*Phase: 06-org-admin-shell*
*Context gathered: 2026-04-27*
