---
plan: 04-03
slug: activation-flow
status: complete
completed: 2026-04-23
---

# Plan 04-03 — Activation Flow — SUMMARY

## Commits

| Hash | Description |
|------|-------------|
| 794ce48 | test(accounts): RED stubs for ActivationForm + activate_account (task 1) |
| 4c61a6f | feat(accounts): ActivationForm + activate_account service (ACTV-01..05) |
| 60d8e8c | feat(accounts): invite_accept_view + templates + URL (ACTV-01..05) |

## Deliverables

**Task 1 — ActivationForm + service:**
- `apps/accounts/forms.py` — `ActivationForm` with full_name (2-100 chars), password1 (Django validator chain), password2 (match check)
- `apps/organisations/services/organisations.py` — `activate_account()` with `@transaction.atomic`, `select_for_update()` race guard, raises `ValidationError` on already-used token, creates `ORG_ADMIN` user, links `invited_user`

**Task 2 — View + URL + Templates:**
- `apps/accounts/views.py` — `invite_accept_view()`: checks `is_used` BEFORE `is_expired` (ACTV-05 ordering), POST calls `activate_account` + `login()` + redirect to `org_admin_dashboard`
- `apps/accounts/urls.py` — `path("invite/accept/<str:token>/", invite_accept_view, name="invite_accept")`
- `templates/accounts/invite_accept.html` — activation form with Alpine.js strength indicator, show/hide toggles, disabled email field
- `templates/accounts/invite_error.html` — error card (no form, no CTA) rendering locked `{{ message }}`

## Tests

| Scope | Count |
|-------|-------|
| ActivationForm (test_views.py::TestActivationForm) | 6 |
| activate_account service (test_services.py) | 3 |
| invite_accept_view integration (test_views.py) | 11 |
| **Total new** | **20** |

All 149 tests pass (accounts + organisations suites).

## Requirements Covered

ACTV-01, ACTV-02, ACTV-03, ACTV-04, ACTV-05
