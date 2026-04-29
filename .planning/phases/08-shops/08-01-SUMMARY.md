---
phase: 08-shops
plan: "01"
subsystem: integrations/google
tags: [google-api, oauth, places, httpx, tenacity, integration-layer]
dependency_graph:
  requires: []
  provides:
    - apps.integrations.google.oauth.build_auth_url
    - apps.integrations.google.oauth.exchange_code_for_token
    - apps.integrations.google.oauth.list_business_locations
    - apps.integrations.google.places.validate_place_id
    - apps.integrations.google.exceptions.*
  affects:
    - apps.shops (Plan 08-02 imports these directly)
tech_stack:
  added:
    - httpx==0.28.1
    - tenacity==9.1.4
  patterns:
    - tenacity @retry with retry_if_exception_type(httpx.TransportError) + stop_after_attempt(3) + wait_exponential
    - _setting() helper with getattr+cast for django-stubs-agnostic settings access
    - @patch("apps.integrations.google.oauth.httpx.post") mock target path
    - override_settings per method (not class) — Django requires SimpleTestCase for class-level decorator
key_files:
  created:
    - apps/integrations/__init__.py
    - apps/integrations/google/__init__.py
    - apps/integrations/google/exceptions.py
    - apps/integrations/google/places.py
    - apps/integrations/google/oauth.py
    - apps/integrations/google/tests/__init__.py
    - apps/integrations/google/tests/test_places.py
    - apps/integrations/google/tests/test_oauth.py
  modified:
    - pyproject.toml (added httpx + tenacity deps + mypy overrides)
    - config/settings/base.py (added GOOGLE_OAUTH_* settings)
    - .pre-commit-config.yaml (added httpx + tenacity to mypy additional_dependencies)
    - uv.lock (regenerated after uv sync)
decisions:
  - "Use _setting(name) helper with getattr+cast instead of settings.ATTR directly — avoids django-stubs attr-defined errors on custom settings without needing .pyi stubs"
  - "TOKEN_ENDPOINT constant name triggers bandit B105 + ruff S105 false positives — suppressed with combined # noqa: S105  # nosec B105 comment"
  - "Django override_settings cannot decorate plain pytest classes (requires SimpleTestCase subclass) — applied per-method instead"
  - "Pre-commit mypy hook required adding httpx==0.28.1 + tenacity==9.1.4 to additional_dependencies to avoid import-not-found errors on these typed packages"
  - "Test method names lowercased to comply with ruff N802 (e.g. test_NOT_FOUND -> test_not_found_raises_place_id_not_found_error)"
metrics:
  duration_seconds: 739
  duration_display: "12 minutes"
  completed_date: "2026-04-29"
  tasks_completed: 3
  tasks_total: 3
  test_count: 15
  test_runtime_seconds: 12.12
  files_created: 8
  files_modified: 4
---

# Phase 08 Plan 01: Google Integration Layer Summary

**One-liner:** HTTP integration layer for Google OAuth 2.0 + Places API using httpx + tenacity retry, behind domain-free Python interfaces.

## What Was Built

Three modules under `apps/integrations/google/` providing stable Python interfaces for all Google API I/O:

1. **`exceptions.py`** — Four domain exceptions: `GoogleUnreachableError`, `GoogleAuthError(reason)`, `PlaceIDNotFoundError`, `APIKeyInvalidError`

2. **`places.py`** — `validate_place_id(*, place_id, api_key) -> dict` — validates a Google Place ID via the Places API with 3-attempt tenacity retry on transport errors

3. **`oauth.py`** — Three OAuth flow functions:
   - `build_auth_url(*, state) -> str` — Google OAuth 2.0 authorization URL with business.manage scope
   - `exchange_code_for_token(*, code) -> dict` — POSTs to token endpoint, validates refresh_token presence
   - `list_business_locations(*, refresh_token) -> list[dict]` — refreshes access token, lists GBP accounts + locations, returns `[{name, address, place_id}]`

## Test Coverage

- 15 unit tests (7 places + 8 oauth), all passing
- Runtime: 12.12 seconds (includes tenacity retry wait times for the retry-then-succeeds test)
- Every error path covered with mocked httpx — no live network calls

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff N802: Test method names with uppercase letters**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Test names like `test_NOT_FOUND_raises_PlaceIDNotFoundError` violate ruff N802 (function names must be lowercase)
- **Fix:** Renamed all test methods to snake_case equivalents (e.g., `test_not_found_raises_place_id_not_found_error`)
- **Files modified:** `apps/integrations/google/tests/test_places.py`, `apps/integrations/google/tests/test_oauth.py`

**2. [Rule 1 - Bug] bandit B105 + ruff S105 false positive on TOKEN_ENDPOINT**
- **Found during:** Task 3 commit (bandit hook)
- **Issue:** Variable named `TOKEN_ENDPOINT` with a URL value is flagged as "hardcoded password" by both bandit (B105) and ruff (S105)
- **Fix:** Added `# noqa: S105  # nosec B105` inline suppression comment — the value is a public OAuth endpoint URL, not a credential
- **Files modified:** `apps/integrations/google/oauth.py`

**3. [Rule 1 - Bug] Django override_settings cannot decorate plain pytest classes**
- **Found during:** Task 3 test execution (RED phase)
- **Issue:** `ValueError: Only subclasses of Django SimpleTestCase can be decorated with override_settings` when using `@override_settings` on plain pytest test classes
- **Fix:** Applied `@override_settings` per-method instead of per-class
- **Files modified:** `apps/integrations/google/tests/test_oauth.py`

**4. [Rule 2 - Missing functionality] Pre-commit mypy missing httpx + tenacity dependencies**
- **Found during:** Task 2 commit (pre-commit mypy hook)
- **Issue:** Pre-commit mypy hook lacked httpx and tenacity in `additional_dependencies`, causing `import-not-found` and `Untyped decorator` errors even after local mypy passed
- **Fix:** Added `httpx==0.28.1` and `tenacity==9.1.4` to `.pre-commit-config.yaml` mypy hook `additional_dependencies`
- **Files modified:** `.pre-commit-config.yaml`

**5. [Rule 1 - Bug] settings.GOOGLE_OAUTH_* attr-defined mypy errors**
- **Found during:** Task 3 commit (pre-commit mypy)
- **Issue:** django-stubs' `Settings` type doesn't include project-specific settings attributes, causing `[attr-defined]` errors
- **Fix:** Replaced direct `settings.GOOGLE_OAUTH_CLIENT_ID` access with `_setting("GOOGLE_OAUTH_CLIENT_ID")` helper using `getattr` + `cast(str, ...)` — avoids stubs issue without needing a custom .pyi file
- **Files modified:** `apps/integrations/google/oauth.py`

## Self-Check

### PASSED

Files verified:
- FOUND: apps/integrations/google/oauth.py
- FOUND: apps/integrations/google/places.py
- FOUND: apps/integrations/google/exceptions.py
- FOUND: apps/integrations/google/tests/test_places.py
- FOUND: apps/integrations/google/tests/test_oauth.py

Commits verified:
- FOUND: 2e9177d (feat(08-01): add google integration package skeleton with exceptions)
- FOUND: 4f6a84a (feat(08-01): implement Places API validator with retry+backoff and full test coverage)
- FOUND: efe7465 (feat(08-01): implement Google OAuth flow primitives with full test coverage)
