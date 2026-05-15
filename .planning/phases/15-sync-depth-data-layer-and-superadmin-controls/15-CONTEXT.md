# Phase 15: Sync Depth Data Layer and Superadmin Controls - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Add `allow_custom_sync_depth` boolean to the Organisation model (Superadmin controls it at create and edit time); add `sync_depth` TextChoices field to the Shop model (defaults to TWO_YEARS, shown on shop detail for all shops); update the initial backfill Celery task to read `shop.sync_depth` and compute a `start_date` (or no date filter for all-time). Phase 16 (Org Admin shop creation selector) depends on this phase.

</domain>

<decisions>
## Implementation Decisions

### Superadmin toggle UX (CreateOrgModal + EditOrgModal)
- **UI element:** Toggle switch (not a checkbox)
- **Placement:** Bottom of form, before the submit button — below Number of Stores
- **Label:** "Allow configurable sync depth"
- **Helper text:** Include a short description below the toggle: "When enabled, Org Admins can choose how far back to sync reviews when adding a new shop."
- Applies to both CreateOrgModal (default off) and EditOrgModal (reflects current value)

### Org detail display (ViewOrgModal)
- **Pattern:** Simple dt/dd row — consistent with other org detail rows
- **Label:** "Configurable sync depth"
- **Values:** "Enabled" or "Disabled"
- No badge/color treatment — plain text value, same styling as other rows

### Shop depth display (ShopDetailsModal)
- **Visibility:** Shown for ALL shops regardless of whether the org has custom sync depth enabled
- **Row label:** "Review history"
- **Display values:** "Last 1 year" / "Last 2 years" / "All time"
- The `sync_depth` serializer field must be included in the ShopRow type and the shops list/detail API response

### Backfill date cutoff
- **Approach:** Fetch all pages from the GBP API, filter by `review_created_at >= start_date` at persist time — do NOT stop paginating early
  - Reason: GBP API returns reviews sorted by `updateTime`, not `createTime`. Stopping early on page age would miss qualifying reviews that were created recently but updated long ago.
- **Date computation:** Fixed `timedelta` — not calendar-month `relativedelta`
  - ONE_YEAR → `timezone.now() - timedelta(days=365)`
  - TWO_YEARS → `timezone.now() - timedelta(days=730)`
  - ALL_TIME → no `start_date` filter; pass no date to Google API
- The `run_initial_backfill` service function reads `shop.sync_depth` and computes `start_date` before beginning pagination; `start_date` is passed through to `_persist_page` or the filter applied there

### Claude's Discretion
- Exact toggle switch component implementation (can reuse or build a minimal Tailwind toggle)
- Where exactly in `_persist_page` the `start_date` filter is applied (pre-save check on `review_created_at`)
- Migration naming and reversibility details
- Index decision for `allow_custom_sync_depth` (boolean field, low cardinality — likely not needed)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §v0.5 — SYNC-01, SYNC-02, SYNC-03, SDEP-02, SDEP-03, BKFL-01, BKFL-02, BKFL-03 (all Phase 15 requirements)

### Architecture constraints
- `CLAUDE.md` §5 — Services/selectors pattern; views are thin; business logic in services
- `CLAUDE.md` §6 — No-N+1 policy; `select_related` for FK access; `CaptureQueriesContext` required on list endpoints
- `CLAUDE.md` §12.3 — Celery tasks are thin wrappers over service functions
- `CLAUDE.md` §24 — Order of implementation: models → migration → services → tests → serializers → views → URLs → permissions

### Existing code to extend
- `apps/organisations/models.py` — Organisation model; add `allow_custom_sync_depth`
- `apps/organisations/serializers.py` — OrganisationListSerializer, OrganisationCreateSerializer, OrganisationUpdateSerializer; add new field to all three
- `apps/shops/models.py` — Shop model; add `sync_depth` TextChoices field, default TWO_YEARS
- `apps/shops/serializers.py` — Shop serializers; add `sync_depth` to ShopRow and API response
- `apps/reviews/services/sync.py` — `run_initial_backfill` / `fetch_and_persist_reviews`; add `start_date` computation and filter
- `apps/integrations/google/reviews_client.py` — `list_reviews()` — does NOT currently accept a date param; filtering stays in the service layer, not the client
- `frontend/src/widgets/org-management/types.ts` — OrgRow, CreateOrgPayload, UpdateOrgPayload
- `frontend/src/widgets/org-management/CreateOrgModal.tsx` — add toggle switch
- `frontend/src/widgets/org-management/EditOrgModal.tsx` — add toggle switch (reflects current value)
- `frontend/src/widgets/org-management/ViewOrgModal.tsx` — add "Configurable sync depth" row
- `frontend/src/widgets/shop-management/types.ts` — ShopRow; add `sync_depth`
- `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` — add "Review history" row

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Organisation.Status` / `Shop.ConnectionStatus` TextChoices: follow same pattern for `Shop.SyncDepth` (ONE_YEAR / TWO_YEARS / ALL_TIME)
- `OrganisationListSerializer` / `OrganisationDetailSerializer` — already split; add `allow_custom_sync_depth` as a BooleanField
- `OrganisationCreateSerializer` / `OrganisationUpdateSerializer` — thin model-level serializers; add field to both
- `ShopDetailsModal.tsx` — renders dt/dd rows with labeled values; add "Review history" row following the same pattern as region/status rows
- `ViewOrgModal.tsx` — same dt/dd row pattern; add "Configurable sync depth" row
- `templates/components/form_fields.html` — existing form field component system; check for toggle/switch support before building new

### Established Patterns
- TextChoices for enums (Organisation.Status, Organisation.OrgType, Shop.ConnectionStatus, Shop.ConnectionMethod) — follow the same for `Shop.SyncDepth`
- Migrations named descriptively (not `0014_auto_...`) per CLAUDE.md §18
- `run_initial_backfill` is a thin wrapper over `fetch_and_persist_reviews` — `start_date` logic should live in `run_initial_backfill`, computed from `shop.sync_depth` before calling `fetch_and_persist_reviews`
- All Celery tasks receive IDs not model instances — `initial_backfill_task(shop_id)` already correct; no task signature change needed

### Integration Points
- `initial_backfill_task` → `run_initial_backfill(shop_id)` → `fetch_and_persist_reviews(shop_id, trigger="initial")` — `start_date` threads through this call chain or is applied inside `_persist_page`
- Superadmin org list/detail React widget already wired to `/api/v1/organisations/` — adding `allow_custom_sync_depth` to serializer exposes it automatically
- ShopRow type in `frontend/src/widgets/shop-management/types.ts` must include `sync_depth` for ShopDetailsModal to render it — the shops list endpoint already returns ShopRow

</code_context>

<specifics>
## Specific Ideas

- Toggle switch UX: Superadmin-facing only. Org Admins never see this field; the conditional selector appears for them in Phase 16.
- Shop depth display shows for all shops ("Last 2 years" is still informative even when the org doesn't allow custom depth — tells the Org Admin what depth was applied).
- "All time" shops: no `start_date` is passed to `list_reviews` — current behavior is already "no date filter"; ALL_TIME is effectively a no-op change to the service.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-sync-depth-data-layer-and-superadmin-controls*
*Context gathered: 2026-05-15*
