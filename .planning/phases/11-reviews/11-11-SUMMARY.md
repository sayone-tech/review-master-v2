---
phase: 11-reviews
plan: "11"
subsystem: frontend/review-management
tags: [react, reply-composer, inline-accordion, data-table, revw-06, revw-09, revw-10, revw-12]
dependency_graph:
  requires: ["11-10"]
  provides: ["ReplyComposer", "DataTable.renderExpanded"]
  affects: ["frontend/src/widgets/data-table/DataTable.tsx", "frontend/src/widgets/review-management/ReviewTable.tsx", "frontend/src/widgets/review-management/ReviewManagementWidget.tsx"]
tech_stack:
  added: []
  patterns: ["accordion expansion via renderExpanded prop", "inline error banner", "char counter with threshold coloring"]
key_files:
  created:
    - frontend/src/widgets/review-management/ReplyComposer.tsx
  modified:
    - frontend/src/widgets/data-table/DataTable.tsx
    - frontend/src/widgets/review-management/ReviewTable.tsx
    - frontend/src/widgets/review-management/ReviewManagementWidget.tsx
decisions:
  - "DataTable extended with optional renderExpanded prop (backward-compatible) — ShopTable and TeamTable unaffected"
  - "emitToast uses {kind, title} API matching lib/toast.ts — plan snippet used wrong {type, message} shape (auto-fixed)"
  - "ReplyComposer renders as <tr> with <td colSpan={TOTAL_COLUMNS}> for correct table layout"
  - "Replied view shown immediately when row.is_replied is true — composer never shown for already-replied rows"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 4
---

# Phase 11 Plan 11: Inline ReplyComposer Accordion Summary

**One-liner:** Inline reply accordion using DataTable's new `renderExpanded` prop — ReplyComposer renders below the active row as a `<tr>` with full review context, textarea, char counter, and 4 error paths.

## What Was Built

### ReplyComposer component (`frontend/src/widgets/review-management/ReplyComposer.tsx`)

A stateful React component that renders as a `<tr>` row for inline table insertion. It has two rendering modes:

1. **Composer mode** (when `row.is_replied === false`): Shows read-only review context (reviewer name, stars, shop, date, comment with REVW-06 truncation), a `<textarea maxLength={4000}>`, char counter, inline error banner, Discard Reply and Submit Reply buttons.

2. **Replied view** (when `row.is_replied === true`): Shows a `<CheckCircle>` icon, "Replied on {date}", the reply text, and a Close button. This state is entered immediately when `submitReply` resolves successfully (because the parent calls `replaceRow(updated)` which flips `is_replied`).

**State machine:**
- Idle → user clicks Submit → `submitting=true`, `errorMessage=null`
- Success: `emitToast({ kind: "success", title: "Reply posted." })` → `onSuccess(updated)` → parent `replaceRow(updated)` → `row.is_replied` flips → Replied view renders
- Error: `errorMessage` set with status-specific copy; button re-enabled; composer stays open

**Error messages:**
- 429 → "You're replying too quickly. Please wait a moment."
- 409 → "Another reply submission is in progress. Please wait."
- 502 + `code: "invalid_grant"` → "Google connection expired. Reconnect Google in Shops."
- 502 + `code: "reply_rejected"` → "Google rejected the reply. Please review the content and try again."
- 502 + `code: "unreachable"` → "Google is temporarily unavailable. Please try again."
- Other → "Failed to post reply. Please try again."

### DataTable extension (`frontend/src/widgets/data-table/DataTable.tsx`)

Added optional `renderExpanded?: (row: T) => ReactNode` prop. In the data-rows render branch, each row is now wrapped in a `<Fragment key={rowKey(row)}>` that emits the row's `<tr>` followed by the expansion `<tr>` if `renderExpanded(row)` returns a non-null value. The prop is optional and defaults to `undefined` — existing usages (ShopTable, TeamTable) are completely unaffected.

### ReviewTable wiring (`frontend/src/widgets/review-management/ReviewTable.tsx`)

Replaced the Plan 10 stub (which had `expandedRow: ReactNode` pass-through). Now:
- Defines `renderExpanded` callback: returns `null` for rows where `expandedRowId !== r.id`, otherwise renders `<ReplyComposer>` with `showFullComment` from the Map.
- Passes `renderExpanded` to DataTable.
- Removed `expandedRow` prop — no longer needed since the accordion lives inside DataTable.

### ReviewManagementWidget wiring (`frontend/src/widgets/review-management/ReviewManagementWidget.tsx`)

- Destructures `replaceRow` from `useReviews()`.
- Passes `onComposerSuccess={(updated) => replaceRow(updated)}` → row badge + reply text update immediately in the table without a full refresh.
- Passes `onComposerClose={() => setOpenComposerId(null)}` → closing the composer collapses the accordion.
- Removed `expandedRow={null}` stub prop.

### REVW-06 — Show more / Show less

The REVW-06 truncation toggle is fully wired. `ReviewManagementWidget` owns `showFullComment: Map<number, boolean>` state (established in Plan 10). `ReviewTable` passes it to `renderExpanded`, which passes the per-row boolean to `ReplyComposer`. Comments ≤ 1000 chars render in full; longer comments truncate with a "Show more" inline button.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect emitToast API call**
- **Found during:** Task 1
- **Issue:** Plan snippet used `emitToast({ type: "success", message: "Reply posted." })` which does not match the actual `lib/toast.ts` signature `emitToast({ kind: ToastKind, title: string, msg?: string })`. Using the wrong shape would silently send `undefined` as the toast kind and produce no visible toast.
- **Fix:** Changed to `emitToast({ kind: "success", title: "Reply posted." })` matching the actual API.
- **Files modified:** `frontend/src/widgets/review-management/ReplyComposer.tsx`
- **Commit:** 96954d6

## Self-Check: PASSED
