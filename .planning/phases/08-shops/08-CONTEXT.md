# Phase 8: Shops - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

> **Post-discuss-phase update (2026-04-29):** User decided to simplify shop creation to
> Google OAuth only. The MANUAL connection method, the `api_key` field, and the
> Reveal/Rotate API Key flows (SHOP-10, SHOP-19, SHOP-20) are **removed** rather than
> deferred. The address model is also reduced to a single `street_address` line — `city`,
> `state`, `zip_code` are dropped. Sections below referencing those flows are retained for
> historical context but marked SUPERSEDED. The retired decisions are repeated in the
> `<deferred>` block at the bottom of this file so downstream planners do not reintroduce
> them. Plans 08-06 and 08-07 are gap-closure plans that surgically remove this surface
> from the backend and frontend.

<domain>
## Phase Boundary

Org Admins can list, create, view, edit, activate/deactivate, manage API keys, and reconnect
Google on their Shops — with allocation enforcement, Connection Status tracking, and audit
logging for sensitive API key operations. Region FK is required for shop creation. Google
OAuth popup flow and manual Place ID entry are both supported create paths. Team and review
logic are entirely separate phases.

</domain>

<decisions>
## Implementation Decisions

### GBP listing picker (SHOP-11)
- **Single listing → auto-select:** Popup detects one listing, immediately calls
  `window.opener.postMessage` with that listing's details, then `window.close()`. No picker
  UI shown. Zero extra clicks for the common case.
- **Multiple listings → picker inside the popup:** `/oauth/google/callback/` Django template
  renders a listing picker (radio buttons or cards). User picks one listing, page calls
  `window.opener.postMessage` with selected listing details, then auto-closes. All selection
  logic stays server-side — no listing data crosses the postMessage boundary in bulk.
- **Listing card shows:** Business name + formatted address only. Clean and scannable.
- **After successful OAuth:** "Connect Google Business Profile" button is replaced by a green
  success row (checkmark icon + connected listing name + address + "Change connection" link).
  Shop Name and Address fields in the Create modal auto-populate from the listing data (per
  SHOP-09). User may overwrite them before submitting.

### Audit log (SHOP-19/20) — SUPERSEDED
> **Retired by post-discuss-phase decision.** Reveal/Rotate API Key flows are removed; no
> code writes ShopAuditLog entries anymore. The `ShopAuditLog` model and `Action` enum are
> retained at the ORM/table level for forward compatibility (no migration to drop them) but
> service-layer writers are deleted. See `<deferred>` section for the retirement note.

- **New `ShopAuditLog` model** in `apps/shops/` — queryable history for compliance.
- **Fields:** `shop` (FK to Shop), `actor` (FK to `settings.AUTH_USER_MODEL`), `action`
  (CharField, values: `shop.api_key.revealed` / `shop.api_key.rotated`), `created_at`
  (auto_now_add). No IP address or metadata JSON in Phase 8.
- **New migration** required for ShopAuditLog in `apps/shops/migrations/`.
- Service functions `reveal_api_key` and `rotate_api_key` write the audit entry inside
  `transaction.atomic()` alongside the shop update.

### Allocation counter mechanics (SHOP-01/02, XMOD-04)
- **X = total shop count by existence** — `Shop.objects.filter(organisation=org).count()`
  regardless of `is_active`. A shop occupies a slot from creation until hard-delete (not yet
  in scope per REQUIREMENTS.md deferred items).
- **Deactivate/activate does NOT change the counter** — consistent with SHOP-17 "allocated
  store slot remains used" note.
- **Allocation check:** at limit when `total_shop_count >= org.number_of_stores`.
- **API response:** Shops list endpoint includes `allocation_status: {current: X, max: Y,
  at_limit: bool}` in the response envelope. React widget uses `at_limit` to disable the
  "+ Add Shop" button on page load and after each successful shop creation.
- **No denormalized counter** — live COUNT query at list time is accurate, avoids sync
  complexity, negligible at typical shop counts.

### Manual Place ID + API Key validation error handling (SHOP-10/20) — SUPERSEDED
> **Retired by post-discuss-phase decision.** MANUAL connection method is removed. There is
> no Place ID + API Key form path on Create, and no Rotate Key flow. The error-handling
> rules below no longer have a UI surface to fire on. Retained here as historical record.

- **Google unreachable (timeout / 5xx) → hard fail:** Return non-field error
  "Could not reach Google to verify this API key. Please try again." Shop is NOT saved.
  Consistent policy on both create (SHOP-10) and rotate (SHOP-20).
- **Place ID invalid (key fine) → inline field error:** "This Place ID was not found."
  shown under the Place ID field. API Key field has no error.
- **API Key invalid → inline field error:** "This API key is not valid." shown under the
  API Key field.
- **Rotate Key:** Same hard-fail policy — existing key NOT replaced if Google unreachable.
  Old key remains active, user retries.

### Claude's Discretion
- Exact Django template for the listing picker inside the OAuth callback page (simple form
  with radio buttons + submit button; brand yellow for submit CTA)
- `postMessage` payload structure (object with `listingName`, `address`, `placeId` keys)
- Origin verification pattern in the React `message` event listener (check
  `event.origin === window.location.origin` before processing)
- `ShopAuditLog` table name and index decisions (created_at index for time-range queries)
- Exact serializer fields for the `allocation_status` envelope (nested vs flat)
- Django view vs DRF viewset for the OAuth views (`/oauth/google/start/`,
  `/oauth/google/callback/`) — plain Django views are simpler for the redirect-heavy OAuth flow
- Whether `reveal_api_key` returns the decrypted key in the API response and masks after 30s
  client-side, or whether the backend provides a separate timed endpoint

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Shops — SHOP-01 through SHOP-21 (all Shop requirements)
- `.planning/REQUIREMENTS.md` §Cross-Module — XMOD-01, XMOD-03, XMOD-04 (Shop-specific cross-module rules)
- `CLAUDE.md` §5 — Services/selectors pattern
- `CLAUDE.md` §6 — No-N+1 policy + CaptureQueriesContext test for every list endpoint
- `CLAUDE.md` §11 — Google Business Profile integration (encrypted tokens, retry/backoff, Redis lock)
- `CLAUDE.md` §13 — Testing standards (pytest, factory-boy, 85% coverage)

### Existing shop scaffold (extend, don't recreate)
- `apps/shops/models.py` — Shop model (ConnectionMethod, ConnectionStatus enums; EncryptedTextField for google_refresh_token and api_key; composite index on org+is_active+connection_status)
- `apps/shops/migrations/0001_initial.py` — existing migration; new ShopAuditLog migration goes in 0002
- `apps/shops/tests/factories.py` — ShopFactory ready for test use
- `apps/organisations/urls.py` — `org_shops` stub URL at `/admin/org/shops/`; Phase 8 replaces view behind it

### Existing tenant security scaffold (inherit directly)
- `apps/common/viewsets.py` — TenantScopedViewSet base class
- `apps/common/permissions.py` — IsOrgAdmin, IsOrgScoped permission classes
- `apps/common/tests/fixtures.py` — assert_query_ceiling, two_orgs_two_admins fixtures

### Frontend reuse (use directly — don't recreate)
- `frontend/src/widgets/data-table/DataTable.tsx` — generic table with columns config, skeleton, empty state
- `frontend/src/widgets/modal/Modal.tsx` — Modal with title, size, footer slot
- `frontend/src/widgets/modal/ConfirmModal.tsx` — amber/blue/red confirm popup (deactivate = amber, activate = blue)
- `frontend/src/lib/toast.ts` — toast system (kind + msg API)
- `frontend/src/widgets/region-management/` — canonical pattern for widget structure, api.ts, types.ts, useRegions.ts hook
- `frontend/src/widgets/region-management/api.ts` — CSRF token + fetch pattern to replicate in shop-management/api.ts

### Phase 7 locked decision (Phase 8 must honour)
- `.planning/phases/07-regions/07-CONTEXT.md` §Shops pre-filter URL — `?region=<pk>` query
  param; Shops list React widget must read `window.location.search` on mount and pre-populate
  the Region filter when this param is present

### Google OAuth integration
- `CLAUDE.md` §11 — refresh tokens encrypted at rest, retry + backoff via tenacity, Redis lock
  per store, 401 invalid_grant handling
- `apps/integrations/google/` — existing google integration directory (oauth.py, client.py,
  exceptions.py); Phase 8 extends this for the OAuth popup flow

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Shop` model: fully defined with all required fields + enums; no new fields needed unless
  ShopAuditLog FK back to Shop counts (it does — new model, not new field on Shop)
- `ShopFactory`: covers basic shop creation; tests will extend it with region, connection_method variants
- `DataTable` + `ConfirmModal` + `toast.ts`: same as Phase 7 — plug in ShopRow type and define columns
- `region-management/api.ts`: exact CSRF + fetch pattern to copy for shop-management/api.ts
- `TenantScopedViewSet`: ShopViewSet inherits this; no manual org filtering in views

### Established Patterns
- Services/selectors: all Shop business logic in `apps/shops/services/`, queries in
  `apps/shops/selectors/`; viewset calls these only
- `transaction.atomic` on all multi-step writes (create shop + audit log, rotate key + audit log)
- React widget entrypoint: `frontend/src/entrypoints/shop-management.tsx` follows the
  `org-management.tsx` / `region-management.tsx` pattern
- Three-dot menu (`RowActionsMenu.tsx` in org-management): adapt this pattern for Shop actions
  (View Details, Edit, Activate/Deactivate, Reveal Key, Rotate Key, Reconnect Google)

### Integration Points
- `apps/organisations/urls.py` `org_shops` stub URL → Phase 8 replaces `org_stub_view` with
  real `shop_list` Django view
- `apps/regions/models.py` `shops` reverse relation — `region.shops.exists()` already used in
  Phase 7 delete guard; Phase 8 reads `region.shops.count()` for the same guard display
- `apps/integrations/google/oauth.py` — extend for the popup OAuth flow; new
  `/oauth/google/start/` and `/oauth/google/callback/` Django views in this app (or
  `apps/shops/views.py` calling integration services)
- `Organisation.number_of_stores` — this is Y in the allocation counter; already on the model

</code_context>

<specifics>
## Specific Ideas

- The GBP listing picker in the popup should use the existing brand yellow CTA button for
  "Connect this listing" — consistent with the rest of the Org Admin UI
- The success row after OAuth connection mirrors the "connected" visual from SHOP-04's
  Connection Status pill ("Connected via Google", green dot) but in a compact form inside
  the Create modal
- `?region=<pk>` pre-population: React widget reads `new URLSearchParams(window.location.search).get('region')`
  on mount and initialises the Region filter dropdown to that value — no navigation, just state init
- The 30-second auto-mask for Reveal API Key (SHOP-19) is a client-side countdown timer in
  React; the backend returns the decrypted key in the API response (over HTTPS, same-origin
  session auth); the timer starts on response receipt

</specifics>

<deferred>
## Deferred Ideas

- Shop hard-delete / freeing an allocation slot on deletion — explicitly out of scope per
  REQUIREMENTS.md deferred items (SHOP-DELET)
- ShopAuditLog viewer UI — audit entries are written in Phase 8 but no list view is built;
  admin inspection via Django admin or future phase
- Google review fetching using the connected Shop credentials — Phase 4 (post-v0.2)
- Staff Admin access to shop-scoped views — Phase 9 (StaffAccessScope uses Shop FK)

### Retired (post-discuss-phase, 2026-04-29)

> User decided post-discuss-phase: shop creation simplified to Google OAuth only —
> MANUAL connection method, api_key field, Reveal/Rotate API key flows (SHOP-10, SHOP-19,
> SHOP-20) are removed rather than deferred. The address model is reduced to a single
> `street_address` line; city/state/zip_code columns are dropped. Plans 08-06 (backend) and
> 08-07 (frontend) execute the gap closure. Downstream planners MUST NOT reintroduce these:

- **MANUAL Place ID validation flow (SHOP-10)** — no "Enter manually" radio in the Create
  modal; no Place ID / API Key fields; no `validate_place_id()` call from `create_shop`.
  The Google Places API is only consulted via the OAuth popup listing-picker flow.
- **Reveal API Key (SHOP-19)** — no `reveal_key` viewset action, no `reveal_api_key`
  service, no RevealKeyModal in the frontend, no row-action menu entry, no audit log writer.
- **Rotate API Key (SHOP-20)** — no `rotate_key` viewset action, no `rotate_api_key`
  service, no `RotateKeySerializer`, no RotateKeyModal in the frontend, no row-action menu
  entry, no audit log writer.
- **`Shop.api_key` column** — removed via migration `0003_remove_manual_and_address_subfields`.
  The `EncryptedTextField` import remains (still used by `google_refresh_token`).
- **City / State / Zip Code address subfields** — removed from the Shop model, all
  serializers, the list-search filter, and the React types/forms. Single `street_address`
  line replaces the three-line address grid.
- **`ConnectionMethod.MANUAL` enum value** — removed from both Django model and TypeScript
  union; `ConnectionMethod` is now exactly `GOOGLE_OAUTH | NOT_CONNECTED`.
- **`ShopAuditLog` writers** — model and table retained for forward compatibility, but no
  service writes to it. The `Action` enum members (`API_KEY_REVEALED`, `API_KEY_ROTATED`)
  stay as ORM-level constants but have no live call sites.

</deferred>

---

*Phase: 08-shops*
*Context gathered: 2026-04-28*
*Updated: 2026-04-29 — post-discuss-phase decision to retire MANUAL/Reveal/Rotate flows*
