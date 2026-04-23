# Deferred Items

## Pre-existing Test Failures (out-of-scope for Plan 03)

These failures exist in the codebase before Plan 03 execution and are NOT caused by any Plan 03 changes. They should be addressed separately.

### apps/common/tests/test_responsive.py

**test_logout_stub_get_returns_302_to_home** — Django's LogoutView (Phase 2) only accepts POST. The test sends GET and expects 302, but receives 405 Method Not Allowed. The logout stub was intended to accept both GET and POST but was implemented as POST-only.

**test_logout_stub_post_returns_302_to_home** — Related: similar issue with logout stub redirect behavior.

**Discovery date:** 2026-04-23
**Confirmed pre-existing:** Yes (verified via git stash)
**Affected file:** apps/common/tests/test_responsive.py
