---
phase: 08-shops
verified: 2026-04-29T18:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 5/5
  note: >
    Third-pass re-verification after post-plan direct cleanup changes applied
    outside formal plan execution. Verified all 8 cleanup changes are in place.
    Phase goal remains fully achieved.
  gaps_closed: []
  gaps_remaining: []
  regressions:
    - id: SHOP-16-ui
      description: >
        EditShopModal no longer shows a disabled connection_method fieldset or
        a locked place_id read-only field. Previous verification treated those
        as present. The post-plan cleanup removed both fields from the edit form
        entirely (they are no longer rendered at all). API-level enforcement via
        ShopUpdateSerializer.LOCKED_FIELDS remains intact and is the canonical
        guard. This is a UI simplification, not a security regression.
      severity: warning
      impact: none — LOCKED_FIELDS in ShopUpdateSerializer prevents API mutation
human_verification:
  - test: "Visit /admin/org/shops/ as Org Admin and confirm the Shops (X / Y) header renders; shop table shows SHOP NAME, REGION, CONTACT, STATUS, CREATED columns only"
    expected: "No LOCATION, PLACE ID, or CONNECTION column visible in the table"
    why_human: "Django template rendering + live data cannot be verified programmatically without a running server"
  - test: "Complete OAuth twice with same Google account to test duplicate-listing prevention"
    expected: "In listing picker (step 2) on second add, already-added listing is disabled/greyed out"
    why_human: "Real Google OAuth + real browser required; takenPlaceIds wiring needs visual confirmation"
  - test: "Close the OAuth popup manually before completing auth"
    expected: "Within ~1.3s, modal shows 'Connection cancelled. Please try again.' (COOP fix: try/catch + immediate Redis poll + 800ms grace)"
    why_human: "window.closed polling requires a real browser event loop"
  - test: "Click Edit on any shop; confirm simplified form"
    expected: "Modal shows Shop Name, Region, Phone, Street Address only — no connection method radio, no Place ID field"
    why_human: "React rendering in browser required to confirm absent UI elements post-cleanup"
  - test: "PATCH /api/v1/shops/{id}/ with connection_method or place_id field"
    expected: "400 response — LOCKED_FIELDS validation error"
    why_human: "Requires HTTP client; automated tests should cover but smoke-test recommended"
  - test: "Run 'cd frontend && npm run build'"
    expected: "Build succeeds without TypeScript errors; shop-management bundle present in static/dist/"
    why_human: "Build environment and node_modules state may differ"
---

# Phase 8: Shops Verification Report

**Phase Goal:** Deliver the full Shops module — a multi-tenant shop management system that lets
Org Admins add stores via Google OAuth, manage their details, and track connection health.
**Verified:** 2026-04-29T18:00:00Z
**Status:** PASSED
**Re-verification:** Yes — third pass after post-plan direct cleanup changes

---

## Summary of Post-Plan Cleanup Changes Verified

All 8 changes described in the verification prompt are confirmed present in the codebase:

| # | Change | File | Status | Evidence |
|---|--------|------|--------|----------|
| 1 | Removed LOCATION, PLACE ID, CONNECTION columns | `ShopTable.tsx` | CONFIRMED | Columns array has exactly 5 entries: SHOP NAME, REGION, CONTACT, STATUS, CREATED. No place_id or connection column. |
| 2 | Removed Connection method fieldset and Place ID field from edit form | `EditShopModal.tsx` | CONFIRMED | Form has 4 fields only: Shop Name, Region, Phone, Street Address. No fieldset, no place_id input anywhere. |
| 3 | Added `existingPlaceIds` prop to disable already-connected listings | `CreateShopModal.tsx` | CONFIRMED | Prop declared at line 37, accepted at line 40, used at line 295 to set `alreadyAdded` flag on listings in picker. |
| 4 | `takenPlaceIds` state tracked in ShopModals, passed to CreateShopModal | `ShopModals.tsx` | CONFIRMED | `useState<Set<string>>` at line 67; updated on create success at line 177; passed as `existingPlaceIds` at line 182. |
| 5 | Modal refactored to flex-column with sticky footer | `frontend/src/widgets/modal/Modal.tsx` | CONFIRMED | Panel: `flex flex-col max-h-[80vh]` (line 63); content: `flex-1 min-h-0 overflow-y-auto` (line 84); footer: `shrink-0` (line 86). |
| 6 | COOP fix: try/catch around popup.closed + immediate Redis poll on close | `OAuthConnectionSection.tsx` | CONFIRMED | try/catch at lines 75-78 silences cross-origin COOP error; immediate `getOAuthResult("")` at line 93 on popup close; 800ms grace window at line 116 before `onError("closed")`. |
| 7 | UniqueConstraint for place_id per org on Shop model | `apps/shops/models.py` + migration `0004` | CONFIRMED | `UniqueConstraint(fields=["organisation","place_id"], condition=Q(place_id__gt=""), name="shop_unique_place_id_per_org")` in Meta; `0004_unique_place_id_per_org.py` chains from `0003`. |
| 8 | Duplicate place_id validation in ShopCreateSerializer | `apps/shops/serializers.py` | CONFIRMED | Line 84: `Shop.objects.filter(organisation_id=org_id, place_id=place_id).exists()` with error "This location has already been added to your organisation." |

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Google integration layer exists with OAuth + Places primitives and domain exceptions | VERIFIED | `oauth.py` (build_auth_url, exchange_code_for_token, list_business_locations), `places.py` (validate_place_id @retry), `exceptions.py` (4 exception classes) in `apps/integrations/google/` |
| 2 | Shop service layer enforces allocation with select_for_update and has activate/deactivate/reconnect_oauth | VERIFIED | `services/shops.py`: create_shop uses select_for_update, ShopAtLimitError on count >= limit; activate_shop, deactivate_shop, reconnect_oauth all present with @transaction.atomic; reveal_api_key and rotate_api_key correctly absent |
| 3 | Shop selector provides search/filter/allocation/region-existence with no MANUAL/city/zip references | VERIFIED | `selectors/shops.py`: list_shops filters on Q(name__icontains) \| Q(street_address__icontains) only; active_only param for XMOD-03; get_has_regions, get_allocation_status returning {current, max, at_limit} |
| 4 | DRF viewset exposes list/create/update/activate/deactivate/reconnect/oauth_result; reveal_key and rotate_key are absent | VERIFIED | ShopViewSet has activate, deactivate, reconnect, oauth_result @actions; no reveal_key or rotate_key; COOP header on OAuth views; allocation envelope on list |
| 5 | React frontend is GOOGLE_OAUTH-only with 3-step create flow, duplicate-listing prevention, no RevealKeyModal/RotateKeyModal | VERIFIED | ConnectionMethod = "GOOGLE_OAUTH" \| "NOT_CONNECTED"; CreateShopModal 3-step with existingPlaceIds; ShopModals tracks takenPlaceIds; no reveal/rotate modals or event subscriptions; OAuthConnectionSection has COOP fix |

**Score:** 5/5 truths verified

---

### Required Artifacts

#### Backend

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/integrations/google/exceptions.py` | 4 exception classes | VERIFIED | GoogleUnreachableError, GoogleAuthError, PlaceIDNotFoundError, APIKeyInvalidError |
| `apps/integrations/google/oauth.py` | build_auth_url, exchange_code_for_token, list_business_locations | VERIFIED | All 3 exported with @retry decorators |
| `apps/integrations/google/places.py` | validate_place_id with retry | VERIFIED | @retry(stop_after_attempt(3)) |
| `apps/shops/models.py` | ConnectionMethod = GOOGLE_OAUTH \| NOT_CONNECTED; no api_key; UniqueConstraint on place_id per org | VERIFIED | No MANUAL in choices; no api_key field; UniqueConstraint with condition Q(place_id__gt="") |
| `apps/shops/migrations/0004_unique_place_id_per_org.py` | Adds UniqueConstraint | VERIFIED | Chains from 0003; AddConstraint operation confirmed |
| `apps/shops/services/shops.py` | create/update/activate/deactivate/reconnect; no reveal/rotate | VERIFIED | 5 service functions; reveal_api_key and rotate_api_key absent |
| `apps/shops/selectors/shops.py` | list_shops, get_has_regions, get_allocation_status | VERIFIED | City removed from Q filters; all 3 present |
| `apps/shops/serializers.py` | ShopCreateSerializer with duplicate place_id check; ShopUpdateSerializer with LOCKED_FIELDS; no RotateKeySerializer | VERIFIED | Duplicate check at line 84; LOCKED_FIELDS = {"connection_method", "place_id"} at lines 98-100; no RotateKeySerializer |
| `apps/shops/views.py` | ShopViewSet with activate/deactivate/reconnect/oauth_result; GoogleOAuthStartView; GoogleOAuthCallbackView; no reveal/rotate | VERIFIED | All confirmed; COOP header set on all OAuth responses |

#### Frontend

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/widgets/modal/Modal.tsx` | flex-column, sticky footer, flex-1 min-h-0 overflow-y-auto on content | VERIFIED | `flex flex-col max-h-[80vh]` on panel (line 63); `flex-1 min-h-0 overflow-y-auto` on content (line 84); `shrink-0` on footer (line 86) |
| `frontend/src/widgets/shop-management/types.ts` | ConnectionMethod = "GOOGLE_OAUTH" \| "NOT_CONNECTED" only | VERIFIED | Exact union; no api_key or city/zip in payloads |
| `frontend/src/widgets/shop-management/CreateShopModal.tsx` | 3-step OAuth-only; existingPlaceIds prop disabling already-connected listings | VERIFIED | Step state: "connect" \| "pick" \| "form"; existingPlaceIds prop at lines 37/40/295; no MANUAL branch |
| `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` | Yellow button; try/catch on popup.closed (COOP); immediate Redis poll on close; 800ms grace | VERIFIED | bg-yellow (line 184); try/catch (lines 75-78); getOAuthResult("") immediately on close (line 93); setTimeout 800ms (line 116) |
| `frontend/src/widgets/shop-management/ShopTable.tsx` | 5 columns only (no LOCATION/PLACE ID/CONNECTION); no reveal/rotate actions | VERIFIED | Columns: SHOP NAME, REGION, CONTACT, STATUS, CREATED; SHOP_ACTIONS: details, edit, deactivate, activate, reconnect only |
| `frontend/src/widgets/shop-management/ShopModals.tsx` | takenPlaceIds state; passed to CreateShopModal; no reveal/rotate event subscriptions | VERIFIED | useState<Set<string>> line 67; updated line 177; passed as existingPlaceIds line 182; event map has no reveal/rotate entries |
| `frontend/src/widgets/shop-management/EditShopModal.tsx` | 4 fields only (Shop Name, Region, Phone, Street Address) — no connection_method fieldset, no place_id | VERIFIED | Full file read confirms exactly 4 fields; no fieldset element; no place_id input |
| No `RevealKeyModal.tsx` or `RotateKeyModal.tsx` | Must not exist | VERIFIED | Confirmed absent in previous pass; no new files added |
| `templates/shops/oauth/callback.html` | window.opener.postMessage with state + listings_json | VERIFIED | Both present; error path sends oauth_error; success path sends oauth_listings |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/shops/serializers.py` ShopCreateSerializer | Shop model uniqueness | `Shop.objects.filter(organisation_id=org_id, place_id=place_id).exists()` in validate() | WIRED | App-level duplicate check (line 84); DB-level UniqueConstraint (migration 0004) as backstop |
| `frontend/src/widgets/shop-management/ShopModals.tsx` | `CreateShopModal.tsx` | `existingPlaceIds={takenPlaceIds}` prop at line 182 | WIRED | takenPlaceIds populated from initial shop data; new place_ids added to set on create success (line 177) |
| `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` | Backend Redis result | `getOAuthResult("")` in close-watcher (line 93) and polling interval (line 133) | WIRED | Immediate on-close poll bridges COOP-blocked postMessage; 30s polling fallback as safety net |
| `frontend/src/widgets/modal/Modal.tsx` | Content overflow containment | `flex-1 min-h-0 overflow-y-auto` on content div | WIRED | Panel is bounded by `max-h-[80vh] flex flex-col`; footer always visible via `shrink-0` |
| `apps/shops/serializers.py` ShopUpdateSerializer | Field mutation prevention | `LOCKED_FIELDS = {"connection_method", "place_id"}` at lines 98-100; validated at line 117 | WIRED | API rejects PATCH/PUT with these fields; UI omits them entirely (defence in depth) |

---

### Requirements Coverage

| Requirement | Description | Status | Notes |
|-------------|-------------|--------|-------|
| SHOP-01 | Allocation counter "Shops (X / Y)" | SATISFIED | Unchanged from previous verification |
| SHOP-02 | + Add Shop disabled at limit | SATISFIED | Unchanged |
| SHOP-03 | Search/filter/pagination | SATISFIED | Unchanged |
| SHOP-04 | Shop row columns | SATISFIED (REVISED) | Post-cleanup: LOCATION, PLACE ID, CONNECTION columns removed. Remaining: name, region, contact, status, created. ConnectionStatusPill still used in ShopDetailsModal; not rendered in table. |
| SHOP-05 | Connection status pill | SATISFIED | ConnectionStatusPill.tsx still exists and used in ShopDetailsModal; absent from table columns (removed in cleanup). |
| SHOP-06 | Pagination 10/25/50/100 default 10 | SATISFIED | Unchanged |
| SHOP-07 | Empty State A/B | SATISFIED | Unchanged |
| SHOP-08 | Create modal — GOOGLE_OAUTH only | SATISFIED | Unchanged; 3-step OAuth-only flow |
| SHOP-09 | OAuth success auto-populates name + address | SATISFIED | Unchanged |
| SHOP-10 | Manual Place ID + API Key validation — RETIRED | RETIRED | Unchanged |
| SHOP-11 | OAuth popup flow | SATISFIED | COOP fix (try/catch + immediate Redis poll) strengthens this |
| SHOP-12 | OAuth popup edge cases | SATISFIED | Immediate Redis poll on close improves closed-popup detection reliability |
| SHOP-13 | Encrypted at rest, never transmitted | SATISFIED | Unchanged |
| SHOP-14 | Successful create closes modal, shows toast, refreshes list | SATISFIED | Unchanged |
| SHOP-15 | Shop Details modal — read-only grid + conditional footer | SATISFIED | ConnectionStatusPill still used here; Reconnect only for GOOGLE_OAUTH+ERROR/EXPIRED |
| SHOP-16 | Edit modal locks connection_method + place_id | SATISFIED (API-ONLY) | Post-cleanup: UI no longer renders these fields at all (stronger than locked UI). API-level enforcement via ShopUpdateSerializer.LOCKED_FIELDS remains intact. |
| SHOP-17 | Deactivate: amber confirm + slot-retention text | SATISFIED | Unchanged |
| SHOP-18 | Activate: blue confirm + toast | SATISFIED | Unchanged |
| SHOP-19 | Reveal Key — RETIRED | RETIRED | Unchanged |
| SHOP-20 | Rotate Key — RETIRED | RETIRED | Unchanged |
| SHOP-21 | Reconnect Google | SATISFIED | Unchanged |
| XMOD-01 | Shop cannot be created without a Region | SATISFIED | Unchanged |
| XMOD-03 | Deactivated shops excluded from Team scope | PARTIAL | active_only=True prerequisite implemented; full Phase 9 enforcement out of scope |
| XMOD-04 | Allocation counter transactional, no race | SATISFIED | Unchanged; select_for_update in create_shop |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ShopTable.tsx` | 93 | `// TODO: fetch full region list from API for complete dropdown` | Info | Region filter shows only regions in current page. UX limitation, not a blocker. |
| `templates/shops/oauth/callback.html` | — | Listing picker rendered in React modal (step 2), not in popup | Info | Functionally equivalent to CONTEXT.md spec. Not a blocker. |

No new anti-patterns introduced by the post-plan cleanup changes.

---

### Regression Finding (Warning — No Blocking Impact)

**SHOP-16 UI layer change:**

The previous verification credited `EditShopModal.tsx` for rendering a `<fieldset disabled>` for connection_method and a `disabled readOnly` place_id input. The post-plan cleanup removed these fields from the edit form entirely. The form now has 4 fields: Shop Name, Region, Phone, Street Address only.

This is a simplification, not a security regression:
- The API-level `ShopUpdateSerializer.LOCKED_FIELDS = {"connection_method", "place_id"}` remains the canonical enforcement.
- The previous UI lock was defence-in-depth; the new approach (omitting the fields entirely) is equally effective.
- No client-side bypass path exists because the fields are not present in the form submission.

No action required. Flagged for documentation only.

---

### Human Verification Required

#### 1. Org Admin Shop List Page — Simplified Columns

**Test:** Log in as Org Admin, navigate to /admin/org/shops/
**Expected:** Table shows exactly 5 columns: SHOP NAME, REGION, CONTACT, STATUS, CREATED — no LOCATION, PLACE ID, or CONNECTION column visible
**Why human:** Django template rendering + live data requires a running server

#### 2. Duplicate-Listing Prevention in OAuth Flow

**Test:** Add one shop via OAuth. Click "+ Add Shop" again with the same Google account.
**Expected:** In the listing picker (step 2), the already-added listing is disabled/greyed out and cannot be selected
**Why human:** Real Google OAuth + real browser required; takenPlaceIds -> existingPlaceIds wiring needs visual confirmation

#### 3. Popup Closure Detection (COOP Fix)

**Test:** Open OAuth popup then close it manually before completing auth
**Expected:** Within ~1.3s, modal shows "Connection cancelled. Please try again."
**Why human:** window.closed polling via setInterval requires a real browser event loop

#### 4. Edit Shop Modal — Simplified Form

**Test:** Click three-dot menu on any shop, click "Edit"
**Expected:** Modal shows Shop Name, Region, Phone, Street Address only — no connection method radio, no Place ID field
**Why human:** React rendering in browser required to confirm absent UI elements

#### 5. API-Level Lock Verification

**Test:** Using DevTools Network tab or curl, PATCH /api/v1/shops/{id}/ with `{"connection_method": "NOT_CONNECTED"}`
**Expected:** 400 with validation error rejecting the locked field
**Why human:** Requires HTTP client; automated test coverage should exist but manual smoke-test recommended

#### 6. Vite Build

**Test:** Run `cd frontend && npm run build`
**Expected:** Build succeeds without TypeScript errors; shop-management bundle present in static/dist/
**Why human:** Build environment and node_modules state may differ

---

## Gaps Summary

No gaps. All 5 observable truths verified. All 8 post-plan cleanup changes confirmed present in the codebase.

Phase goal is achieved: Org Admins can create and manage shops connected via Google OAuth, with duplicate-listing prevention (both app-layer and DB-level UniqueConstraint), allocation enforcement, connection status tracking, and activate/deactivate flow. The Modal layout refactor ensures sticky footers work correctly in all modals. The COOP fix ensures popup closure is reliably detected even when Chrome blocks cross-origin property access.

---

_Verified: 2026-04-29T18:00:00Z_
_Verifier: Claude (gsd-verifier) — third-pass re-verification after post-plan direct cleanup_
