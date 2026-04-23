---
phase: 04-invitation-and-activation
plan: "01"
subsystem: organisations
tags: [dashboard, org-admin, layout, templates, access-control, tdd]
dependency_graph:
  requires: []
  provides:
    - "templates/base_org.html — Org Admin role-scoped layout base"
    - "templates/partials/sidebar_org.html — Org Admin-only sidebar (Dashboard + Profile only)"
    - "org_admin_dashboard view — POST-activation landing for Org Admins"
    - "URL name org_admin_dashboard resolves to /admin/org-dashboard/"
  affects:
    - "Plan 03 activation view (redirect target)"
tech_stack:
  added: []
  patterns:
    - "Dedicated layout base per role (base_org.html mirrors base.html)"
    - "Role-scoped sidebar partial (no branching logic — separate file per role)"
    - "@login_required + isinstance/role checks for view-level RBAC"
    - "TDD: RED test commit → GREEN implementation commit"
key_files:
  created:
    - templates/base_org.html
    - templates/partials/shell_org_open.html
    - templates/partials/shell_org_close.html
    - templates/partials/sidebar_org.html
    - templates/organisations/org_dashboard.html
  modified:
    - apps/organisations/views.py
    - apps/organisations/urls.py
    - apps/organisations/tests/test_views.py
decisions:
  - "Separate sidebar_org.html file (not branching in multi-role sidebar.html) keeps role layout boundaries clean and prevents Superadmin nav items leaking into Org Admin shell"
  - "SUPERADMIN visiting /admin/org-dashboard/ redirects to /admin/organisations/ (role-appropriate landing)"
  - "ORG_ADMIN with no organisation FK redirects to /login/ — org FK required to render dashboard"
metrics:
  duration: "4m"
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_changed: 8
---

# Phase 4 Plan 01: Org Admin Dashboard Stub Summary

**One-liner:** Dedicated Org Admin shell layout (base_org.html + sidebar_org.html) and role-gated stub dashboard at /admin/org-dashboard/ serving as the post-activation redirect target.

## What Was Built

A complete Org Admin layout boundary and stub landing page:

1. **base_org.html** — mirrors base.html but wires to org-scoped shell partials. Provides the extend target for all future Org Admin pages.

2. **shell_org_open.html / shell_org_close.html** — identical in structure to the Superadmin shell but includes `sidebar_org.html` instead of the multi-role `sidebar.html`.

3. **sidebar_org.html** — Org Admin-only sidebar with no `{% if user.role %}` branching. Contains only two nav items: Dashboard (`/admin/org-dashboard/`) and Profile (`/profile/`). No Organisations link, no Superadmin nav items.

4. **org_admin_dashboard view** — `@login_required` decorated function with explicit role gating: SUPERADMIN → `/admin/organisations/`, ORG_ADMIN without org → `/login/`, ORG_ADMIN with org → render welcome card.

5. **org_dashboard.html** — Extends `base_org.html`. Renders a white welcome card with `Welcome to {organisation.name}` heading.

6. **URL** — `path("admin/org-dashboard/", ..., name="org_admin_dashboard")` registered in `apps/organisations/urls.py`.

## Deviations from Plan

None — plan executed exactly as written.

Auto-fixed: Ruff N814 (Camelcase import as constant) — the plan's test code used `User as _U` which ruff rejects. Fixed inline during RED phase to import `User` directly.

## Tests

6 new tests in `apps/organisations/tests/test_views.py`:

| Test | Verifies |
|------|----------|
| test_org_admin_dashboard_url_name_resolves | reverse("org_admin_dashboard") == "/admin/org-dashboard/" |
| test_org_admin_dashboard_anonymous_redirects_to_login | 302 with next= param |
| test_org_admin_dashboard_superadmin_redirects_to_organisations | 302 to /admin/organisations/ |
| test_org_admin_dashboard_org_admin_without_org_redirects_to_login | 302 when user.organisation is None |
| test_org_admin_dashboard_org_admin_sees_welcome_card | 200 with org name + testid |
| test_org_admin_dashboard_renders_org_sidebar_not_superadmin_sidebar | sidebar testid present; /admin/organisations/ NOT in response |

All 27 tests in test_views.py pass (21 pre-existing + 6 new).

## Self-Check: PASSED

All 8 files found on disk. All 3 task commits (67ada95, 23adc56, 9b46d43) verified in git log.
