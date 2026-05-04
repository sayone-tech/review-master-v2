---
phase: "11-reviews"
plan: "07"
subsystem: reviews
tags: [reply, google-api, audit-log, distributed-lock, rate-throttle, exception-handling]
dependency_graph:
  requires: ["11-02", "11-06"]
  provides: [submit_reply service, reply endpoint, ReplyConflictError, ReplyFailedError]
  affects: [apps/reviews/views.py, apps/reviews/services/replies.py, apps/reviews/exceptions.py]
tech_stack:
  added: []
  patterns: [distributed-lock-30s, ScopedRateThrottle, AuditLog reply_posted/reply_failed, HTTP 409/502 mapping]
key_files:
  created:
    - apps/reviews/exceptions.py
    - apps/reviews/services/replies.py
    - apps/reviews/tests/test_reply_service.py
  modified:
    - apps/reviews/views.py
    - apps/reviews/consumers.py
decisions:
  - "Lock TTL = 30s (CLAUDE.md §7.6) — reply is a fast synchronous HTTP call; 30s prevents double-post on rapid clicks without holding lock longer than needed"
  - "HTTP status mapping: ReplyConflictError -> 409, ReplyFailedError -> 502 — 409 signals concurrent request conflict; 502 signals upstream (Google) failure"
  - "AuditLog uses string entity_type='review' consistent with Plan 01 decision — avoids GenericForeignKey overhead"
  - "throttle_scope set as both class attribute fallback and per-action self.throttle_scope — ensures DRF routing introspection works"
metrics:
  duration_minutes: 7
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 5
---

# Phase 11 Plan 07: Reply Endpoint + Service Summary

Reply service posts to Google synchronously via distributed lock, persisting locally only on success with full AuditLog coverage and ScopedRateThrottle (30/min).

## What Was Built

### Task 1: Reply service + exception classes

Created `apps/reviews/exceptions.py` with two domain exceptions:

- `ReplyConflictError` — raised when per-review Redis lock is held (concurrent submission)
- `ReplyFailedError(code, message)` — raised on Google API failure; carries a machine-readable `code` for the view to serialize

Created `apps/reviews/services/replies.py` with `submit_reply(review, comment, actor)`:

- Acquires `lock:reply:review:{review_id}` (30s TTL) before any network call
- Refreshes Google access token via `_refresh_access_token`
- Posts to Google via `post_reply`
- On `invalid_grant`: marks `shop.connection_status = EXPIRED` then raises `ReplyFailedError(code="invalid_grant")`
- On `GoogleReplyError`: raises `ReplyFailedError(code="reply_rejected")` — no local mutation
- On `GoogleUnreachableError`: raises `ReplyFailedError(code="unreachable")`
- On success: persists `reply_comment`, `reply_update_time`, `is_replied=True` atomically and writes `AuditLog(action="reply_posted")`
- All failure paths write `AuditLog(action="reply_failed")` before raising

### Task 2: ViewSet @action(reply) endpoint

Updated `apps/reviews/views.py`:

- Added `@action(detail=True, methods=["post"], url_path="reply", throttle_classes=[ScopedRateThrottle])`
- `throttle_scope = "review_reply"` class attribute (30/min per `DEFAULT_THROTTLE_RATES`)
- Maps `ReplyConflictError` → 409, `ReplyFailedError` → 502 with `{detail, code}` body
- Returns `ReviewReadSerializer(updated_review).data` with HTTP 200 on success
- Empty `comment` validated by `ReviewReplySerializer(min_length=1)` → 400

## HTTP Status Mapping

| Condition | HTTP Status | Code |
|-----------|-------------|------|
| Success | 200 | - |
| Empty comment | 400 | validation_error |
| Cross-org review | 404 | - |
| Concurrent submission | 409 | conflict |
| Google API failure | 502 | reply_rejected / unreachable / invalid_grant |
| >30 requests/minute | 429 | - |

## AuditLog Event Vocabulary

| Action | When | after_data keys |
|--------|------|-----------------|
| `reply_posted` | Google accepted the reply | google_response_status, reply_update_time |
| `reply_failed` | Any error path | error_code, error_message |

## Lock TTL Choice

30 seconds: reply is a synchronous HTTP call to Google (REQUEST_TIMEOUT=10s). 30s prevents double-post on rapid UI clicks while releasing promptly. A 5-minute TTL (used for sync) would be excessive for a single API call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed consumers.py SIM103 + mypy type errors**
- **Found during:** Task 1 commit (pre-commit hook caught it)
- **Issue:** SIM103 "Return the condition directly" on `_user_can_access_shop`; mypy type errors for `user_id` lookup
- **Fix:** Refactored to explicit if-return pattern with `user_pk: int = user.pk`; split `region_id` to local typed variable
- **Files modified:** apps/reviews/consumers.py
- **Commit:** 0c165d1

## Tests

10 tests in `apps/reviews/tests/test_reply_service.py`:

- `test_submit_reply_success_persists_and_audits` — verifies is_replied=True, reply_comment set, AuditLog reply_posted
- `test_submit_reply_failure_does_not_mutate_review` — verifies is_replied stays False on GoogleReplyError, AuditLog reply_failed
- `test_submit_reply_invalid_grant_marks_shop_expired` — verifies shop.connection_status=EXPIRED
- `test_submit_reply_conflict_when_lock_held` — verifies ReplyConflictError raised
- `test_reply_endpoint_success_returns_updated_review` — 200 + is_replied=True in response
- `test_reply_endpoint_validation_error_on_empty_comment` — 400 on empty comment
- `test_reply_endpoint_502_on_google_failure` — 502 + code="unreachable"
- `test_reply_endpoint_409_when_lock_held` — 409 on concurrent submission
- `test_reply_endpoint_throttle_after_30_per_minute` — 429 after 30 requests
- `test_reply_endpoint_cross_org_returns_404` — cross-org review returns 404

## Self-Check: PASSED

- apps/reviews/exceptions.py: FOUND
- apps/reviews/services/replies.py: FOUND
- apps/reviews/tests/test_reply_service.py: FOUND
- Commit 0c165d1 (Task 1): FOUND
- Commit fb04fd2 (Task 2): FOUND
