---
status: partial
phase: 25-org-admin-tag-management-dashboard-polarity
source: [25-VERIFICATION.md]
started: 2026-06-16T00:00:00Z
updated: 2026-06-16T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Tags page renders the widget
expected: Open `/admin/org/tags/` as an ORG_ADMIN — a sortable, paginated table renders with columns Label, Polarity Type badge (colored), Review Count, First Seen, and an Actions menu.
result: [pending]

### 2. Inline rename UX
expected: Click Rename on a tag, type a new label, save — the label updates in place with no full page reload; entering an existing (case-insensitive) label shows an inline duplicate-name error and does not merge.
result: [pending]

### 3. Merge modal two-step UX
expected: From a tag's Actions → Merge, the modal shows a searchable target picker (step 1) then an explicit "re-maps N reviews, cannot be undone" warning (step 2); confirming starts the merge and shows the progress banner.
result: [pending]

### 4. Merge progress reload survival
expected: While a merge is in progress, reload the page — the in-progress banner re-appears (from the durable `TagMergeJob`); the banner can be dismissed; on completion a success toast appears; a failed merge surfaces a rollback state.
result: [pending]

### 5. Dashboard polarity chart visual
expected: On the dashboard, the tag-distribution chart shows `always_positive`/`always_negative` tags as single colored count bars and `mixed` tags as a stacked positive/negative split.
result: [pending]

### 6. Staff admin access guard
expected: As a STAFF_ADMIN, the Tags nav item is absent from the sidebar, and navigating directly to `/admin/org/tags/` redirects (no access).
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
