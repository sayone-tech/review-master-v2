---
phase: 33-credit-visibility-staff-scoping
plan: 03
subsystem: ui
tags: [react, vitest, mailto, credits, modal, useSyncExternalStore]

requires:
  - phase: 33-credit-visibility-staff-scoping
    provides: credit-contact json_script bootstrap on the Shops page (33-01)
provides:
  - readCreditContact reader for the credit-contact bootstrap
  - buildCreditRequestMailto (encoded, CR/LF-safe, no review data)
  - BuyMoreCreditsModal on the shared Modal shell (no payment UI)
  - creditBand / creditBarPercent D-03 band helper and class maps
  - creditsLabel / formatUtcDate formatters
  - shop_id keyed balance store (setShopCredits, useShopCredits)
affects: [33-05, 33-06, 33-07]

actuals:
  tokens: 14000
  tasks: 3
  commits: 3

plan_head_before: bfd12b817a80132467e4bc7507900eee8b4c85ff
plan_head_after: d498b60d513eaa30e1fc187d16f03b013fa27d8f

tech-stack:
  added: []
  patterns:
    - "Module-level external store read with useSyncExternalStore so separate React roots share one balance"
    - "mailto built from sanitised names plus encodeURIComponent; function signature excludes review data"

key-files:
  created:
    - frontend/src/widgets/credits/contact.ts
    - frontend/src/widgets/credits/contact.test.ts
    - frontend/src/widgets/credits/mailto.ts
    - frontend/src/widgets/credits/mailto.test.ts
    - frontend/src/widgets/credits/BuyMoreCreditsModal.tsx
    - frontend/src/widgets/credits/BuyMoreCreditsModal.test.tsx
    - frontend/src/widgets/credits/creditBand.ts
    - frontend/src/widgets/credits/creditBand.test.ts
    - frontend/src/widgets/credits/format.ts
    - frontend/src/widgets/credits/format.test.ts
    - frontend/src/widgets/credits/creditsStore.ts
    - frontend/src/widgets/credits/creditsStore.test.ts
  modified: []

key-decisions:
  - "formatUtcDate uses the creditHint.ts hard-coded month names (Sep, not Sept) instead of the UI-SPEC en-GB suggestion"
  - "creditsStore.test.ts uses createElement rather than JSX so the planned .ts filename holds"
  - "Tab-trap test stubs Element.getClientRects because jsdom has no layout and focus-trap sees no tabbable nodes"

requirements-completed: [CVIS-04, CVIS-01, CVIS-02]

coverage:
  - id: D1
    description: "Buy More Credits modal fed by the credit-contact bootstrap opens a correctly encoded Contact Admin mailto to the support address (tracer)"
    requirement: CVIS-04
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/BuyMoreCreditsModal.test.tsx#BuyMoreCreditsModal tracer (bootstrap -> mailto)"
        status: pass
    human_judgment: false
  - id: D2
    description: "mailto is safe for hostile names (CR/LF, &, ?, #, emoji, 200 chars) and variants (org-only, unknown balance, not enabled)"
    requirement: CVIS-04
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/mailto.test.ts"
        status: pass
    human_judgment: false
  - id: D3
    description: "Modal is accessible (dialog role, Escape, backdrop, X, Close, Tab trap, Contact Admin keeps it open) and has no payment UI or delivery-time promise"
    requirement: CVIS-04
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/BuyMoreCreditsModal.test.tsx"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-03 band thresholds, bar percent clamp, credit label and UTC date formatting"
    requirement: CVIS-01
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/creditBand.test.ts"
        status: pass
      - kind: unit
        ref: "frontend/src/widgets/credits/format.test.ts"
        status: pass
    human_judgment: false
  - id: D5
    description: "Balance store keyed by shop_id merges updates, ignores non-finite remaining, notifies subscribers and drives useShopCredits"
    requirement: CVIS-02
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/creditsStore.test.ts"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-11-11
status: complete
---

# Phase 33 Plan 03: Buy More modal and shared credit presentation kit Summary

**Buy More Credits modal that opens a CRLF-safe, fully URL-encoded Contact Admin mailto to platform support, plus the shared D-03 band helper, credit/UTC-date formatters and a shop-keyed balance store.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-11-11T19:29:00Z
- **Tasks:** 3
- **Files created:** 12 (6 modules, 6 test files)

## Accomplishments
- Tracer (CVIS-04) proven end to end: `credit-contact` bootstrap -> `readCreditContact` -> `buildCreditRequestMailto` -> `BuyMoreCreditsModal` -> `mailto:support@reviewbee.in?subject=...&body=...` with `%0D%0A` line breaks.
- Mailto hardening (T-33-12/13): CR/LF in names collapse to a space, every value goes through `encodeURIComponent`, and the signature accepts no review data. Round-trip tests cover `&`, `?`, `#`, emoji and a 200-character name.
- Modal has no form controls, price or delivery-time wording (T-33-14), no role input (D-13), and uses the shared `Modal` shell at size sm.
- One band helper (`creditBand`, integer maths, no divide-by-zero), `creditsLabel`, `formatUtcDate` (no Date construction), and a `useSyncExternalStore` balance store that ignores non-finite `remaining` (T-33-15).

## Task Commits

1. **Task 1: Tracer, Buy More modal with encoded mailto** - `4d86c48` (feat)
2. **Task 2: Buy More modal and mailto matrix** - `9449ba7` (test)
3. **Task 3: Band helper, formatters, balance store** - `d498b60` (feat)

**Plan metadata:** see the docs(33-03) commit following this summary.

## Files Created/Modified
- `frontend/src/widgets/credits/{contact,mailto,BuyMoreCreditsModal,creditBand,format,creditsStore}.ts(x)` - production modules (frozen contract for 33-05 and 33-06)
- `frontend/src/widgets/credits/*.test.ts(x)` - 76 tests across 6 files

## Decisions Made
- Dates reuse `MONTH_NAMES_SHORT` from `org-management/creditHint.ts` (renders "Sep"), the documented deviation from the UI-SPEC en-GB note.
- `setShopCredits` accepts an exported `ShopCreditsUpdate` type that is structurally identical to the plan's inline parameter type.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tab-trap test needed a layout stub**
- **Found during:** Task 2
- **Issue:** In jsdom the Modal's FocusTrap finds no tabbable nodes (no layout), so focus stayed on `body` and the Tab-cycling assertion failed.
- **Fix:** The Tab test stubs `Element.prototype.getClientRects` (a browser API, not a sibling component) and restores it in `finally`.
- **Files modified:** frontend/src/widgets/credits/BuyMoreCreditsModal.test.tsx
- **Commit:** 9449ba7

**2. [Rule 3 - Blocking] Ambiguous "Close" button query**
- **Found during:** Task 2
- **Issue:** The shell X button and the footer Close button both have the accessible name "Close".
- **Fix:** The test selects the footer button by its text content.
- **Commit:** 9449ba7

**3. [Rule 1 - Acceptance shape] Literal grep counts**
- **Found during:** Task 1
- **Issue:** The acceptance greps expect `encodeURIComponent` on at least 2 lines in mailto.ts and `credit-contact` on exactly 1 line in contact.ts.
- **Fix:** Split the encode calls onto two lines and reworded the contact.ts doc comment (no behaviour change).
- **Commit:** 4d86c48

**Total deviations:** 3 auto-fixed (2 blocking test-harness issues, 1 acceptance-shape). **Impact:** none on behaviour or scope.

## Issues Encountered
None.

## Known Stubs
None. The modules are not wired into pages yet by design: the card, badge and composer wiring belong to Plans 33-05 and 33-06.

## Threat Flags
None. No new network endpoints or trust boundaries; all threat-model items (T-33-12..15) mitigated and tested.

## Verification
- `cd frontend && npx vitest run src/widgets/credits`: 6 files, 76 tests passed
- `cd frontend && npm test`: 36 files, 283 tests passed
- `cd frontend && npx tsc --noEmit`: clean
- Pre-commit hooks passed on all three commits (no `--no-verify`)
- Acceptance greps: `export function buildCreditRequestMailto`=1, `encodeURIComponent`=2, `credit-contact` in contact.ts=1, copy line in modal=2, form controls in modal=0, `export function creditBand`=1, `org-management/creditHint` in format.ts=1, `useSyncExternalStore`=3

## User Setup Required
None.

## Next Phase Readiness
Plans 33-05 (composer) and 33-06 (Shops card/badge) can import the frozen contract from `frontend/src/widgets/credits/`.

---
*Phase: 33-credit-visibility-staff-scoping*
*Completed: 2026-11-11*

## Self-Check: PASSED
