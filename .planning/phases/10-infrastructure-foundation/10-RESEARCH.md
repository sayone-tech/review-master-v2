# Phase 10: Infrastructure Foundation - Research

**Researched:** 2026-05-01
**Domain:** Celery 5 + Django Channels 4 + Redis distributed locks + Sentry SDK + ASGI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Local dev container setup**
- Celery `worker` and `beat` are separate Docker services in `docker-compose.yml`, using the same image as `web` with different `command`. Follows the Paperless-ngx pattern.
- Both services start automatically with `make up` (not opt-in).
- Flower is included in `docker-compose.yml` on port 5555 and starts with `make up`. Production deployment never includes Flower (INFRA-03).
- Worker concurrency: `CELERY_WORKER_CONCURRENCY=2` in `docker-compose.yml` (local dev), `8` in production env.
- `worker` depends_on: `db` (healthy) + `redis` (healthy) — prevents first-run failures before migrations complete.

**ASGI transition**
- Local dev keeps `python manage.py runserver` — Django 6 auto-detects `ASGI_APPLICATION` and handles WebSockets natively. Hot reload works unchanged.
- Production / CI uses Daphne: `daphne -b 0.0.0.0 -p 8000 config.asgi:application`.
- `config/asgi.py` becomes fully ASGI: `ProtocolTypeRouter` with HTTP routed to `get_asgi_application()` and WebSocket routed via `URLRouter` → `SyncProgressConsumer`. Both protocols served from a single process/port.

**Sentry integration**
- Full setup in Phase 10: `sentry-sdk` installed, integrated with both Django (web) and Celery (worker).
- `before_send` hook scrubs fields whose key contains any of: `email`, `token`, `key`, `secret`, `password`, `refresh`, `access`.
- Enabled only when `SENTRY_DSN` env var is present. Local dev and tests have no DSN → Sentry silently inactive.

**Beat schedule seeding**
- Phase 10 runs only schema migrations from `django-celery-beat` — no data migrations for Beat tasks.
- Each later phase seeds its own Beat schedule via data migration when the task exists (Phase 11+ for sync/enrichment/retry tasks).

**CI smoke test**
- `CELERY_TASK_ALWAYS_EAGER = True` in `config/settings/test.py` — tasks execute synchronously in the pytest process.
- Smoke test creates a minimal no-op task, enqueues it on `google-sync` and `ai-enrichment`, asserts completion (INFRA-07).

**App skeletons**
- Phase 10 creates empty app skeletons: `apps/reviews`, `apps/action_items`, `apps/notifications` — each with `__init__.py`, `apps.py`, empty `models.py`. No migrations yet; apps registered in `INSTALLED_APPS`.
- This lets `CELERY_TASK_ROUTES` reference real module paths (e.g., `apps.reviews.tasks.*`) without import errors when Phase 11 adds tasks.

### Claude's Discretion
- Exact `Makefile` targets for `make worker`, `make beat`, `make flower` — follow existing patterns.
- `config/celery.py` auto-discovery configuration.
- `apps/common/locks.py` and `apps/common/retry.py` internal implementation, as long as the public interface matches CLAUDE.md §7.6 and §12.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Celery 5.x worker with Redis broker (DB 3) + result backend (DB 4); two named queues (`google-sync`, `ai-enrichment`) | Standard Celery setup verified via official docs; queue routing via `CELERY_TASK_ROUTES` in settings |
| INFRA-02 | Celery Beat single instance with `django-celery-beat` DB-backed schedule; editable at runtime | `CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'`; schema migration from `django-celery-beat` required |
| INFRA-03 | Flower dev/staging only; never production | Add as `docker-compose.yml` service; production deploy templates must omit it |
| INFRA-04 | Worker concurrency configurable via env var; soft limit 5 min, hard limit 10 min | `CELERY_TASK_SOFT_TIME_LIMIT=300`, `CELERY_TASK_TIME_LIMIT=600`; concurrency via `--concurrency` CLI arg or `CELERY_WORKER_CONCURRENCY` env |
| INFRA-05 | Auto-retry with exponential backoff: 3 retries, base 30s, max 10 min | `autoretry_for=(Exception,)`, `retry_backoff=30`, `retry_backoff_max=600`, `retry_jitter=True`, `max_retries=3` on `@shared_task` |
| INFRA-06 | Sentry captures task failures with traceback + task args for web and worker | `sentry_sdk.init()` called in `config/settings/base.py` when `SENTRY_DSN` present; `CeleryIntegration` auto-detected; `before_send` scrubs PII |
| INFRA-07 | CI smoke test enqueues task on each queue, verifies completion in 30 seconds | `CELERY_TASK_ALWAYS_EAGER=True` in test settings; minimal no-op `@shared_task`; assert on result |
| INFRA-08 | Django Channels with Redis channel layer (DB 5); ASGI alongside WSGI | `CHANNEL_LAYERS` pointing at `redis://redis:6379/5`; `ProtocolTypeRouter` in `config/asgi.py`; `daphne` first in `INSTALLED_APPS` |
| INFRA-09 | `SyncProgressConsumer` at `/ws/sync-progress/` accepts authenticated; rejects unauthenticated (4401) + cross-tenant (4403) | `AuthMiddlewareStack` wraps `URLRouter`; consumer checks `scope["user"].is_authenticated` and `organisation_id` match |
| INFRA-10 | Redis distributed lock helper implemented + unit-tested | `redis-py` `Lock` class with `blocking=False`; context manager interface; unit test verifies two concurrent acquisitions |
| INFRA-11 | Retry/backoff decorator implemented; tested with deliberately-failing task that retries 3× then fails permanently | `tenacity` (already installed at 9.1.4); `@retry(stop=stop_after_attempt(3), wait=wait_exponential(...), reraise=True)` |
</phase_requirements>

---

## Summary

Phase 10 wires up the async runtime layer — Celery workers, Beat scheduler, Django Channels WebSocket infrastructure, Redis distributed locks, and retry utilities — without delivering user-facing features. The codebase already has `tenacity==9.1.4` and `django-redis==5.4.0` installed; everything else (celery, django-celery-beat, channels, channels-redis, daphne, sentry-sdk) must be added.

All architectural decisions are locked via CLAUDE.md (§12 Celery, §13 Channels, §7.6 Redis locks, §21 Sentry) and CONTEXT.md. Research confirms these patterns are current and correct for the verified package versions. The primary complexity is the multi-component wiring: five independent subsystems must each be installed, configured, and minimally tested in one phase.

**Primary recommendation:** Install all packages first, then configure in order: Celery → Beat → Channels/ASGI → Sentry → locks/retry utilities → app skeletons → Docker services → tests.

---

## Standard Stack

### Core (must install)
| Library | Verified Version | Purpose | Notes |
|---------|-----------------|---------|-------|
| celery | 5.6.3 | Task queue, worker, Beat | Latest stable as of May 2026; Django 2.2+ supported |
| django-celery-beat | 2.9.0 | DB-backed Beat schedule | Released Feb 2026; adds `django_celery_beat` INSTALLED_APP + schema migration |
| channels | 4.3.2 | WebSocket/ASGI runtime | Released Nov 2025; classifies Django 6.0 support |
| channels-redis | 4.3.0 | Redis channel layer for Channels | Released Jul 2025; requires Python 3.9+ |
| daphne | 4.2.1 | ASGI HTTP/WebSocket server (prod) | Released Jul 2025; must be FIRST in INSTALLED_APPS |
| sentry-sdk | 2.58.0 | Error capture for web + Celery | Latest stable; CeleryIntegration auto-detected |
| flower | 2.0.1 | Celery monitoring UI (dev only) | Last release Aug 2023; stable, no newer version |

### Already installed (no changes needed)
| Library | Current Version | Role in This Phase |
|---------|----------------|-------------------|
| tenacity | 9.1.4 | Powers `apps/common/retry.py` backoff decorator |
| django-redis | 5.4.0 | Powers `apps/common/locks.py` via `redis-py` Lock |
| redis (redis-py) | 7.4.0 (transitive) | `Lock` class for distributed lock helper |

### Installation (production dependencies)
```bash
uv add celery==5.6.3 django-celery-beat==2.9.0 channels==4.3.2 channels-redis==4.3.0 daphne==4.2.1 sentry-sdk==2.58.0
uv add --dev flower==2.0.1
```

**Note:** `flower` is development-only — add to `[dependency-groups]` dev section, or install separately in the worker image with a `--dev` flag. It must never ship to the production image.

**Version verification:** All versions above were confirmed against PyPI JSON API on 2026-05-01. No training-data versions were used.

---

## Architecture Patterns

### Recommended Project Structure Additions
```
config/
├── celery.py           # new — Celery app instance
├── routing.py          # new — Channels URL routing
├── asgi.py             # modify — ProtocolTypeRouter wrapper
├── __init__.py         # modify — import celery_app
└── settings/
    ├── base.py         # modify — CELERY_*, ASGI_APPLICATION, CHANNEL_LAYERS, SENTRY_*
    └── test.py         # modify — CELERY_TASK_ALWAYS_EAGER, in-memory channel layer

apps/
├── common/
│   ├── locks.py        # new — distributed_lock() context manager
│   └── retry.py        # new — with_retry() decorator
├── reviews/            # new skeleton (no migrations)
│   ├── __init__.py
│   ├── apps.py
│   └── models.py
├── action_items/       # new skeleton (no migrations)
│   └── ...
└── notifications/      # new skeleton (no migrations)
    └── ...
```

### Pattern 1: Celery App Initialisation
**What:** Create `config/celery.py` as a standalone module; import it in `config/__init__.py` so Django's startup loads it.
**When to use:** Always — foundational for `@shared_task` decorator to work across all apps.

```python
# config/celery.py
# Source: https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("review_master")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```python
# config/__init__.py
from .celery import app as celery_app

__all__ = ("celery_app",)
```

### Pattern 2: Settings Block for Celery (base.py addition)
**What:** Add all CELERY_* settings to `config/settings/base.py` under existing Redis config.

```python
# config/settings/base.py  — add after CACHES block
# Source: CLAUDE.md §12.2
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379") + "/3"
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://redis:6379") + "/4"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment"},
}
CELERY_TASK_TIME_LIMIT = 600        # 10 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 300   # 5 min soft limit
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
```

```python
# config/settings/test.py  — add to existing file
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

### Pattern 3: Channels ASGI Configuration
**What:** Wrap `config/asgi.py` with `ProtocolTypeRouter`; create `config/routing.py`.
**When to use:** Required for any WebSocket endpoint.

```python
# config/routing.py  — new file
# Source: https://channels.readthedocs.io/en/latest/topics/routing.html
from django.urls import path
from channels.routing import URLRouter

websocket_urlpatterns = [
    path("ws/sync-progress/<uuid:shop_id>/", SyncProgressConsumer.as_asgi()),
]
```

```python
# config/asgi.py  — modify existing
# Source: https://channels.readthedocs.io/en/latest/installation.html
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from config.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

```python
# config/settings/base.py  — add alongside Celery settings
# Source: CLAUDE.md §13.1
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://redis:6379") + "/5"],
            "capacity": 1500,
            "expiry": 30,
        },
    },
}
```

```python
# config/settings/test.py  — override to in-memory layer (no Redis needed)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

**IMPORTANT:** `daphne` must appear FIRST in `INSTALLED_APPS` in `base.py` (before `django.contrib.staticfiles`) to override the `runserver` management command for ASGI. In practice, local dev uses `runserver` which Django 6 also handles natively with `ASGI_APPLICATION` set — Daphne is only required in production.

**INSTALLED_APPS order:** `"daphne"` → `"django.contrib.admin"` → ... → `"django_celery_beat"` → `"apps.reviews"` → `"apps.action_items"` → `"apps.notifications"`.

### Pattern 4: SyncProgressConsumer (full spec from CLAUDE.md §13.3)
**What:** Async JSON WebSocket consumer. Auth + tenant check on connect; push snapshot from Redis; relay group events.
**When to use:** Only consumer in Phase 10.

```python
# apps/reviews/consumers.py  — new file
# Source: CLAUDE.md §13.3
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.reviews.selectors.sync_progress import get_progress_snapshot

class SyncProgressConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        shop_id = self.scope["url_route"]["kwargs"]["shop_id"]
        if not await self._user_can_access_shop(user, shop_id):
            await self.close(code=4403)
            return
        self.group = f"sync-progress-{shop_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        snapshot = await get_progress_snapshot(shop_id=shop_id)
        if snapshot:
            await self.send_json(snapshot)

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def progress_event(self, event):
        await self.send_json(event["payload"])
```

**Note on stub selector:** `apps/reviews/selectors/sync_progress.py` needs a stub `get_progress_snapshot()` returning `None` in Phase 10 (full implementation in Phase 11).

### Pattern 5: Redis Distributed Lock Helper
**What:** Context manager that wraps `redis-py`'s `Lock` class. Non-blocking; exits silently if lock already held.
**Interface contract (from CLAUDE.md §7.6):**

```python
# apps/common/locks.py  — new file
# Source: redis-py docs https://redis.readthedocs.io/en/latest/lock.html
import contextlib
from typing import Generator
import redis
from django.core.cache import caches
from django_redis import get_redis_connection

@contextlib.contextmanager
def distributed_lock(
    key: str,
    timeout: int = 300,
    blocking: bool = False,
) -> Generator[bool, None, None]:
    """Acquire a Redis lock. Non-blocking by default.

    Usage:
        with distributed_lock("lock:google_sync:shop:{shop_id}", timeout=300) as acquired:
            if not acquired:
                return  # another worker holds the lock
            _do_work()
    """
    conn = get_redis_connection("default")
    lock = conn.lock(key, timeout=timeout)
    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass  # TTL expired before we could release; safe to ignore
```

**Key conventions (CLAUDE.md §7.6):**

| Key Pattern | TTL |
|-------------|-----|
| `lock:google_sync:shop:{shop_id}` | 5 min |
| `lock:enrich:review:{review_id}` | 5 min |
| `lock:reply:review:{review_id}` | 30 sec |

### Pattern 6: Tenacity Retry Decorator
**What:** Reusable retry decorator backed by `tenacity`. Matches Celery's `autoretry_for` semantics but usable in service functions independent of Celery.

```python
# apps/common/retry.py  — new file
# Source: https://tenacity.readthedocs.io/en/stable/
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def with_retry(
    *,
    max_attempts: int = 3,
    wait_min: float = 30,
    wait_max: float = 600,
    reraise: bool = True,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator factory for exponential-backoff retry.

    Example:
        @with_retry(max_attempts=3, wait_min=30, wait_max=600)
        def call_external_api() -> dict:
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(retry_on),
        reraise=reraise,
    )
```

### Pattern 7: Sentry Initialisation
**What:** `sentry_sdk.init()` in `base.py`, gated on `SENTRY_DSN`. Scrubs PII via `EventScrubber` + custom `before_send`.

```python
# config/settings/base.py  — add at end of file
# Source: https://docs.sentry.io/platforms/python/guides/django/data-management/sensitive-data/
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST

_SENSITIVE_SUBSTRINGS = {"email", "token", "key", "secret", "password", "refresh", "access"}

def _before_send(event: dict, hint: dict) -> dict | None:  # type: ignore[type-arg]
    """Scrub fields whose key contains any sensitive substring."""
    def _scrub(obj: object) -> object:
        if isinstance(obj, dict):
            return {
                k: "[Filtered]" if any(s in k.lower() for s in _SENSITIVE_SUBSTRINGS) else _scrub(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_scrub(item) for item in obj]
        return obj
    return _scrub(event)  # type: ignore[return-value]

SENTRY_DSN = env("SENTRY_DSN", default=None)
ENVIRONMENT = env("ENVIRONMENT", default="local")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(propagate_traces=True),
        ],
        send_default_pii=False,
        event_scrubber=EventScrubber(
            denylist=DEFAULT_DENYLIST + ["organisation_id"],
            recursive=True,
        ),
        before_send=_before_send,
        traces_sample_rate=0.1,
    )
```

### Pattern 8: Docker Compose Worker/Beat/Flower Services
**What:** Append three services to `docker-compose.yml`. Same image, different `command`. Worker and Beat depend on db+redis being healthy.

```yaml
# docker-compose.yml additions — follow Paperless-ngx pattern
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: sh -c "uv sync --frozen && celery -A config worker -Q google-sync,ai-enrichment,default --concurrency=${CELERY_WORKER_CONCURRENCY:-2} --loglevel=info"
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DJANGO_SECRET_KEY: dev-insecure-secret
      DATABASE_URL: postgres://app:app@db:5432/reviewmaster
      REDIS_URL: redis://redis:6379
      CELERY_WORKER_CONCURRENCY: "2"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app
      - web_venv:/app/.venv

  beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: sh -c "uv sync --frozen && celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info"
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DJANGO_SECRET_KEY: dev-insecure-secret
      DATABASE_URL: postgres://app:app@db:5432/reviewmaster
      REDIS_URL: redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app
      - web_venv:/app/.venv

  flower:
    build:
      context: .
      dockerfile: Dockerfile
    command: sh -c "uv sync --frozen && celery -A config flower --port=5555"
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.local
      DATABASE_URL: postgres://app:app@db:5432/reviewmaster
      REDIS_URL: redis://redis:6379
    depends_on:
      - worker
    ports:
      - "5555:5555"
    volumes:
      - .:/app
      - web_venv:/app/.venv
```

**Note:** `flower` uses the same `web_venv` volume. It is installed in the dev dependency group. The production Dockerfile/Cloud Run deployment templates must never include the `flower` service.

### Pattern 9: App Skeleton Structure
**What:** Minimal Django app — just enough for `INSTALLED_APPS` registration and future `tasks.py` import paths to work.

```python
# apps/reviews/apps.py
from django.apps import AppConfig

class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
```

Same pattern for `apps/action_items` and `apps/notifications`. No models means no migrations in Phase 10.

### Anti-Patterns to Avoid
- **daphne not first in INSTALLED_APPS:** If another app (like `debug_toolbar`) overrides `runserver` before Daphne, WebSocket handling breaks in `runserver` mode. Daphne must be `INSTALLED_APPS[0]`.
- **Multiple Beat instances:** `celery beat` is a single-writer process. Running two Beat containers causes duplicate task dispatch. Enforce `replicas: 1` in Cloud Run templates.
- **Flower in production image:** Flower has no production auth by default. Never include it in the production Docker service set.
- **Business logic in task body:** Celery tasks must be thin wrappers around service functions. All logic goes in `apps/<app>/services/`.
- **`CELERY_TASK_ALWAYS_EAGER` in non-test settings:** This silently bypasses the broker. It must only appear in `test.py`.
- **Forgetting `CELERY_TASK_EAGER_PROPAGATES = True` in tests:** Without this, eager tasks swallow exceptions, making tests pass when they should fail.
- **Channels test missing `InMemoryChannelLayer` override:** Test suites that hit a real Redis channel layer are slow and fragile in CI. Always use the in-memory layer in `test.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Distributed locking | Custom Redis SET NX loops | `redis-py` `Lock` class | Handles TTL, atomic release, LockNotOwnedError edge cases |
| Retry with backoff | Custom sleep/try loop | `tenacity` `@retry` decorator | Handles jitter, max delay, reraise, retry predicates correctly |
| WebSocket auth | Custom handshake validation | `AuthMiddlewareStack` + `scope["user"]` | Reuses Django session auth; handles anonymous users correctly |
| Beat scheduling | File-based schedule | `django-celery-beat` `DatabaseScheduler` | Schedule survives restarts; editable at runtime via admin |
| Sentry PII scrubbing | Custom middleware | `EventScrubber` + `before_send` | Handles nested event structure; covers request body, extra, tags |

**Key insight:** Every "don't hand-roll" item here has subtle correctness requirements (atomic lock release, TTL racing, event nesting). The listed libraries have solved these already.

---

## Common Pitfalls

### Pitfall 1: `import` ordering in `config/asgi.py`
**What goes wrong:** `get_asgi_application()` must be called before any models are imported, or Django raises `AppRegistryNotReady`.
**Why it happens:** ASGI module is imported at worker startup before `django.setup()` completes.
**How to avoid:** Call `get_asgi_application()` first, assign to a local variable, then import routing/consumer modules.
**Warning signs:** `django.core.exceptions.AppRegistryNotReady` at startup.

### Pitfall 2: `daphne` position in INSTALLED_APPS
**What goes wrong:** `python manage.py runserver` serves plain HTTP, not ASGI, so WebSocket connections fail silently.
**Why it happens:** Another app's AppConfig overrides the `runserver` command before Daphne.
**How to avoid:** `"daphne"` must be the first entry in `INSTALLED_APPS`.
**Warning signs:** WebSocket connect never fires consumer code; browser shows HTTP 200 for `/ws/` endpoints.

### Pitfall 3: Channels Redis URL format
**What goes wrong:** `channels-redis` expects a Redis URL string, not a tuple. Passing `("redis://redis:6379", "/5")` fails.
**Why it happens:** The `hosts` config accepts a list of strings, not `(host, db_index)` tuples for URL-style connections.
**How to avoid:** Pass the full URL string with DB index: `"redis://redis:6379/5"`. Alternatively use a list of dicts.
**Warning signs:** `TypeError` or `ConnectionError` when the channel layer tries to connect.

### Pitfall 4: `CELERY_TASK_ROUTES` referencing unimported modules
**What goes wrong:** Celery fails to start if `CELERY_TASK_ROUTES` references a task path in an app that has no `tasks.py` yet.
**Why it happens:** Celery resolves routes at startup by inspecting the task registry. Missing modules cause `ImportError`.
**How to avoid:** Phase 10 creates empty app skeletons (`apps/reviews`, `apps/action_items`, `apps/notifications`) with `models.py` but no `tasks.py`. Use glob patterns in `CELERY_TASK_ROUTES` (e.g., `"apps.reviews.tasks.*"`) — Celery only resolves these when tasks exist.
**Warning signs:** `ImportError: No module named 'apps.reviews.tasks'` at worker startup.

**Resolution:** Use string-prefix routing patterns, not exact task names, in `CELERY_TASK_ROUTES`. These only match when the named tasks exist.

### Pitfall 5: `SyncProgressConsumer` import in `config/routing.py`
**What goes wrong:** `config/routing.py` imports `SyncProgressConsumer` from `apps/reviews/consumers.py`, which imports `get_progress_snapshot` from `apps/reviews/selectors/sync_progress.py`. If that selector doesn't exist, ASGI fails at startup.
**Why it happens:** Python resolves all imports at module load time.
**How to avoid:** Create a stub `apps/reviews/selectors/sync_progress.py` with `get_progress_snapshot()` returning `None` in Phase 10.
**Warning signs:** `ImportError` or `ModuleNotFoundError` during ASGI startup.

### Pitfall 6: Beat and Web sharing the same `worker_venv` volume
**What goes wrong:** Beat starts before `uv sync` completes on the web service, causing import errors.
**Why it happens:** Beat has its own `uv sync --frozen` call, but if the `.venv` volume is partially written by another service, it may start with a stale environment.
**How to avoid:** Give worker, beat, and flower their own named volumes (or ensure each runs `uv sync --frozen` independently). The `depends_on: db: condition: service_healthy` covers the DB; there's no compose-level "venv ready" signal.
**Warning signs:** `ModuleNotFoundError: No module named 'celery'` in the beat container on first `docker-compose up`.

### Pitfall 7: Sentry initialisation in `base.py` vs `settings.py`
**What goes wrong:** If `sentry_sdk.init()` is called at module import time with imports inside functions, `CeleryIntegration` may not hook into the worker correctly.
**Why it happens:** Celery workers load their task modules independently of the Django web process; the integration must be active when the worker starts.
**How to avoid:** Call `sentry_sdk.init()` at the top level of `base.py` (not inside a function), so it runs during `django.setup()` in both web and worker processes.
**Warning signs:** Sentry receives web exceptions but not Celery task exceptions.

---

## Code Examples

### Celery Smoke Test Task
```python
# apps/common/tasks.py  — new file (smoke test task only)
# Source: CLAUDE.md §12.8
from celery import shared_task

@shared_task(bind=True)
def smoke_test_task(self, message: str = "ok") -> str:
    return message
```

```python
# apps/common/tests/test_celery_smoke.py
import pytest
from apps.common.tasks import smoke_test_task

@pytest.mark.django_db
def test_smoke_task_google_sync_queue():
    result = smoke_test_task.apply_async(args=["ping"], queue="google-sync")
    assert result.get(timeout=30) == "ping"

@pytest.mark.django_db
def test_smoke_task_ai_enrichment_queue():
    result = smoke_test_task.apply_async(args=["ping"], queue="ai-enrichment")
    assert result.get(timeout=30) == "ping"
```

### Distributed Lock Unit Test
```python
# apps/common/tests/test_locks.py
import pytest
from unittest.mock import patch, MagicMock
from apps.common.locks import distributed_lock

def test_lock_acquired_when_free():
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with patch("apps.common.locks.get_redis_connection", return_value=mock_conn):
        with distributed_lock("test:lock:key") as acquired:
            assert acquired is True
    mock_lock.release.assert_called_once()

def test_lock_not_acquired_when_held():
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = False
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with patch("apps.common.locks.get_redis_connection", return_value=mock_conn):
        with distributed_lock("test:lock:key") as acquired:
            assert acquired is False
    mock_lock.release.assert_not_called()
```

### Channels Consumer Test (inject user into scope)
```python
# apps/reviews/tests/test_consumers.py
import pytest
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser
from config.asgi import application

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_unauthenticated_connection_rejected():
    communicator = WebsocketCommunicator(application, "/ws/sync-progress/some-shop-id/")
    communicator.scope["user"] = AnonymousUser()
    connected, code = await communicator.connect()
    assert not connected
    assert code == 4401

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_authenticated_connection_accepted(user_factory):
    user = await user_factory()  # async factory
    shop_id = "00000000-0000-0000-0000-000000000001"
    communicator = WebsocketCommunicator(
        application,
        f"/ws/sync-progress/{shop_id}/"
    )
    communicator.scope["user"] = user
    # Patch _user_can_access_shop to return True for the test user
    # ...
    connected, _ = await communicator.connect()
    await communicator.disconnect()
```

### Retry Decorator Test
```python
# apps/common/tests/test_retry.py
import pytest
from apps.common.retry import with_retry

def test_retry_exhaustion_raises():
    call_count = 0

    @with_retry(max_attempts=3, wait_min=0.01, wait_max=0.01)
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise ValueError("deliberate failure")

    with pytest.raises(ValueError, match="deliberate failure"):
        always_fails()

    assert call_count == 3
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CELERY_ALWAYS_EAGER` | `CELERY_TASK_ALWAYS_EAGER` (UPPERCASE-prefixed) | Celery 4.0 | Must use the uppercase prefix form when `config_from_object(..., namespace='CELERY')` |
| File-based Beat schedule | `django-celery-beat` DB scheduler | Celery 4.0 | Schedules persist across deploys; editable at runtime |
| Gunicorn WSGI only | Daphne ASGI (HTTP + WebSocket) | Channels 4.0 | Single port, single process handles both protocols |
| Custom lock scripts | `redis-py` `Lock` class | redis-py 3.x | Atomic Lua scripts; handles edge cases correctly |
| `channels[daphne]` install extra | `daphne` as separate dep, first in INSTALLED_APPS | Channels 4.0 | Allows explicit control of app order |

**Deprecated/outdated:**
- `CELERY_ALWAYS_EAGER` (no underscore prefix) — will silently not apply with `namespace='CELERY'`. Use `CELERY_TASK_ALWAYS_EAGER`.
- `ASGI_APPLICATION` pointing directly to consumer — must point to `ProtocolTypeRouter` wrapper.
- Flower on pypi as `flower` package — still current (v2.0.1, Aug 2023). No newer release, but it works correctly with Celery 5.

---

## Open Questions

1. **`web_venv` volume sharing between web/worker/beat**
   - What we know: All three services mount the same `.:/app` and `web_venv:/app/.venv` volumes. Each runs `uv sync --frozen` independently.
   - What's unclear: If `worker` starts before `web` finishes `uv sync`, the `.venv` may be incomplete.
   - Recommendation: Each service should use its own named `venv` volume OR the compose startup order should ensure `web` installs first. Alternatively, bake dependencies into the Docker image (not rely on volume-based install). This is a dev-only concern; production uses baked images.

2. **`pytest-asyncio` mode configuration for Channels tests**
   - What we know: `pytest-asyncio==1.1.0` defaults to `strict` mode, requiring `@pytest.mark.asyncio` on every async test. The existing `pyproject.toml` doesn't set `asyncio_mode`.
   - What's unclear: Whether `asyncio_mode = "auto"` should be set globally or kept strict.
   - Recommendation: Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` — it's less boilerplate and the Channels docs examples assume it. Strict mode works too but requires explicit marking on every consumer test.

3. **`AllowedHostsOriginValidator` and `ALLOWED_HOSTS = ["*"]` in `local.py`**
   - What we know: `local.py` sets `ALLOWED_HOSTS = ["*"]`. `AllowedHostsOriginValidator` validates WebSocket origin against `ALLOWED_HOSTS`.
   - What's unclear: With `["*"]`, all origins are allowed in dev, which is correct. In production, `ALLOWED_HOSTS` will be explicit.
   - Recommendation: This is fine as-is. No change needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/common/tests/test_celery_smoke.py apps/common/tests/test_locks.py apps/common/tests/test_retry.py -x -q` |
| Full suite command | `pytest apps/ -x -q` |

**Additional required dev dependency:** `pytest-asyncio==1.1.0` for Channels consumer tests.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Celery worker starts; tasks route to correct queues | smoke | `pytest apps/common/tests/test_celery_smoke.py -x -q` | Wave 0 |
| INFRA-02 | Beat scheduler runs with DB backend; tables exist | smoke/integration | `pytest apps/common/tests/test_beat_schema.py -x -q` | Wave 0 |
| INFRA-03 | Flower not in production deploy | manual | Review Dockerfile/Cloud Run config | manual-only |
| INFRA-04 | Time limits set; concurrency env var respected | unit | `pytest apps/common/tests/test_celery_config.py -x -q` | Wave 0 |
| INFRA-05 | Task retries 3× with backoff then fails permanently | unit | `pytest apps/common/tests/test_retry.py -x -q` | Wave 0 |
| INFRA-06 | Sentry captures task failure with traceback | unit (mock Sentry) | `pytest apps/common/tests/test_sentry_integration.py -x -q` | Wave 0 |
| INFRA-07 | CI smoke test enqueues task on each queue; completes in 30s | smoke | `pytest apps/common/tests/test_celery_smoke.py -x -q` | Wave 0 |
| INFRA-08 | Channels configured; ASGI app wraps ProtocolTypeRouter | unit | `pytest apps/reviews/tests/test_asgi.py -x -q` | Wave 0 |
| INFRA-09 | WebSocket accepts authenticated; rejects unauth (4401) + cross-tenant (4403) | integration | `pytest apps/reviews/tests/test_consumers.py -x -q` | Wave 0 |
| INFRA-10 | Lock prevents double acquisition; releases on exit | unit | `pytest apps/common/tests/test_locks.py -x -q` | Wave 0 |
| INFRA-11 | Retry decorator: 3 attempts, correct wait, reraise on exhaustion | unit | `pytest apps/common/tests/test_retry.py -x -q` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/common/tests/ apps/reviews/tests/test_consumers.py -x -q`
- **Per wave merge:** `pytest apps/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (test files that must be created)
- [ ] `apps/common/tasks.py` — smoke test task (`smoke_test_task`)
- [ ] `apps/common/tests/test_celery_smoke.py` — INFRA-01, INFRA-07
- [ ] `apps/common/tests/test_beat_schema.py` — INFRA-02 (assert `django_celery_beat` migration tables exist)
- [ ] `apps/common/tests/test_celery_config.py` — INFRA-04 (assert time limit and queue settings)
- [ ] `apps/common/tests/test_locks.py` — INFRA-10
- [ ] `apps/common/tests/test_retry.py` — INFRA-05, INFRA-11
- [ ] `apps/common/tests/test_sentry_integration.py` — INFRA-06 (mock Sentry capture)
- [ ] `apps/reviews/tests/test_consumers.py` — INFRA-09 (WebsocketCommunicator)
- [ ] `apps/reviews/tests/test_asgi.py` — INFRA-08 (ProtocolTypeRouter assertion)
- [ ] `apps/reviews/selectors/sync_progress.py` — stub needed before consumer imports work
- [ ] Framework install: `uv add --dev pytest-asyncio==1.1.0` — for async consumer tests
- [ ] `pyproject.toml` `asyncio_mode = "auto"` in `[tool.pytest.ini_options]`

---

## Sources

### Primary (HIGH confidence)
- [Celery 5.6.3 Django docs](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html) — `config/celery.py` + `__init__.py` pattern
- [Celery 5.6.3 testing docs](https://docs.celeryq.dev/en/stable/userguide/testing.html) — `CELERY_TASK_ALWAYS_EAGER`, pytest fixtures
- [Channels 4.3.2 installation](https://channels.readthedocs.io/en/latest/installation.html) — INSTALLED_APPS + daphne order
- [Channels 4.3.2 routing](https://channels.readthedocs.io/en/latest/topics/routing.html) — ProtocolTypeRouter + URLRouter patterns
- [Channels 4.3.2 auth](https://channels.readthedocs.io/en/latest/topics/authentication.html) — AuthMiddlewareStack, scope["user"]
- [Channels 4.3.2 testing](https://channels.readthedocs.io/en/stable/topics/testing.html) — WebsocketCommunicator, scope injection
- [channels_redis README](https://github.com/django/channels_redis/blob/main/README.rst) — configuration options (capacity, expiry, host URL format)
- [redis-py Lock docs](https://redis.readthedocs.io/en/latest/lock.html) — Lock constructor, blocking=False, context manager
- [Tenacity docs](https://tenacity.readthedocs.io/en/stable/) — stop_after_attempt, wait_exponential, reraise
- [Sentry Django sensitive data](https://docs.sentry.io/platforms/python/guides/django/data-management/sensitive-data/) — EventScrubber, before_send, DEFAULT_DENYLIST
- [Sentry Celery integration](https://docs.sentry.io/platforms/python/integrations/celery/) — CeleryIntegration, propagate_traces
- PyPI JSON API (2026-05-01) — all package versions verified directly

### Secondary (MEDIUM confidence)
- PyPI celery==5.6.3 release page — confirmed latest stable, Django 2.2+ support policy
- PyPI channels==4.3.2 release page — confirmed Django 6.0 classifier
- PyPI channels-redis==4.3.0 — Python 3.9+ requirement confirmed
- PyPI daphne==4.2.1 — latest stable confirmed
- PyPI sentry-sdk==2.58.0 — latest stable confirmed
- PyPI django-celery-beat==2.9.0 — latest stable confirmed
- PyPI flower==2.0.1 — latest stable (Aug 2023; no newer release)
- PyPI pytest-asyncio==1.1.0 — latest stable confirmed

### Tertiary (LOW confidence, flagged)
- Community pattern for `WebsocketCommunicator` user scope injection (`communicator.scope["user"] = user`) — confirmed by GitHub issues #1107 and #903, not in official docs. Pattern is universally accepted by community but not formally documented.

---

## Metadata

**Confidence breakdown:**
- Standard stack (versions): HIGH — all versions verified against PyPI JSON API on research date
- Architecture patterns: HIGH — verified against official Celery and Channels 4.x docs
- Pitfalls: HIGH — verified against official docs; pitfall 6 (venv volume sharing) is MEDIUM (observed pattern, no official doc)
- Test patterns: MEDIUM — `WebsocketCommunicator` scope injection verified via multiple community sources; official docs lack an example

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (30 days for stable infra libraries; channels-redis and daphne move slowly)
