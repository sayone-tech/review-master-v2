---
phase: 05-profile-and-hardening
plan: 03
subsystem: ui
tags: [alpine.js, django-templates, tailwind, profile, password-change]

# Dependency graph
requires:
  - phase: 05-02
    provides: "Profile views (update_name_view, change_password_view), ProfileNameForm, ProfilePasswordChangeForm, URL names profile_update_name / profile_change_password"
provides:
  - "Two-card profile page at /admin/profile/ with Alpine.js edit-in-place name + full password-change form"
  - "3 xfail markers removed — all 8 PROF-01/PROF-02 view tests green"
affects: [05-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Alpine.js edit-in-place pattern: x-data{editing, orig, val} with x-show guards for display/form modes"
    - "4-bar password strength indicator verbatim reuse from invite_accept.html (score/label/barClass getters)"
    - "Three independent show/hide eye toggles: nested x-data='{ show: false }' inside outer form x-data"
    - "Error-driven Alpine auto-open: editing init reads {% if name_form.errors %}true{% else %}false{% endif %}"

key-files:
  created: []
  modified:
    - "templates/accounts/profile.html"
    - "apps/accounts/tests/test_views.py"

key-decisions:
  - "name_form.full_name.value|default:user.full_name used to pre-fill Alpine val — re-populates invalid input on error re-render"
  - "editing init uses Django template tag (not JS) so edit form auto-opens on name validation failure without extra JS"
  - "pw_form context guards ({% if pw_form.current_password.errors %}) use the form object passed only on validation failure — safe because None.field would raise TemplateDoesNotExist, not AttributeError in templates"

requirements-completed: [PROF-01, PROF-02]

# Metrics
duration: 2min
completed: 2026-04-24
---

# Phase 5 Plan 03: Profile Page UI Summary

**Two-card profile page with Alpine.js edit-in-place name form and password-change form with 4-bar strength indicator — all 8 PROF-01/PROF-02 view tests now GREEN, 3 xfail markers removed**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-24T06:50:46Z
- **Completed:** 2026-04-24T06:52:30Z
- **Tasks:** 1 of 2 (Task 2 is human-verify checkpoint — awaiting sign-off)
- **Files modified:** 2

## Accomplishments

- Replaced 24-line stub `templates/accounts/profile.html` with full 182-line two-card page
- Card 1 "Your profile": Alpine.js edit-in-place name with Save/Cancel revert (`@click="editing = false; val = orig"`), email + role read-only
- Card 2 "Change password": three password fields (current/new/confirm), each with independent show/hide eye toggle, new password field drives 4-bar strength indicator (verbatim from `invite_accept.html`)
- Error rendering via `{{ form.field.errors.0 }}` turns the 3 previously-xfail tests GREEN; `grep -c '@pytest.mark.xfail'` returns 0
- All 53 accounts tests pass; `manage.py check` 0 issues; all pre-commit hooks pass

## Task Commits

1. **Task 1: Rewrite profile.html as two-card page + remove 3 xfail markers** - `cd71edb` (feat)
2. **Task 2: Human-verify profile page interactive behaviour** - PENDING (checkpoint)

## Files Created/Modified

- `templates/accounts/profile.html` — Full two-card layout with Alpine.js reactivity (182 lines)
- `apps/accounts/tests/test_views.py` — Removed 3 `@pytest.mark.xfail` decorators from `test_update_name_post_invalid`, `test_change_password_wrong_current`, `test_change_password_mismatch`

## Decisions Made

- `name_form.full_name.value|default:user.full_name` used for Alpine `val` init so the invalid input value is preserved across the error re-render
- `editing` init driven by Django template (`{% if name_form.errors %}true{% else %}false{% endif %}`) so the name edit form auto-opens when there are errors without any extra JS
- The template guards `{% if pw_form.current_password.errors %}` are safe even on GET (where `pw_form` is not in context) because Django templates silently resolve missing context keys to `""` — no TemplateError

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Human-Verify Checkpoint

**Status:** AWAITING SIGN-OFF

Verification steps for the user:

1. Start local dev (`make up`, then `python manage.py runserver` or equivalent; Vite dev server `npm run dev` in `frontend/` for Tailwind hot-reload)
2. Log in as a superadmin at `/login/`, then navigate to `/admin/profile/`
3. **Name edit:**
   - Click "Edit" — verify input appears with current name pre-filled + Save / Cancel visible
   - Type new name, click Cancel — displayed name reverts (NO reload)
   - Click Edit, type "A", click Save — page reloads, edit form stays open (auto-opened), red error "Name must be at least 2 characters." appears
   - Click Edit, type a valid new name, click Save — page reloads, name updated, green "Name updated." toast top-right
4. **Password change:**
   - Click eye on each of the 3 fields — each toggles independently
   - Type in New password — 4 bars fill progressively; label changes "Too short" → "Weak" → "Fair" → "Good" → "Strong"
   - Submit with wrong current password — red "Current password is incorrect." under Current password
   - Submit with mismatched new/confirm — red "Passwords do not match." under Confirm password
   - Submit with correct current + valid matching new — green "Password updated." toast, user stays logged in
5. **Accessibility:** tab through password form — focus ring visible; eye-toggle aria-label reads "Show password" / "Hide password"
6. **Mobile** (DevTools <768px): both cards stack; form controls wrap; no horizontal scroll

Reply "approved" to complete this plan, or describe any issues found.

## Next Phase Readiness

- Profile page fully functional pending human-verify sign-off
- All PROF-01 / PROF-02 requirements satisfied at code level (14/14 tests green)
- Plan 05-04 can proceed once checkpoint is cleared

---
*Phase: 05-profile-and-hardening*
*Completed: 2026-04-24 (pending human-verify)*
