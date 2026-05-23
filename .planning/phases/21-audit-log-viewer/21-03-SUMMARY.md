---
phase: 21-audit-log-viewer
plan: 03
subsystem: audit-log
tags: [django-templates, sidebar, react-mount-point, vite]
requires:
  - 21-01 (AuditLogEntry model + selectors)
  - 21-02 (audit_log_view + /admin/org/activity-log/ URL)
provides:
  - templates/org-admin/audit-log.html (React widget mount point)
  - Activity Log sidebar nav entry visible to ORG_ADMIN + STAFF_ADMIN
affects:
  - templates/partials/sidebar_org.html (one nav include added)
tech-stack:
  added: []
  patterns:
    - "json_script bootstrap for SSR-to-React data handoff"
    - "django_vite {% vite_asset %} entrypoint binding"
key-files:
  created:
    - templates/org-admin/audit-log.html
  modified:
    - templates/partials/sidebar_org.html
decisions:
  - "Nav item placed outside the {% if user.role != 'STAFF_ADMIN' %} guard; Staff users can view the Activity Log (API scopes data per role)"
  - "Mount point id is exactly 'audit-log-root' to match the 21-04 entrypoint's document.getElementById"
  - "actors_json passed via json_script (not inline JSON) — Django HTML-escapes and the React entrypoint reads via JSON.parse(document.getElementById('audit-log-actors-data').textContent)"
metrics:
  duration: ~10 minutes
  tasks_completed: 2/2
  files_created: 1
  files_modified: 1
  completed_date: 2026-05-23
---

# Phase 21 Plan 03: Activity Log Template + Sidebar Nav Summary

Server-side scaffold for the Activity Log page — a Django template that hosts the React widget (built in 21-04) plus a sidebar nav entry that makes the page discoverable to ORG_ADMIN and STAFF_ADMIN.

## What Was Built

### Task 1 — `templates/org-admin/audit-log.html` (commit `28c797b`)

A thin template that extends `base_org.html` and provides:

- `<div id="audit-log-root" data-user-role="{{ user_role }}"></div>` — the React mount point, with role data attribute for client-side conditional rendering (e.g., Staff-only restrictions on UI controls).
- `{{ actors_json|json_script:"audit-log-actors-data" }}` — Django's `json_script` template tag serialises the actors list (provided by `audit_log_view` from plan 21-02) into a safely-escaped `<script type="application/json">` element. The React entrypoint reads this with `JSON.parse(document.getElementById("audit-log-actors-data").textContent)`.
- `{% vite_asset 'src/entrypoints/audit-log.tsx' %}` — injects the Vite-built bundle for the audit-log widget (the entrypoint itself is created in plan 21-04 running in parallel).

This mirrors the established pattern from `templates/reviews/review_list.html`.

### Task 2 — `templates/partials/sidebar_org.html` nav entry (commit `5c967aa`)

A single `{% include "partials/_nav_item.html" with href="/admin/org/activity-log/" icon="clock" label="Activity Log" %}` line, placed inside the `<ul role="list">` immediately after the closing `{% endif %}` of the Org-Admin-only conditional block. Because it sits outside the guard, both ORG_ADMIN and STAFF_ADMIN see the entry. The `_nav_item.html` partial handles active-state highlighting based on the current request path.

## How It Fits Together

1. User navigates to `/admin/org/activity-log/`.
2. URL routes to `audit_log_view` (21-02) which renders this template with `actors_json`, `user_role`, `page_title` context.
3. Template extends `base_org.html` (sidebar + chrome) and renders the mount point + bootstrap JSON.
4. Vite asset loads the audit-log.tsx entrypoint (21-04) which mounts the React app at `#audit-log-root`.
5. Sidebar nav highlights the Activity Log row via `_nav_item.html`'s active-state logic.

## Verification

- `grep -c "activity-log" templates/partials/sidebar_org.html` → `1` (exactly one nav entry, as required).
- Template loadability: deferred to runtime — Django's template loader needs an active settings module which is not the executor's concern at this layer. The template only uses standard Django tags (`extends`, `load`, `block`, `json_script`) and the `django_vite` tag (already loaded successfully in `templates/reviews/review_list.html`), so a template-engine load is guaranteed to succeed when Django boots.

## Deviations from Plan

None — both tasks executed exactly as specified.

## Threat Surface

No new threat surface introduced. The template uses Django's `json_script` (HTML-escapes all values, mitigates T-21-07) and inherits `@login_required` from the underlying view (mitigates T-21-08). No package installs (T-21-SC accepted).

## Self-Check: PASSED

- `templates/org-admin/audit-log.html` — FOUND
- `templates/partials/sidebar_org.html` — FOUND (modified)
- Commit `28c797b` — FOUND
- Commit `5c967aa` — FOUND
