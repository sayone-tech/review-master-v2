---
status: complete
phase: 05-profile-and-hardening
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md]
started: 2026-04-27T00:00:00Z
updated: 2026-04-27T12:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Profile page loads
expected: Navigate to /admin/profile/ as a logged-in superadmin. The page loads without errors. Two cards are visible: "Your profile" (showing your name, email, and role, plus an Edit button) and "Change password" (with three password fields). The sidebar and topbar are present as normal.
result: pass

### 2. Name edit-in-place appears
expected: On the profile page, click the "Edit" button in the "Your profile" card. An input field appears with your current full name pre-filled. Save and Cancel buttons become visible. The static name display is hidden.
result: pass

### 3. Cancel reverts without reload
expected: While the name edit form is open, type something new into the name field. Click Cancel. The original name immediately reappears and the edit form collapses — no page reload occurs.
result: pass

### 4. Name update saves with toast
expected: Click Edit, type a valid new name (e.g. "Admin User Updated"), click Save. The page reloads. The new name is displayed in the profile card. A green "Name updated." toast notification appears in the top-right corner.
result: pass

### 5. Name validation error auto-opens edit form
expected: Click Edit, clear the name field, type a single character (e.g. "A"), click Save. The page reloads. The edit form is automatically open (not collapsed). A red error message "Name must be at least 2 characters." appears under the input field.
result: pass

### 6. Password show/hide eye toggles work independently
expected: On the Change password card, click the eye icon on the "Current password" field — the text becomes visible. The "New password" and "Confirm password" fields remain hidden. Then click the eye on "New password" — it becomes visible independently. All three eye toggles operate independently of each other.
result: pass

### 7. Password strength indicator fills progressively
expected: Click into the "New password" field and type progressively longer/stronger passwords. Four colour bars fill up progressively and a label below them changes: "Too short" (1 bar) → "Weak" (2 bars) → "Fair" (3 bars) → "Good" / "Strong" (4 bars). The bars update in real-time as you type.
result: pass

### 8. Wrong current password shows inline error
expected: Fill in the Change password form with an incorrect current password, a valid new password, and matching confirm. Click the submit button. The form re-renders with a red error message "Current password is incorrect." displayed under the Current password field.
result: pass

### 9. Mismatched passwords shows inline error
expected: Fill in the Change password form with the correct current password, then type different values in "New password" and "Confirm password". Submit. The form re-renders with "Passwords do not match." displayed under the Confirm password field.
result: pass

### 10. Successful password change keeps session alive
expected: Fill in the Change password form with your correct current password, a new valid password (e.g. "NewSecurePass123!"), and the same value in Confirm. Submit. A green "Password updated." toast appears. You are NOT logged out — you can navigate to /admin/organisations/ without being redirected to /login/.
result: pass

### 11. Sidebar and topbar profile links go to /admin/profile/
expected: In the left sidebar, click the "Profile" nav item. You land on /admin/profile/ (not /profile/). Similarly, click your avatar in the topbar to open the dropdown, then click "Profile" — same /admin/profile/ destination.
result: pass

### 12. CI pipeline file has 5 required steps
expected: The file .github/workflows/ci.yml exists in the repo. Opening it shows a workflow that triggers on push and pull_request to main, with exactly 5 steps: (1) pre-commit run --all-files, (2) mypy, (3) pytest --cov=apps --cov-fail-under=85, (4) makemigrations --check --dry-run, (5) manage.py check --deploy. Postgres and Redis service containers are defined.
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
