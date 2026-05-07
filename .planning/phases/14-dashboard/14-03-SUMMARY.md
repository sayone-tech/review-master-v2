---
phase: "14-dashboard"
plan: "03"
subsystem: "dashboard"
tags: ["api", "views", "cache", "error-handlers", "tdd"]
dependency_graph:
  requires: ["14-02"]
  provides: ["dashboard-api-views", "error-handlers"]
  affects: ["apps/dashboard/views.py", "apps/dashboard/urls.py", "apps/common/views.py", "config/urls.py"]
tech_stack:
  added: []
  patterns:
    - "DashboardApiView base class with single security + cache gate"
    - "Five concrete views each implementing only _fetch()"
    - "handler404/handler500 string-path assignments at config/urls module level"
key_files:
  created:
    - apps/dashboard/views.py
    - apps/dashboard/urls.py
    - apps/dashboard/tests/test_views.py
    - apps/common/tests/test_views.py
  modified:
    - apps/common/views.py
    - config/urls.py
decisions:
  - "IsOrgScoped used directly on DashboardApiView — no queryset class needed for pure-read APIViews"
  - "Cache hit returns Response(cached) without calling _fetch — selector skipped entirely on cache hit"
  - "handler404/handler500 added as module-level string paths after urlpatterns definition in config/urls.py"
  - "Error handler tests use try/except with TemplateDoesNotExist early return to avoid PT017/PT012 ruff violations — acceptable until 14-08 ships templates"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-07"
  tasks_completed: 2
  files_changed: 6
---

# Phase 14 Plan 03: Dashboard HTTP Views + Error Handlers Summary

**One-liner:** DashboardApiView base with single security+cache gate, five concrete endpoint views delegating to selectors, and branded 404/500 handlers wired in config/urls.py.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DashboardApiView base + 5 concrete views + urls.py registration | e6ee29c | apps/dashboard/views.py, apps/dashboard/urls.py, apps/common/views.py, config/urls.py |
| 2 | Wire handler404/handler500 + page_not_found/server_error views + view tests | 529dd9f | apps/dashboard/tests/test_views.py, apps/common/tests/test_views.py |

## What Was Built

### DashboardApiView Base Class

`apps/dashboard/views.py` — `DashboardApiView(APIView)` provides a single shared gate for all dashboard endpoints:

1. `permission_classes = [IsOrgScoped]` — authentication + org membership enforced at class level
2. `validate_filter_params()` — validates query params, resolves accessible shop IDs, raises 400/403
3. `dashboard_cache_key()` + `cache_get()` — returns cached payload directly if found (selector never called)
4. `_fetch()` — abstract; concrete subclasses each implement exactly one call to their selector
5. `cache_set()` — stores fresh data at 5-minute TTL

Five concrete subclasses: `KpisView`, `SentimentView`, `TopPerformingView`, `HighlightsView`, `YourStoreView` — each has `endpoint_name` and a one-line `_fetch()`.

### URL Registration

`apps/dashboard/urls.py` — five routes under `api/v1/dashboard/` with `app_name = "dashboard"`.

`config/urls.py` — added `path("api/v1/dashboard/", include("apps.dashboard.urls"))` and module-level `handler404`/`handler500` string assignments.

### Error Handlers

`apps/common/views.py` — added `page_not_found(request, exception=None)` (ERR-01) and `server_error(request)` (ERR-02). Both render branded templates; `server_error` does not access `request.user` in Python.

### Tests (15 tests, all passing)

**apps/dashboard/tests/test_views.py (11 tests):**
- 200 happy path for all 5 endpoints
- 403 out-of-scope store (FILT-08)
- 400 date range > 365 days (FILT-09)
- 400 from > to (FILT-10)
- Cache hit skips selector — selector called exactly once across two identical requests (TECH-02)
- Query count ceiling ≤ 5 queries per request (TECH-04)

**apps/common/tests/test_views.py (4 tests):**
- `handler404` module path assertion (ERR-01)
- `handler500` module path assertion (ERR-02)
- `page_not_found` view callable (ERR-01)
- `server_error` view callable (ERR-02)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy union-attr errors on request.user.organisation_id**
- **Found during:** Task 1 commit (pre-commit hook)
- **Issue:** `request.user` is typed as `User | AnonymousUser` — mypy flagged `organisation_id` and `pk` accesses
- **Fix:** Added `user: User = request.user  # type: ignore[assignment]` and `int(user.pk)` cast
- **Files modified:** apps/dashboard/views.py
- **Commit:** e6ee29c

**2. [Rule 1 - Bug] PT017 ruff rule — assert in except block**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Original plan's test code used `assert ... in str(exc)` inside except blocks, violating ruff PT017
- **Fix:** Rewrote error-handler tests to use try/except with early `return` on TemplateDoesNotExist instead of asserting on the exception variable
- **Files modified:** apps/common/tests/test_views.py
- **Commit:** 529dd9f

**3. [Rule 2 - Missing functionality] pytest-mock not installed**
- **Found during:** Task 2 (test execution)
- **Issue:** Plan specified `mocker.spy` which requires `pytest-mock`, not installed in this project
- **Fix:** Replaced with `unittest.mock.patch(side_effect=counting_kpis)` — equivalent functionality using stdlib
- **Files modified:** apps/dashboard/tests/test_views.py
- **Commit:** 529dd9f

## Self-Check

Files exist:
- apps/dashboard/views.py: FOUND
- apps/dashboard/urls.py: FOUND
- apps/common/views.py (modified): FOUND
- config/urls.py (modified): FOUND
- apps/dashboard/tests/test_views.py: FOUND
- apps/common/tests/test_views.py: FOUND

Commits:
- e6ee29c: feat(14-03): DashboardApiView base + 5 concrete views — FOUND
- 529dd9f: test(14-03): add view tests — FOUND

## Self-Check: PASSED
