---
phase: 33-credit-visibility-staff-scoping
plan: 05
subsystem: ui
tags: [react, vitest, credits, reply-composer, django-template, json-script]

requires:
  - phase: 33-credit-visibility-staff-scoping
    provides: shared credit client kit (creditsStore, contact reader, BuyMoreCreditsModal, format) from plan 33-03
  - phase: 30-metered-ai-reply-generation
    provides: GET credit-cost and POST generate-reply contracts (402/409/422/502 bodies)
provides:
  - credit-contact json_script bootstrap on the Reviews page (organisation name, support email)
  - getCreditCost, GenerateReplyResult, InsufficientCreditsBody, readInsufficientCredits in review-management/api.ts
  - credit-aware ReplyComposer state machine (loading, ready, not enabled, insufficient, load error)
  - 402 handling that keeps the draft and switches state; 409 banner; 422/502 store updates
affects: [33-06, 33-07]

actuals:
  tokens: 40000
  tasks: 3
  commits: 3

plan_head_before: 1a6f7170abe7d7104b202003f158f383d3f5046f
plan_head_after: eae3dfee9f4d908bd4b8148545ae943661f4424e

tech-stack:
  added: []
  patterns:
    - "Composer reads the shop balance through useShopCredits and writes it with setShopCredits on every credit-bearing response, so sibling composers of one shop stay in sync"
    - "Cost fetch effect with AbortController and an attempt counter (StrictMode-safe, reused by Retry Credit Check)"
    - "Single derived creditState (none|loading|ready|not_enabled|insufficient|load_error) drives button, status line and Buy More link"

key-files:
  created:
    - frontend/src/widgets/review-management/ReplyComposer.test.tsx
  modified:
    - apps/reviews/views.py
    - templates/reviews/review_list.html
    - apps/reviews/tests/test_views.py
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/ReplyComposer.tsx

key-decisions:
  - "Cost is only ever the server's number (credit-cost response or the 402 body's required); the client never derives one from review text"
  - "Load error fails open (button enabled, no cost suffix) with a Retry Credit Check button; the server 402 remains the spend authority"
  - "A 402 also sets costStatus to ready so a prior load error cannot mask the server's reason, required and remaining"
  - "Composer reads the bootstrap through readCreditContact() rather than prop-drilling through ReviewTable"

patterns-established:
  - "Credit refusal is a state change in place (no banner, no toast); only 409/422/502/429 use the red banner"

requirements-completed: [CVIS-03, CVIS-04]

coverage:
  - id: D1
    description: "Reviews page renders credit-contact bootstrap for Org Admin and Staff (empty organisation name without an organisation, script-closing tag escaped)"
    requirement: CVIS-04
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestReviewListCreditContactBootstrap"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tracer: composer shows the server cost on the AI button and the shop's remaining credits, and the line updates after a generate"
    requirement: CVIS-03
    verification:
      - kind: unit
        ref: "frontend/src/widgets/review-management/ReplyComposer.test.tsx#ReplyComposer credit awareness (tracer, CVIS-03)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every disabled state explains itself inline (star-only, loading, not enabled, insufficient with Buy More, load error with retry); tone pills carry the cost once a draft exists and are disabled while generating; Buy More mailto carries no review text"
    requirement: CVIS-03
    verification:
      - kind: unit
        ref: "frontend/src/widgets/review-management/ReplyComposer.test.tsx#ReplyComposer credit states (CVIS-03, D-06, D-07)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Generate outcomes: 402 keeps the draft and focuses the textarea without a banner, 409 banner, 422/502 update the store, null credits_remaining ignored, two composers share a shop balance"
    requirement: CVIS-03
    verification:
      - kind: unit
        ref: "frontend/src/widgets/review-management/ReplyComposer.test.tsx#ReplyComposer generate outcomes (CVIS-03, D-08)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Insufficient-credits message wraps and the Generate with AI label does not collide with Use template at 360px"
    requirement: CVIS-03
    verification: []
    human_judgment: true
    rationale: "Layout at 360px width is not asserted by jsdom; deferred to /gsd-verify-work as the plan's backstop checks"

duration: 15min
completed: 2026-11-12
status: complete
---

# Phase 33 Plan 05: Reply composer credit awareness Summary

**ReplyComposer now fetches the server's credit cost, labels the AI button "Generate with AI · N credits", shows the shop's live remaining balance, explains every disabled state inline, and turns a 402 into an in-place state change that keeps the user's draft.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-11-12
- **Tasks:** 3 (1 tracer, 2 auto/tdd)
- **Files modified:** 6 (1 new)

## Accomplishments
- Reviews page bootstrap: `credit_contact` context (one extra `values_list` query for the organisation name, empty when the user has no organisation) rendered via `json_script:"credit-contact"`.
- `api.ts`: `getCreditCost`, typed `generateReply` result, `readInsufficientCredits` (402 body guard).
- Composer: five-state machine from the cost status and the shop-keyed store; status line with `role="status"`, `#92400E` insufficient copy, Retry Credit Check, Buy More Credits link opening the shared modal with shop name and numbers only.
- Tone pills read "Professional · N cr" with "N credit(s)" aria-labels once a draft exists; all disabled while a generate is in flight.
- Response handling: 402 adopts the server's reason/required/remaining and focuses the textarea; 409 banner copy; 422/502 write `credits_remaining` to the store; null values never overwrite a known balance; two composers of one shop share remaining while keeping their own cost.

## Task Commits

1. **Task 1: Tracer, bootstrap to cost label to live remaining line** - `f756f00` (feat)
2. **Task 2: Disabled states, tone-pill costs, Buy More link** - `197ea05` (feat)
3. **Task 3: Generate outcome handling (402/409/422/502, shared store)** - `eae3dfe` (feat)

**Plan metadata:** docs(33-05) commit following this summary.

## Files Created/Modified
- `apps/reviews/views.py`, `templates/reviews/review_list.html` - credit-contact bootstrap
- `apps/reviews/tests/test_views.py` - bootstrap tests (Org Admin, Staff, no-org, escaping)
- `frontend/src/widgets/review-management/api.ts` - cost client, result and 402 types
- `frontend/src/widgets/review-management/ReplyComposer.tsx` - credit state machine
- `frontend/src/widgets/review-management/ReplyComposer.test.tsx` - 21 composer tests (new)

## Decisions Made
- A 402 forces `costStatus` to ready so a previous load error cannot hide the server's numbers.
- 409 reuses the existing red banner (CONTEXT discretion item).
- Composer-launched Buy More omits total and month unless the store already knows them (research open question 4); Phase 30 contract unchanged.

## Deviations from Plan

None - plan executed exactly as written. (Tasks 2 and 3 are marked tdd; the implementation and tests were written together per task rather than as separate RED commits, matching the plan's one-commit-per-task structure.)

## Issues Encountered
- Vitest spy variables needed `MockInstance<typeof fn>` typing to satisfy `tsc --noEmit`.
- React `act` warnings from the templates fetch resolving after interaction; resolved by flushing in the test helper.

## Known Stubs

None.

## Threat Flags

None. T-33-22/23/24 mitigations are covered by tests: cost only from server responses, mailto without review text, json_script escaping.

## Verification
- `cd frontend && npm test`: 37 files, 304 tests passed; `npx tsc --noEmit`: clean
- `pytest apps/reviews apps/credits`: passed (pg-only tests skipped on SQLite)
- ruff, mypy and pre-commit hooks passed on all three commits
- Backstop for /gsd-verify-work: the two 360px layout checks (insufficient message wrapping; AI label vs Use template)

## Next Phase Readiness
Plan 33-06 (Shops credit UI) can proceed independently; the composer entry point to Buy More is in place for the phase walk-through in 33-07.

---
*Phase: 33-credit-visibility-staff-scoping*
*Completed: 2026-11-12*

## Self-Check: PASSED
