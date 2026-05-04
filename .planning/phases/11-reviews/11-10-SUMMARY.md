---
phase: "11"
plan: "10"
subsystem: frontend/reviews-ui
tags: [react, django, reviews, datatable, filters, empty-states]
dependency_graph:
  requires: ["11-09"]
  provides: ["11-11"]
  affects: ["apps/reviews/views.py", "templates/reviews/review_list.html"]
tech_stack:
  added: []
  patterns:
    - "ReviewEmptyStates namespace export pattern: export const ReviewEmptyStates = { EmptyStateA, EmptyStateB, EmptyStateC }"
    - "CustomEvent bus: window.dispatchEvent(new CustomEvent('review:open-composer', { detail: row }))"
    - "JSON script island: {{ shops_json|json_script:'review-shops-data' }}"
    - "user.pk None guard before int narrowing (pre-commit strict mypy compatibility)"
key_files:
  created:
    - frontend/src/widgets/review-management/StarRating.tsx
    - frontend/src/widgets/review-management/SentimentBadge.tsx
    - frontend/src/widgets/review-management/ReplyStatusBadge.tsx
    - frontend/src/widgets/review-management/ReviewFilters.tsx
    - frontend/src/widgets/review-management/ReviewEmptyStates.tsx
    - frontend/src/widgets/review-management/ReviewTable.tsx
  modified:
    - frontend/src/widgets/review-management/ReviewManagementWidget.tsx
    - apps/reviews/views.py
    - templates/reviews/review_list.html
decisions:
  - "[Phase 11-10]: ReviewEmptyStates exports individual named functions + namespace object — supports both `import { EmptyStateA }` and `ReviewEmptyStates.EmptyStateA` usage patterns"
  - "[Phase 11-10]: shops_data typed as list[Any] in view to avoid strict mypy conflict with QuerySet.values() TypedDict return type"
  - "[Phase 11-10]: user.pk None guard (raw_pk = user.pk; if raw_pk is None: return none) replaces type: ignore[assignment] — pre-commit mypy strict mode rejects unused ignore comments"
  - "[Phase 11-10]: review:open-composer CustomEvent dispatched from ReviewManagementWidget — Plan 11 reply composer listens via window event"
metrics:
  duration: 30
  completed_date: "2026-05-02"
  tasks: 2
  files: 9
---

# Phase 11 Plan 10: Reviews List UI Summary

Reviews list UI built with 7 React components wired to the existing DataTable + useReviews hook, plus backend context injection for the Store filter dropdown.

## What Was Built

### Task 1 — Atom Components

| Component | File | Purpose |
|-----------|------|---------|
| `StarRating` | `StarRating.tsx` | 5-star renderer (size 14, filled = `text-yellow fill-current`, empty = `text-line fill-current`, aria-label on group) |
| `SentimentBadge` | `SentimentBadge.tsx` | Positive/Neutral/Negative colored pills + "Analyzing..." amber pill (Loader2 spin) + AlertCircle on FAILED |
| `ReplyStatusBadge` | `ReplyStatusBadge.tsx` | "Replied" (green + CheckCircle) / "Not Replied" (amber) badges |
| `ReviewFilters` | `ReviewFilters.tsx` | 7-control filter bar + active chip row + Clear all + result count + sort selector |
| `ReviewEmptyStates` | `ReviewEmptyStates.tsx` | Three empty states (A: no connected shops / B: no reviews / C: no matches) + namespace export |

### Task 2 — Table, Widget, Backend

| Artifact | Purpose |
|----------|---------|
| `ReviewTable.tsx` | DataTable wired with 7 column accessors (Rating, Shop, Reviewer, Date, Sentiment, Reply, Reply CTA) + ••• row actions + Plan-11 expansion slot |
| `ReviewManagementWidget.tsx` | Full widget replacing Plan-09 stub: useReviews, ReviewFilters, ReviewTable, pagination, showFullComment Map |
| `apps/reviews/views.py` | `review_list` now provides `shops_json` + `has_connected_shops` context (STAFF_ADMIN-scoped) |
| `templates/reviews/review_list.html` | JSON script islands: `{{ shops_json|json_script:"review-shops-data" }}` + `{{ has_connected_shops|json_script:"review-has-connected-shops" }}` |

## Namespace Export Pattern

`ReviewEmptyStates.tsx` exports each component both as a named export and as a namespace object:

```tsx
export function EmptyStateA(...) { ... }
export function EmptyStateB() { ... }
export function EmptyStateC(...) { ... }
export const ReviewEmptyStates = { EmptyStateA, EmptyStateB, EmptyStateC };
```

This allows `ReviewManagementWidget.tsx` to use `ReviewEmptyStates.EmptyStateA` while still supporting direct named imports in tests or other callers.

## CustomEvent Contract

The Reply CTA in `ReviewManagementWidget.tsx` dispatches a custom event on click:

```ts
window.dispatchEvent(new CustomEvent("review:open-composer", { detail: row }));
```

- **Event name:** `review:open-composer`
- **Detail payload:** full `ReviewRow` object
- **Purpose:** Plan 11 `ReplyComposer` listens to this event to open the inline accordion for the target review
- **Local state:** `openComposerId` is also set in the widget so Plan 11 can pass `expandedRowId` to `ReviewTable`

## REVW-06 Show More / Show Less State

`showFullComment: Map<number, boolean>` is maintained in `ReviewManagementWidget`. Keys are `review.id`; value `true` = full text shown. `toggleShowFullComment(reviewId)` is passed to `ReviewTable` as a prop — Plan 11's comment cell renderer will use it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] user.pk None guard for strict mypy**
- **Found during:** Task 2 commit (pre-commit mypy hook)
- **Issue:** The pre-commit mypy strict environment treats `user.pk` as `int | None` and rejected `user_id: int = user.pk` with `type: ignore[assignment]` — the ignore was reported as "unused" by the hook
- **Fix:** Replaced with explicit None check (`raw_pk = user.pk; if raw_pk is None: return Review.objects.none(); user_id: int = raw_pk`)
- **Files modified:** `apps/reviews/views.py`
- **Commit:** 3d7fc1d

**2. [Rule 1 - Bug] shops_data type annotation change**
- **Found during:** Task 2 commit (pre-commit mypy hook)
- **Issue:** `list[dict[str, Any]]` + `type: ignore[arg-type]` on `.values()` call caused "unused ignore" error in strict mode
- **Fix:** Changed type annotation to `list[Any]` — avoids the incompatibility without suppression
- **Files modified:** `apps/reviews/views.py`
- **Commit:** 3d7fc1d

## Self-Check: PASSED

Files verified:
- `frontend/src/widgets/review-management/StarRating.tsx` — FOUND
- `frontend/src/widgets/review-management/SentimentBadge.tsx` — FOUND
- `frontend/src/widgets/review-management/ReplyStatusBadge.tsx` — FOUND
- `frontend/src/widgets/review-management/ReviewFilters.tsx` — FOUND
- `frontend/src/widgets/review-management/ReviewEmptyStates.tsx` — FOUND
- `frontend/src/widgets/review-management/ReviewTable.tsx` — FOUND
- `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` — FOUND

Commits verified:
- `2478fda` — Task 1 atom components
- `3d7fc1d` — Task 2 table + widget + view
