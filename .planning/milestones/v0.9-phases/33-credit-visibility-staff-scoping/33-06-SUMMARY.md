---
phase: 33-credit-visibility-staff-scoping
plan: 06
subsystem: ui
tags: [react, vitest, credits, shops, modal, useSyncExternalStore]

requires:
  - phase: 33-credit-visibility-staff-scoping
    provides: "creditBand, format, creditsStore, contact, mailto and BuyMoreCreditsModal client kit (33-03)"
  - phase: 33-credit-visibility-staff-scoping
    provides: "ShopRow credit fields and credit-contact bootstrap on the Shops page (33-01); shop credits GET (33-04)"
provides:
  - getShopCredits / ShopCredits / ShopCreditsError client for GET /api/v1/shops/{id}/credits/
  - CreditsCard (AI Reply Credits card in Shop Details) with loading, error + Retry, not-enabled and band-coloured populated states
  - CreditBadge (Shops-list CREDITS column) with every D-02/D-04 state and store precedence
  - shop:open-credits event, focusCredits/dismissible/onBuyMore on ShopDetailsModal, sibling Buy More modal in ShopModals
  - useShops store seeding and the defensive Staff "No shops assigned" empty state behind isOrgAdmin
affects: [33-07]

actuals:
  tokens: 11000
  tasks: 3
  commits: 3

plan_head_before: 854a17cf1c606a414d7b813865c34a6224b0479e
plan_head_after: 485326884c2e2693c7061d81494ade598f3e8290

tech-stack:
  added: []
  patterns:
    - "Card result tagged with its shopId; an outcome for another shop is treated as loading so a fast switch never shows stale numbers"
    - "Stacked modals: second modal rendered as a sibling and the lower Modal set dismissible=false while it is open, so Escape closes one modal at a time"
    - "List loads mirror credit fields into the shared module store, so a later row without them keeps its last known badge"

key-files:
  created:
    - frontend/src/widgets/credits/creditsApi.ts
    - frontend/src/widgets/credits/CreditsCard.tsx
    - frontend/src/widgets/credits/CreditsCard.test.tsx
    - frontend/src/widgets/credits/CreditBadge.tsx
    - frontend/src/widgets/credits/CreditBadge.test.tsx
  modified:
    - frontend/src/widgets/shop-management/types.ts
    - frontend/src/widgets/shop-management/ShopDetailsModal.tsx
    - frontend/src/widgets/shop-management/ShopModals.tsx
    - frontend/src/widgets/shop-management/ShopModals.test.tsx
    - frontend/src/widgets/shop-management/ShopTable.tsx
    - frontend/src/widgets/shop-management/ShopTable.test.tsx
    - frontend/src/widgets/shop-management/useShops.ts
    - frontend/src/entrypoints/shop-management.tsx

key-decisions:
  - "Credit dates use formatUtcDate (Sep, never Sept) rather than the UI-SPEC en-GB suggestion; ShopDetailsModal's local-time formatDate is untouched"
  - "CreditsCard stores the request outcome with its shopId and derives loading when the shop changed, instead of resetting state in an effect"
  - "focusCredits is reset by an effect on detailsOpen so every way of closing Shop Details (Close, Edit, Activate, Deactivate, Reconnect) clears it"
  - "Entrypoint reads data-is-org-admin once before mounting either root and defaults to true when the modals root is absent"

patterns-established:
  - "Sibling-modal Escape ordering: dismissible={otherModalOpen === false} on the lower Modal"

requirements-completed: [CVIS-01, CVIS-02, CVIS-04]

coverage:
  - id: D1
    description: "Tracer: badge click opens Shop Details with the credits card fetched from the shop credits GET, showing 35 / 100, the period label and the UTC renewal date, focus on the card heading"
    requirement: CVIS-01
    verification:
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopModals.test.tsx#should open Shop Details with a populated credits card focused on its heading when shop:open-credits fires"
        status: pass
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopTable.test.tsx#should render a credits badge that dispatches shop:open-credits with the row when clicked"
        status: pass
    human_judgment: false
  - id: D2
    description: "Card states: aria-busy skeleton without Buy More, role=alert error with Retry, not-enabled body without bar/number/renews, band classes and ARIA values, singular and thousands copy, omitted period/renews lines"
    requirement: CVIS-01
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/CreditsCard.test.tsx"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fresh fetch per open, abort on close, stale response for a previous shop ignored, store write makes the badge match the card"
    requirement: CVIS-01
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/CreditsCard.test.tsx#should never render a slow response for shop A after switching to shop B"
        status: pass
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopModals.test.tsx#should fetch credits again each time Shop Details is reopened"
        status: pass
    human_judgment: false
  - id: D4
    description: "Badge states (bands, 0 credits, Not enabled, dash, singular, 10,000 on one line), store precedence, list seeding with last-known preservation"
    requirement: CVIS-02
    verification:
      - kind: unit
        ref: "frontend/src/widgets/credits/CreditBadge.test.tsx"
        status: pass
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopTable.test.tsx#ShopTableWidget credit seeding"
        status: pass
    human_judgment: false
  - id: D5
    description: "Buy More from the card opens as a sibling dialog with the encoded shop context; first Escape closes only Buy More, second closes Shop Details; focus returns to the Buy More Credits button"
    requirement: CVIS-04
    verification:
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopModals.test.tsx#ShopModals Buy More from the credits card"
        status: pass
    human_judgment: false
  - id: D6
    description: "Defensive Staff empty state (No shops assigned, no CTA) behind isOrgAdmin; filtered-empty and Org Admin states unchanged"
    requirement: CVIS-02
    verification:
      - kind: unit
        ref: "frontend/src/widgets/shop-management/ShopTable.test.tsx#ShopTableWidget Staff empty state"
        status: pass
    human_judgment: false
  - id: D7
    description: "Two-Escape ordering and colour bands in a real browser (jsdom does not render layout or true focus return)"
    requirement: CVIS-04
    verification: []
    human_judgment: true
    rationale: "Backstop per plan: verify in a browser at /gsd-verify-work (33-VALIDATION manual rows)"

duration: 12 min
completed: 2026-11-11
---

# Phase 33 Plan 06: Shops credits card, badge and Buy More Summary

**Shops-page credit path end to end: a CREDITS badge opens Shop Details with a server-fresh AI Reply Credits card (all states), which stacks a sibling Buy More modal with correct Escape ordering, plus store seeding and a defensive Staff empty state.**

## Performance

- **Duration:** ~12 min (approximate; start time was not captured)
- **Completed:** 2026-11-11
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Files modified:** 13

## Accomplishments

- Tracer: `CreditBadge` in the Shops table dispatches `shop:open-credits`; `ShopModals` opens Shop Details with `focusCredits`; `CreditsCard` calls `getShopCredits` and renders "35 / 100", the period label and "Renews 1 Dec 2026 (UTC)" with focus on its heading.
- Card state machine: skeleton with `aria-busy`, `role="alert"` banner with "Retry Loading Credits", not-enabled copy with no bar/number/breakdown/renews line (no divide-by-zero), green/amber/red/muted bar bands with full progressbar ARIA, singular and thousands copy, omitted period/renews lines.
- Stale and lifecycle guards: abort on unmount, result tagged by `shopId` so a response for a previous shop never renders, fresh fetch per open, result written to the shop-keyed store so the badge agrees with the card.
- Stacked Buy More: `BuyMoreCreditsModal` rendered as a sibling of Shop Details; Shop Details is `dismissible={false}` while it is open so Escape closes one at a time; focus returns to the Buy More Credits button.
- Badge: all D-02/D-04 states, store beats row, `useShops` seeds the store from bootstrap and every list load and keeps the last known value when a later row lacks credit fields.
- Staff "No shops assigned" empty state behind `isOrgAdmin` (default true); entrypoint passes the page's `data-is-org-admin`.

## Task Commits

1. **Task 1: Tracer, badge to card end to end** - `2829c65` (feat)
2. **Task 2: Card states and stacked Buy More** - `56a5b2c` (feat)
3. **Task 3: Badge states, seeding, Staff empty state** - `4853268` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Reset the focus flag on every Shop Details close path**
- **Found during:** Task 1
- **Issue:** Plan resets `focusCredits` only when the modal closes via `onClose`; Edit/Activate/Deactivate/Reconnect close Shop Details without it, so a later "View Details" would steal focus to the card heading.
- **Fix:** An effect in `ShopModals` clears `focusCredits` whenever `detailsOpen` becomes false.
- **Files modified:** `frontend/src/widgets/shop-management/ShopModals.tsx`
- **Commit:** 2829c65

**2. [Rule 1 - Bug] Card showed the previous shop's numbers while loading a new shop**
- **Found during:** Task 2 (RED test for the shop A to B switch)
- **Issue:** Simple local state kept shop A's data until shop B resolved.
- **Fix:** State holds `{shopId, data|error}`; an outcome for a different shop counts as loading.
- **Files modified:** `frontend/src/widgets/credits/CreditsCard.tsx`
- **Commit:** 56a5b2c

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug). **Impact:** none on scope.

### Process notes (not deviations)

- Task 1's `CreditBadge` already implements the not-enabled, dash and empty states (the plan staged them for Task 3); Task 3 therefore added tests and store seeding rather than the component states, so those badge tests passed on first run.
- Task 2's card and Task 1's tracer card were staged as planned: loading/error/not-enabled were absent in the tracer commit and the Task 2 tests failed (4 RED) before the state machine was added.
- In the focus-return test the Buy More button is focused explicitly before the click, because jsdom's `fireEvent.click` does not move focus the way a real click does.

## Known Stubs

None.

## Threat Flags

None. T-33-26..T-33-29 mitigations are covered by tests (stale-shop guard, no bar at total 0, sibling modal + two-Escape, text/title/aria-label on every badge state).

## Verification

- `npm test` in `frontend/`: 39 files, 349 tests pass.
- `npx tsc --noEmit`: clean.
- All task acceptance greps pass (including `No shops assigned` = 1, `isOrgAdmin` in the entrypoint = 3).
- Not run here: real-browser two-Escape ordering and colour bands (backstop for `/gsd-verify-work`). Frontend production build not run (not required by the plan).

## Self-Check: PASSED

- Created files exist: creditsApi.ts, CreditsCard.tsx, CreditsCard.test.tsx, CreditBadge.tsx, CreditBadge.test.tsx.
- Commits 2829c65, 56a5b2c, 4853268 are ancestors of HEAD.
