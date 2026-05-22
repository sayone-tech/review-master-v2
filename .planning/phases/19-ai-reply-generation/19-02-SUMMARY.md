---
phase: 19-ai-reply-generation
plan: 02
subsystem: reviews
tags: [api, drf, openai, throttle, reviews]
requires:
  - apps/reviews/services/reply_generation.py (from 19-01)
  - apps/integrations/openai/exceptions.py (Phase 12)
provides:
  - POST /api/v1/reviews/{id}/generate-reply/ endpoint
  - GenerateReplySerializer
  - generate_reply throttle scope (10/minute)
affects:
  - ReviewViewSet.get_queryset() now includes select_related("shop__organisation")
tech-stack:
  added: []
  patterns: [drf-action, scoped-rate-throttle, thin-view-thick-service]
key-files:
  created: []
  modified:
    - apps/reviews/serializers.py
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py
    - config/settings/base.py
decisions:
  - Map all OpenAI exceptions (transient, permanent, generic) to a single 502 with code=ai_unavailable per D-17 — uniform client behaviour and no error-detail leakage (T-19-06).
  - Add select_related("shop__organisation") inside ReviewViewSet.get_queryset() (not in the shared base_reviews_queryset selector) so the join is scoped to the API path that needs it and existing query-count budgets (REVW-14 list ≤5) are unaffected.
  - Throttle cache is cleared inside the query-count test only — production behaviour and existing tests are untouched; the cache survives DB rollback between test methods because it lives in Redis.
metrics:
  duration: ~15min
  completed: 2026-05-22
---

# Phase 19 Plan 02: generate_reply API Endpoint Summary

DRF endpoint wiring for AI reply generation: GenerateReplySerializer + ReviewViewSet.generate_reply @action + 10/min ScopedRateThrottle. Full 9-test suite covering 200/400/403/404/502 paths and N+1 query-count guard.

## What Was Built

- **GenerateReplySerializer** (apps/reviews/serializers.py): `tone` ChoiceField restricted to `["professional", "friendly"]`. Returns 400 for any other value or missing field.
- **ReviewViewSet.generate_reply** (@action, detail=True, methods=["post"], url_path="generate-reply"):
  - Thin wrapper: validates input with GenerateReplySerializer, fetches the review via `self.get_object()` (inherits org + Staff-scope filtering from get_queryset), calls `generate_reply_draft(review=..., tone=...)`, returns `{"draft": ...}` on success.
  - Catches `OpenAITransientError`, `OpenAIPermanentError`, and any other `Exception` (`# noqa: BLE001`) — all map to a single 502 response `{"code": "ai_unavailable", "detail": "AI generation failed. Please try again or write your reply manually."}` per D-17. Logs the exception type at WARNING.
  - Uses `ScopedRateThrottle` with `self.throttle_scope = "generate_reply"`.
- **Throttle setting** (config/settings/base.py): `"generate_reply": "10/minute"` added to `DEFAULT_THROTTLE_RATES` (D-12).
- **N+1 guard** (apps/reviews/views.py get_queryset): `select_related("shop__organisation")` so `generate_reply_draft()` can read `review.shop.organisation.name` without extra queries (CLAUDE.md §6). Verified by the new query-count test.
- **TestGenerateReplyEndpoint** (apps/reviews/tests/test_views.py): 9 tests
  1. `test_success_returns_draft` — mocked service → 200 `{"draft": "..."}`
  2. `test_invalid_tone_returns_400` — `tone: "formal"` → 400
  3. `test_unauthenticated_returns_403` — no auth → 403
  4. `test_transient_error_returns_502` — service raises OpenAITransientError → 502 ai_unavailable
  5. `test_permanent_error_returns_502` — service raises OpenAIPermanentError → 502 ai_unavailable
  6. `test_generic_exception_returns_502` — service raises ValueError → 502 ai_unavailable
  7. `test_staff_admin_accessible_shop` — Staff with shop in scope → 200
  8. `test_staff_admin_inaccessible_shop_returns_404` — Staff without scope → 404 (no service call)
  9. `test_generate_reply_query_count` — CaptureQueriesContext asserts ≤4 SQL queries on the path

## Commits

- `dc6a050` test(19-02): add failing TestGenerateReplyEndpoint suite (RED)
- `033db81` feat(19-02): add generate_reply endpoint + GenerateReplySerializer + 10/min throttle (GREEN)
- `6c80eb3` test(19-02): clear throttle cache in generate_reply query-count test (fix for cross-test cache leakage)

## Verification

- `pytest apps/reviews/` → 157 passed, 0 failed (no regressions on existing reviews tests).
- `pytest apps/reviews/tests/test_views.py::TestGenerateReplyEndpoint` → 9 passed.
- Automated verify snippet from plan (`GenerateReplySerializer` validation + `ReviewViewSet.generate_reply` attribute + throttle rate `10/minute`) → PASS.
- pre-commit hooks (ruff, mypy, bandit, django-upgrade, gitleaks, missing-migrations) → all passed on every commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Cross-test throttle-cache leakage broke the query-count test in the full suite**
- **Found during:** Task 2 verify, when running the broader `pytest apps/reviews/` suite
- **Issue:** `TestGenerateReplyEndpoint::test_generate_reply_query_count` returned 429 instead of 200 because the 10/min `ScopedRateThrottle` bucket was already saturated by the 8 prior tests in the same class. The throttle cache lives in Redis (`CACHES["throttle"]`) and survives the DB transaction rollback that pytest-django applies between methods. In isolation the test passed (cache empty); in the full suite it failed.
- **Fix:** Clear the throttle cache at the top of the query-count test only (`caches["throttle"].clear()`). Scoped to that single test method so production behaviour and other tests are untouched.
- **Files modified:** apps/reviews/tests/test_views.py
- **Commit:** 6c80eb3

## Success Criteria — All Met

- [x] POST `/api/v1/reviews/{id}/generate-reply/` with valid tone returns 200 `{"draft": "..."}`
- [x] Invalid tone returns 400; unauthenticated returns 403
- [x] OpenAI failure (any exception) returns 502 `{"code": "ai_unavailable", "detail": "AI generation failed. Please try again or write your reply manually."}`
- [x] `generate_reply: 10/minute` in `DEFAULT_THROTTLE_RATES`
- [x] `ReviewViewSet.get_queryset()` includes `select_related("shop__organisation")` — no N+1 on the generate_reply path
- [x] All 9 new test cases pass (including ≤4-query assertion); existing test_views.py tests unaffected
- [x] `pre-commit run --all-files` passes (verified via per-commit hook runs)

## Self-Check: PASSED

- File `apps/reviews/serializers.py`: present (GenerateReplySerializer at lines 91-100).
- File `apps/reviews/views.py`: present (generate_reply action at the end of ReviewViewSet).
- File `config/settings/base.py`: present (`"generate_reply": "10/minute"`).
- File `apps/reviews/tests/test_views.py`: present (TestGenerateReplyEndpoint at the end).
- Commits `dc6a050`, `033db81`, `6c80eb3` exist in `git log --oneline`.
