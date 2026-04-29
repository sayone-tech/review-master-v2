---
phase: 08-shops
plan: "07"
subsystem: frontend
tags: [react, typescript, cleanup, gap-closure]

# Dependency graph
requires:
  - phase: 08-shops-06
    provides: Simplified backend contract — no MANUAL, no api_key, no city/state/zip_code
provides:
  - Frontend type surface mirroring new backend (GOOGLE_OAUTH | NOT_CONNECTED only)
  - OAuth-only CreateShopModal (3-step connect → pick → form; no manual radio)
  - Yellow primary CTA on "Connect Google Business Profile" button
  - Deleted RevealKeyModal.tsx + RotateKeyModal.tsx
  - ShopTable without api_key column; LOCATION renders street_address only
  - ShopModals without reveal/rotate event subscriptions
  - 17 Vitest tests passing; clean tsc; valid Vite bundle
affects: [phase-09-onwards, production-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Surgical frontend gap-closure: delete modal files, trim types, update column definitions"
    - "Brand yellow primary button: bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover"

key-files:
  deleted:
    - frontend/src/widgets/shop-management/RevealKeyModal.tsx
    - frontend/src/widgets/shop-management/RotateKeyModal.tsx
  modified:
    - frontend/src/widgets/shop-management/types.ts
    - frontend/src/widgets/shop-management/api.ts
    - frontend/src/widgets/shop-management/CreateShopModal.tsx
    - frontend/src/widgets/shop-management/CreateShopModal.test.tsx
    - frontend/src/widgets/shop-management/EditShopModal.tsx
    - frontend/src/widgets/shop-management/ShopDetailsModal.tsx
    - frontend/src/widgets/shop-management/ConnectionStatusPill.tsx
    - frontend/src/widgets/shop-management/OAuthConnectionSection.tsx
    - frontend/src/widgets/shop-management/ShopTable.tsx
    - frontend/src/widgets/shop-management/ShopTable.test.tsx
    - frontend/src/widgets/shop-management/ShopModals.tsx
    - frontend/src/widgets/shop-management/ShopModals.test.tsx

key-decisions:
  - "RevealKeyModal + RotateKeyModal files deleted entirely — no migration needed, no imports remain"
  - "OAuthConnectionSection button restyled to bg-yellow primary — matches brand CTA pattern from RegionEmptyState"
  - "CreateShopModal.test.tsx reduced to 1 smoke test — manual-path tests (Enter manually, api_key field errors) deleted as retired"
  - "ShopTable LOCATION column simplified to street_address only — city/state/zip secondary line removed"
  - "ShopModals event map reduced from 7 to 5 events (no reveal-key, rotate-key)"

patterns-established:
  - "Gap-closure: delete test cases for retired UI paths rather than maintaining them green"

requirements-completed: [SHOP-04, SHOP-08, SHOP-09, SHOP-10, SHOP-11, SHOP-13, SHOP-15, SHOP-16, SHOP-19, SHOP-20]

# Metrics
duration: ~35min (split across two sessions; Task 3 completed manually after executor connection error)
completed: "2026-04-29"
---

# Phase 8 Plan 07: Frontend Cleanup — Drop MANUAL and Address Subfields

**Surgical removal of MANUAL connection method, api_key UI, city/state/zip_code fields, and Reveal/Rotate modals from the React frontend; OAuth button restyled to brand yellow primary**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-04-29
- **Tasks:** 3
- **Files deleted:** 2 (RevealKeyModal.tsx, RotateKeyModal.tsx)
- **Files modified:** 12

## Accomplishments

- Trimmed `types.ts`: `ConnectionMethod` → `"GOOGLE_OAUTH" | "NOT_CONNECTED"` (no MANUAL); `ShopRow` loses `city`, `state`, `zip_code`, `api_key_masked`; `ShopCreatePayload`/`ShopUpdatePayload` lose same fields; `RotateKeyPayload`/`RevealKeyResponse` interfaces deleted
- `api.ts`: removed `revealKey` and `rotateKey` export functions; removed their type imports
- Deleted `RevealKeyModal.tsx` and `RotateKeyModal.tsx` entirely
- `CreateShopModal.tsx`: removed city/state/zip state hooks + JSX grid block; `CreateShopModal.test.tsx` trimmed to 1 smoke test (oauth-connect-button present on open)
- `EditShopModal.tsx`: removed city/state/zip hooks, reset calls, payload fields, JSX grid block, MANUAL radio option, and `connectionMethodLabel` const
- `ShopDetailsModal.tsx`: deleted City/State/ZIP row, API Key row; Connection Method cell simplified to Google OAuth / Not connected ternary
- `ConnectionStatusPill.tsx`: deleted `MANUAL + CONNECTED → "Connected via API key"` branch
- `OAuthConnectionSection.tsx`: restyled button to `bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover` (brand yellow primary); kept `data-testid="oauth-connect-button"` and ExternalLink icon
- `ShopTable.tsx`: removed `api_key` column, removed `city`/`state`/`zip_code` rendering from LOCATION column, updated search placeholder to "Search name, address…"
- `ShopTable.test.tsx`: removed `city`/`state`/`zip_code`/`api_key_masked` from `fakeRow()`; deleted 2 reveal-key tests → 5 tests remain
- `ShopModals.tsx`: removed `RevealKeyModal`/`RotateKeyModal` imports, `revealOpen`/`rotateOpen` state, `shop:open-reveal-key`/`shop:open-rotate-key` event listeners, and both JSX modals
- `ShopModals.test.tsx`: removed `city`/`state`/`zip_code`/`api_key_masked` from `row()` → 6 tests remain

## Task Commits

1. **Task 1: Types + API client + delete reveal/rotate modals** — `3763b11` (feat)
2. **Task 2: Modals, pill, OAuth button restyle** — `25e3717` (feat)
3. **Task 3: ShopTable, ShopModals, test cleanup** — `5a4429d` (feat)

## Files Created/Modified

- `frontend/src/widgets/shop-management/types.ts` — Trimmed type surface
- `frontend/src/widgets/shop-management/api.ts` — Removed revealKey/rotateKey
- `frontend/src/widgets/shop-management/RevealKeyModal.tsx` — **DELETED**
- `frontend/src/widgets/shop-management/RotateKeyModal.tsx` — **DELETED**
- `frontend/src/widgets/shop-management/CreateShopModal.tsx` — OAuth-only, no city/state/zip
- `frontend/src/widgets/shop-management/CreateShopModal.test.tsx` — 1 smoke test
- `frontend/src/widgets/shop-management/EditShopModal.tsx` — No city/state/zip, no MANUAL radio
- `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` — Grid trimmed
- `frontend/src/widgets/shop-management/ConnectionStatusPill.tsx` — No MANUAL branch
- `frontend/src/widgets/shop-management/OAuthConnectionSection.tsx` — Yellow primary button
- `frontend/src/widgets/shop-management/ShopTable.tsx` — No api_key column, simplified LOCATION
- `frontend/src/widgets/shop-management/ShopTable.test.tsx` — 5 tests (2 reveal-key tests deleted)
- `frontend/src/widgets/shop-management/ShopModals.tsx` — No reveal/rotate subscriptions
- `frontend/src/widgets/shop-management/ShopModals.test.tsx` — 6 tests (row helper trimmed)

## Test Results

```
Test Files  5 passed (5)
     Tests  17 passed (17)
  Duration  1.13s
```

## Build Output

```
../static/dist/assets/shop-management-CwKj-4_s.js   33.83 kB │ gzip: 9.44 kB
✓ built in 1.52s
```

TypeScript compile: **0 errors** (`tsc --noEmit`)

## Test Cases Deleted

From `ShopTable.test.tsx`:
- "Reveal Key item visible only for MANUAL shop"
- "Reveal Key NOT visible for OAuth shop"

From `CreateShopModal.test.tsx`:
- "clicking Enter manually shows place_id and api_key fields"
- "renders place_id field error when API responds with field errors"
- "renders non-field error at top when API responds with non_field_errors"

**Total deleted:** 5 test cases

## Deviations from Plan

### Task 3 manual execution (connection error recovery)

Task 3 was executed manually (inline) after the gsd-executor agent lost API connectivity mid-execution. The changes were identical to the plan's action items. All acceptance criteria verified and tests run manually before commit.

No functional deviations — all must_have truths satisfied.

## Final Verification

All plan `must_haves.truths` confirmed:

| Truth | Status |
|-------|--------|
| ConnectionMethod is 'GOOGLE_OAUTH' \| 'NOT_CONNECTED' — no MANUAL | ✅ |
| ShopRow has no city, state, zip_code, api_key_masked | ✅ |
| ShopCreatePayload has no city/state/zip/api_key | ✅ |
| ShopUpdatePayload has no city/state/zip | ✅ |
| RotateKeyPayload + RevealKeyResponse deleted | ✅ |
| api.ts has no revealKey/rotateKey functions | ✅ |
| RevealKeyModal.tsx + RotateKeyModal.tsx deleted | ✅ |
| ShopRowActionsMenu has no Reveal Key/Rotate Key entries | ✅ |
| ShopTable column list omits api_key column | ✅ |
| CreateShopModal has no Enter manually radio, no api_key input | ✅ |
| EditShopModal has no city/state/zip inputs and no MANUAL branch | ✅ |
| ShopDetailsModal grid omits City/State/ZIP, API Key rows | ✅ |
| ConnectionStatusPill has no MANUAL/'Connected via API key' branch | ✅ |
| ShopModals no longer subscribes to reveal-key/rotate-key events | ✅ |
| OAuth button uses yellow primary style | ✅ |
| Vitest passes; Vite build valid | ✅ |

---
*Phase: 08-shops*
*Completed: 2026-04-29*
