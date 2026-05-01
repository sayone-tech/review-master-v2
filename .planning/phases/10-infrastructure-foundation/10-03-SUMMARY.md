---
phase: 10
plan: "03"
subsystem: channels-asgi
tags: [channels, websocket, asgi, daphne, celery, infrastructure]
dependency_graph:
  requires: [10-01]
  provides: [channels-asgi-layer, sync-progress-consumer, websocket-routing]
  affects: [config/asgi.py, config/routing.py, apps/reviews/consumers.py]
tech_stack:
  added: [channels==4.3.2, channels-redis==4.3.0, daphne==4.2.1]
  patterns: [ProtocolTypeRouter, AsyncJsonWebsocketConsumer, database_sync_to_async, InMemoryChannelLayer-in-tests]
key_files:
  created:
    - config/routing.py
    - apps/reviews/consumers.py
    - apps/reviews/selectors/__init__.py
    - apps/reviews/selectors/sync_progress.py
    - apps/reviews/tests/__init__.py
    - apps/reviews/tests/test_asgi.py
    - apps/reviews/tests/test_consumers.py
    - apps/reviews/__init__.py
    - apps/reviews/apps.py
    - apps/reviews/models.py
    - apps/action_items/__init__.py
    - apps/action_items/apps.py
    - apps/action_items/models.py
    - apps/notifications/__init__.py
    - apps/notifications/apps.py
    - apps/notifications/models.py
  modified:
    - config/asgi.py
    - config/settings/base.py
    - config/settings/test.py
    - pyproject.toml
    - uv.lock
decisions:
  - "Shop uses integer PK (not UUID) — routing uses <int:shop_id> instead of <uuid:shop_id> as the plan specified"
  - "AsyncJsonWebsocketConsumer and database_sync_to_async get type: ignore[misc] — channels has no mypy stubs (same pattern as celery tasks in Plan 10-01)"
  - "SyncProgressConsumer._user_can_access_shop uses org-level scoping in Phase 10; Phase 11 tightens to staff-scope"
metrics:
  duration: "~35 minutes (continuation agent; previous agent timed out on mypy pre-commit)"
  completed_date: "2026-05-01"
  tasks_completed: 3
  files_created: 16
  files_modified: 4
  tests_added: 9
---

# Phase 10 Plan 03: Channels ASGI Infrastructure Summary

Django Channels 4 + Daphne + channels-redis wired up with ProtocolTypeRouter, a single narrowly-scoped SyncProgressConsumer, and full auth/tenant rejection test coverage (4401/4403).

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Install Channels deps + create three app skeletons | 012697b | pyproject.toml, uv.lock, apps/reviews/, apps/action_items/, apps/notifications/, settings |
| 2 | Configure Channels ASGI, routing, channel layers, selector stub | 6d5ee1f | config/asgi.py, config/routing.py, settings/base.py, settings/test.py, pyproject.toml, selectors, test_asgi.py |
| 3 | SyncProgressConsumer tests (INFRA-09) | 8a83599 | apps/reviews/tests/test_consumers.py |

## What Was Built

- `config/asgi.py` rewritten as `ProtocolTypeRouter` with HTTP and WebSocket handlers wrapped in `AllowedHostsOriginValidator` + `AuthMiddlewareStack`
- `config/routing.py` maps `/ws/sync-progress/<int:shop_id>/` to `SyncProgressConsumer.as_asgi()`
- `apps/reviews/consumers.py` — `SyncProgressConsumer` per CLAUDE.md §13.3 verbatim; adds `_user_can_access_shop` (org-level tenant scoping via `database_sync_to_async`)
- `apps/reviews/selectors/sync_progress.py` — `get_progress_snapshot` stub always returning `None` (Phase 11 implements Redis read)
- `config/settings/base.py` — `ASGI_APPLICATION` + `CHANNEL_LAYERS` (RedisChannelLayer on DB 5)
- `config/settings/test.py` — `CHANNEL_LAYERS` override with `InMemoryChannelLayer` (no Redis in CI)
- `pyproject.toml` — `asyncio_mode = "auto"` so no `@pytest.mark.asyncio` boilerplate needed
- 9 tests total: 4 ASGI structural tests + 5 consumer auth/relay tests, all passing

## Success Criteria Verification

- [x] `config.asgi.application` is a `ProtocolTypeRouter` with both `http` and `websocket` keys
- [x] WebSocket to `/ws/sync-progress/<id>/` with anonymous user rejected with code 4401
- [x] WebSocket to `/ws/sync-progress/<id>/` with different-organisation user rejected with code 4403
- [x] WebSocket with matching authenticated user accepted (connected=True)
- [x] Channel layer is `RedisChannelLayer` in production; `InMemoryChannelLayer` in tests
- [x] `apps.reviews`, `apps.action_items`, `apps.notifications` registered in `INSTALLED_APPS`
- [x] `python manage.py makemigrations --check --dry-run` exits 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Routing path uses `<int:shop_id>` instead of `<uuid:shop_id>`**
- **Found during:** Task 3 test authoring
- **Issue:** The plan specified `path("ws/sync-progress/<uuid:shop_id>/", ...)` but `apps.shops.models.Shop` inherits from `TimeStampedModel` (integer BigAutoField PK), not `UUIDModel`. Using `<uuid:>` path converter would never match.
- **Fix:** Changed `config/routing.py` to `path("ws/sync-progress/<int:shop_id>/", ...)` and adjusted test factory calls to use `shop.pk` (integer) rather than `str(uuid.uuid4())`.
- **Files modified:** config/routing.py, apps/reviews/tests/test_consumers.py
- **Commit:** 6d5ee1f, 8a83599

**2. [Rule 1 - Bug] Mypy `type: ignore[misc]` on channels class and decorator**
- **Found during:** Task 2 commit (pre-commit mypy hook)
- **Issue:** `AsyncJsonWebsocketConsumer` is typed as `Any` in channels stubs; `database_sync_to_async` decorator similarly untyped. Two `error: [misc]` mypy failures blocked commit.
- **Fix:** Added `# type: ignore[misc]` to `class SyncProgressConsumer(AsyncJsonWebsocketConsumer)` and `@database_sync_to_async` — consistent with the project's existing pattern for celery decorators (State.md decision from Plan 10-01).
- **Files modified:** apps/reviews/consumers.py
- **Commit:** 6d5ee1f

## Self-Check: PASSED

All key files verified present on disk. All three task commits (012697b, 6d5ee1f, 8a83599) verified in git history.
