---
phase: 32-superadmin-credit-controls
plan: 02
subsystem: frontend
tags: [react, typescript, vitest, org-management, credits, forms]
status: complete

requires:
  - phase: 32-superadmin-credit-controls
    provides: "Plan 32-01 API fields monthly_credit_allocation / current_month_credit_allocation on org list and create/update"
provides:
  - "creditHint.ts pure helpers: computeCreditHint, parseCreditInput, formatNextMonthStart, formatMonthYear, formatCount, month-name arrays"
  - "OrgRow / CreateOrgPayload / UpdateOrgPayload credit fields"
  - "Edit Organisation 'Monthly credits per shop' field with live deferred-change hint, changed-only PATCH"
  - "Create Organisation 'Monthly credits per shop' field (default 0) with helper, hint, validation and payload"
affects: [32-04, 33-credit-visibility]

requirements-completed: [CRED-01, CRED-06]

actuals:
  tokens: 8600
  tasks: 3
  commits: 3
plan_head_before: ee35211d1efdec17e43fe70987274f81e0e2f1aa
plan_head_after: c6344cc63becd0948061b01984f66b29096adb16

tech-stack:
  added: []
  patterns:
    - "Hint rule lives in a pure, React-free module so every state is table-tested without the DOM"
    - "UTC getters + hard-coded month-name arrays for the 1st-of-next-month date (no locale formatting)"
    - "Edit payload includes an optional field only when it differs from the value captured at modal open"

key-files:
  created:
    - frontend/src/widgets/org-management/creditHint.ts
    - frontend/src/widgets/org-management/creditHint.test.ts
    - frontend/src/widgets/org-management/EditOrgModal.test.tsx
  modified:
    - frontend/src/widgets/org-management/types.ts
    - frontend/src/widgets/org-management/EditOrgModal.tsx
    - frontend/src/widgets/org-management/CreateOrgModal.tsx
    - frontend/src/widgets/org-management/CreateOrgModal.test.tsx
    - frontend/src/widgets/org-management/OrgTable.test.tsx
    - frontend/src/widgets/org-management/StoreAllocationModal.test.tsx
    - frontend/src/widgets/org-management/DeleteConfirmModal.test.tsx
    - frontend/src/widgets/org-management/ResendInvitationModal.test.tsx

key-decisions:
  - "Hint keys on current_month_credit_allocation (D-21): immediate only when saved === 0 AND thisMonth === 0; the 'Shops keep N' number is always this month's value"
  - "Create and Edit forms use noValidate so the inline 'Enter a whole number between 0 and 10,000.' error shows instead of the browser's native min/max bubble"
  - "Edit sends monthly_credit_allocation only when it differs from the value captured at open (T-32-09)"

duration: ~11 min
completed: 2026-11-11
---

# Phase 32 Plan 02: Org credits field and live hint (CRED-01 / CRED-06) Summary

"Monthly credits per shop" on Create and Edit Organisation with a live inline hint that tells the Superadmin whether a change is immediate or applies on the 1st of next UTC month, using the same D-18/D-21 rule as the backend, and an Edit PATCH that sends the allocation only when it changed.

## Accomplishments

- **Tracer (end to end):** editing an organisation with 100 saved / 100 this month, typing 50 shows the amber hint "Takes effect on 1 Dec 2026. Shops keep 100 this month." (system time 2026-11-15 UTC) and Save sends `PATCH /api/v1/organisations/7/` with `monthly_credit_allocation: 50`.
- **Hint rule pinned (D-01, D-02, D-18, D-21):** a 26-case pure-function table covers create off/immediate, edit immediate (saved 0 and this month 0), the D-21 case (saved 0, this month 100 -> deferred "keep 100"), deferred decrease, deferred-off, unchanged positive (hidden), unchanged 0 (off) and invalid inputs hidden in both modes. UTC date edge cases (December -> "1 Jan 2027", September -> "Sep", month-end 23:30Z) are tested.
- **Edit field behaviour:** visible label bound by `htmlFor`/`id`, `aria-describedby` on the helper+hint wrapper, only the live line carries `role="status"`; empty or out-of-range value blocks submit with the red `role="alert"` message and no request; server 400 keyed `monthly_credit_allocation` renders under the field; a name-only edit omits the key from the PATCH body (silent-revert guard).
- **Create field (D-04):** prefilled 0 with static helper and the "AI replies are off" hint; typing 25 switches to the immediate hint and the POST carries `monthly_credit_allocation: 25`; out-of-range blocked client-side; server error displayed.
- **Types:** `OrgRow` gained both credit fields, payloads gained the allocation; four existing OrgRow test fixtures updated so `tsc --noEmit` stays clean.

## Task Commits

1. Task 1 (tracer): `eae5993` feat(32-02): Edit Organisation monthly credits per shop field with live timing hint
2. Task 2: `f35e188` test(32-02): pin credit hint states, UTC date edge cases and input parsing
3. Task 3: `c6344cc` feat(32-02): Create Organisation gains monthly credits per shop (default 0)

## Verification (real output)

- `cd frontend && npx vitest run src/widgets/org-management`: 7 files, **66 tests passed** (after Task 3)
- `npx vitest run src/widgets/org-management/creditHint.test.ts src/widgets/org-management/EditOrgModal.test.tsx`: 2 files, 35 tests passed (26 + 9)
- `npx tsc --noEmit`: exit 0, no output
- `npm test` (full frontend): **27 files, 167 tests passed**
- `npm run build` (`tsc --noEmit && vite build`): built in 2.67s (only the pre-existing chunk-size warning); output under `static/dist` is gitignored
- Acceptance greps all met: types.ts 3 x `monthly_credit_allocation` and 1 x `current_month_credit_allocation`; each of the four fixture files has `current_month_credit_allocation`; `edit-field-monthly_credit_allocation` 1; `htmlFor="edit-org-credits"` 1; `export function computeCreditHint` 1; `DateTimeFormat|toLocaleDateString` in creditHint.ts 0; `1 Jan 2027` 2 and `Shops keep 100 this month` 3 in creditHint.test.ts; EditOrgModal.test.tsx 9 `it(`; `data-testid="field-monthly_credit_allocation"` 1 in Create; Create test file 5 mentions; off-copy 1 in creditHint.ts
- Pre-commit hooks ran on all three commits (frontend-only changes, Python hooks skipped, secret and whitespace hooks passed)
- Not run: the `frontend-react-builder` review subagent (the plan says "if the Agent tool is available"; it is not available to this executor), visual verification at 360px (no browser/dev server per instructions), backend tests (no backend changes in this plan)

## Deviations from Plan

**1. [Rule 3 - Blocking] Create payload default added in Task 1**
- **Found during:** Task 1 `tsc --noEmit`
- **Issue:** making `CreateOrgPayload.monthly_credit_allocation` required broke compilation of `CreateOrgModal.tsx` until Task 3 wired the field, but Task 1's verify requires a clean `tsc`.
- **Fix:** Task 1 sent `monthly_credit_allocation: 0` (the same value the server defaults to) in the Create payload; Task 3 replaced it with `Number(credits)`.
- **Files modified:** `CreateOrgModal.tsx`
- **Commit:** `eae5993` (placeholder), `c6344cc` (real wiring)

**2. [Rule 1 - Bug] `noValidate` on the Create and Edit forms**
- **Found during:** Task 1 test run (out-of-range test)
- **Issue:** `type="number" max=10000` made jsdom (and real browsers) block submit natively, so the required inline error "Enter a whole number between 0 and 10,000." never rendered, contradicting the E1 error contract.
- **Fix:** added `noValidate` to both forms. Every field is already validated in `validate()` with inline errors, so no validation was lost; only the native bubbles for the other `required`/`min`/`max` fields are replaced by the existing inline errors.
- **Files modified:** `EditOrgModal.tsx`, `CreateOrgModal.tsx`
- **Commit:** `eae5993`

**3. Ordering note (no rule triggered):** the full EditOrgModal behaviour suite (hint states, validation, server error, changed-only payload, a11y wiring) was written alongside the tracer test and landed in the Task 1 commit; Task 2's commit therefore contains only `creditHint.test.ts`. Both Task 2 test files passed on first run (the Task 1 implementation already satisfied them), so there was no RED commit or GREEN fix commit.

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug). **Impact:** none on scope; `noValidate` slightly changes how pre-existing fields surface errors (inline instead of native bubble).

## Threat Surface

T-32-09 mitigated (changed-only PATCH, tested by the name-only edit asserting the key is absent). T-32-10 mitigated (hint keys on server-supplied `current_month_credit_allocation`; saved 0 / this month 100 -> deferred is pinned). T-32-11 and T-32-SC-02 accepted as planned (client checks are UX only; no packages installed). No new threat flags.

## Known Stubs

None.

## Next Phase Readiness

Plan 32-04 can import `formatNextMonthStart`, `formatMonthYear`, `formatCount`, `MONTH_NAMES_*` and `parseCreditInput` from `creditHint.ts`, and `OrgRow` already carries `monthly_credit_allocation` and `current_month_credit_allocation` for the table column and View Organisation pending note.

## Self-Check: PASSED

- Files exist: creditHint.ts, creditHint.test.ts, EditOrgModal.test.tsx, types.ts, EditOrgModal.tsx, CreateOrgModal.tsx, CreateOrgModal.test.tsx and the four fixture test files
- Commits `eae5993`, `f35e188`, `c6344cc` are ancestors of HEAD; `git rev-list --count ee35211..HEAD` = 3
