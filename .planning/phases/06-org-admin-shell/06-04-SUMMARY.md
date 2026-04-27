---
phase: 06-org-admin-shell
plan: 04
subsystem: ui
tags: [django-templates, tailwind, org-admin, dashboard, regions]

# Dependency graph
requires:
  - phase: 06-02
    provides: org_admin_required decorator + org admin shell infrastructure
  - phase: 06-01
    provides: Region model with FK to Organisation
  - phase: 06-03
    provides: base_org.html sidebar template + /admin/org/dashboard/ alias URL

provides:
  - Personalised welcome card with first_name extraction (full_name split or email prefix fallback)
  - Conditional zero-regions setup banner using Region.objects.filter().exists()
  - 403 response for STAFF_ADMIN and org-less ORG_ADMIN (replacing redirect to /login/)
  - 20 passing dashboard tests covering all edge cases

affects: [07-regions, all phases that add dashboard widgets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - First-name extraction: split full_name on first whitespace, fall back to email prefix before @
    - Banner gating via .exists() not .count() for performance
    - 403 for wrong-role access (no redirect masking auth failures)

key-files:
  created: []
  modified:
    - apps/organisations/views.py
    - templates/organisations/org_dashboard.html
    - apps/organisations/tests/test_views.py
    - apps/organisations/tests/conftest.py

key-decisions:
  - "06-04: org-less ORG_ADMIN now returns 403 (was redirect to /login/) — aligns with CONTEXT.md wrong-role spec"
  - "06-04: Banner check uses Region.objects.filter(organisation=...).exists() not .count() — short-circuits at first row"
  - "06-04: first_name extracted via user.full_name.split()[0] with fallback to user.email.split('@')[0] when blank/whitespace-only"

patterns-established:
  - "Dashboard personalisation: first_name context key from full_name first word or email prefix"
  - "Setup banner pattern: show_setup_banner bool context key driven by .exists() query"
  - "assert_query_ceiling fixture re-exported in apps/organisations/tests/conftest.py for use by org tests"

requirements-completed: [SHEL-02, SHEL-03]

# Metrics
duration: 5min
completed: 2026-04-27
---

# Phase 6 Plan 04: Personalised Dashboard + Zero-Regions Setup Banner Summary

**Personalised Org Admin dashboard with first_name extraction, org subtitle, and conditional yellow zero-regions setup banner using Region.objects.exists()**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-27T12:11:10Z
- **Completed:** 2026-04-27T12:16:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- SHEL-02 satisfied: Welcome card renders "Welcome, {first_name}" with org name + manage subtitle
- SHEL-03 satisfied: Yellow banner (`bg-yellow text-black`) with "Get started by creating your first region" CTA appears only when org has 0 Regions; self-removes once a Region exists
- Role rejection changed from redirect to 403: both STAFF_ADMIN and org-less ORG_ADMIN return `HttpResponseForbidden`
- 20 dashboard tests pass (12 new + 2 legacy updated + 6 prior passing)

## First-Name Extraction Algorithm

The algorithm (locked in CONTEXT.md) extracts the greeting name in this order:

1. **full_name present and non-blank:** `user.full_name.split()[0]` — Python's `.split()` with no args handles multiple/leading/trailing whitespace correctly. `"   Bob   Jones  ".split()[0]` → `"Bob"`.
2. **full_name blank or whitespace-only:** `user.email.split("@")[0]` — returns everything before the `@` sign. `"alice.smith@example.com".split("@")[0]` → `"alice.smith"`.

Edge cases verified by tests:
- `full_name="Renjith Raj"` → `first_name="Renjith"` ✓
- `full_name="   Bob   Jones  "` → `first_name="Bob"` ✓
- `full_name=""` + `email="alice.smith@example.com"` → `first_name="alice.smith"` ✓
- `full_name="   "` + `email="bob@example.com"` → `first_name="bob"` ✓

## Banner Show/Hide Logic

`show_setup_banner = not Region.objects.filter(organisation=user.organisation).exists()`

- `.exists()` chosen over `.count() == 0` per CONTEXT.md: short-circuits at the first matching row, never counts all rows. PostgreSQL executes a `LIMIT 1` query internally.
- Verified by a 50-region performance test asserting total query count ≤ 10 (query ceiling fixture).
- Banner only counts Regions belonging to `user.organisation` — a different org having Regions does not hide the banner.

## Role-Rejection Model Change

| Scenario | Before Plan 04 | After Plan 04 |
|---|---|---|
| ORG_ADMIN without organisation | 302 → /login/ | **403 Forbidden** |
| STAFF_ADMIN | 302 → /login/ | **403 Forbidden** |
| SUPERADMIN | 302 → /admin/organisations/ | unchanged |

The change aligns with CONTEXT.md: "Wrong-role access → 403 Forbidden, not redirect" — prevents silent 302s masking auth failures.

## Task Commits

TDD task committed in two phases:

1. **RED — failing tests** - `7772af5` (test)
2. **GREEN — implementation + legacy test updates** - `d61e259` (feat)

**Plan metadata:** [this commit]

## Files Created/Modified

- `apps/organisations/views.py` — Extended `org_admin_dashboard` with first_name extraction, exists() banner check, 403 for wrong roles; added `HttpResponseForbidden` and `Region` imports
- `templates/organisations/org_dashboard.html` — Rewritten: setup banner (conditional, `bg-yellow`) + welcome card with `{{ first_name }}` + org subtitle
- `apps/organisations/tests/test_views.py` — 12 new dashboard tests; 2 legacy tests updated to reflect new 403 behaviour and updated template
- `apps/organisations/tests/conftest.py` — Re-exported `assert_query_ceiling` fixture from `apps.common.tests.fixtures`

## Decisions Made

- **403 not redirect for wrong-role access** — Aligns with CONTEXT.md spec. Prevents silent 302 masking auth failures. Legacy tests updated accordingly.
- **.exists() not .count()** — Per CONTEXT.md Pitfall guidance. Confirmed by performance test.
- **assert_query_ceiling in conftest** — Re-exported to avoid F811 ruff lint error (fixture parameter shadows module-level import). STATE.md note confirmed Phase 7-9 tests must explicitly import from `apps.common.tests.fixtures`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed F811 lint error — assert_query_ceiling import conflicted with fixture parameter**
- **Found during:** Task 1 RED (pre-commit ruff-check hook)
- **Issue:** Module-level `from apps.common.tests.fixtures import assert_query_ceiling` conflicted with the pytest fixture parameter of the same name in `test_dashboard_uses_exists_query_for_setup_banner`
- **Fix:** Removed module-level import from `test_views.py`; re-exported `assert_query_ceiling` in `apps/organisations/tests/conftest.py` instead (standard pytest fixture discovery pattern)
- **Files modified:** `apps/organisations/tests/test_views.py`, `apps/organisations/tests/conftest.py`
- **Verification:** ruff-check passes, fixture available via conftest auto-discovery
- **Committed in:** `7772af5`

**2. [Rule 1 - Bug] Fixed legacy test `test_org_admin_dashboard_org_admin_without_org_redirects_to_login` expecting 302**
- **Found during:** Task 1 GREEN (test run)
- **Issue:** Legacy test expected `302 → /login/` for org-less ORG_ADMIN; Plan 04 changed this to `403` per CONTEXT.md spec
- **Fix:** Updated test name and assertion to expect 403
- **Files modified:** `apps/organisations/tests/test_views.py`
- **Verification:** Test passes with new expectation
- **Committed in:** `d61e259`

**3. [Rule 1 - Bug] Fixed legacy test `test_org_admin_dashboard_org_admin_sees_welcome_card` checking old template text**
- **Found during:** Task 1 GREEN (test run)
- **Issue:** Test checked for `"Welcome to Acme Holdings"` (old stub template copy); new template uses `"Welcome, {first_name}"` + org name separately. Also `UserFactory` generates random `full_name` so email prefix fallback was unreliable.
- **Fix:** Explicitly set `full_name="Jane Doe"` in UserFactory call; updated assertion to `"Welcome, Jane"` + `"Acme Holdings"`
- **Files modified:** `apps/organisations/tests/test_views.py`
- **Verification:** Test passes with deterministic name
- **Committed in:** `d61e259`

---

**Total deviations:** 3 auto-fixed (3 Rule 1 - Bug)
**Impact on plan:** All auto-fixes were necessary for correctness. No scope creep. Pre-existing unrelated failure in `apps/common/tests/test_components.py::test_empty_state_renders_icon_title_desc_cta` confirmed pre-existing before this plan's changes (logged to deferred-items).

## Issues Encountered

- Pre-existing test failure: `apps/common/tests/test_components.py::test_empty_state_renders_icon_title_desc_cta` — `href="/organisations/new/"` not in rendered output. Confirmed pre-existing (present on clean stash before any plan changes). Logged to deferred-items; out of scope for Plan 04.

## Next Phase Readiness

- Plan 05 (org profile stub, the last plan in Phase 6) can now proceed
- Phase 7 (Regions) can build on the banner CTA — once a Region is created, the banner on `/admin/org/dashboard/` will automatically disappear
- Phase 7 should add a regression test: "banner disappears the moment the first Region is created" to explicitly cover that lifecycle
- The query-ceiling fixture (`assert_query_ceiling`) is now available in `apps/organisations/tests/conftest.py` for use by Phase 6 Plan 05 and future org-related tests

---
*Phase: 06-org-admin-shell*
*Completed: 2026-04-27*
