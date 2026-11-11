---
phase: 32-superadmin-credit-controls
plan: 04
subsystem: frontend
tags: [react, typescript, vitest, org-management, credits, superadmin, modal]
status: complete

requires:
  - phase: 32-superadmin-credit-controls
    provides: "Plan 32-02 creditHint.ts helpers and OrgRow credit fields; Plan 32-03 shop credit list + bonus endpoints"
provides:
  - "creditsApi.ts: listCreditShops, allocateBonus, CreditsApiError, isPeriodMismatch and the frozen contract types"
  - "useCreditShops hook: 300 ms debounced, abortable, stale-safe paginated shop list"
  - "ManageCreditsModal: one size-lg Modal with list and Add Bonus Credits views"
  - "Manage Credits row action (every org status), Credits/shop table column + mobile card value"
  - "View Organisation Monthly credits per shop value with pending-change pill"
affects: [32-05, 33-credit-visibility]

requirements-completed: [CSUP-01, CRED-06]

actuals:
  tokens: 40000
  tasks: 3
  commits: 5
plan_head_before: 3036271d6909db458ba33aab66c5f3cf62ccb00c
plan_head_after: 8dd513104c26ecef214078ffd4600d7aa0f1ffe0

tech-stack:
  added: []
  patterns:
    - "Single Modal with internal view state (list | bonus); title, subtitle, footer and body swap per view so the shell and focus trap never remount"
    - "Request counter plus AbortController in the list hook so an older response can never overwrite a newer one"
    - "Bonus POST uses its own CreditsApiError that keeps the raw JSON body, so 409/400/404 are branched on status and shape (not api.ts handle())"
    - "Focus and highlight applied only after the post-allocation reload has rendered, so the row button survives the skeleton swap"

key-files:
  created:
    - frontend/src/widgets/org-management/creditsApi.ts
    - frontend/src/widgets/org-management/useCreditShops.ts
    - frontend/src/widgets/org-management/ManageCreditsModal.tsx
    - frontend/src/widgets/org-management/ManageCreditsModal.test.tsx
    - frontend/src/widgets/org-management/ViewOrgModal.test.tsx
  modified:
    - frontend/src/widgets/org-management/OrgTable.tsx
    - frontend/src/widgets/org-management/OrgTable.test.tsx
    - frontend/src/widgets/org-management/ViewOrgModal.tsx
    - frontend/src/entrypoints/org-management.tsx

key-decisions:
  - "409 period_mismatch applies the body's balance and period to the selected shop, awaits a list reload, keeps typed amount and reason, and never auto-resubmits (D-12, T-32-23)"
  - "404 toast copy is the D-23 wording 'This shop is no longer active.' (UI-SPEC alternative 'no longer available' is absent from the widget directory)"
  - "Row focus and the 3 s bg-yellow-tint highlight are set after the reload promise resolves, not when the view switches"

duration: ~25 min
completed: 2026-11-11
---

# Phase 32 Plan 04: Manage Credits modal, Credits/shop column and View Org note (CSUP-01 / CRED-06) Summary

Superadmin Manage Credits flow built to the approved 32-UI-SPEC: org row action, a single two-view modal (searchable, paginated shop list then bonus form with live before/after preview and one-click Allocate), every list/form/error state, plus the Credits/shop table column and the View Organisation allocation with a pending-change pill.

## Accomplishments

- **Tracer (CSUP-01):** from an org row, "Manage Credits" opens the modal, GETs `/api/v1/superadmin/organisations/{id}/credits/shops/?page=1`, shows `Acme — November 2026 · 100 credits per shop` and rows with `Monthly 100 · Bonus 20 · Used 85`; "Add bonus" switches views with no request; typing 50 previews `Remaining 35 → 85 · Bonus 20 → 70`; Allocate POSTs `{amount: 50, period_year: 2026, period_month: 11}` (no reason key) with `X-CSRFToken`, toasts `Added 50 credits to Alpha.`, returns to the list and refetches it.
- **List states (E5):** 5 skeleton rows with `aria-busy`, search kept interactive, `No active shops` and `No shops match "zzz"` + Clear search, load error + Retry, server pagination (10/page, `Showing 11–20 of 23`, disabled arrows at the ends, `No results` at zero), debounced search (one request per 300 ms pause, immediate refetch when cleared), stale-response guard.
- **Bonus form states (E6/E7):** live amount validation (disabled Allocate, `Enter a whole number between 1 and 10,000.`), submit guard (single POST, inputs/Back disabled), 409 amber banner with in-place refresh and a fresh click required (next POST carries `period_month: 12`), 404 toast + return to reloaded list, 400 messages under amount/reason with no toast, generic error toast with values kept, reason trimmed or omitted, `1 credit` / `1,000 credits` formatting, focus on search then amount then the updated row, 3 s static highlight.
- **D-14 / D-15:** `Credits/shop` right-aligned column (`Off` muted at 0, `1,000` separator) and mobile card row; View Organisation shows `{M} credits` / `1 credit` / `Off — AI replies are disabled` and the amber `This month: N (changes to M on 1 Dec 2026)` / `(turns off on ...)` pill only when this month differs.

## Task Commits

1. Task 1 (tracer): `74afeb3` feat(32-04): Manage Credits modal with bonus allocation and live preview
2. Task 2 RED: `7ff38e6` test(32-04): Manage Credits list and bonus states (10 of 18 failing)
3. Task 2 GREEN: `4832126` feat(32-04): Manage Credits list and bonus states (18 of 18 passing)
4. Task 3: `8dd5131` feat(32-04): Credits/shop column and View Organisation allocation with pending note

`commits: 5` is the measured `plan_head_before..HEAD` count; one of the five (`f9f83f8 docs(33): UI design contract`) was committed by another session during this run and is not part of this plan. This plan's own commits are the four above.

## Verification (real output)

- `cd frontend && npx vitest run src/widgets/org-management`: 9 files, **92 tests passed** (ManageCreditsModal 18, ViewOrgModal 5, OrgTable 11)
- `cd frontend && npx tsc --noEmit`: exit 0, no output
- `cd frontend && npm test`: **29 files, 193 tests passed**
- `cd frontend && npm run build` (`tsc --noEmit && vite build`): built in 2.66s (only the pre-existing chunk-size warning)
- Acceptance greps: creditsApi `/api/v1/superadmin/` 2; OrgTable `onOpenManageCredits` 2, `Manage Credits` 1, `Credits/shop` 2; entrypoint `onOpenManageCredits` 4, `ManageCreditsModal` 2; `size="lg"` 1; `This shop is no longer active.` 1; `no longer available` across the widget directory 0; 409 banner copy 1; `AbortController` 2; ManageCreditsModal `it(` 18; ViewOrgModal `it(` 5; `Monthly credits per shop` 1; `view-credit-pending` 1
- Pre-commit hooks ran on every commit (frontend-only, Python hooks skipped; whitespace, secrets and large-file hooks passed)
- Not run: the `frontend-react-builder` review subagent (Agent tool not available to this executor), the two backstop checks at 360px width (no browser or dev server; left for `/gsd-verify-work`), a manual 409 against a running backend (no docker/backend started), backend tests (no backend changes)

## Deviations from Plan

**1. [Rule 1 - Bug] Task 1 first rendered two Modal elements**
- **Found during:** Task 2 acceptance grep (`size="lg"` count was 2, plan expects 1)
- **Issue:** the tracer returned a separate `<Modal>` per view, so the shell remounted on every view change (the plan calls for one Modal with internal view state).
- **Fix:** Task 2 GREEN restructured to a single `<Modal size="lg">` whose title, subtitle, footer and body swap by view.
- **Files modified:** `ManageCreditsModal.tsx`
- **Commit:** `4832126`

**2. Ordering note (no rule triggered):** the Task 2 RED commit contains the full 18-test file (including the Task 1 tracer, rewritten to the fake-timer-with-advance setup shared by all tests); 8 tests already passed against the Task 1 implementation, 10 failed for the missing states, as intended.

**Total deviations:** 1 auto-fixed (bug). **Impact:** none on scope or contract.

## Threat Surface

T-32-22 mitigated (Allocate disabled and handler early-return while submitting; single-POST test). T-32-23 mitigated (displayed period echoed in every POST; 409 swaps period and balance and requires a fresh click; tested with `period_month: 12` on the second POST). T-32-24 mitigated (shop names rendered as React text nodes only). T-32-25 mitigated (`X-CSRFToken` from the csrftoken cookie, same-origin credentials; asserted in the tracer test). T-32-26 transferred (server-side IsSuperadmin in 32-03). T-32-SC-04 accepted (no packages installed). No new threat flags.

## Known Stubs

None.

## Next Phase Readiness

Plan 32-05 can cross-check the frozen contract: this plan consumes exactly the 32-03 shapes (list `{count, next, previous, period, allocation_per_shop, results}`; bonus 201, 400 field map, 409 `period_mismatch` with `balance`, 404 any body). Pending for `/gsd-verify-work`: 360px visual checks (2-column balance block, long names wrapping under the close button) and a forced month-rollover 409 against a running backend.

## Self-Check: PASSED

- Files exist: creditsApi.ts, useCreditShops.ts, ManageCreditsModal.tsx, ManageCreditsModal.test.tsx, ViewOrgModal.test.tsx, OrgTable.tsx, ViewOrgModal.tsx, entrypoints/org-management.tsx
- Commits `74afeb3`, `7ff38e6`, `4832126`, `8dd5131` are ancestors of HEAD
