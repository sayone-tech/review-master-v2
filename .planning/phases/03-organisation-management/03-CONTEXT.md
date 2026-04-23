# Phase 3: Organisation Management - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Superadmin full CRUD for the organisation roster: list with search/filter/pagination, create/view/edit/enable/disable/delete via modals, and store allocation adjustment. Invitation email sending is part of this phase (CORG-04); the activation page and token acceptance flow are Phase 4.

</domain>

<decisions>
## Implementation Decisions

### React widget scope
- **Hybrid approach:** Django template (`organisations/list.html`) extends `base.html` (sidebar + topbar), renders the existing `filter_bar.html` component for search/filter, and uses a server-side `pagination.html` component. A single React `OrgManagement` entrypoint mounts inside `<div id="org-table-root">` and owns the DataTable rows + all modal dialogs.
- Filter bar (search, status filter, type filter) uses the existing `filter_bar.html` GET form — submits trigger a page reload.
- Pagination uses the existing server-side `pagination.html` — extended with a rows-per-page selector (see below).
- React does NOT own search, filters, or pagination controls. It owns: table rows (with row-action menus), all modal dialogs.
- This keeps the Phase 1 boundary: React for data tables + modals, Django templates for shell and controls.

### Initial data loading
- Django view queries organisations and serialises the first page into a JSON blob embedded in the template: `<script id="org-data" type="application/json">{{ orgs_json|safe }}</script>`
- React reads that blob on mount — no initial fetch, instant first render.
- Subsequent mutations call DRF to refresh the table in-place.

### Filter state and page reloads
- Applying a filter or search submits the GET form → Django re-renders the template with filtered data in the JSON blob → React re-mounts with the new data. No React state to sync with URL params for filters.
- React reads `window.location.search` on mount to know the current filter params (needed for post-mutation refresh calls).

### Rows-per-page selector
- Server-side: `per_page` GET param added to `pagination.html` (extended with a `<select>` for 10/25/50/100, default 10).
- Django view reads `per_page` from GET params and passes it to `Paginator`. Per-page selection persists via URL param across page navigation.
- Default: 10 rows/page per ORGL-06.

### Confirmation modal patterns
- **All confirmations use React portals** — no Alpine.js for any modal in this page. React OrgManagement widget owns all dialogs: create, view, edit, enable, disable, delete, and store allocation.
- Consistent focus trap, ARIA, and animation across all modal types.
- **Delete modal (DORG-01):** Requires typing the exact organisation name before Delete button enables. Shows a soft-delete warning: *"This organisation will be hidden from the list. It can be restored by an administrator."*
- **Enable/disable modals (ENBL-01/02):** Simple confirmation popups with the icons, copy, and buttons specified in REQUIREMENTS.md (warning amber for disable, info blue for enable).
- **Store allocation modal (STOR-01/02/03):** Inline validation (amber warning when value < current usage, Update button blocked), then confirmation popup showing old and new count.

### Table refresh after mutations
- After any successful mutation (create, edit, enable, disable, delete, store allocation change), React calls `GET /api/v1/organisations/` with the current URL search params (preserving active filters, page, per_page).
- React updates its local state with the fresh response — no page reload.
- Filter state source of truth = URL; React reads `window.location.search`, never tracks filters internally.

### API layer
- DRF ViewSet at `/api/v1/organisations/` (list, create, retrieve, update, partial_update, destroy).
- List endpoint must support query params: `search`, `status`, `type`, `page`, `per_page`.
- Write operations (create, update, patch, delete) each have their own serializer shapes per CLAUDE.md §8.
- Strict no-N+1: list endpoint CI query-count ceiling test required (ORGL-08).

### Claude's Discretion
- Exact modal animation (fade/slide, duration)
- Row-action three-dot menu implementation (Alpine.js dropdown is the established pattern; React may use a Radix/headless dropdown or a simple positioned div)
- Loading spinner on action buttons while DRF call is in-flight
- Toast message copy for each action (beyond what REQUIREMENTS.md specifies exactly)
- DRF serializer field names and nesting depth

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `CLAUDE.md` — Full architectural constraints: services/selectors pattern (§5), no-N+1 query policy (§6), DRF conventions (§8), Redis usage (§7), pre-commit hooks (§14). Single most important reference.
- `CLAUDE.md §8` — DRF conventions: one ViewSet per resource, two serializers (read/write), explicit permissions on every viewset, pagination required on every list endpoint, `django-filter` for filtering.
- `CLAUDE.md §6.9` — CI query-count ceiling test pattern (`CaptureQueriesContext`) — required for ORGL-08.
- `.planning/REQUIREMENTS.md` — Phase 3 requirements: ORGL-01 through ORGL-08, CORG-01 through CORG-04, VORG-01 through VORG-03, EORG-01 through EORG-03, ENBL-01 through ENBL-02, DORG-01 through DORG-02, STOR-01 through STOR-03. Read all of these carefully — exact copy, icons, validation rules, and success conditions are specified.
- `docs/Requirements_Phase1_Superadmin.docx` — Original requirements document (v1.0, April 2026); contains design details beyond what REQUIREMENTS.md captures.

### Prior phase decisions
- `.planning/phases/01-foundation/01-CONTEXT.md` — Design system tokens, React vs template boundary, Alpine.js patterns, component patterns (badges, toasts, modals, filter bar, pagination).
- `.planning/phases/02-authentication/02-CONTEXT.md` — Session auth patterns, confirmed that React handles modals with focus-trap.

### Existing code
- `apps/organisations/models.py` — Organisation model (Status enum: ACTIVE/DISABLED/DELETED, OrgType enum, `soft_delete()` method, `annotate_store_counts()` stub returning zeros).
- `apps/organisations/managers.py` — `OrganisationQuerySet` with `active()`, `disabled()`, `deleted()`, `not_deleted()`, `annotate_store_counts()` methods.
- `templates/components/filter_bar.html` — Search input + status/type select dropdowns; renders as GET form.
- `templates/components/pagination.html` — Server-side pagination component; needs extending with `per_page` selector.
- `templates/components/badges.html` — Status + type badge variants (green=Active, gray=Disabled, red=Deleted, etc.).
- `templates/components/toasts.html` — Toast notification system (Alpine.js + Django messages).
- `apps/accounts/models.py` — `InvitationToken` model (needed for CORG-04 invitation creation on org create).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OrganisationQuerySet` — `not_deleted()`, `annotate_store_counts()`, filter methods ready to use in selectors.
- `filter_bar.html` — Supports `search_placeholder`, `status_options`, `type_options` context vars; already handles `request.GET` value preservation.
- `pagination.html` — Needs a `per_page` selector added; otherwise ready for the list view.
- `badges.html` — All needed variants present (green, gray, amber, blue, red).
- `apps/accounts/models.InvitationToken` — Model exists; services need to be written for token creation and email dispatch.
- `apps/common/services/email.send_transactional_email` — Already wired to SES; use for CORG-04 invitation email.

### Established Patterns
- Services/selectors: write-side logic in `apps/organisations/services/`, read-side in `apps/organisations/selectors/`.
- DRF ViewSet with explicit permission classes (`IsSuperadmin` from `apps/accounts/permissions.py`).
- React entrypoints in `frontend/src/entrypoints/` — one file per widget, mounted via `{% vite_asset %}`.
- Alpine.js for row-action three-dot menus (established in Phase 1 showcase page).
- `annotate_store_counts()` currently returns zeros — `total_stores` = `number_of_stores` (allocation), `active_stores` = 0 (no Store model yet). Phase 3 uses these stubs; they become real in a future phase.

### Integration Points
- `apps/organisations/urls.py` — Placeholder `organisation_list` view here; Phase 3 replaces it.
- `apps/organisations/views.py` — Template view + DRF viewset both live here.
- `config/urls.py` — DRF router registration for `/api/v1/organisations/` goes here.
- `apps/accounts/permissions.py` — `IsSuperadmin` permission class; used on all organisation viewset actions.

</code_context>

<specifics>
## Specific Ideas

- Delete modal soft-delete warning copy: *"This organisation will be hidden from the list. It can be restored by an administrator."*
- Rows-per-page defaults to 10; options: 10, 25, 50, 100 (per ORGL-06).
- Toast on create: *"Organisation created. Invitation email sent to {email}."* (exact copy from CORG-03).
- React reads filter params from `window.location.search` on mount for post-mutation refreshes — filter state never duplicated in React state.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 3 scope.

</deferred>

---

*Phase: 03-organisation-management*
*Context gathered: 2026-04-23*
