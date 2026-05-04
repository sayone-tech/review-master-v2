---
phase: 12-ai-enrichment-pipeline
plan: "07"
subsystem: ui
tags: [react, typescript, tailwind, lucide-react, action-items, sentiment-badge]

dependency_graph:
  requires:
    - phase: 12-01
      provides: "ExtractedActionItem type + ReviewRow.extracted_action_items field in types.ts"
    - phase: 11-15
      provides: "SentimentBadge.tsx with amber-tint/amber token patterns + ReviewTable.tsx sentiment column"
  provides:
    - ActionItemChip.tsx — non-interactive amber count chip per UI-SPEC.md §3
    - ReviewTable.tsx sentiment column wraps SentimentBadge + ActionItemChip in flex flex-col gap-2
  affects:
    - Phase 13 — will replace ActionItemChip with clickable variant that opens Action Item modal

tech-stack:
  added: []
  patterns:
    - Non-interactive chip as <span> not <button> — visual indicator only, no focus ring, no onClick
    - Conditional chip rendering guarded by array.length > 0 check — no empty state chip
    - flex flex-col gap-2 pattern for stacking multiple indicators in a table cell

key-files:
  created:
    - frontend/src/widgets/review-management/ActionItemChip.tsx
  modified:
    - frontend/src/widgets/review-management/ReviewTable.tsx

key-decisions:
  - "ActionItemChip uses <span> not <button> — non-interactive in Phase 12 (CONTEXT.md locked decision); Phase 13 replaces with clickable chip that opens Action Item modal"
  - "bg-amber-tint/text-amber tokens reused from SentimentBadge Analyzing pill — visual cohesion signals both are AI-driven UI elements"
  - "r.extracted_action_items.length > 0 guard is safe without optional chaining — Plan 12-01 serializer always returns an array (default [])"
  - "Only the sentiment column accessor in ReviewTable.tsx was modified — all other columns, TOTAL_COLUMNS=8, renderExpanded, renderRowActions untouched"

patterns-established:
  - "Non-interactive count chip: <span> with aria-label, singular/plural copy, null-guard for zero count"
  - "Stacked cell rendering: flex flex-col gap-2 wrapper for multi-indicator cells in DataTable"

requirements-completed: [ENRCH-14]

duration: 2min
completed: "2026-05-02"
---

# Phase 12 Plan 07: ActionItemChip UI Component Summary

**Non-interactive amber count chip (ActionItemChip.tsx) wired into ReviewTable.tsx sentiment column beneath SentimentBadge, closing ENRCH-14 UI delivery.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-02T14:25:05Z
- **Completed:** 2026-05-02T14:27:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `ActionItemChip.tsx` — non-interactive amber-tint chip matching UI-SPEC.md §3 contract verbatim (Sparkles icon, singular/plural copy, no onClick/cursor-pointer/button)
- Updated `ReviewTable.tsx` sentiment column to stack SentimentBadge above ActionItemChip in a `flex flex-col gap-2` container when extracted_action_items is non-empty
- TypeScript type-check passes with zero errors; pre-commit hooks pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ActionItemChip.tsx** - `7a5ffeb` (feat)
2. **Task 2: Wire ActionItemChip into ReviewTable sentiment column** - `d488279` (feat)

## Files Created/Modified

- `frontend/src/widgets/review-management/ActionItemChip.tsx` — New non-interactive amber count chip; renders null for count ≤ 0
- `frontend/src/widgets/review-management/ReviewTable.tsx` — Sentiment column accessor wrapped in flex flex-col gap-2; ActionItemChip conditionally rendered beneath SentimentBadge

## Decisions Made

**1. ActionItemChip uses `<span>` not `<button>` (non-interactive in Phase 12)**

CONTEXT.md locked decision: Phase 12 chip is intentionally non-interactive — clicking opens nothing. Phase 13 will replace this component with a clickable variant that opens the Action Item modal (REVW-08 full delivery). Using `<span>` prevents accidental focus ring and keyboard tab stop that would confuse screen reader users who then try to activate it.

**2. Same amber-tint/amber tokens as SentimentBadge "Analyzing..." pill**

The amber palette is the established token for AI-driven UI elements in this codebase. The "Analyzing…" pill and the ActionItemChip are both signals of AI-extracted content. Reusing the same tokens (`bg-amber-tint` → #FEF3C7, `text-amber` → #D97706) creates visual cohesion that helps users understand "this information came from AI enrichment."

**3. `r.extracted_action_items.length > 0` is safe without optional chaining**

Plan 12-01's `ReviewReadSerializer` always serialises `extracted_action_items` as an array (the Django model field has `default=list`). The API never returns `null` or `undefined` for this field. No nullish-coalescing operators needed. The guard is purely to suppress rendering the chip when no action items have been extracted.

**4. Minimal-change ethos for ReviewTable.tsx**

Only the `sentiment` column accessor was modified. Every other column definition (`rating`, `shop`, `reviewer`, `date`, `reply_status`, `reply_cta`), `TOTAL_COLUMNS = 8`, `renderExpanded`, `renderRowActions`, `formatRelativeDate` — all untouched. This keeps the diff reviewable and makes it trivial to verify no regressions were introduced.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ENRCH-14 UI half is closed for action item count display
- Phase 13 can replace `ActionItemChip` with a clickable variant by changing only `ActionItemChip.tsx` and updating the Props interface — clean separation of concerns
- No backend changes required; chip activates automatically as soon as the GPT enrichment pipeline (Plans 12-02 through 12-06) populates `extracted_action_items`

---
*Phase: 12-ai-enrichment-pipeline*
*Completed: 2026-05-02*

## Self-Check: PASSED

- `frontend/src/widgets/review-management/ActionItemChip.tsx` — exists
- `frontend/src/widgets/review-management/ReviewTable.tsx` — exists
- `.planning/phases/12-ai-enrichment-pipeline/12-07-SUMMARY.md` — exists
- Commit `7a5ffeb` (Task 1: ActionItemChip.tsx) — verified
- Commit `d488279` (Task 2: ReviewTable.tsx update) — verified
