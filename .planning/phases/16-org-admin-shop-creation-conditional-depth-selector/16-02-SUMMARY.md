---
phase: "16"
plan: "02"
subsystem: shops/frontend
tags: [sync-depth, react, conditional-render, shop-creation, bootstrap-tag]
dependency_graph:
  requires: [phase-16-01-backend-sync-depth-api, allow-custom-sync-depth-bootstrap]
  provides: [conditional-review-history-dropdown, sync-depth-prop-threading, shop-create-payload-sync-depth]
  affects: [shop-creation-wizard, CreateShopModal, ShopModals, shop-management-entrypoint]
tech_stack:
  added: []
  patterns: [react-conditional-render, bootstrap-tag-parseJson, useState-with-reset]
key_files:
  created: []
  modified:
    - frontend/src/widgets/shop-management/types.ts
    - frontend/src/entrypoints/shop-management.tsx
    - frontend/src/widgets/shop-management/ShopModals.tsx
    - frontend/src/widgets/shop-management/CreateShopModal.tsx
decisions:
  - "SyncDepth type and SYNC_DEPTH_LABELS added to types.ts (worktree branch did not have Phase 15 additions)"
  - "sync_depth always included in payload (not conditional) per D-05 — backend accepts any valid value"
  - "allowCustomSyncDepth threaded as prop (not context/store) per plan — shallow 2-level depth makes prop-drilling appropriate"
  - "setSyncDepth reset included in reset() to prevent stale state on modal reopen (RESEARCH pitfall 2)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-18"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 4
---

# Phase 16 Plan 02: Conditional Depth Selector Frontend Summary

**One-liner:** React conditional render of Review History select in CreateShopModal Step 3, gated on allowCustomSyncDepth prop threaded from shop-org-data bootstrap tag through ShopModals.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add sync_depth to ShopCreatePayload and wire allowCustomSyncDepth through entrypoint and ShopModals | b4604a6 | types.ts, shop-management.tsx, ShopModals.tsx |
| 2 | Add conditional Review History select to CreateShopModal Step 3 | e6cd136 | CreateShopModal.tsx |

## What Was Built

### Task 1: Types + Entrypoint + ShopModals prop threading
- Added `SyncDepth = "ONE_YEAR" | "TWO_YEARS" | "ALL_TIME"` type and `SYNC_DEPTH_LABELS` to `types.ts`
- Added `sync_depth?: string` to `ShopCreatePayload` (not `ShopUpdatePayload` — depth is immutable post-creation)
- Added `parseJson<{ allow_custom_sync_depth: boolean }>("shop-org-data", { allow_custom_sync_depth: false })` to the `shop-management.tsx` entrypoint
- Passed `allowCustomSyncDepth={orgData.allow_custom_sync_depth}` to `<ShopModals>` component
- Added `allowCustomSyncDepth?: boolean` to `ShopModalsProps` and destructured it; passed it through to `<CreateShopModal>`

### Task 2: CreateShopModal conditional Review History select
- Added `allowCustomSyncDepth?: boolean` to `Props` interface
- Imported `SyncDepth` type; added `const [syncDepth, setSyncDepth] = useState<SyncDepth>("TWO_YEARS")`
- Added `setSyncDepth("TWO_YEARS")` to `reset()` function to restore default on modal reopen
- Inserted `{allowCustomSyncDepth && (<div>...</div>)}` conditional block in Step 3 JSX after Region select, before Phone field, with:
  - `<label htmlFor="cs-sync-depth">Review History</label>`
  - Helper text: "Sets how far back this shop's initial review sync will go."
  - `<select id="cs-sync-depth">` with three options (ONE_YEAR/TWO_YEARS/ALL_TIME)
  - DOM-absent conditional render (not CSS hidden/disabled)
- Added `sync_depth: syncDepth` to the `ShopCreatePayload` submission object (always included per D-05)

## Checkpoint: Human Verify

**Task 3** is a `checkpoint:human-verify` gate requiring manual browser verification. This is pending human sign-off.

### Verification Steps Required

1. Start dev server (`make up`)
2. Log in as Org Admin with `allow_custom_sync_depth=False` → navigate to /shops/ → open Add Shop wizard → reach Step 3 → confirm NO Review History dropdown, no `id="cs-sync-depth"` in DOM
3. Log in as Org Admin with `allow_custom_sync_depth=True` → reach Step 3 → confirm dropdown IS visible after Region, before Phone, with default "Last 2 years" and three options
4. Select "Last 1 year" → Cancel → reopen → confirm reset to "Last 2 years"
5. Create shop with "Last 1 year" → verify shop detail shows "Last 1 year"

**Resume signal:** Type "approved" if all five verification steps pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Types] Added SyncDepth type and SYNC_DEPTH_LABELS to worktree types.ts**
- **Found during:** Task 1
- **Issue:** The worktree branch (`worktree-agent-ade8b032ff7c147c6`) was created from a commit before Phase 15's `SyncDepth` additions were merged to `feature/categories`. The plan's interface contract assumed `SyncDepth` already existed in `types.ts`, but the worktree's version did not have it.
- **Fix:** Added `SyncDepth` type and `SYNC_DEPTH_LABELS` to the worktree's `types.ts` alongside the plan-required `sync_depth?: string` addition to `ShopCreatePayload`.
- **Files modified:** `frontend/src/widgets/shop-management/types.ts`
- **Commit:** b4604a6
- **Note:** The main repo's `feature/categories` branch already had these types from Phase 15 (commit a331dcb). The worktree needed them added separately.

## Known Stubs

None — all changes are fully wired: bootstrap tag set by Plan 01 → parseJson in entrypoint → prop threading → conditional render → payload field → backend ChoiceField validates and persists.

## Threat Flags

None — no new network endpoints introduced. The `allow_custom_sync_depth` boolean flows via Django's built-in `json_script` filter (XSS-safe by design). The `sync_depth` field in the payload is validated by DRF `ChoiceField` (Plan 01, commit 09b2412) and returns 400 for invalid values. Fallback for missing `shop-org-data` tag is `false` — safe-fail direction (no dropdown shown, shop gets TWO_YEARS default).

## Self-Check: PASSED

Files confirmed present in worktree:
- `frontend/src/widgets/shop-management/types.ts` — contains `SyncDepth` type and `sync_depth?: string`
- `frontend/src/entrypoints/shop-management.tsx` — contains `parseJson` with `"shop-org-data"` and `allowCustomSyncDepth={orgData.allow_custom_sync_depth}`
- `frontend/src/widgets/shop-management/ShopModals.tsx` — contains `allowCustomSyncDepth?: boolean` in props and passes to CreateShopModal
- `frontend/src/widgets/shop-management/CreateShopModal.tsx` — contains `id="cs-sync-depth"`, `allowCustomSyncDepth && (`, `setSyncDepth("TWO_YEARS")` in reset(), `sync_depth: syncDepth` in payload

Commits confirmed:
- b4604a6 — Task 1 (types.ts, shop-management.tsx, ShopModals.tsx)
- e6cd136 — Task 2 (CreateShopModal.tsx)

TypeScript compilation: `npx tsc --noEmit` exits 0 (verified in main repo's frontend which shares the same node_modules)
Frontend build: `npm run build` exits 0 — all 44 chunks built without errors
Backend test suite: 892 passed, 2 skipped — coverage 88.09% (above 85% threshold)
Pre-commit: all 19 hooks passed
