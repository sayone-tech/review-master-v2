---
phase: 02-authentication
plan: "01"
subsystem: accounts/settings
tags: [auth, settings, throttling, tests, wave-0]
dependency_graph:
  requires: []
  provides:
    - config/settings/base.py:LOGIN_URL,LOGIN_REDIRECT_URL,LOGOUT_REDIRECT_URL
    - config/settings/base.py:SESSION_COOKIE_AGE,SESSION_EXPIRE_AT_BROWSER_CLOSE
    - config/settings/base.py:PASSWORD_RESET_TIMEOUT
    - config/settings/base.py:CACHES['throttle']
    - config/settings/base.py:DEFAULT_THROTTLE_RATES['login']
    - apps/accounts/throttling.py:LoginRateThrottle
    - apps/accounts/tests/conftest.py:superadmin,client_logged_in,anon_client
    - apps/accounts/tests/test_views.py:21 AUTH-01..AUTH-05 test stubs
  affects:
    - plans 02-02, 02-03 (views/templates depend on these settings + throttle class)
tech_stack:
  added: []
  patterns:
    - DRF SimpleRateThrottle subclass with custom parse_rate for multi-unit periods
    - Redis DB separation: DB 0 default cache, DB 1 throttle cache
key_files:
  created:
    - apps/accounts/throttling.py
    - apps/accounts/tests/conftest.py
    - apps/accounts/tests/test_views.py
  modified:
    - config/settings/base.py
    - config/settings/test.py
decisions:
  - "LoginRateThrottle overrides parse_rate because DRF's built-in only reads period[0], making '10/15min' fail (period[0]='1' not in {'s','m','h','d'}). Override handles multi-unit periods like '15min' by regex matching."
  - "test.py CACHES throttle alias uses locmem.LocMemCache (not RedisCache) to keep tests fast and isolated"
metrics:
  duration: ~12 min
  completed_date: "2026-04-23"
  tasks: 3
  files: 5
---

# Phase 02 Plan 01: Settings + Throttle Foundation + Test Stubs Summary

Wave 0 foundation for Phase 02: auth settings, LoginRateThrottle class with multi-unit parse_rate fix, and 21 failing test stubs covering every AUTH-01..AUTH-05 behavior.

## What Was Built

### Task 1 — Auth + Throttle Settings (config/settings/base.py)

Settings values added verbatim per plan:

| Setting | Value |
|---------|-------|
| `LOGIN_URL` | `/login/` |
| `LOGIN_REDIRECT_URL` | `/admin/organisations/` |
| `LOGOUT_REDIRECT_URL` | `/login/` |
| `SESSION_COOKIE_AGE` | `86400` (60×60×24) |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | `False` |
| `SESSION_SAVE_EVERY_REQUEST` | `False` |
| `SESSION_COOKIE_HTTPONLY` | `True` |
| `SESSION_COOKIE_SAMESITE` | `"Lax"` |
| `PASSWORD_RESET_TIMEOUT` | `3600` (1 hour) |
| `CACHES["throttle"]` | Redis DB 1, KEY_PREFIX="throttle", TIMEOUT=900 |
| `DEFAULT_THROTTLE_RATES["login"]` | `"10/15min"` |

Also updated `config/settings/test.py` to add a `"throttle"` cache alias using `LocMemCache`.

### Task 2 — LoginRateThrottle (apps/accounts/throttling.py)

- `scope = "login"` matches `DEFAULT_THROTTLE_RATES["login"]`
- `cache = caches["throttle"]` sends throttle keys to Redis DB 1
- `get_cache_key` returns IP-scoped key via `get_ident(request)` (X-Forwarded-For aware)
- Overrides `parse_rate` to handle `"10/15min"` format (see Deviations below)

### Task 3 — Test Stubs (apps/accounts/tests/)

**conftest.py fixtures:**
- `superadmin` — UserFactory(email="super@example.com", role="SUPERADMIN"), password "testpass1234"
- `client_logged_in` — Django test Client force-logged in as superadmin
- `anon_client` — anonymous Django test Client

**test_views.py — 21 tests (all failing, Wave 0):**

| Test Name | AUTH Req | What It Checks |
|-----------|----------|----------------|
| `test_login_get` | AUTH-01 | GET /login/ returns 200 with "Sign in" |
| `test_login_post_valid` | AUTH-01 | POST valid creds → 302 to /admin/organisations/ |
| `test_login_success` | AUTH-01 | Session contains _auth_user_id after login |
| `test_login_invalid` | AUTH-01 | Wrong password → 200 with "Invalid email or password" |
| `test_login_no_enumeration` | AUTH-01 | Nonexistent user → same error, never "does not exist" |
| `test_login_rate_limit` | AUTH-01 | 11th failed POST → 429 with "Too many" |
| `test_login_remember_me` | AUTH-05 | remember_me=on → session age = 30 days |
| `test_login_no_remember_me` | AUTH-05 | no remember_me → session age = 24 hours |
| `test_remember_me` | AUTH-05 | Alias: same as test_login_remember_me |
| `test_login_next_param` | AUTH-01 | Safe next= honored; absolute URL next= rejected |
| `test_logout` | AUTH-02 | POST /logout/ → 302 /login/, session cleared |
| `test_logout_get_rejected` | AUTH-02 | GET /logout/ → 405 or non-login 302 |
| `test_password_reset_email_sent` | AUTH-03 | POST /password-reset/ → email with html alt |
| `test_password_reset_no_enumeration` | AUTH-03 | Ghost email → same 302/done, no email sent |
| `test_password_reset_confirm` | AUTH-04 | Valid token → can set new password |
| `test_password_reset_expired` | AUTH-04 | Expired token → 200 with expired/invalid message |
| `test_password_reset_redirect` | AUTH-04 | After confirm → 302 to /login/ |
| `test_password_reset_flow` | AUTH-04 | End-to-end; asserts flash "Password updated. Please sign in." |
| `test_session_persists` | AUTH-05 | sessionid cookie has positive max-age |
| `test_login_required_redirect` | AUTH-05 | GET /admin/organisations/ → 302 /login/?next=... |
| `test_redirect_unauthenticated` | AUTH-05 | Alias: same check as test_login_required_redirect |

**Flash message locked copy (test_password_reset_flow):**
```
"Password updated. Please sign in."
```
Plan 03 Task 1's `messages.success()` call must use this exact string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed DRF parse_rate incompatibility with "10/15min" format**

- **Found during:** Task 2 verification
- **Issue:** DRF's `SimpleRateThrottle.parse_rate` uses `period[0]` as the period unit key. For `"10/15min"`, `period[0]` = `"1"` which is not in `{"s": 1, "m": 60, "h": 3600, "d": 86400}`, raising `KeyError: '1'`.
- **Fix:** Added `parse_rate` override in `LoginRateThrottle` that regex-matches multi-unit periods (e.g. `15min`) and falls back to DRF's single-char lookup for standard rates. `_PERIOD_RE` and `_UNIT_SECONDS` annotated as `ClassVar` to pass ruff RUF012.
- **Files modified:** `apps/accounts/throttling.py`
- **Commit:** d2247b4

**2. [Rule 3 - Blocking] Added throttle cache alias to test.py**

- **Found during:** Task 1 verification
- **Issue:** `config/settings/test.py` overrides `CACHES` with only `{"default": {...}}`. Without a `"throttle"` key, `caches["throttle"]` would raise `InvalidCacheBackendError` during test collection.
- **Fix:** Added `"throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}` to the test CACHES dict.
- **Files modified:** `config/settings/test.py`
- **Commit:** c6ba67e

## Self-Check: PASSED

All files present and all task commits found:
- FOUND: apps/accounts/throttling.py
- FOUND: apps/accounts/tests/conftest.py
- FOUND: apps/accounts/tests/test_views.py
- FOUND: commit c6ba67e (Task 1 - settings)
- FOUND: commit d2247b4 (Task 2 - throttle class)
- FOUND: commit 1dbc566 (Task 3 - test stubs)
