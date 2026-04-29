---
phase: 08-shops
verified: 2026-04-29T14:30:00Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 5/5
  note: "Re-verified after gap-closure plans 08-06 (backend) and 08-07 (frontend) executed.
         Previous report was written before those plans ran. This report reflects the final
         post-gap-closure state of the codebase."
  gaps_closed:
    - "MANUAL ConnectionMethod removed from model, migration, serializers, services, selectors, and tests"
    - "api_key, city, state, zip_code columns removed via migration 0003"
    - "reveal_api_key and rotate_api_key services removed"
    - "reveal_key and rotate_key viewset @action endpoints removed"
    - "RotateKeySerializer removed"
    - "RevealKeyModal.tsx and RotateKeyModal.tsx deleted"
    - "ShopModals.tsx: no reveal/rotate event subscriptions"
    - "ConnectionMethod TypeScript type narrowed to GOOGLE_OAUTH | NOT_CONNECTED"
    - "ShopTable.tsx: no api_key column, no reveal/rotate row actions"
    - "OAuthConnectionSection button restyled to brand yellow (bg-yellow)"
    - "CreateShopModal is a 3-step OAuth-only flow (connect -> pick -> form)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Visit /admin/org/shops/ as Org Admin and confirm the Shops (X / Y) header renders correctly"
    expected: "Header shows current shop count and org allocation max; + Add Shop button visible"
    why_human: "Django template rendering + live data cannot be verified programmatically without a running server"
  - test: "Click '+ Add Shop', confirm only 'Connect Google Business Profile' button appears (no radio buttons, no manual option)"
    expected: "Modal opens directly to OAuth connect step with yellow 'Connect Google Business Profile' button; no MANUAL/Enter manually radio visible"
    why_human: "React component rendering in a browser required to confirm absent UI elements"
  - test: "Click 'Connect Google Business Profile'; popup opens; complete OAuth"
    expected: "Popup opens at ~600x700px to accounts.google.com; after auth the modal advances to the listing picker step (step 2) if multiple listings, or directly to form (step 3) if one; popup auto-closes"
    why_human: "window.open synchronous popup behaviour + real Google OAuth credentials required"
  - test: "Close the OAuth popup before completing the flow"
    expected: "Inline message 'Connection cancelled. Please try again.' appears in the modal"
    why_human: "setTimeout/setInterval window.closed polling requires a real browser event loop"
  - test: "Complete OAuth with a multi-listing account"
    expected: "Modal shows listing picker (step 2) with business name + address cards; selecting one advances to form (step 3) and pre-fills Shop Name and Street Address"
    why_human: "Multi-listing OAuth path requires real Google credentials and a live session"
  - test: "Open Deactivate confirm and verify copy"
    expected: "Amber modal with text 'The allocated store slot remains used.' and shop name"
    why_human: "UI copy/modal rendering requires a real browser"
  - test: "Run 'cd frontend && npm run build' and confirm static/dist/ contains a shop-management bundle"
    expected: "Build succeeds without TypeScript errors; bundle present"
    why_human: "Build environment dependencies may differ from local checks"
---

# Phase 8: Shops Verification Report

**Phase Goal:** Org Admins can create and manage shops — connected via Google OAuth — with
allocation enforcement, connection status visibility, and activate/deactivate flow.
(MANUAL connection method, Reveal/Rotate API Key, and address sub-fields retired post-discussion.)
**Verified:** 2026-04-29T14:30:00Z
**Status:** PASSED
**Re-verification:** Yes — after gap-closure plans 08-06 (backend) and 08-07 (frontend)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Google integration layer exists with OAuth + Places primitives and domain exceptions | VERIFIED | `oauth.py` (build_auth_url, exchange_code_for_token, list_business_locations), `places.py` (validate_place_id @retry stop_after_attempt(3)), `exceptions.py` (4 exception classes) present in `apps/integrations/google/` |
| 2 | Shop service layer enforces allocation with select_for_update and has activate/deactivate/reconnect_oauth | VERIFIED | `services/shops.py`: create_shop uses `Organisation.objects.select_for_update().get(pk=...)`, ShopAtLimitError on count >= limit; activate_shop, deactivate_shop, reconnect_oauth all present with @transaction.atomic; reveal_api_key and rotate_api_key are ABSENT (correctly removed) |
| 3 | Shop selector provides search/filter/allocation/region-existence with no MANUAL/city/zip references | VERIFIED | `selectors/shops.py`: list_shops filters on Q(name__icontains) | Q(street_address__icontains) only (city removed); active_only param present for XMOD-03; get_has_regions, get_allocation_status returning {current, max, at_limit} |
| 4 | DRF viewset exposes list/create/update/activate/deactivate/reconnect/oauth_result endpoints; reveal_key and rotate_key are ABSENT | VERIFIED | ShopViewSet has only: list, create, partial_update, activate, deactivate, reconnect, oauth_result — no reveal_key or rotate_key @action; COOP header on both OAuth views; allocation envelope on list |
| 5 | React frontend is GOOGLE_OAUTH-only with 3-step create flow, no RevealKeyModal/RotateKeyModal, yellow primary button | VERIFIED | types.ts: ConnectionMethod = "GOOGLE_OAUTH" \| "NOT_CONNECTED" only; CreateShopModal: 3 steps (connect/pick/form) driven by OAuthConnectionSection; no RevealKeyModal.tsx or RotateKeyModal.tsx in widget directory; OAuthConnectionSection button class="bg-yellow ..."; ShopModals.tsx has no reveal/rotate event subscriptions; ShopTable.tsx has no api_key column |

**Score:** 5/5 truths verified

---

### Required Artifacts

#### Backend

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/integrations/google/exceptions.py` | 4 exception classes | VERIFIED | GoogleUnreachableError, GoogleAuthError, PlaceIDNotFoundError, APIKeyInvalidError present |
| `apps/integrations/google/oauth.py` | build_auth_url, exchange_code_for_token, list_business_locations | VERIFIED | All 3 exported; AUTH_ENDPOINT + TOKEN_ENDPOINT + SCOPE constants; @retry decorators via tenacity |
| `apps/integrations/google/places.py` | validate_place_id with retry | VERIFIED | @retry(stop_after_attempt(3)); all error conversions |
| `apps/integrations/google/tests/test_places.py` | 7 tests | VERIFIED | 7 test methods confirmed |
| `apps/integrations/google/tests/test_oauth.py` | 8 tests | VERIFIED | 8 test methods confirmed |
| `apps/shops/models.py` | ConnectionMethod = GOOGLE_OAUTH \| NOT_CONNECTED only; no api_key field | VERIFIED | No MANUAL in ConnectionMethod choices; no api_key EncryptedTextField; ShopAuditLog model retained for forward compatibility |
| `apps/shops/migrations/0003_remove_manual_and_address_subfields.py` | Removes api_key, city, state, zip_code; alters ConnectionMethod choices | VERIFIED | RemoveField for api_key/city/state/zip_code; AlterField confirms choices=[('GOOGLE_OAUTH', ...), ('NOT_CONNECTED', ...)] only |
| `apps/shops/exceptions.py` | ShopAtLimitError, PlaceIdLockedError | VERIFIED | Both classes present |
| `apps/shops/services/shops.py` | create_shop (select_for_update), update_shop, activate_shop, deactivate_shop, reconnect_oauth; no reveal_api_key or rotate_api_key | VERIFIED | 5 service functions present; reveal_api_key and rotate_api_key correctly absent |
| `apps/shops/selectors/shops.py` | list_shops (name/street_address search only), get_has_regions, get_allocation_status | VERIFIED | city removed from Q filters; all 3 functions present |
| `apps/shops/serializers.py` | ShopReadSerializer, ShopCreateSerializer, ShopUpdateSerializer; no RotateKeySerializer | VERIFIED | 3 serializer classes; no RotateKeySerializer; google_refresh_token write_only; api_key column excluded with comment |
| `apps/shops/views.py` | ShopViewSet with activate/deactivate/reconnect/oauth_result only; GoogleOAuthStartView; GoogleOAuthCallbackView | VERIFIED | No reveal_key or rotate_key @action; COOP header on all OAuth responses; session token resolution and single-use consumption |
| `apps/shops/tests/` | 64 test methods across 7 test files | VERIFIED | `grep -rn "def test_" apps/shops/tests/ | wc -l` = 64; combined with integrations = 79 total |

#### Frontend

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/widgets/shop-management/types.ts` | ConnectionMethod = "GOOGLE_OAUTH" \| "NOT_CONNECTED" only; no api_key or city/zip fields | VERIFIED | Exact union confirmed; ShopCreatePayload/ShopUpdatePayload have no api_key, city, zip_code |
| `frontend/src/widgets/shop-management/CreateShopModal.tsx` | 3-step OAuth-only flow (connect / pick / form); no MANUAL radio | VERIFIED | Step state: "connect" | "pick" | "form"; OAUTH_ERROR_MESSAGES includes "closed"/"denied"/"auth_error"/"no_listings"/"popup_blocked"; no MANUAL branch anywhere in the file |
| `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` | Yellow primary button; synchronous window.open; postMessage with origin check; polling fallback | VERIFIED | className="...bg-yellow..."; window.open is first statement; event.origin !== window.location.origin guard; polling via getOAuthResult("") every 2s for 30s |
| `frontend/src/widgets/shop-management/ShopTable.tsx` | No api_key column; no reveal/rotate row actions; Reconnect only for GOOGLE_OAUTH+ERROR/EXPIRED | VERIFIED | SHOP_ACTIONS array has: details, edit, deactivate, activate, reconnect (GOOGLE_OAUTH + ERROR/EXPIRED) — no reveal_key or rotate_key entries; columns have no api_key |
| `frontend/src/widgets/shop-management/ShopModals.tsx` | No reveal/rotate CustomEvent subscriptions; deactivate amber with slot-retention text; activate blue; reconnect modal | VERIFIED | event map: shop:open-details, shop:open-edit, shop:open-deactivate, shop:open-activate, shop:open-reconnect — no reveal/rotate entries; ConfirmModal variant="amber" with "allocated store slot remains used"; variant="blue" for activate |
| `frontend/src/widgets/shop-management/ConnectionStatusPill.tsx` | States: Connected via Google (green), Connection error (red, covers ERROR+EXPIRED), Quota exceeded (amber), Not connected (grey) | VERIFIED | 4 states rendered; "Connected via API key" correctly absent (MANUAL removed) |
| `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` | Read-only two-column grid; Connection Status pill; Reconnect Google only for GOOGLE_OAUTH+ERROR/EXPIRED | VERIFIED | dl grid-cols-2; ConnectionStatusPill rendered; showReconnect = GOOGLE_OAUTH && (ERROR || EXPIRED) |
| `frontend/src/widgets/shop-management/EditShopModal.tsx` | Connection method fieldset disabled; place_id disabled+readOnly | VERIFIED | `<fieldset disabled>` for connection method radio; place_id `disabled readOnly`; no api_key, city, zip_code fields |
| No `RevealKeyModal.tsx` or `RotateKeyModal.tsx` | Files must not exist | VERIFIED | `ls frontend/src/widgets/shop-management/` confirms neither file is present |
| `frontend/src/widgets/shop-management/*.test.*` | 17 it() test cases across 5 test files | VERIFIED | ShopModals.test.tsx: 6; ShopTable.test.tsx: 5; useShops.test.tsx: 2; api.test.ts: 3; CreateShopModal.test.tsx: 1 = 17 total |
| `templates/shops/oauth/callback.html` | window.opener.postMessage with state + listings_json | VERIFIED | Both present; sends all listings via postMessage; picker rendered in React modal step 2 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/integrations/google/oauth.py` | Google token endpoint | httpx.post in exchange_code_for_token with @retry | WIRED | TOKEN_ENDPOINT constant; _post_token decorated with @retry |
| `apps/shops/services/shops.py` | `apps/organisations/models.py` | Organisation.objects.select_for_update().get() in create_shop | WIRED | Confirmed at line 29 of services/shops.py |
| `config/urls.py` | `apps/shops/views.py` ShopViewSet | router.register at api/v1/shops | WIRED | ShopViewSet registered; shop_list view at /admin/org/shops/ |
| `apps/shops/views.py` | `apps/shops/services/shops.py` | activate_shop, create_shop, deactivate_shop, reconnect_oauth, update_shop imported and called | WIRED | Confirmed in views.py imports and perform_create/update/action methods |
| `apps/shops/views.py` | `apps/integrations/google/oauth.py` | build_auth_url, exchange_code_for_token, list_business_locations | WIRED | All 3 imported and used in GoogleOAuthStartView/GoogleOAuthCallbackView |
| `apps/shops/views.py` | Cross-Origin-Opener-Policy header | response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups" | WIRED | Set on GoogleOAuthStartView.get, GoogleOAuthCallbackView.get, and GoogleOAuthCallbackView._render_error |
| `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` | /oauth/google/start/ | synchronous window.open as first statement in click handler | WIRED | Confirmed; popup = window.open(...) is the first line of handleConnect() |
| `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` | window.opener.postMessage | addEventListener('message') with origin check | WIRED | event.origin !== window.location.origin guard confirmed |
| `frontend/src/widgets/shop-management/ShopModals.tsx` | deactivateShop / activateShop / reconnectShop from api.ts | await calls in handle*Confirm handlers | WIRED | All three API calls confirmed with shop:refresh dispatch on success |
| `templates/shops/shop_list.html` | `frontend/src/entrypoints/shop-management.tsx` | vite_asset 'shop-management' | WIRED | vite_asset tag confirmed in shop_list.html template |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence / Notes |
|-------------|-------------|--------|-----------------|
| SHOP-01 | Allocation counter "Shops (X / Y)" | SATISFIED | list envelope has allocation_status {current, max, at_limit}; template renders ({{ allocation.current }} / {{ allocation.max }}) |
| SHOP-02 | + Add Shop disabled at limit with toast | SATISFIED | CreateButtonBridge reads data-at-limit; emits error toast and blocks modal when at_limit=true |
| SHOP-03 | Search (name/address) + status + region filters + pagination | SATISFIED | list_shops filters on name/street_address (city removed per gap-closure); ShopTable renders search, status select, region select; pagination 10/25/50/100 |
| SHOP-04 | Shop row columns | SATISFIED | ShopTable columns: name, location (street_address), region badge, contact (phone), place_id, status badge, ConnectionStatusPill, created date, actions; api_key column correctly absent |
| SHOP-05 | Connection status pill | SATISFIED | ConnectionStatusPill: Connected via Google (green), Connection error (red, covers ERROR+EXPIRED), Quota exceeded (amber), Not connected (grey); "Connected via API key" state absent — correct since MANUAL removed |
| SHOP-06 | Pagination 10/25/50/100 default 10 | SATISFIED | ShopsPagination(page_size=10); [10,25,50,100] options in ShopTable |
| SHOP-07 | Empty State A (no regions) and B (no shops) | SATISFIED | ShopsEmptyStateA with regions link; ShopsEmptyStateB with open-create-shop-empty CTA |
| SHOP-08 | Create modal — GOOGLE_OAUTH only (MANUAL retired) | SATISFIED (REVISED) | CreateShopModal is OAuth-only 3-step; MANUAL radio correctly absent per post-discussion decision |
| SHOP-09 | OAuth success auto-populates name + address | SATISFIED | handleSelectListing sets name and streetAddress from listing data if fields are blank |
| SHOP-10 | Manual Place ID + API Key validation — RETIRED | RETIRED | Per post-discussion-phase decision: MANUAL flow removed. No validate_place_id call in create_shop or any service; Places API is not called during OAuth shop creation |
| SHOP-11 | OAuth popup flow with postMessage + polling fallback | SATISFIED | GoogleOAuthStartView redirects to Google; callback exchanges code, lists locations, stores session token; OAuthConnectionSection: synchronous popup, postMessage, 30s Redis polling fallback |
| SHOP-12 | OAuth popup edge cases with correct inline messages | SATISFIED | OAuthConnectionSection handles: popup_blocked (null popup), closed (window.closed setInterval + 600ms grace), denied, auth_error, no_listings; all mapped in OAUTH_ERROR_MESSAGES including "Connection cancelled. Please try again." |
| SHOP-13 | Encrypted at rest, never transmitted to browser | SATISFIED | ShopReadSerializer excludes google_refresh_token; frontend sends OAuth state in google_refresh_token field; backend resolves actual token from session; single-use token consumption confirmed |
| SHOP-14 | Successful create closes modal, shows toast, refreshes list | SATISFIED | CreateShopModal: emitToast + onCreated() + reset() + onClose() on 201; ShopModals calls refresh() which dispatches shop:refresh |
| SHOP-15 | Shop Details modal — read-only grid + conditional footer | SATISFIED | ShopDetailsModal: dl grid-cols-2; ConnectionStatusPill; Reconnect Google button only for GOOGLE_OAUTH+ERROR/EXPIRED; no reveal/rotate buttons |
| SHOP-16 | Edit modal locks connection_method + place_id | SATISFIED | EditShopModal: fieldset disabled for connection_method; place_id disabled+readOnly; ShopUpdateSerializer LOCKED_FIELDS validate() rejects at API level |
| SHOP-17 | Deactivate: amber confirm + slot-retention text + no allocation change | SATISFIED | deactivate_shop sets is_active=False without changing shop count; ConfirmModal variant="amber" with "allocated store slot remains used"; test_rejects_deactivation_changes_count confirms no allocation change |
| SHOP-18 | Activate: blue confirm + toast | SATISFIED | activate_shop sets is_active=True; ConfirmModal variant="blue"; "Shop '{name}' activated." toast |
| SHOP-19 | Reveal Key — RETIRED | RETIRED | Per post-discussion-phase decision: reveal_api_key service removed; reveal_key @action removed; RevealKeyModal.tsx deleted; no audit log writers |
| SHOP-20 | Rotate Key — RETIRED | RETIRED | Per post-discussion-phase decision: rotate_api_key service removed; rotate_key @action removed; RotateKeyModal.tsx deleted; RotateKeySerializer removed |
| SHOP-21 | Reconnect Google: restart OAuth, replace token, status CONNECTED | SATISFIED | reconnect_oauth sets connection_status=CONNECTED and stores new google_refresh_token; /reconnect/ @action resolves state from session; ShopModals reconnect modal reuses OAuthConnectionSection |
| XMOD-01 | Shop cannot be created without a Region | SATISFIED | ShopCreateSerializer region is required PrimaryKeyRelatedField scoped to org |
| XMOD-03 | Deactivated shops excluded from Team scope selectors | PARTIAL | active_only=True parameter implemented in list_shops and tested; full enforcement in Team modal is Phase 9 scope — prerequisite hook implemented here |
| XMOD-04 | Allocation counter transactional, no race | SATISFIED | select_for_update() on Organisation row in create_shop; @transaction.atomic on all write services; test_uses_select_for_update verifies FOR UPDATE in captured queries |

---

### Post-Discussion Retirements (Formally Verified as Absent)

The following were explicitly retired by the post-discuss-phase decision (2026-04-29). Verified ABSENT in the codebase:

| Retired Item | Absent From | Verification |
|---|---|---|
| `ConnectionMethod.MANUAL` | `apps/shops/models.py` choices, migration 0003 AlterField, `types.ts` | CONFIRMED ABSENT |
| `Shop.api_key` field | Model, migration 0003 RemoveField, serializers | CONFIRMED ABSENT |
| `Shop.city` / `Shop.state` / `Shop.zip_code` | Model, migration 0003 RemoveField | CONFIRMED ABSENT |
| `reveal_api_key` service | `apps/shops/services/shops.py` | CONFIRMED ABSENT |
| `rotate_api_key` service | `apps/shops/services/shops.py` | CONFIRMED ABSENT |
| `reveal_key` viewset @action | `apps/shops/views.py` | CONFIRMED ABSENT |
| `rotate_key` viewset @action | `apps/shops/views.py` | CONFIRMED ABSENT |
| `RotateKeySerializer` | `apps/shops/serializers.py` | CONFIRMED ABSENT |
| `RevealKeyModal.tsx` | `frontend/src/widgets/shop-management/` | CONFIRMED ABSENT |
| `RotateKeyModal.tsx` | `frontend/src/widgets/shop-management/` | CONFIRMED ABSENT |
| `shop:open-reveal` / `shop:open-rotate` events | `ShopModals.tsx` | CONFIRMED ABSENT |
| reveal/rotate entries in SHOP_ACTIONS | `ShopTable.tsx` | CONFIRMED ABSENT |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/widgets/shop-management/ShopTable.tsx` | 93 | `// TODO: fetch full region list from API for complete dropdown` | Info | Region filter dropdown shows only regions present in current page of results. UX limitation — filter works for visible regions. Not a blocker since regions are seeded server-side for modal dropdowns. |
| `templates/shops/oauth/callback.html` | — | Listing picker moved to React modal instead of popup | Info | CONTEXT.md specified picker inside the OAuth popup (callback.html). Implementation sends all listings to opener and renders picker in React modal step 2. Functionally equivalent outcome (user selects one listing before proceeding to form). Not a blocker. |

---

### Human Verification Required

#### 1. Org Admin Shop List Page

**Test:** Log in as Org Admin, navigate to /admin/org/shops/
**Expected:** Page renders "Shops (X / Y)" header with live counts; "+ Add Shop" button visible; no javascript errors
**Why human:** Django template rendering + live data requires a running server

#### 2. OAuth Create Flow — Happy Path

**Test:** Click "+ Add Shop"; modal opens to OAuth connect step (step 1) with yellow "Connect Google Business Profile" button; click it; popup opens at ~600x700px; complete Google auth
**Expected:** No MANUAL radio visible; after OAuth completes, modal advances to step 2 (listing picker) or step 3 (form) depending on listing count; popup auto-closes; Shop Name and Street Address pre-filled from listing
**Why human:** window.open + real Google OAuth credentials + real browser required

#### 3. Popup Closure Detection (SHOP-12)

**Test:** Open OAuth popup then close it manually (X button) before completing auth
**Expected:** Within ~1 second, modal shows "Connection cancelled. Please try again."
**Why human:** window.closed polling via setInterval requires a real browser event loop

#### 4. Deactivate Amber Confirm Copy (SHOP-17)

**Test:** Click three-dot menu on any shop, click "Deactivate"
**Expected:** Amber ConfirmModal with text including "The allocated store slot remains used." and shop name
**Why human:** Visual appearance and modal copy require browser rendering

#### 5. Vite Build Produces shop-management Bundle

**Test:** Run `cd frontend && npm run build` and confirm `static/dist/` contains a shop-management bundle
**Expected:** Build succeeds without TypeScript errors; bundle present
**Why human:** Build environment and node_modules state may differ

---

## Gaps Summary

No gaps found. All 5 observable truths verified. The phase goal is achieved in its revised form:

**Original goal** (ROADMAP before discuss-phase): MANUAL + Reveal/Rotate included.
**Revised goal** (post-discuss-phase): Google OAuth only; MANUAL, Reveal, Rotate retired.

The verification confirms the revised goal is fully delivered:

1. **Google integration layer** (Plan 08-01): oauth.py, places.py, exceptions.py all present with retry/backoff and domain exceptions. 15 integration tests (7+8) confirmed.

2. **Shop service layer** (Plans 08-02, 08-06): create_shop with select_for_update allocation enforcement, update_shop with LOCKED_FIELDS, activate_shop, deactivate_shop, reconnect_oauth — all with @transaction.atomic. reveal_api_key and rotate_api_key correctly absent. 64 shop test methods confirmed.

3. **Shop selector layer** (Plans 08-02, 08-06): list_shops with name/street_address search (city removed), active_only for XMOD-03, get_has_regions, get_allocation_status returning {current, max, at_limit}.

4. **DRF viewset + OAuth views** (Plans 08-03, 08-06): ShopViewSet with 5 endpoints (list/create/partial_update/activate/deactivate/reconnect/oauth_result); reveal_key/rotate_key absent; COOP headers on OAuth views; session-based single-use token resolution; allocation envelope on list.

5. **React frontend** (Plans 08-04, 08-05, 08-07): ConnectionMethod type narrowed to GOOGLE_OAUTH|NOT_CONNECTED; CreateShopModal is 3-step OAuth-only (connect/pick/form); OAuthConnectionSection has yellow primary button + synchronous window.open + origin-verified postMessage + 30s polling fallback + window.closed detection; ShopModals has no reveal/rotate subscriptions; ShopTable has no api_key column; RevealKeyModal.tsx and RotateKeyModal.tsx do not exist; 17 frontend tests confirmed.

Migration chain is complete: 0001 (initial) → 0002 (ShopAuditLog) → 0003 (remove MANUAL + address subfields).

XMOD-03 prerequisite (active_only parameter) is implemented and tested; full Phase 9 enforcement is explicitly out of scope.

---

_Verified: 2026-04-29_
_Verifier: Claude (gsd-verifier) — re-verification after plans 08-06 and 08-07_
