# Phase 16: Org Admin Shop Creation — Conditional Depth Selector - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a conditional "Review History" `<select>` to Step 3 of the Org Admin "Add Shop" wizard. The dropdown appears only when the parent org's `allow_custom_sync_depth` is `True`; when `False`, the field is hidden and the shop silently receives `TWO_YEARS`. The selected value is posted in the shop creation payload, accepted by `ShopCreateSerializer`, and persisted to `shop.sync_depth` via `create_shop()`. The shop detail page already shows "Review history" (delivered in Phase 15) so no further UI change is needed post-creation.

</domain>

<decisions>
## Implementation Decisions

### Org flag delivery to frontend
- **D-01:** Use a new Django bootstrap tag — `{{ allow_custom_sync_depth|json_script:"shop-org-data" }}` — in `templates/shops/shop_list.html`, immediately after the existing `shop-regions-data` tag. The view already has `org = request.user.organisation`; add `"allow_custom_sync_depth": org.allow_custom_sync_depth` to the context (or pass the boolean directly).
- **D-02:** Payload is flag-only: `{"allow_custom_sync_depth": true/false}`. Not the full org object — minimal surface area on the shops page.
- **D-03:** Entrypoint (`shop-management.tsx`) reads the tag via `parseJson<{ allow_custom_sync_depth: boolean }>("shop-org-data", { allow_custom_sync_depth: false })` and passes the value down through `ShopModals` → `CreateShopModal` as a new `allowCustomSyncDepth: boolean` prop.

### Backend validation
- **D-04:** Add `sync_depth = serializers.ChoiceField(choices=Shop.SyncDepth.choices, required=False, default=Shop.SyncDepth.TWO_YEARS)` to `ShopCreateSerializer`. DRF handles choice validation; the serializer always produces a valid value.
- **D-05:** No server-side enforcement of the org flag — if a crafted request posts `sync_depth` when the org's flag is `False`, the backend accepts it silently. The frontend is the only gate. This keeps the API simple and avoids a DB lookup in the serializer.
- **D-06:** `create_shop()` in `apps/shops/services/shops.py` must accept a new keyword argument `sync_depth: str = Shop.SyncDepth.TWO_YEARS` and persist it to the model. The service currently does not take this parameter.

### Dropdown placement and UX (CreateShopModal Step 3)
- **D-07:** Dropdown position: **after Region, before Phone** (top-to-bottom: listing pill → Shop Name → Region → **Review History** → Phone → Street Address → footer). Groups it with structural shop config rather than burying it at the bottom.
- **D-08:** Include a short helper text line below the label: `"Sets how far back this shop's initial review sync will go."` Use the same `<p className="mt-1 text-[12px] text-muted">` pattern used by other helper texts in the form.
- **D-09:** UI element is a `<select>` with the same `inputCls` Tailwind class already used by the Region select in this form — no new component needed.
- **D-10:** Default selected option is "Last 2 years" (`TWO_YEARS`). The dropdown only renders when `allowCustomSyncDepth === true`; when `false`, the field is completely absent from the DOM (not hidden/disabled — absent).

### Claude's Discretion
- Exact prop threading path through `ShopModals` (whether to add `allowCustomSyncDepth` directly to `ShopModalsProps` or read it from a context/store — prop-drilling is fine given the shallow depth)
- Whether `shop-org-data` bootstrap tag lives on the same line as `shop-regions-data` or in a separate template block
- State variable name inside `CreateShopModal` for the selected sync depth value

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §v0.5 — SDEP-01 (the only Phase 16 requirement)

### Architecture constraints
- `CLAUDE.md` §5 — Services/selectors pattern; `create_shop()` is the sole entry point for shop creation
- `CLAUDE.md` §6 — No-N+1; `select_related` required for any FK access added in this phase
- `CLAUDE.md` §24 — Order: models (none needed) → serializer → service → tests → views (none needed) → permissions (none needed)

### Phase 15 output (foundational — read before implementing)
- `apps/shops/models.py` — `Shop.SyncDepth` TextChoices (ONE_YEAR / TWO_YEARS / ALL_TIME, default TWO_YEARS); already in place
- `apps/shops/serializers.py` — `ShopCreateSerializer` (current — no `sync_depth` yet; Phase 16 adds it); `ShopReadSerializer` already exposes `sync_depth` (read-only)
- `apps/shops/services/shops.py` — `create_shop()` current signature (no `sync_depth` kwarg yet; Phase 16 adds it)
- `.planning/phases/15-sync-depth-data-layer-and-superadmin-controls/15-02-SUMMARY.md` — confirms `Shop.SyncDepth` values and migration number

### Existing code to extend
- `apps/shops/views.py` — `shop_list` view (adds `allow_custom_sync_depth` to context); `ShopViewSet.create` (thin — calls `create_shop()`; no change needed if serializer passes value through)
- `templates/shops/shop_list.html` — add `{{ allow_custom_sync_depth|json_script:"shop-org-data" }}`
- `frontend/src/entrypoints/shop-management.tsx` — `parseJson` + `ShopModals` props (add `allowCustomSyncDepth`)
- `frontend/src/widgets/shop-management/ShopModals.tsx` — `ShopModalsProps` (add `allowCustomSyncDepth`); thread to `CreateShopModal`
- `frontend/src/widgets/shop-management/CreateShopModal.tsx` — add `allowCustomSyncDepth` prop, `syncDepth` state, conditional `<select>` in Step 3
- `frontend/src/widgets/shop-management/types.ts` — `ShopCreatePayload` (add optional `sync_depth?: string`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `inputCls` / `labelCls` constants already in `CreateShopModal.tsx` (lines 9–13) — reuse for the Review History select and label; no new Tailwind classes needed
- `Region <select>` in `CreateShopModal.tsx` (lines 436–454) — exact template to copy for the Review History `<select>` (same wrapper div, same label, same select element with `inputCls`)
- `parseJson<T>` utility in `shop-management.tsx` (lines 16–24) — reuse to read the new `shop-org-data` bootstrap tag

### Established Patterns
- Bootstrap tag pattern: `{{ value|json_script:"id" }}` in template → `parseJson<T>("id", fallback)` in entrypoint → prop down the tree (see `shop-allocation`, `shop-regions-data`)
- `ShopCreatePayload` in `types.ts` carries all form fields; add `sync_depth?: string` (optional — only sent when org allows it)
- `create_shop()` in `services/shops.py` accepts keyword-only args; add `sync_depth: str = Shop.SyncDepth.TWO_YEARS` following the same pattern as other optional kwargs

### Integration Points
- `ShopViewSet.create` (line ~220 in views.py) calls `create_shop(organisation=user.organisation, region=region, **data)` — `sync_depth` in `data` passes through automatically once serializer exposes it and service accepts it
- `initial_backfill_task` → `run_initial_backfill(shop_id)` → `fetch_and_persist_reviews(trigger="initial")` — Phase 15 already wired `shop.sync_depth` to the date filter; Phase 16 just needs to persist the right value at creation time

</code_context>

<specifics>
## Specific Ideas

- The dropdown must be completely **absent** from the DOM (not disabled or hidden via CSS) when `allowCustomSyncDepth === false` — `{allowCustomSyncDepth && <div>...</div>}` React pattern
- Helper text: `"Sets how far back this shop's initial review sync will go."` — exact wording locked by D-08
- Default selected value when the dropdown renders: `"TWO_YEARS"` (state initialized to `Shop.SyncDepth.TWO_YEARS`)

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-org-admin-shop-creation-conditional-depth-selector*
*Context gathered: 2026-05-15*
