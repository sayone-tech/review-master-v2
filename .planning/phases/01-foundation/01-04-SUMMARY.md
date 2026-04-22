---
phase: 01-foundation
plan: "04"
subsystem: ui
tags: [django-templates, tailwind, alpine.js, vite, responsive, components]

# Dependency graph
requires:
  - phase: 01-03
    provides: base.html, shell.html stub, tailwind.config.js, app-shell.ts stub, pages/placeholder.html
  - phase: 01-02
    provides: User model with role field (SUPERADMIN/ORG_ADMIN/STAFF_ADMIN) and full_name field

provides:
  - Shell chrome (sidebar + topbar) rendered via partials/shell.html include
  - Sidebar with role-based nav items, active state (border-yellow), 240px desktop / 64px tablet rail / mobile drawer
  - Topbar with notification bell and Alpine.js avatar dropdown
  - Phase-1 logout URL stub (path 'logout/' name='logout' in apps/common/urls.py)
  - is_active_route/is_active_url custom template tags in apps/common/templatetags/ui.py
  - Alpine.store('nav') registered in app-shell.ts for mobile drawer state
  - 8 reusable component partials: buttons, form_fields, badges, toasts, empty_state, skeletons, filter_bar, pagination
  - sk-pulse keyframe + x-cloak + focus ring CSS in tailwind.css

affects: [01-05, 02-organisations, all-phases-with-templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "{% include 'components/<name>.html' with ... %} — component API pattern for all reusable UI"
    - "Alpine.store('nav') for cross-component mobile drawer state"
    - "app:toast CustomEvent dispatched to window for toast stack integration"
    - "is_active_route template tag for declarative active nav detection"

key-files:
  created:
    - apps/common/templatetags/__init__.py
    - apps/common/templatetags/ui.py
    - apps/common/tests/test_responsive.py
    - apps/common/tests/test_components.py
    - templates/partials/sidebar.html
    - templates/partials/topbar.html
    - templates/partials/_nav_item.html
    - templates/components/toasts.html
    - templates/components/buttons.html
    - templates/components/form_fields.html
    - templates/components/badges.html
    - templates/components/empty_state.html
    - templates/components/skeletons.html
    - templates/components/filter_bar.html
    - templates/components/pagination.html
  modified:
    - apps/common/views.py
    - apps/common/urls.py
    - templates/partials/shell.html
    - frontend/src/entrypoints/app-shell.ts
    - frontend/src/styles/tailwind.css

key-decisions:
  - "User.full_name used instead of first_name/last_name — matches Plan 01-02 custom User model"
  - "logout_stub registered as path('logout/', name='logout') in apps/common/urls.py for Phase 1; Phase 2 swaps view body, URL name is stable"
  - "toasts.html included directly from shell.html (not base.html) — always present in shell but not in email/API layouts"

patterns-established:
  - "{% include 'components/<name>.html' with variant=... label=... %} — component call pattern"
  - "Alpine.store('nav') for sidebar mobile open/close state shared across shell partials"
  - "app:toast CustomEvent schema: { kind: 'success'|'error'|'info'|'warning', title: str, msg: str }"
  - "logout stub pattern: register URL name in Phase 1, replace view body in Phase 2 (never change URL name)"

requirements-completed: ["DSYS-02", "DSYS-03", "DSYS-05", "DSYS-06", "DSYS-07"]

# Metrics
duration: 6min
completed: 2026-04-22
---

# Phase 01 Plan 04: Shell Chrome + Component Library Summary

**Django-template shell chrome (sidebar/topbar/responsive) with 8 reusable component partials, Alpine.js interactions, and Phase-1 logout stub delivered via TDD**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-22T10:30:21Z
- **Completed:** 2026-04-22T10:36:00Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments

- Sidebar renders at 240px desktop / 64px tablet rail / hidden mobile with hamburger drawer toggle; Alpine.js `$store.nav.mobileOpen` wires hamburger to sidebar
- Topbar renders notification bell and avatar dropdown with Alpine.js open/close/escape/click-outside; `{% url 'logout' %}` resolves via Phase-1 stub registered in apps/common/urls.py
- 8 component template partials built with correct Tailwind brand tokens, ARIA semantics, and Alpine.js bindings; 19 tests across two test files pass with 0 failures

## Task Commits

1. **Task 1: Sidebar + topbar partials with responsive behaviour + logout URL stub** - `9f329e4` (feat)
2. **Task 2: Reusable component template partials** - `949c3e1` (feat)

## Files Created/Modified

- `apps/common/templatetags/ui.py` — `is_active_route` and `is_active_url` custom template tags for active nav detection
- `apps/common/templatetags/__init__.py` — package marker for templatetags
- `apps/common/views.py` — appended `logout_stub` (Phase-1 placeholder; 302 to /)
- `apps/common/urls.py` — appended `path('logout/', logout_stub, name='logout')`
- `apps/common/tests/test_responsive.py` — 8 tests: is_active_route, logout stub, responsive markup, Alpine.js dropdown
- `apps/common/tests/test_components.py` — 11 tests: all 8 component partials
- `templates/partials/sidebar.html` — full sidebar with role-gated nav, active state, logout footer
- `templates/partials/topbar.html` — topbar with bell and Alpine.js avatar dropdown
- `templates/partials/_nav_item.html` — reusable nav item with is_active_route active state
- `templates/partials/shell.html` — overwritten with skip link + sidebar + topbar + toasts include
- `templates/components/toasts.html` — Alpine.js toast stack listening for `app:toast` CustomEvent
- `templates/components/buttons.html` — primary/secondary/danger/ghost variants
- `templates/components/form_fields.html` — text/email/password/textarea/select with Alpine eye toggle
- `templates/components/badges.html` — 7 colour variants with optional dot indicator
- `templates/components/empty_state.html` — yellow-tint icon container, title, description, CTA link
- `templates/components/skeletons.html` — `animate-sk-pulse` with `aria-busy="true"`
- `templates/components/filter_bar.html` — search input + status/type selects in `rounded-menu` container
- `templates/components/pagination.html` — page range with black/yellow active page, aria-current, aria-disabled
- `frontend/src/entrypoints/app-shell.ts` — `Alpine.store('nav', { mobileOpen: false })` added
- `frontend/src/styles/tailwind.css` — sk-pulse keyframe, focus-visible ring, `[x-cloak]` rule

## Decisions Made

- **User.full_name vs first_name/last_name:** Plan 01-02 created User with `full_name` (single field) not `first_name`/`last_name` as the plan interface assumed. Templates updated to use `user.full_name` and `user.get_role_display`. Test fixtures updated accordingly.
- **logout_stub in Phase 1:** Phase 2 will replace the view body with the real logout flow; the `name='logout'` URL identifier is frozen so sidebar/topbar templates need no changes in Phase 2.
- **toasts.html in shell.html:** Toast stack is included from shell.html (not base.html) so it's always present in authenticated shell pages but absent from email/API layouts.

## Component Partial API Contract

All components use `{% include "components/<name>.html" with ... %}` pattern:

| Component | Key parameters |
|-----------|---------------|
| `buttons.html` | `variant` (primary/secondary/danger/ghost), `label`, `type`, `icon`, `disabled`, `loading`, `size` (sm/default/lg), `extra_class` |
| `form_fields.html` | `name`, `label`, `type` (text/email/password/number/textarea/select), `value`, `required`, `disabled`, `error`, `help_text`, `warn`, `options` (for select) |
| `badges.html` | `variant` (neutral/green/gray/amber/blue/red/yellow), `label`, `dot` |
| `toasts.html` | no params — listens for `window.dispatchEvent(new CustomEvent('app:toast', { detail: { kind, title, msg } }))` |
| `empty_state.html` | `icon`, `title`, `description`, `cta_label`, `cta_href` |
| `skeletons.html` | `width`, `height`, `rounded` |
| `filter_bar.html` | `search_placeholder`, `status_options` (list of (value, label)), `type_options`, `request` |
| `pagination.html` | `page_obj` (Django Paginator Page object) |

## Alpine.js Store / Event Contract

- `$store.nav.mobileOpen` — boolean, true when mobile drawer is open; toggled by hamburger button (topbar) and sidebar backdrop click
- `app:toast` CustomEvent schema: `{ kind: 'success' | 'error' | 'info' | 'warning', title: string, msg?: string }`
  - Example: `window.dispatchEvent(new CustomEvent('app:toast', { detail: { kind: 'success', title: 'Saved', msg: 'Organisation created.' } }))`

## Phase-1 Logout Stub Contract

- URL: `path('logout/', logout_stub, name='logout')` in `apps/common/urls.py`
- View: accepts GET and POST, returns 302 to `/` — does NOT call `django.contrib.auth.logout()`
- Phase 2 action: replace `logout_stub` view body with real `LogoutView` or custom session-clearing view; URL name `'logout'` is stable, no template changes needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] User model uses full_name not first_name/last_name**
- **Found during:** Task 1 (test_topbar_has_avatar_dropdown_alpine_state)
- **Issue:** Plan interface assumed `User.first_name` and `User.last_name`, but Plan 01-02 created `User.full_name` (single field)
- **Fix:** Updated sidebar.html, topbar.html to use `user.full_name`, `user.get_role_display`; updated test fixtures to pass `full_name="Tee Oh"` instead of `first_name="Tee", last_name="Oh"`
- **Files modified:** templates/partials/sidebar.html, templates/partials/topbar.html, apps/common/tests/test_responsive.py
- **Verification:** All 8 responsive tests pass
- **Committed in:** 9f329e4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary correction for User model reality; no scope change.

## Issues Encountered

None.

## Next Phase Readiness

- Shell chrome ready for Plan 01-05 (React data table + modal dialog embedded components)
- All 8 component partials available via `{% include %}` for all downstream phases
- Logout URL `name='logout'` registered and stable for Phase 2 auth wiring
- `app:toast` CustomEvent contract established for Django messages integration in any view

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
