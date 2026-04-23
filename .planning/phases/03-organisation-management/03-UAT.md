---
status: diagnosed
phase: 03-organisation-management
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md]
started: 2026-04-23T14:00:00Z
updated: 2026-04-23T14:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Organisation List Page Loads
expected: Navigate to /admin/organisations/ while logged in as a superadmin. The page renders with a "Organisations" heading, a "Create Organisation" button in the top-right, a filter bar (search input, Status dropdown, Type dropdown), and an organisation data table showing columns: Name, Type, Status, Stores, Activation Status, and an Actions column.
result: issue
reported: "sidebar nav link redirects to /organisations/ which 404s instead of /admin/organisations/. Page works when URL is typed manually. All components present but the DataTable column headers appear at the bottom as a separate detached table, not attached to the data rows."
severity: major

### 2. Search and Filter
expected: Type a partial organisation name or email into the search box and press Enter (or the form auto-submits). The table updates to show only matching organisations. Then select a Status filter (e.g. "Disabled") — the list filters to show only disabled orgs. Change the Type filter to "Pharmacy" — only pharmacy orgs appear. Clearing filters restores the full list.
result: skipped
reason: Create Organisation modal does not open — no test data to search through

### 5-note: Create Organisation modal broken (discovered during test 2 skip)
expected: Clicking "Create Organisation" opens a modal
result: issue
reported: "popup/modal does not open when clicking Create Organisation button"
severity: major

### 3. Per-Page Selector
expected: At the bottom of the table, a "Show: 10 per page" dropdown is visible. Changing it to 25 reloads the page and shows up to 25 rows. Pagination links preserve the per_page value in their URLs (e.g. clicking Next shows ?per_page=25&page=2). Invalid per_page in URL (e.g. ?per_page=999) falls back to 10.
result: issue
reported: "this component missing"
severity: major

### 4. Empty State
expected: Apply a search or filter that matches no organisations (e.g. search "zzznomatch"). The table disappears and an empty state is shown (e.g. "No organisations yet" or similar message). The "Create Organisation" button is still visible.
result: issue
reported: "this also not working"
severity: major

### 5. Create Organisation
expected: Click "Create Organisation". A modal opens with fields: Name, Org Type, Email, Address, Number of Stores. Fill in all fields with valid data and submit. The modal closes, a green toast appears: "Organisation created. Invitation email sent to {email}.", and the new org appears in the table.
result: issue
reported: "popup/modal does not open when clicking Create Organisation button"
severity: major

### 6. Duplicate Email Validation
expected: Open the Create Organisation modal again and submit with an email address that already belongs to an existing org. The modal stays open and shows an inline field error under the Email field: "An organisation with this email already exists." No toast is shown.
result: skipped
reason: Depends on Create Organisation modal which does not open

### 7. View Organisation
expected: In the Actions menu for any row (three-dot or similar), click "View". A View modal opens showing the organisation's details (name, type, email, address, stores, status, activation status). The modal has a close button. Clicking close dismisses it without changes.
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

### 8. Edit Organisation
expected: In the Actions menu, click "Edit". An Edit modal opens pre-filled with the org's current name, type, address, and store count (the Email field is absent — it cannot be changed). Update the name to something new and save. The modal closes, a toast shows "Organisation updated.", and the table row reflects the new name.
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

### 9. Disable Organisation
expected: In the Actions menu for an Active org, click "Disable". An amber confirmation modal appears asking to confirm disabling the org. Click Confirm. The modal closes, a toast shows "{name} has been disabled.", and the org's status in the table changes to "Disabled".
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

### 10. Enable Organisation
expected: In the Actions menu for a Disabled org, click "Enable". A blue confirmation modal appears. Click Confirm. The modal closes, a toast shows "{name} has been enabled.", and the org's status changes to "Active".
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

### 11. Delete Organisation
expected: In the Actions menu, click "Delete". A red confirmation modal appears requiring you to type the organisation's name to confirm deletion. Type the name exactly and click Delete. The modal closes, a toast shows "{name} has been deleted.", and the org disappears from the table.
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

### 12. Store Allocation
expected: In the Actions menu, click "Stores" (or similar). A Step 1 modal appears with a number input pre-filled with the current store allocation and a helper text "Currently using X of Y stores." Enter a new value and click Update. A Step 2 blue confirmation modal appears showing old → new counts. Click Confirm. The modal closes and a toast shows "Store allocation updated to {N}." The Stores column in the table reflects the new value.
result: skipped
reason: No organisations in the table — Create Organisation modal does not open

## Summary

total: 12
passed: 0
issues: 4
pending: 0
skipped: 8

## Gaps

- truth: "Clicking Organisations in sidebar nav opens /admin/organisations/ correctly"
  status: failed
  reason: "User reported: sidebar nav link redirects to /organisations/ which 404s"
  severity: major
  test: 1
  root_cause: "sidebar.html line 31 hardcodes href='/organisations/' but the URL is registered as /admin/organisations/"
  artifacts:
    - path: "templates/partials/sidebar.html"
      issue: "line 31: href='/organisations/' should be href='{% url 'organisation_list' %}'"
  missing:
    - "Change href to {% url 'organisation_list' %} (or hardcode /admin/organisations/)"

- truth: "DataTable column headers appear above the data rows as a single cohesive table"
  status: failed
  reason: "User reported: DataTable column headers appear at the bottom as a separate detached table, not attached to the data rows"
  severity: major
  test: 1
  root_cause: "overflow-hidden on the outer wrapper div in DataTable.tsx creates a scroll context that breaks position:sticky on the thead, snapping it to the bottom of the container"
  artifacts:
    - path: "frontend/src/widgets/data-table/DataTable.tsx"
      issue: "line 40: overflow-hidden on wrapper div breaks sticky thead (line 45)"
  missing:
    - "Remove overflow-hidden from the wrapper div className on line 40"

- truth: "Clicking Create Organisation button opens the Create Organisation modal"
  status: failed
  reason: "User reported: popup/modal does not open when clicking Create Organisation button"
  severity: major
  test: 2
  root_cause: "onOpen is passed as a new inline arrow function on every render; CreateButtonBridge's useEffect re-registers/removes the click listener on every re-render; under React 18 StrictMode's double-invoke, the button ends up with no active listener"
  artifacts:
    - path: "frontend/src/entrypoints/org-management.tsx"
      issue: "line 100: onOpen passed as inline arrow () => setCreateOpen(true) — unstable reference"
  missing:
    - "Wrap onOpen in useCallback(() => setCreateOpen(true), []) so the reference is stable across renders"

- truth: "Per-page selector dropdown is visible at the bottom of the organisations table"
  status: failed
  reason: "User reported: this component missing"
  severity: major
  test: 3
  root_cause: "pagination.html (which contains the per-page form) is guarded by {% if page_obj.paginator.count > 0 %} and is also inside the {% else %} of the empty-state conditional in list.html, so it disappears with zero results"
  artifacts:
    - path: "templates/organisations/list.html"
      issue: "lines 23-27: pagination include is in the else branch of the empty-state conditional"
    - path: "templates/components/pagination.html"
      issue: "line 5: entire nav (including per-page form) wrapped in count > 0 guard"
  missing:
    - "Extract per-page selector form from the paginator.count guard so it renders unconditionally when per_page_options is present"

- truth: "Searching with no matching results shows an empty state message"
  status: failed
  reason: "User reported: this also not working"
  severity: major
  test: 4
  root_cause: "div#org-table-root is rendered unconditionally outside the if/else block in list.html, so the React widget always mounts and visually obscures the Django-rendered empty state above it"
  artifacts:
    - path: "templates/organisations/list.html"
      issue: "line 29: div#org-table-root and vite_asset are outside the if/else block — React always mounts regardless of result count"
  missing:
    - "Move div#org-table-root and vite_asset inside the {% else %} branch so React only mounts when results exist; handle zero-results empty state in the {% if %} branch"
