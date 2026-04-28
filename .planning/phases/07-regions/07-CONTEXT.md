# Phase 7: Regions - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admins can list, create, edit, and delete Regions for their organisation. The
auto-ID mechanic auto-populates a suggested Region ID from the name as the user types
(create mode only). Deletion is blocked when Shops are assigned. Shops, Team, and
review logic are entirely separate phases.

</domain>

<decisions>
## Implementation Decisions

### Auto-ID sequence number (RGN-04)
- Sequence suffix (3-digit zero-padded) is computed **client-side** from `regions.length + 1`
  from the already-loaded list — zero extra API calls or endpoints
- No separator in the auto-generated ID: format is `ABCD001` (pure uppercase letters + digits),
  not `ABCD-001` — matches RGN-03 validation pattern `[A-Z0-9]` exactly
- Frontend always shows the `regions.length + 1` suggestion; if that ID is already taken, the
  server returns the RGN-06 duplicate error and the field highlights inline — **no client-side
  skip-to-next-available logic**
- Auto-population fires on every keystroke in the Region Name field (real-time per RGN-04):
  take the first letter of each word, uppercased, up to 4 letters, then append the 3-digit suffix

### Edit mode Region ID (RGN-08)
- In Edit mode the Region ID field is **pre-filled with the existing value** and always editable
  (no lock/unlock toggle — requirements say editable, no toggle mentioned)
- **No auto-population in edit mode** — clearing the field leaves it empty; user must type a
  valid ID themselves; the "auto-resume on clear" from RGN-05 applies only to Create mode
- Typing in the Region Name field in edit mode does NOT update the Region ID field (RGN-08)

### Shops pre-filter URL (RGN-10)
- "Manage Shops" link in the delete guard uses **integer PK** as the filter key:
  `/admin/org/shops/?region={region.pk}`
- Rationale: PKs are stable; `region_id` is editable and could drift after a rename
- Phase 8 reads `?region=` from the Shops list query string — this format is locked here

### Delete guard (RGN-10 / RGN-11)
- `delete_region` service first checks `shop_set.exists()` (or `region.shops.exists()`)
- If shops assigned → raise `RegionHasShopsError` (service-layer exception); view returns the
  amber blocking popup (not a toast) with shop count and the pre-filter Manage Shops link
- If no shops → permanent hard delete (no soft-delete for regions per requirements)
- Confirmation popup is **red variant** of existing `ConfirmModal` component

### Race safety for unique Region ID
- `UniqueConstraint(["organisation", "region_id"])` at DB level is the authoritative guard
- No `select_for_update()` needed on the Organisation row for ID generation since IDs are
  user-submitted (not server-auto-assigned); the DB constraint rejects duplicates atomically
- `django-sequences` is not used for Region ID generation in this phase (user controls the ID)

### Claude's Discretion
- Exact service exception class name and module location (`apps/regions/exceptions.py` or inline)
- Whether `list_regions` returns all regions or only active ones (requirements show no
  active/inactive filter in the list — return all, `is_active` field reserved for future use)
- Vite entrypoint filename and React widget directory name (follow `org-management` pattern:
  `frontend/src/entrypoints/region-management.tsx`, `frontend/src/widgets/region-management/`)
- Template for the Regions page (extend `base_org.html`, mount React widget into a `<div id="region-management-root">`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Regions — RGN-01 through RGN-11 (all Region requirements)
- `.planning/REQUIREMENTS.md` §Cross-Module XMOD-02 — Region deletion blocked when shops assigned
- `CLAUDE.md` §5 — Services/selectors pattern (write logic in services/, read in selectors/)
- `CLAUDE.md` §6 — No-N+1 policy + `CaptureQueriesContext` test for every list endpoint
- `CLAUDE.md` §13 — Testing standards (pytest, factory-boy, 85% coverage)

### Existing Phase 6 scaffold (extend, don't recreate)
- `apps/regions/models.py` — Region model with `UniqueConstraint(org, region_id)`, `created_at` ordering
- `apps/regions/tests/factories.py` — `RegionFactory` ready for test use
- `apps/common/viewsets.py` — `TenantScopedViewSet` base class (Phase 7 `RegionViewSet` inherits from it)
- `apps/common/permissions.py` — `IsOrgAdmin`, `IsOrgScoped` permission classes
- `apps/common/tests/fixtures.py` — `assert_query_ceiling`, `two_orgs_two_admins` fixtures
- `apps/common/tests/conftest.py` — shared pytest conftest; Phase 7 tests import fixtures explicitly

### Frontend reuse (use directly — don't recreate)
- `frontend/src/widgets/data-table/DataTable.tsx` — generic table with columns config, skeleton, empty state
- `frontend/src/widgets/modal/Modal.tsx` — Modal with title, subtitle, size (sm/default/lg), footer slot
- `frontend/src/widgets/modal/ConfirmModal.tsx` — amber/blue/red confirm popup (use for delete flows)
- `frontend/src/lib/toast.ts` — toast system (use for RGN-07, RGN-09, RGN-11 success toasts)
- `frontend/src/widgets/org-management/` — canonical pattern for React widget structure + API layer

### Design system reference
- `frontend/src/widgets/org-management/OrgTable.tsx` — StatusBadge pattern; adapt for Region ID pill badge (monospace, per RGN-01)
- `frontend/src/widgets/org-management/api.ts` — API fetch pattern to replicate in `region-management/api.ts`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DataTable` — plug in `RegionRow[]` type, define 3 columns (Name, Region ID pill, Actions); already handles loading skeleton + empty state
- `ConfirmModal` — amber variant for the "Cannot delete" block (RGN-10), red variant for the delete confirmation (RGN-11); both already styled
- `RegionFactory` — use in all test files for Region instances
- `two_orgs_two_admins` fixture — required for cross-tenant isolation test in RegionViewSet tests

### Established Patterns
- Services/selectors: all Region business logic lives in `apps/regions/services/` and `apps/regions/selectors/`; the RegionViewSet calls these only
- `TenantScopedViewSet` filters by `organisation_id=request.user.organisation_id` automatically — RegionViewSet inherits this, no manual filtering in views
- React widget entrypoints: `frontend/src/entrypoints/org-management.tsx` is the canonical template; replicate for `region-management.tsx`

### Integration Points
- `apps/organisations/urls.py` — `/admin/org/regions/` stub URL registered in Phase 6; Phase 7 replaces the stub view with the real Regions page view
- `config/urls.py` — org app URLs already included; no new include needed
- `apps/regions/models.py` — the `shops` reverse relation (from Shop FK to Region) is used in the delete guard: `region.shops.exists()`

</code_context>

<specifics>
## Specific Ideas

- The Region ID pill (RGN-01) renders in monospace font inside a badge — reuse the pattern from `OrgTable.tsx`'s StatusBadge but without the dot indicator; just text with a subtle border
- The empty state (RGN-02) uses Map icon (Lucide `MapPin`), "No regions yet" heading, "Create your first region" CTA — plug into `DataTable`'s `emptyState` prop
- Both the "Cannot delete" amber block (RGN-10) and the red delete confirmation (RGN-11) are distinct `ConfirmModal` instances — two separate state booleans in the component

</specifics>

<deferred>
## Deferred Ideas

- Region `is_active` toggle / enable-disable — field exists in the model but no requirement for it in Phase 7; reserved for a future phase
- Region search / filter — not in Phase 7 requirements (list is creation-order only)
- Shops pre-filter implementation — Phase 8 reads `?region=<pk>` from its Shops list; Phase 7 only outputs the link

</deferred>

---

*Phase: 07-regions*
*Context gathered: 2026-04-28*
