# Deferred Items — Phase 06

## Pre-existing Test Failure (Out of Scope)

**File:** `apps/common/tests/test_components.py::test_empty_state_renders_icon_title_desc_cta`
**Discovered:** Phase 06-01 execution
**Status:** Pre-existing failure on main branch (confirmed via git stash check)
**Issue:** Test asserts `href="/organisations/new/"` in rendered empty-state component output, but the button renders without an href attribute (renders as `<button>` not `<a>`).
**Root cause:** Likely a template change that wasn't reflected in the test expectation.
**Action needed:** Fix the template or test assertion in a future plan.
