---
phase: 13-action-items-and-notifications
plan: 07
subsystem: ui
tags: [react, modal, action-items, reviews, exists-annotation, drf]

requires:
  - phase: 13-04
    provides: ActionItem REST API (transition-status, add-note, PATCH detail)
  - phase: 13-06
    provides: ActionItemManagementWidget shell, types, api, useActionItems hook
provides:
  - ActionItemModal with 3 tabs (Details / Notes / Source Review) and read/edit toggle
  - ActionItemCreateModal for manual creation with cross-field scope/shop validation
  - PriorityIndicator, NotesTab, SourceReviewTab supporting components
  - Clickable ActionItemChip upgrade on Reviews list (REVW-08 final delivery)
  - has_action_items annotation on Review queryset (Exists() — REVW-14 budget intact)
affects: [phase-14, future-action-item-extensions, reviews-list-ui]

tech-stack:
  added: []
  patterns:
    - "Tab-state hook pattern for modal sub-views"
    - "Read/edit toggle inside modal with optimistic local form state, server PATCH on Save"
    - "Exists() annotation for boolean badge fields — keeps query count flat"

key-files:
  created:
    - frontend/src/widgets/action-items/ActionItemModal.tsx
    - frontend/src/widgets/action-items/ActionItemCreateModal.tsx
    - frontend/src/widgets/action-items/PriorityIndicator.tsx
    - frontend/src/widgets/action-items/NotesTab.tsx
    - frontend/src/widgets/action-items/SourceReviewTab.tsx
  modified:
    - frontend/src/widgets/action-items/ActionItemManagementWidget.tsx
    - frontend/src/widgets/review-management/ActionItemChip.tsx
    - frontend/src/widgets/review-management/types.ts
    - apps/reviews/serializers.py
    - apps/reviews/views.py

key-decisions:
  - "Used Exists() annotation rather than denormalized counter — single SQL subquery, no migration overhead, REVW-14 budget unchanged"
  - "Source Review tab hidden when source=MANUAL — avoids empty state and matches plan truth"
  - "Scope and Shop strictly read-only in edit mode — enforced by absence of inputs, not just disabled attribute"

patterns-established:
  - "Modal-as-widget pattern: 3-tab Action Item modal sets the template for future detail modals"
  - "Boolean badge via Exists annotation: pattern for cheap presence checks on list endpoints"

requirements-completed:
  - ACTN-06
  - ACTN-07
  - ACTN-09
  - ACTN-10
  - ACTN-11
  - ACTN-13
  - REVW-08

duration: ~25min (incl. stalled stream + inline finalization)
completed: 2026-05-04
---

# Phase 13-07: Action Item Detail/Create Modals + Clickable Chip Summary

**3-tab Action Item detail modal, manual create modal, clickable ActionItemChip on Reviews list, and `has_action_items` Exists() annotation on the Review queryset.**

## Performance

- **Duration:** ~25 min (stream stalled near end of Task 2; inline finalization committed staged work)
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments
- ActionItemModal with Details / Notes / Source Review tabs, read/edit toggle, status transition on change
- ActionItemCreateModal with scope/shop cross-validation and Brand option hidden from Staff (ACTN-09)
- ActionItemChip upgraded to clickable (REVW-08 final delivery), navigates to filtered list
- `has_action_items` boolean exposed on `/api/v1/reviews/` via `Exists()` annotation — REVW-14 query budget unchanged

## Task Commits

1. **Task 1: ActionItemModal + supporting components** — `b2b7644` (feat)
2. **Task 2: CreateModal, chip upgrade, has_action_items annotation** — `a9d8447` (feat)

## Files Created/Modified
- `frontend/src/widgets/action-items/ActionItemModal.tsx` — 3-tab detail modal
- `frontend/src/widgets/action-items/ActionItemCreateModal.tsx` — manual creation form
- `frontend/src/widgets/action-items/PriorityIndicator.tsx` — priority pill
- `frontend/src/widgets/action-items/NotesTab.tsx` — append-only notes timeline + compose
- `frontend/src/widgets/action-items/SourceReviewTab.tsx` — read-only review snippet
- `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` — wires row click → ActionItemModal, "Create" button → ActionItemCreateModal
- `frontend/src/widgets/review-management/ActionItemChip.tsx` — clickable when `has_action_items=true`
- `frontend/src/widgets/review-management/types.ts` — added `has_action_items: boolean`
- `apps/reviews/serializers.py` — exposes `has_action_items`
- `apps/reviews/views.py` — annotates queryset with `Exists(ActionItem.objects.filter(source_review=OuterRef("pk")))`

## Decisions Made
- `Exists()` over denormalized counter — keeps REVW-14 budget flat, no migration overhead
- Source Review tab hidden for `source=MANUAL` items — cleaner than empty state
- Scope/Shop are read-only via absent inputs, not disabled attributes — defense-in-depth alongside Layer 1/2 backend enforcement

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Style] Ruff formatter reflow on Exists() annotation**
- **Found during:** Task 2 finalization
- **Issue:** Multi-line `Exists()` block was reflowed onto a single line by ruff format
- **Fix:** Accepted formatter output
- **Files modified:** apps/reviews/views.py
- **Verification:** Pre-commit ruff passes; query-count tests still pass
- **Committed in:** a9d8447

---

**Total deviations:** 1 auto-fix (style)
**Impact on plan:** None — formatting only.

## Issues Encountered

- **Stream stall near end of Task 2:** The execution agent's stream watchdog timed out after staging Task 2 work. Files on disk were complete and the Task 2 staged set matched the plan; the orchestrator finalized inline by running the REVW-14 query-count tests (`test_reviews_list_query_count_org_admin`, `test_reviews_list_query_count_staff_admin` — both passing) and creating the commit + this SUMMARY.

## User Setup Required

None.

## Next Phase Readiness

- Action Items end-to-end UI is now wired: list → detail modal → status transitions → notes; Reviews list → clickable chip → filtered Action Items list.
- Ready for phase verification.

---
*Phase: 13-action-items-and-notifications*
*Completed: 2026-05-04*
