---
phase: 09-team
plan: "03"
subsystem: email-templates
tags: [email, templates, ses, team-invitation, tdd]
dependency_graph:
  requires: ["09-01"]
  provides: ["TEML-01", "TEML-02"]
  affects: ["09-04", "09-05"]
tech_stack:
  added: []
  patterns:
    - "Django template conditional rendering for role-based email sections"
    - "600px max-width inline-CSS email table layout"
    - "TDD: RED/GREEN cycle for email body-content assertions"
key_files:
  created:
    - apps/accounts/tests/test_team_emails.py
  modified:
    - templates/emails/team_invitation.html
    - templates/emails/team_invitation.txt
    - templates/emails/team_invitation_resent.html
    - templates/emails/team_invitation_resent.txt
decisions:
  - "team_invitation_resent.html is a standalone file (not extends) — email clients need fully self-contained HTML"
  - "Resend notice placed before scope lists — immediately visible after the intro paragraph"
  - "PT018 fix: compound assertions split into separate assert statements to satisfy ruff rule"
metrics:
  duration_seconds: 180
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_changed: 5
---

# Phase 09 Plan 03: Team Email Templates Summary

Production email templates for TEAM_MEMBER invitations, replacing Plan 01's placeholder stubs. Six body-content tests verify TEML-01/TEML-02 requirements end-to-end.

## What Was Built

### Template Structure (600px table, inline CSS, brand yellow CTA)

All four templates use the same outer table structure as `invitation.html`:
- Outer `<table width="100%">` with `background:#FAFAFA;padding:32px 16px`
- Inner `<table width="600" style="max-width:600px">` — the email card
- No `<style>` blocks anywhere (inline CSS only, per CLAUDE.md §12.5)
- Brand yellow CTA: `<td style="background-color:#FACC15">` with black text `#0A0A0A`

### Conditional Rendering Logic (Staff vs Manager)

`team_invitation.html` and its resent variant use Django template conditionals:

```
{% if is_staff_role and assigned_region_names %}
  <tr><td>Regions: {{ assigned_region_names|join:", " }}</td></tr>
{% endif %}
{% if is_staff_role and assigned_shop_names %}
  <tr><td>Stores: {{ assigned_shop_names|join:", " }}</td></tr>
{% endif %}
```

- `is_staff_role=True` (STAFF_ADMIN): renders comma-separated Regions and Stores sections
- `is_staff_role=False` (ORG_ADMIN/Manager): neither section renders

### Resend Differentiation

`team_invitation_resent.html` / `.txt` differ from the initial templates in exactly one way:

**HTML:** A notice `<tr>` is inserted between the intro paragraph and the scope rows:
```html
<p style="...;font-style:italic;">
  This replaces any previous invitation. The earlier link is no longer valid.
</p>
```

**TXT:** The notice appears as the very first line before the heading.

The `send_team_invitation_email` service (Plan 01) selects the correct template pair via `is_resend` and sets the subject:
- Initial: subject `"You're invited to join {org_name}"`, template `emails/team_invitation`
- Resend: subject `"New invitation link for {org_name}"`, template `emails/team_invitation_resent`

## Test Coverage Map (6 tests → TEML-01 + TEML-02)

| Test | Requirement | What It Checks |
|---|---|---|
| `test_team_invitation_email_manager_omits_scopes` | TEML-01 | invitee name, inviter name, role, accept_url, 48 hours, NO Regions/Stores |
| `test_team_invitation_email_staff_lists_scopes` | TEML-01 | Regions: comma-separated, Stores: name shown, both in HTML + TXT |
| `test_team_invitation_email_resent_subject_and_notice` | TEML-02 | subject change + resend notice in HTML and TXT |
| `test_team_invitation_email_initial_omits_resent_notice` | TEML-01 | notice absent from initial invitation |
| `test_team_invitation_template_uses_brand_yellow` | CLAUDE.md §12.5 | `#FACC15` present in HTML body |
| `test_team_invitation_template_max_width_600` | CLAUDE.md §12.5 | `width="600"` and `max-width:600px` present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff PT018 compound assertion violations**
- **Found during:** pre-commit run
- **Issue:** Two assertions used `and` in a single `assert` statement; ruff PT018 requires each condition to be its own assert
- **Fix:** Split `assert "North" in html and "South" in html` into separate `assert "North" in html` / `assert "South" in html` lines
- **Files modified:** `apps/accounts/tests/test_team_emails.py`
- **Commit:** 9d21f58 (same commit — fixed before commit landed)

**2. [Auto] djhtml reformatted HTML templates**
- DjHTML reindented `team_invitation.html` and `team_invitation_resent.html` during pre-commit
- Accepted — consistent with project formatting conventions

## Commits

| Hash | Description |
|---|---|
| 9d21f58 | feat(09-03): production email templates for team member invitations |

## Self-Check

- [x] `templates/emails/team_invitation.html` exists
- [x] `templates/emails/team_invitation.txt` exists
- [x] `templates/emails/team_invitation_resent.html` exists
- [x] `templates/emails/team_invitation_resent.txt` exists
- [x] `apps/accounts/tests/test_team_emails.py` exists
- [x] Commit 9d21f58 exists in git log
- [x] All 6 tests pass: `pytest apps/accounts/tests/test_team_emails.py -v` → 6 passed
- [x] `python manage.py check` → no issues
- [x] `pre-commit run --files` → all hooks passed

## Self-Check: PASSED
