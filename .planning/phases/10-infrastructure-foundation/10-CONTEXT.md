# Phase 10: Infrastructure Foundation - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up the async runtime so every subsequent phase can use it: Celery workers (two queues), Celery Beat scheduler, Django Channels WebSocket layer, Redis distributed lock helper, and retry/backoff utilities. Also creates empty app skeletons for `reviews`, `action_items`, and `notifications` so task routing can reference real module paths. No user-facing features land in this phase — everything here is infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Local dev container setup
- Celery `worker` and `beat` are separate Docker services in `docker-compose.yml`, using the same image as `web` with different `command`. Follows the Paperless-ngx pattern.
- Both services start automatically with `make up` (not opt-in).
- Flower is included in `docker-compose.yml` on port 5555 and starts with `make up`. Production deployment never includes Flower (INFRA-03).
- Worker concurrency: `CELERY_WORKER_CONCURRENCY=2` in `docker-compose.yml` (local dev), `8` in production env.
- `worker` depends_on: `db` (healthy) + `redis` (healthy) — prevents first-run failures before migrations complete.

### ASGI transition
- Local dev keeps `python manage.py runserver` — Django 6 auto-detects `ASGI_APPLICATION` and handles WebSockets natively. Hot reload works unchanged.
- Production / CI uses Daphne: `daphne -b 0.0.0.0 -p 8000 config.asgi:application`.
- `config/asgi.py` becomes fully ASGI: `ProtocolTypeRouter` with HTTP routed to `get_asgi_application()` and WebSocket routed via `URLRouter` → `SyncProgressConsumer`. Both protocols served from a single process/port.

### Sentry integration
- Full setup in Phase 10: `sentry-sdk` installed, integrated with both Django (web) and Celery (worker).
- `before_send` hook scrubs fields whose key contains any of: `email`, `token`, `key`, `secret`, `password`, `refresh`, `access`.
- Enabled only when `SENTRY_DSN` env var is present. Local dev and tests have no DSN → Sentry silently inactive.

### Beat schedule seeding
- Phase 10 runs only schema migrations from `django-celery-beat` — no data migrations for Beat tasks.
- Each later phase seeds its own Beat schedule via data migration when the task exists (Phase 11+ for sync/enrichment/retry tasks).

### CI smoke test
- `CELERY_TASK_ALWAYS_EAGER = True` in `config/settings/test.py` — tasks execute synchronously in the pytest process.
- Smoke test creates a minimal no-op task, enqueues it on `google-sync` and `ai-enrichment`, asserts completion (INFRA-07).

### App skeletons
- Phase 10 creates empty app skeletons: `apps/reviews`, `apps/action_items`, `apps/notifications` — each with `__init__.py`, `apps.py`, empty `models.py`. No migrations yet; apps registered in `INSTALLED_APPS`.
- This lets `CELERY_TASK_ROUTES` reference real module paths (e.g., `apps.reviews.tasks.*`) without import errors when Phase 11 adds tasks.

### Claude's Discretion
- Exact `Makefile` targets for `make worker`, `make beat`, `make flower` — follow existing patterns.
- `config/celery.py` auto-discovery configuration.
- `apps/common/locks.py` and `apps/common/retry.py` internal implementation, as long as the public interface matches CLAUDE.md §7.6 and §12.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Celery configuration
- `CLAUDE.md` §12 — Full Celery architecture: queues, broker/result DBs, task conventions, idempotency layers, Beat schedule list, deployment rules, testing approach
- `CLAUDE.md` §12.2 — Exact `CELERY_*` settings to add to `config/settings/base.py`
- `CLAUDE.md` §12.3 — Task decorator conventions (`bind=True`, `autoretry_for`, `retry_backoff`, etc.)
- `CLAUDE.md` §12.8 — Celery test settings (`CELERY_TASK_ALWAYS_EAGER`)

### Django Channels / ASGI
- `CLAUDE.md` §13 — Channels architecture, `SyncProgressConsumer` spec, authorisation rules (4401/4403), event payload schema
- `CLAUDE.md` §13.1 — `ASGI_APPLICATION`, `CHANNEL_LAYERS` settings to add
- `CLAUDE.md` §13.2 — Scope discipline: only `SyncProgressConsumer` in Phase 3; no other consumers
- `CLAUDE.md` §13.3 — Full `SyncProgressConsumer` code reference

### Redis distributed lock
- `CLAUDE.md` §7.6 — `distributed_lock` helper interface, lock key conventions, TTLs, non-blocking acquisition policy

### Sentry / observability
- `CLAUDE.md` §21 — Structured JSON logging, Sentry integration, PII scrubbing rules, metrics for Phase 3+

### Docker / deployment
- `CLAUDE.md` §20 — Single image, multiple entry commands; `web`, `worker`, `beat` service split; Flower never in production

### Requirements
- `.planning/REQUIREMENTS.md` INFRA-01 through INFRA-11 — All Phase 10 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/common/models.py` — `TimeStampedModel`, `UUIDModel` base models; new `locks.py` and `retry.py` go alongside
- `pyproject.toml` — `tenacity==9.1.4` already installed; use it for `apps/common/retry.py` backoff decorator
- `config/settings/base.py` — Redis `CACHES` already uses DB 0 (cache) and DB 1 (throttle); Celery adds DB 3/4, Channels adds DB 5
- `config/asgi.py` — exists with plain `get_asgi_application()`; needs `ProtocolTypeRouter` wrapper added

### Established Patterns
- Settings split: `base.py` / `local.py` / `production.py` / `test.py` — add Celery/Channels settings to `base.py`, overrides in environment-specific files
- `docker-compose.yml` uses `depends_on` with `condition: service_healthy` — follow the same pattern for `worker` and `beat`
- `apps/common/services/` already exists — `locks.py` and `retry.py` go in `apps/common/` (not in a sub-package)

### Integration Points
- `config/celery.py` (new) — Celery app instance, `autodiscover_tasks(["apps"])`, imported in `config/__init__.py`
- `config/asgi.py` (modify) — wrap with `ProtocolTypeRouter`; add `config/routing.py` for WebSocket URL patterns
- `config/settings/base.py` (modify) — add `CELERY_*` settings, `ASGI_APPLICATION`, `CHANNEL_LAYERS`
- `config/settings/test.py` (modify) — add `CELERY_TASK_ALWAYS_EAGER = True`
- `docker-compose.yml` (modify) — add `worker`, `beat`, `flower` services

</code_context>

<specifics>
## Specific Ideas

- Worker/Beat service pattern should follow Paperless-ngx: same image, different `command`, all in `docker-compose.yml`, starts automatically with `make up`.
- No separate `docker-compose.override.yml` changes needed for the new services — they belong in the main compose file.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-infrastructure-foundation*
*Context gathered: 2026-05-01*
