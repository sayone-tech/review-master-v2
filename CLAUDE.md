# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

---

## 1. Project Overview

This is a **multi-tenant SaaS platform** for managing organisations, their stores, and Google Business Profile reviews. It supports three user roles: **Superadmin**, **Organisation Admin**, and **Staff Admin**.

- **Backend:** Django 6.0+ with Django REST Framework (DRF)
- **Frontend:** Django templates + Tailwind CSS, with React components embedded for complex interactive views (data tables, modals, dashboards)
- **Database:** PostgreSQL
- **Cache / Rate Limiting / Queue backing / Channels layer:** Redis
- **Background jobs (Phase 1 & 2):** Django management commands + GCP Cloud Scheduler
- **Background jobs (Phase 3+):** Celery + Celery Beat with named queues `google-sync`, `ai-enrichment-high`, `ai-enrichment-low`, `tag-merge`, `default` (the AI queue was split high/low and a `tag-merge` queue added in v0.8 — see §29)
- **Real-time UI updates (Phase 3+):** Django Channels (ASGI) — scoped narrowly to initial sync progress only
- **External APIs:**
  - Google Business Profile API (OAuth 2.0, per-store connection)
  - OpenAI Chat Completions API (GPT-4o-mini for review enrichment)
  - LangSmith (tracing of AI calls)
- **Transactional email:** Amazon SES via `django-ses` backend
- **Hosting:** Google Cloud (Cloud Run / GKE), Docker + docker-compose for local dev
- **CI/CD:** GitHub Actions
- **Monitoring:** Sentry (errors), Better Stack / Datadog (logs + uptime)

---

## 2. Python & Django Versions

- **Python:** 3.12+ (required by Django 6)
- **Django:** 6.0.x (latest stable)
- **DRF:** Latest compatible with Django 6

Always pin exact versions in `pyproject.toml`. Do **not** use `>=` for production dependencies.

---

## 3. File & Folder Structure

Use a **domain-driven, app-per-bounded-context** layout. Keep apps small and focused.

```
repo-root/
├── CLAUDE.md                        # this file
├── README.md
├── pyproject.toml                   # single source of truth for deps + tool config
├── uv.lock                          # dependency lockfile (uv preferred) OR poetry.lock
├── .pre-commit-config.yaml
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml      # local-only overrides
├── Makefile                         # common dev commands
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # lint, type-check, test on PR
│       └── deploy.yml               # deploy on merge to main
│
├── config/                          # Django project package (NOT "myproject")
│   ├── __init__.py
│   ├── asgi.py                      # Channels-aware ASGI app (Phase 3+)
│   ├── wsgi.py
│   ├── urls.py
│   ├── routing.py                   # Channels URL routing (Phase 3+)
│   ├── celery.py                    # Celery app instance (Phase 3+)
│   └── settings/
│       ├── __init__.py
│       ├── base.py                  # shared settings
│       ├── local.py                 # DEBUG=True, local DB
│       ├── production.py            # GCP, Sentry, secure cookies
│       └── test.py                  # fast SQLite or postgres-test, disabled migrations
│
├── apps/                            # ALL Django apps live here
│   ├── __init__.py
│   │
│   ├── accounts/                    # custom User model, auth, invitations
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── managers.py
│   │   ├── admin.py
│   │   ├── permissions.py           # RBAC: IsSuperadmin, IsOrgAdmin, IsStaffAdmin
│   │   ├── serializers.py
│   │   ├── views.py                 # DRF viewsets + template views
│   │   ├── urls.py
│   │   ├── services/                # business logic (see §5)
│   │   │   ├── __init__.py
│   │   │   └── invitations.py
│   │   ├── selectors/               # read-only query functions (see §5)
│   │   │   ├── __init__.py
│   │   │   └── users.py
│   │   ├── tasks.py                 # Celery tasks (Phase 3+)
│   │   ├── signals.py
│   │   ├── migrations/
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── factories.py
│   │       ├── test_models.py
│   │       ├── test_services.py
│   │       ├── test_selectors.py
│   │       └── test_views.py
│   │
│   ├── organisations/               # Organisation model, superadmin mgmt
│   ├── stores/                      # Store model, per-org, Google Place linkage
│   ├── reviews/                     # Reviews, replies, sync logic, enrichment orchestration
│   │   ├── consumers.py             # Channels consumers (Phase 3+)
│   │   ├── tasks.py                 # Celery tasks: sync, enrich, retry
│   │   ├── services/
│   │   │   ├── sync.py              # Google review fetching
│   │   │   ├── replies.py           # Reply submission and Google posting
│   │   │   └── enrichment.py        # OpenAI enrichment orchestration
│   │   └── selectors/
│   │       └── reviews.py
│   ├── action_items/                # Action items extracted from reviews + manual creation
│   │   ├── services/
│   │   │   ├── lifecycle.py         # Create, status transitions, assignment, notes
│   │   │   └── extraction.py        # Convert GPT JSON → ActionItem rows
│   │   └── selectors/items.py
│   ├── notifications/               # In-app bell counter + delivery model (Phase 3+)
│   │   └── services/dispatch.py
│   ├── integrations/                # External API clients
│   │   ├── google/
│   │   │   ├── client.py
│   │   │   ├── oauth.py
│   │   │   └── exceptions.py
│   │   └── openai/                  # Phase 3+
│   │       ├── client.py            # OpenAI SDK wrapper with LangSmith tracing
│   │       ├── prompts.py           # Versioned prompt templates
│   │       ├── parser.py            # Structured-JSON response parser
│   │       ├── pricing.py           # Cost calculator
│   │       └── tracing.py           # LangSmith integration
│   └── common/                      # shared utilities, base models, mixins
│       ├── models.py                # TimeStampedModel, UUIDModel
│       ├── pagination.py
│       ├── exceptions.py
│       ├── locks.py                 # Redis distributed-lock helper (Phase 3+)
│       ├── retry.py                 # Retry/backoff decorator (Phase 3+)
│       └── throttling.py
│
├── templates/                       # project-level templates (base.html, emails)
│   ├── base.html
│   ├── partials/
│   └── emails/
│
├── static/                          # source static files
│   ├── css/
│   └── js/
│
├── frontend/                        # React source for complex components
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── entrypoints/             # one per embedded widget
│   └── tsconfig.json
│
├── scripts/                         # one-off scripts, data migrations
└── docs/                            # architecture notes, ADRs, runbooks
```

### Rules
- **Never** put apps at the repo root. Always under `apps/`.
- **Never** name the project package after the product. Use `config/`.
- One app = one bounded context. If an app has more than ~8 models, split it.
- `common/` is for truly shared code. Do not use it as a dumping ground.

---

## 4. Settings Structure

Split `settings.py` into a package:

- `base.py` — everything shared
- `local.py` — imports from base, overrides for dev
- `production.py` — imports from base, secure, reads from env
- `test.py` — fast, deterministic

Use `DJANGO_SETTINGS_MODULE=config.settings.local` (etc.) via env var. Never check secrets into git. Use `django-environ` or `pydantic-settings` to read `.env`.

---

## 5. Code Architecture — Services & Selectors Pattern

Views should be **thin**. Business logic lives in two types of modules:

### Services (`services/`)
Write-side logic. Functions that **change state**. Each function does one thing.

```python
# apps/organisations/services/organisations.py
from django.db import transaction
from apps.organisations.models import Organisation
from apps.accounts.services.invitations import send_org_admin_invitation

@transaction.atomic
def create_organisation(*, name: str, org_type: str, email: str,
                        address: str, number_of_stores: int,
                        created_by) -> Organisation:
    org = Organisation.objects.create(
        name=name,
        org_type=org_type,
        email=email,
        address=address,
        number_of_stores=number_of_stores,
        created_by=created_by,
    )
    send_org_admin_invitation(organisation=org)
    return org
```

### Selectors (`selectors/`)
Read-side logic. Functions that **return data**. No mutations.

```python
# apps/organisations/selectors/organisations.py
from apps.organisations.models import Organisation

def list_organisations_for_superadmin(*, search: str = "",
                                       status: str | None = None,
                                       org_type: str | None = None):
    qs = (
        Organisation.objects
        .select_related("created_by")
        .prefetch_related("stores")
        .annotate_store_counts()   # custom manager method
    )
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))
    if status:
        qs = qs.filter(status=status)
    if org_type:
        qs = qs.filter(org_type=org_type)
    return qs.order_by("-created_at")
```

### Views call services/selectors. That's it.

```python
# apps/organisations/views.py
class OrganisationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSuperadmin]
    serializer_class = OrganisationSerializer

    def get_queryset(self):
        return list_organisations_for_superadmin(
            search=self.request.query_params.get("search", ""),
            status=self.request.query_params.get("status"),
            org_type=self.request.query_params.get("type"),
        )

    def perform_create(self, serializer):
        create_organisation(**serializer.validated_data,
                            created_by=self.request.user)
```

### Same pattern for Celery tasks (Phase 3+)

Celery tasks are **thin wrappers** — they call service functions. Business logic stays in services so it can be tested without the worker:

```python
# apps/reviews/tasks.py
from celery import shared_task
from apps.reviews.services.enrichment import enrich_review

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,),
             retry_backoff=30, retry_backoff_max=600, retry_jitter=True)
def enrich_review_task(self, review_id: str) -> None:
    enrich_review(review_id=review_id)
```

### Never
- Put business logic in serializers (they validate + shape data only)
- Put business logic in model `save()` (override only for trivial normalization)
- Put multi-step workflows in views
- Call `.objects.create()` directly from a view for anything with side effects
- Put business logic inside Celery task bodies — keep tasks thin

---
## 6. Database — Query Optimization (Strict No-N+1 Policy)

N+1 queries are a **blocker-level bug**. Every list view, every serializer, every template must be audited.
Ensure that atomic transactions are used for operations involving multiple related database updates, to maintain data consistency in case of failures.

### Required Practices

**6.1 Always use `select_related` for forward ForeignKey / OneToOne access**
```python
# BAD: N+1
stores = Store.objects.all()
for s in stores:
    print(s.organisation.name)   # one extra query per store

# GOOD
stores = Store.objects.select_related("organisation")
```

**6.2 Always use `prefetch_related` for reverse FK and M2M**
```python
# GOOD
orgs = Organisation.objects.prefetch_related("stores", "stores__reviews")
```

**6.3 Use `Prefetch` with filtered/ordered inner querysets**
```python
from django.db.models import Prefetch

orgs = Organisation.objects.prefetch_related(
    Prefetch(
        "stores",
        queryset=Store.objects.filter(is_active=True).order_by("name"),
    )
)
```

**6.4 Use `.only()` / `.defer()` when serializing large tables with only a few columns needed.**

**6.5 Use `annotate()` + aggregates for counts. Never `len()` on a queryset when you need a count.**
```python
orgs = Organisation.objects.annotate(active_store_count=Count("stores", filter=Q(stores__is_active=True)))
```

**6.6 Custom Managers / QuerySets for reusable query primitives**
```python
# apps/organisations/managers.py
class OrganisationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Organisation.Status.ACTIVE)

    def annotate_store_counts(self):
        return self.annotate(
            total_stores=Count("stores"),
            active_stores=Count("stores", filter=Q(stores__is_active=True)),
        )

class Organisation(models.Model):
    ...
    objects = OrganisationQuerySet.as_manager()
```

**6.7 DRF serializers for nested data must use `SerializerMethodField` sparingly. Prefer flattened data + prefetch.**

**6.8 Add indexes for every field used in filtering, ordering, or FK lookups.**
Use `Meta.indexes` and composite indexes for common query shapes. Review with `EXPLAIN ANALYZE`.

**6.9 Detect N+1 in development**
- Install `django-debug-toolbar` (local only)
- Install `nplusone` or `django-silk` — fail fast on detected N+1
- In CI, run performance tests that assert query count using `django.test.CaptureQueriesContext`:

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

def test_list_organisations_query_count(api_client):
    OrganisationFactory.create_batch(20)
    with CaptureQueriesContext(connection) as ctx:
        resp = api_client.get("/api/organisations/")
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5   # fixed ceiling, not proportional to results
```

**6.10 Use `bulk_create`, `bulk_update`, `update()`, and `F()` expressions for batch writes.**

**6.11 Always wrap multi-step writes in `transaction.atomic()`.**

**6.12 Use `select_for_update()` inside transactions for row-level locking on critical updates** (e.g., decrementing store allocation counters, transitioning enrichment status).

**6.13 Postgres full-text search** (Phase 3+ for review text search) — use `SearchVector` + `GinIndex` on the `Review.text` field, maintained via migration. Never use `icontains` on review text at scale.

---

## 7. Redis Usage

Redis has multiple roles in this project. Keep them logically separated by DB index.

| Redis DB | Purpose | Introduced |
|---|---|---|
| `0` | Django cache (`django-redis` backend) | Phase 1 |
| `1` | DRF throttling / rate limiting | Phase 1 |
| `2` | Session store (if not using DB sessions) | Phase 1 |
| `3` | Celery broker | Phase 3 |
| `4` | Celery result backend | Phase 3 |
| `5` | Channels layer (WebSocket pub/sub) | Phase 3 |

### 7.1 Cache configuration
```python
# config/settings/base.py
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL") + "/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "IGNORE_EXCEPTIONS": True,    # don't take down app if Redis is down
        },
        "KEY_PREFIX": "app",
        "TIMEOUT": 300,                   # default 5 min
    },
}
DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
```

### 7.2 When to cache
- **Cache:** list views with expensive joins, expensive aggregates, external API responses, rendered page fragments
- **Do NOT cache:** user-specific dashboards (unless keyed by user), anything with write-after-read semantics

### 7.3 Cache key conventions
Format: `{app}:{entity}:{id_or_slug}:{variant}`

```python
def org_list_cache_key(search: str, status: str, page: int) -> str:
    return f"organisations:list:{hash((search, status, page))}"

def org_detail_cache_key(org_id: int) -> str:
    return f"organisations:detail:{org_id}"
```

### 7.4 Invalidation
Prefer **event-based invalidation over TTL** for anything a user edits:

```python
# apps/organisations/services/organisations.py
from django.core.cache import cache

def update_organisation(org, **data):
    for k, v in data.items():
        setattr(org, k, v)
    org.save()
    cache.delete_pattern(f"organisations:detail:{org.id}")
    cache.delete_pattern("organisations:list:*")
    return org
```

### 7.5 Rate limiting
Use DRF's built-in throttle classes backed by Redis via `django-redis`:
```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/hour",
        "anon": "100/hour",
        "invite": "5/hour",            # scoped throttle for invite endpoints
        "google_sync": "60/minute",
        "openai_call": "120/minute",   # Phase 3+
        "review_reply": "30/minute",   # Phase 3+
    },
}
```

### 7.6 Distributed locks

Use the helper in `apps/common/locks.py` (introduced in Phase 3) for any task that must not run concurrently for the same entity. Backed by `redis-py`'s lock primitive.

```python
from apps.common.locks import distributed_lock

def sync_shop_reviews(shop_id: str) -> None:
    with distributed_lock(f"google_sync:shop:{shop_id}", timeout=300, blocking=False) as acquired:
        if not acquired:
            return  # another worker is already syncing this shop
        _do_sync(shop_id)
```

**Lock key conventions** (Phase 3+):

| Key Pattern | Purpose | TTL |
|---|---|---|
| `lock:google_sync:shop:{shop_id}` | Per-shop Google review sync | 5 min |
| `lock:enrich:review:{review_id}` | Per-review OpenAI enrichment | 5 min |
| `lock:reply:review:{review_id}` | Per-review reply submission | 30 sec |

Lock acquisition is **non-blocking** by default — if another worker holds the lock, the task exits cleanly without retrying. The next scheduled run will pick it up.

### 7.7 Phase 3 ephemeral state keys

| Key Pattern | Purpose | TTL |
|---|---|---|
| `sync:progress:{shop_id}` | Current initial-sync progress for WebSocket and snapshot API | 24h while running, 1h after success, 7d after permanent failure |
| `rate:openai:org:{organisation_id}` | Per-org OpenAI **cross-worker global rate limiter** (`OPENAI_GLOBAL_RATE_LIMIT`, live since v0.8/Phase 23). The seed loop pre-acquires a token via `_wait_for_openai_token`; the bulk/task path raises a retriable error when depleted. The per-worker Celery `rate_limit` (`ENRICHMENT_RATE_LIMIT`) is the **secondary** guard. See §29. | rolling 1 min |
| `rate:google:project` | Global Google API call counter (token bucket) | rolling 1 min |
| `lock:tag_merge:org:{org_id}` | Per-org lock for canonical tag merge / finalising jobs (`tag-merge` queue, §29) | 5 min |

---
## 8. DRF Conventions

- **One ViewSet per resource.** Use `ModelViewSet` only when all CRUD is needed; otherwise compose `GenericViewSet` + mixins.
- **Two serializers per resource** when input and output differ: `OrganisationReadSerializer`, `OrganisationCreateSerializer`.
- **Permissions are explicit on every viewset.** No global `AllowAny`. Compose `IsAuthenticated & IsSuperadmin`.
- **Pagination is required on every list endpoint.** Use `PageNumberPagination` or `CursorPagination` (cursor for large tables like reviews).
- **Filtering:** use `django-filter` with explicit `FilterSet` classes. Never expose arbitrary `__` lookups.
- **Versioning:** URL path versioning, `/api/v1/...`.
- **Errors:** use DRF's exception handler; wrap custom errors in `apps/common/exceptions.py`.

---

## 9. Authentication & Authorization

- **User model:** custom, in `apps.accounts.models.User`. Set `AUTH_USER_MODEL = "accounts.User"` **before the first migration**.
- **Role:** enum field `User.role` → `SUPERADMIN | ORG_ADMIN | STAFF_ADMIN`.
- **Tenant scoping:** `User` has a nullable FK to `Organisation` (null for superadmins). Every queryset in Org/Staff-admin views **must** be filtered by the caller's `organisation_id`. Enforce this in a base permission or mixin, not in each view.
- **Auth for API:** session auth for the Django-rendered frontend, token auth (SimpleJWT) only if a separate client is added later.
- **Auth for Channels (Phase 3+):** Channels session middleware reuses the same Django session; consumers verify role + organisation match before accepting the connection (see §13.4).
- **Invitation tokens:** use `django.core.signing.TimestampSigner` with a 48-hour max age. Store token hash in DB, mark single-use.
- **Password policy:** Django's built-in validators, minimum length 10.

### Phase 3 — Brand vs Shop scoping for action items

Beyond role + organisation scoping, action items have a **scope** field (`SHOP` or `BRAND`). Staff users must NEVER see brand-scoped action items, even by direct URL access. This is enforced at three layers:

1. **Selector layer** — every Staff queryset includes `.filter(scope=SHOP)`
2. **Permission layer** — detail/edit/status endpoints return 403 when role is `STAFF_ADMIN` and the target's scope is `BRAND`
3. **UI layer** — the brand-scope filter and "Create brand action item" controls are not rendered for Staff

Layer 1 is the authoritative defence; layers 2 and 3 are belt-and-braces.

---

## 10. Background Jobs

The platform uses **two complementary systems** for background work, chosen based on the workload's needs.

### Phase 1 & 2 features: Management Commands + Cloud Scheduler

Used for low-frequency, low-concurrency, scheduled jobs (e.g., refreshing OAuth tokens, scheduled cleanups).

- Each job is a **thin management command** under `apps/<app>/management/commands/`.
- The command calls a **service function**. Business logic stays in the service.
- GCP Cloud Scheduler hits a secured HTTP endpoint (`/internal/jobs/<job_name>/`) that runs the command's service function. Secure with a shared secret header + IP allowlist.
- Jobs must be **idempotent**. Design them to re-run safely.
- Always acquire a Redis lock before processing per-entity jobs (see §7.6).

This pattern continues to work for Phase 1 and Phase 2 features and **does not require migration**.

### Phase 3+ features: Celery + Celery Beat

Used for high-concurrency, retry-heavy, or real-time-progress workloads. See §12 for the full Celery convention.

### Choosing between them

Use **Celery** when any of:
- Concurrency > 1 worker per entity
- Retries with exponential backoff are needed
- Per-entity locking is required
- Real-time progress updates over WebSocket are required
- Tasks may take longer than an HTTP request timeout (60s on Cloud Run by default)

Use **management commands + Cloud Scheduler** when all of:
- The job runs at a fixed interval
- Concurrency is 1 (one global runner is fine)
- Total runtime fits within the HTTP timeout
- No per-entity progress visibility required

---

## 11. Google Business Profile Integration

- All Google API code lives in `apps/integrations/google/`.
- OAuth flow is **per-store** (each store owner authorizes the app to access that store's reviews).
- Store refresh tokens **encrypted at rest** using `django-cryptography` or Fernet with a key from GCP Secret Manager.
- Wrap every API call with retry + exponential backoff (`tenacity`).
- Respect Google's rate limits. Use the token bucket in Redis (`rate:google:project`).
- Always log `request_id` from Google responses for debugging.
- On `401 invalid_grant`, mark the store's connection as expired and notify the Org Admin.

### Phase 3 — Review fetching specifics

- Reviews are unique on `(shop_id, google_review_id)`. Inserts use `ON CONFLICT DO UPDATE` semantics so re-fetches update rather than duplicate.
- A review's `text` or `rating` may be edited by the reviewer on Google. When detected, update the local row and reset `enrichment_status = PENDING` so the AI pipeline re-runs.
- Reviews removed by Google are **soft-deleted** (`deleted_at` set) — never hard-deleted, to preserve audit trail and action item linkage.
- Replies are posted to Google **synchronously** within the request lifecycle so the user sees Google's accept/reject immediately.

---
## 12. Celery — Background Job Processor (Phase 3+)

Phase 3 introduces Celery for workloads that exceed what management commands + Cloud Scheduler can do (concurrency, retries with backoff, per-entity locking, real-time progress).

### 12.1 Architecture

- **Broker:** Redis DB index 3
- **Result backend:** Redis DB index 4
- **Beat schedule store:** `django-celery-beat` (DB-backed) so schedules can be edited at runtime via Django admin
- **Named queues** with separate worker pools (v0.8 split — `CELERY_QUEUE_NAMES` in `config/settings/base.py`):
  - `google-sync` — Google API operations (review fetch, token refresh)
  - `ai-enrichment-high` — OpenAI enrichment for **initial sync** (seed + bulk), must not be starved by daily traffic
  - `ai-enrichment-low` — OpenAI enrichment for **daily incremental** sync + retries (conservative-default fallback)
  - `tag-merge` — canonical-tag merge / finalising / reclassification-adjacent jobs (per-org locked)
  - `default` — everything else (notifications, lightweight fan-outs, the weekly polarity job)

### 12.2 Configuration

```python
# config/settings/base.py
CELERY_BROKER_URL = env("REDIS_URL") + "/3"
CELERY_RESULT_BACKEND = env("REDIS_URL") + "/4"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task":   {"queue": "google-sync"},
    # enrich_review_task fallback routes to -low; initial sync overrides to
    # -high at call time via apply_async(queue="ai-enrichment-high").
    "apps.reviews.tasks.enrich_review_task":      {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment-low"},
    "apps.reviews.tasks.finalize_canonical_tags_task":  {"queue": "tag-merge"},
    "apps.reviews.tasks.reclassify_polarity_task":      {"queue": "default"},
}
CELERY_TASK_TIME_LIMIT = 600         # 10-minute hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 300    # 5-minute soft limit (raises SoftTimeLimitExceeded)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ACKS_LATE = True         # ack only after task succeeds — survives worker crashes
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # prevent slow tasks blocking fast ones
```

### 12.3 Task conventions

- Tasks live in `apps/<app>/tasks.py`.
- **Tasks are thin wrappers around service functions.** No business logic in task bodies.
- Use `@shared_task(bind=True)` so the task can access `self` for retries and logging.
- Always declare `autoretry_for`, `retry_backoff`, `retry_backoff_max`, `retry_jitter`, `max_retries`.
- Tasks receive **IDs**, never model instances (model instances don't serialize to the broker reliably).

```python
# apps/reviews/tasks.py
from celery import shared_task
from apps.reviews.services.enrichment import enrich_review

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_review_task(self, review_id: str) -> None:
    enrich_review(review_id=review_id)
```

### 12.4 Idempotency — three layers

Background tasks **must be idempotent**. Running the same task twice with the same arguments must produce the same final state, never duplicates or partial-state corruption. Enforce at three layers:

**Layer 1 — Database uniqueness constraints.** Reviews are unique on `(shop_id, google_review_id)`. Inserts use upsert semantics.

**Layer 2 — Per-entity Redis locks** (see §7.6). A task that mutates a single shop or review acquires a lock before proceeding.

**Layer 3 — Status flags + row-level locks.** For example, `Review.enrichment_status` transitions `PENDING → IN_PROGRESS → SUCCESS / FAILED`. The transition uses `select_for_update()` inside `transaction.atomic()`:

```python
@transaction.atomic
def enrich_review(*, review_id: str) -> None:
    review = (
        Review.objects
        .select_for_update()
        .get(id=review_id)
    )
    if review.enrichment_status == Review.EnrichmentStatus.SUCCESS:
        return  # already done; idempotent no-op
    if review.enrichment_status == Review.EnrichmentStatus.IN_PROGRESS:
        return  # another worker holds the row lock; exit silently
    review.enrichment_status = Review.EnrichmentStatus.IN_PROGRESS
    review.save(update_fields=["enrichment_status", "enrichment_attempted_at"])
    # ... call OpenAI, parse, persist results, transition to SUCCESS or FAILED
```

### 12.5 Beat schedules

Beat tasks are stored in the database via `django-celery-beat`. Seed initial schedules via a data migration so they exist in fresh environments.

| Task | Queue | Schedule |
|---|---|---|
| `enqueue_incremental_syncs_task` | `google-sync` | Every hour at minute 0 (fans out per-shop tasks with jitter) |
| `retry_failed_enrichments_task` | `ai-enrichment-low` | Every 6 hours |
| `refresh_google_tokens_task` | `google-sync` | Hourly |
| `reclassify_polarity_task` | `default` | Weekly, Sunday 03:00 UTC — DB-only polarity reclassification (v0.8/Phase 24, §29) |

### 12.6 Deployment

- Celery worker, Celery Beat, and the web server run as **separate Cloud Run services** (or separate processes in a GKE pod set).
- All three use the **same Docker image**; the entry command differs per service.
- **Beat instance count: exactly 1.** Multiple Beat instances = duplicate jobs. Enforce at the deployment template.
- **Worker instance count:** scales horizontally per queue based on queue depth. Different scaling profiles per queue (e.g., `ai-enrichment-*` workers can scale slower since OpenAI is the bottleneck; `ai-enrichment-high` is prioritised for initial sync).
- **Sentry integration** captures task failures with full traceback and task arguments.

### 12.7 Monitoring

- **Flower** runs in **dev and staging only** — never in production. Bind to localhost in dev; gate behind staging auth in staging.
- Worker health metrics shipped to Better Stack / Datadog: queue depth per queue, task throughput, task latency p50/p95/p99, retry rate, failure rate.
- Per-task log records include `task_id`, `task_name`, `args` (sanitized — no secrets), and `result_status`.

### 12.8 Testing

- Use `CELERY_TASK_ALWAYS_EAGER = True` in `config/settings/test.py` so tasks execute synchronously in the test runner.
- Tasks must have unit tests against their service function (not the task body) — test the logic, not the wrapper.
- Integration tests with `--celery-eager` verify that the right tasks are dispatched on the right events (e.g., creating a Review enqueues `enrich_review_task`).
- A CI smoke test verifies a Celery task completes within 30 seconds in the test runner.

---

## 13. Django Channels — Real-time UI Updates (Phase 3+)

Phase 3 adds Channels for **one specific feature**: real-time progress updates during a shop's initial review backfill. The infrastructure is added once and is available for future real-time features, but its surface area is intentionally narrow.

### 13.1 Configuration

- ASGI server: **Daphne** (or Uvicorn) running alongside the WSGI web server
- Channel layer: **Redis**, DB index 5
- Routing in `config/routing.py`; consumer in `apps/reviews/consumers.py`

```python
# config/settings/base.py
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL") + "/5"],
            "capacity": 1500,
            "expiry": 30,
        },
    },
}
```

### 13.2 Scope discipline (non-negotiable)

In Phase 3, Channels is used **only** for `SyncProgressConsumer` at `/ws/sync-progress/`. The following are explicitly out of scope and must NOT be added without an architecture review:

- Live new-review toast notifications
- Live action item status sync between concurrent users
- Real-time review reply confirmations
- The notification bell counter — uses HTTP polling at 60s, not WebSocket
- Any other live data synchronisation

This discipline keeps the Channels surface small, auditable, and verifiable in Phase 3. Adding new consumers requires updating this section of CLAUDE.md and explicit sign-off in code review.

### 13.3 Single Phase 3 consumer — `SyncProgressConsumer`

```python
# apps/reviews/consumers.py
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
        # Send current snapshot from Redis on connect
        snapshot = await get_progress_snapshot(shop_id=shop_id)
        if snapshot:
            await self.send_json(snapshot)

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def progress_event(self, event):
        await self.send_json(event["payload"])
```

### 13.4 Authorisation rules for consumers

Every consumer must enforce, on connect:

1. The user is authenticated. If not → `close(code=4401)`.
2. The user's `organisation_id` matches the resource's `organisation_id`. If not → `close(code=4403)`.
3. For Staff users, the shop is in the user's `StaffAccessScope`. If not → `close(code=4403)`.

Failures must close the connection — never leak data via the WebSocket.

### 13.5 Event payload conventions

Server-to-client events are JSON objects with a `type` discriminator. Client code switches on `type`:

Initial sync is a **four-step** flow (v0.8/Phase 23) — Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising — surfaced by **extending** `SyncProgressConsumer` (still **no new consumer**, §13.2). The Redis snapshot carries a `step` discriminator + per-step counters so a reconnect repaints the current step.

| Event | Payload Fields | When Sent |
|---|---|---|
| `sync.fetch.progress` | `shop_id, fetched, total_estimate` | Step 1 — after every Google API page is persisted |
| `sync.vocab.progress` | `shop_id, vocab_enriched, vocab_total` | Step 2 — after each review in the sequential seed pass (vocabulary building) |
| `sync.enrichment.progress` | `shop_id, enriched, fetched` | Step 3 — after every batch of bulk reviews is enriched |
| `sync.finalising.progress` | `shop_id, finalising_processed, finalising_total` | Step 4 — during the canonical dedup/backfill/count-refresh pass |
| `sync.complete` | `shop_id, total_fetched, total_enriched, duration_seconds` | When the **finalising** step finishes (it owns `sync.complete`, not enrichment) |
| `sync.error` | `shop_id, stage, error_code, error_message` | When sync fails permanently after retries |

### 13.6 Persistence + reconnect

Progress state for each in-progress sync is mirrored in Redis at `sync:progress:{shop_id}`. On reconnect, the consumer reads from Redis and sends the current snapshot immediately so the UI is correct without waiting for the next event.

---

## 14. OpenAI Integration & AI Cost Tracking (Phase 3+)

Phase 3 introduces GPT-4o-mini for review enrichment (sentiment, tags, action items). Every call is traced, cost-logged, and idempotently retried.

### 14.1 Module layout — `apps/integrations/openai/`

| File | Responsibility |
|---|---|
| `client.py` | Thin wrapper around the `openai` SDK with LangSmith tracing, retry, and structured-response parsing |
| `prompts.py` | Versioned prompt templates. Bumping a prompt version increments `Review.enrichment_version` so future bulk re-enrichment can target a version. |
| `parser.py` | Parses GPT's JSON response, validates schema with Pydantic, raises `EnrichmentParseError` on malformed output |
| `pricing.py` | Cost calculator that reads from `AiPricing` table |
| `tracing.py` | LangSmith SDK integration |
| `exceptions.py` | `OpenAITransientError` (retry-able), `OpenAIPermanentError` (do not retry) |

### 14.2 Single combined prompt

All enrichment outputs come from **one GPT call per review** that returns structured JSON. Multiple specialised calls are wasteful and prohibited.

The prompt receives:
- Brand name (= Organisation Name)
- Shop name
- Shop address
- Review text
- Review rating

The prompt returns JSON conforming to a Pydantic schema:

```python
# apps/integrations/openai/parser.py
from pydantic import BaseModel
from typing import Literal

class Tag(BaseModel):
    label: str
    polarity: Literal["positive", "negative", "neutral"]

class ActionItem(BaseModel):
    title: str
    scope: Literal["shop", "brand"]
    priority: Literal["high", "medium", "low"]

class EnrichmentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    tags: list[Tag]              # max 5 tags (enforced by prompt + validator)
    action_items: list[ActionItem]
```

### 14.3 Cost tracking — `AiUsageLog` and `AiPricing`

Every OpenAI call writes one row to `AiUsageLog`. **Cost is calculated server-side using `AiPricing` rates** — never relying on OpenAI's billing API (not real-time, not per-call).

**`AiUsageLog`** captures: `organisation_id`, `request_type`, `model`, `review_id`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `total_tokens`, `estimated_cost_usd`, `latency_ms`, `langsmith_trace_id`, `status`, `error_code`, `error_message`, `created_at`. Indexes on `(organisation_id, created_at)`, `(review_id)`, `(status)`.

**`AiPricing`** is **time-versioned**: `model`, `input_token_price_per_1m`, `output_token_price_per_1m`, `cached_token_price_per_1m`, `effective_from`, `effective_to` (nullable for current). Unique on `(model, effective_from)`.

Cost calculation runs at log time using the active pricing record. **Historical pricing changes do NOT retroactively change historical costs** — `estimated_cost_usd` is locked-in at write time.

```python
# apps/integrations/openai/pricing.py
from decimal import Decimal
from apps.integrations.openai.models import AiPricing

def calculate_cost(*, model: str, prompt_tokens: int, completion_tokens: int,
                   cached_tokens: int = 0) -> Decimal:
    pricing = AiPricing.objects.get_active(model=model)
    non_cached_input = prompt_tokens - cached_tokens
    cost = (
        Decimal(non_cached_input) / 1_000_000 * pricing.input_token_price_per_1m
        + Decimal(cached_tokens)   / 1_000_000 * pricing.cached_token_price_per_1m
        + Decimal(completion_tokens) / 1_000_000 * pricing.output_token_price_per_1m
    )
    return cost.quantize(Decimal("0.000001"))
```

### 14.4 Pricing maintenance

- Pricing rows are managed via Django admin (Phase 3) or a dedicated Superadmin UI (future phase).
- Adding a new pricing row sets `effective_from = now()` and updates the previous row's `effective_to`.
- **Never edit a historical pricing row in place.** Add a new row instead.
- Initial seed data: GPT-4o-mini at the model's published rates as of model release. Stored as `Decimal` to avoid floating-point drift.

### 14.5 LangSmith tracing

- Every OpenAI call is wrapped with the LangSmith Python SDK.
- LangSmith API key in env / Secret Manager. Project name: `review-platform-{environment}`.
- Trace metadata includes: `organisation_id`, `review_id`, `shop_id`, `model`, `request_type`.
- The `langsmith_trace_id` is captured from the SDK response and persisted on `AiUsageLog` so support can cross-reference traces from a usage log row.
- **LangSmith is best-effort, not blocking.** If LangSmith is unreachable, the OpenAI call still proceeds. Tracing failure is logged at WARNING; the OpenAI call's success is unaffected.

### 14.6 Failure handling

- **OpenAI rate limit (429) or 5xx** → retry up to 3 times with exponential backoff (30s, 2min, 10min).
- **OpenAI 4xx other than 429** (e.g., context length exceeded) → no retry. Mark `Review.enrichment_status = FAILED` with error code. Record on `AiUsageLog`.
- **JSON parse failure** (Pydantic validation) → retry once. If still bad, mark `FAILED`.
- Failed enrichments do NOT block the review from appearing in the Reviews list.
- The `retry_failed_enrichments_task` (Beat-scheduled every 6 hours) re-attempts `FAILED` reviews up to 3 total attempts before giving up permanently.

### 14.7 Idempotency

`enrich_review(review_id)` follows the three-layer pattern in §12.4. The Redis lock is `lock:enrich:review:{review_id}`. If the review's `enrichment_status` is already `SUCCESS`, the function returns immediately — **no OpenAI call, no cost incurred**. This is critical because the same review may be re-fetched by Google sync and shouldn't be re-billed.

### 14.8 Settings additions

```python
# config/settings/base.py
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini-2024-07-18")
OPENAI_MAX_RETRIES = env.int("OPENAI_MAX_RETRIES", default=3)

LANGSMITH_API_KEY = env("LANGSMITH_API_KEY", default=None)
LANGSMITH_PROJECT = env("LANGSMITH_PROJECT", default=f"review-platform-{ENVIRONMENT}")
LANGSMITH_ENABLED = bool(LANGSMITH_API_KEY)

INITIAL_SYNC_PAGE_SIZE = env.int("INITIAL_SYNC_PAGE_SIZE", default=50)
ENRICHMENT_BATCH_SIZE = env.int("ENRICHMENT_BATCH_SIZE", default=10)
INCREMENTAL_SYNC_INTERVAL_HOURS = env.int("INCREMENTAL_SYNC_INTERVAL_HOURS", default=6)
INCREMENTAL_SYNC_JITTER_MINUTES = env.int("INCREMENTAL_SYNC_JITTER_MINUTES", default=30)
```

### 14.9 Required dependencies

```toml
[project.dependencies]
celery = "^5.4.0"
django-celery-beat = "^2.7.0"
channels = "^4.2.0"
channels-redis = "^4.2.0"
daphne = "^4.1.0"
openai = "^1.55.0"
langsmith = "^0.2.0"
tenacity = "^9.0.0"
pydantic = "^2.10.0"
```

### 14.10 Testing

- **Never hit real OpenAI in tests.** Mock the client using `respx` or a fake response factory.
- Use deterministic GPT response fixtures stored in `apps/integrations/openai/tests/fixtures/`.
- Unit tests for `pricing.py` cover boundary cases: zero cached tokens, all-cached prompt, pricing transition mid-month.
- Integration tests for `enrichment.py` cover: success path, retry-then-success, malformed-JSON-then-success, permanent failure, idempotency (calling twice = one usage log row).

---
## 15. Transactional Email — Amazon SES

All outbound email goes through Amazon SES. This covers Org Admin invitations, invitation resends, password resets, and any future notification emails.

### 15.1 Integration approach

Use `django-ses` as the email backend — it plugs into Django's standard email API so nothing in the application code needs to know about SES specifically. Services call `send_mail()` or `EmailMultiAlternatives.send()` and the backend handles the SES API call.

```python
# config/settings/base.py
EMAIL_BACKEND = "django_ses.SESBackend"

AWS_SES_REGION_NAME = env("AWS_SES_REGION_NAME", default="us-east-1")
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
AWS_SES_FROM_EMAIL = env("AWS_SES_FROM_EMAIL")           # e.g., noreply@yourdomain.com
DEFAULT_FROM_EMAIL = AWS_SES_FROM_EMAIL
SERVER_EMAIL = AWS_SES_FROM_EMAIL

# Credentials: prefer IAM role / Workload Identity in production.
# Use a dedicated IAM user scoped to ses:SendEmail / ses:SendRawEmail only.
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)

# Configuration Set — enables open/click/bounce/complaint tracking via SNS
AWS_SES_CONFIGURATION_SET = env("AWS_SES_CONFIGURATION_SET", default=None)
```

### 15.2 Local development

- **Never send real email from local dev.** Use MailHog (already in `docker-compose.yml`) by overriding the backend in `config/settings/local.py`:
  ```python
  EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
  EMAIL_HOST = "mailhog"
  EMAIL_PORT = 1025
  EMAIL_USE_TLS = False
  ```
- In `config/settings/test.py`, use `django.core.mail.backends.locmem.EmailBackend` so tests capture outgoing mail in `django.core.mail.outbox`.

### 15.3 From-address & domain setup

- **Production from-address:** `noreply@<your-domain>` — must be verified in SES.
- **Domain verification:** complete DKIM + SPF records in DNS before going live. Without DKIM, emails land in spam.
- **Start in the SES sandbox** (can only send to verified addresses). Request production access from AWS before launch.
- **Reply-to:** set a monitored mailbox (e.g. `support@<your-domain>`) so users can reply.

### 15.4 Service-layer usage

Wrap `send_mail` in a thin service — never call Django's email API directly from views.

```python
# apps/common/services/email.py
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_transactional_email(
    *,
    to: list[str],
    subject: str,
    template_base: str,       # e.g. "emails/invitation" -> .html + .txt
    context: dict,
    reply_to: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or [settings.DEFAULT_REPLY_TO],
    )
    msg.attach_alternative(html_body, "text/html")
    # SES message tags — useful for tracking categories in SNS events
    if tags:
        msg.extra_headers["X-SES-MESSAGE-TAGS"] = ", ".join(
            f"category={t}" for t in tags
        )
    if settings.AWS_SES_CONFIGURATION_SET:
        msg.extra_headers["X-SES-CONFIGURATION-SET"] = settings.AWS_SES_CONFIGURATION_SET
    msg.send(fail_silently=False)
```

### 15.5 Templates

- Store email templates under `templates/emails/<name>.html` and `templates/emails/<name>.txt`.
- Always ship **both** plain-text and HTML versions. SES penalises HTML-only senders.
- Use a base template `templates/emails/base.html` with brand colours (yellow primary, black CTA) and a clear support / unsubscribe footer.
- Inline CSS (use `premailer` or `django-premailer`) — email clients ignore `<style>` blocks inconsistently.
- Keep HTML width at **600px** max for mobile compatibility.

### 15.6 Sending must be resilient and async-safe

- **Never block a web request on `send()` for more than a single attempt.** Wrap the call in try/except and log failures.
- In Phase 1 the invitation email is small enough to send synchronously. If latency becomes noticeable, move sending to a Celery task (Phase 3+).
- In Phase 3+, Celery tasks wrap the same service function. No logic duplication.

### 15.7 Bounces, complaints, and suppression

- Configure an SNS topic for SES bounce, complaint, and delivery notifications.
- Set up an internal webhook endpoint (e.g. `/webhooks/ses/`) secured by SNS signature verification.
- On hard bounce or complaint: mark the user's email as `email_suppressed=True`. Do not attempt to send to suppressed addresses again.
- Never remove suppressions automatically — requires manual review or user-driven re-opt-in.

### 15.8 Rate limits & throttling

- SES has account-level send quotas (starts at 200/day in sandbox, scales after production access).
- Use Redis (see §7) to track per-minute send counts as a safety net — circuit-break and log if the app approaches the SES limit.
- Batch transactional sends are **not** appropriate here; every email is triggered by a discrete user event.

### 15.9 Security

- IAM policy for the SES user must be minimal:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["ses:SendEmail", "ses:SendRawEmail"],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "ses:FromAddress": "noreply@yourdomain.com" }
      }
    }]
  }
  ```
- AWS credentials only in GCP Secret Manager — **never** in `.env` in production.
- Rotate the IAM access key every 90 days.
- All email templates must render user-supplied values through Django's auto-escaping templating — never use `|safe` on user input in emails.

### 15.10 Observability

- Log every send with a structured record: `{event: "email.sent", template, to_hash, message_id}`. Hash recipient emails in logs — don't store raw addresses in log aggregators.
- Monitor the SES dashboard for bounce rate (must stay below 5%) and complaint rate (must stay below 0.1%) — exceeding these thresholds leads to SES suspension.
- Alert via Better Stack / Datadog if bounce rate > 3% or complaint rate > 0.05% over a 24-hour window.

### 15.11 Required dependencies

```toml
[project.dependencies]
django-ses = "^4.3.0"
boto3 = "^1.35.0"
premailer = "^3.10.0"     # for CSS inlining at send time if not done at build time
```

### 15.12 Testing

- Use `django.core.mail.backends.locmem.EmailBackend` in tests.
- Every email-sending service must have a test asserting:
  1. An email was sent (`len(mail.outbox) == 1`)
  2. The correct recipient
  3. The correct subject
  4. Key substrings (invitation URL, user's name) appear in both HTML and text bodies
- **Never** let tests hit real SES.

---

## 16. Testing

- **Framework:** `pytest` + `pytest-django`.
- **Factories:** `factory-boy`. One factory per model in `apps/<app>/tests/factories.py`.
- **Coverage:** minimum 85% line coverage on services, selectors, and permissions. Enforced in CI.
- **Structure:** one test file per module (`test_services.py`, `test_selectors.py`, `test_views.py`).
- **Fast tests:** disable migrations in test settings (`MIGRATION_MODULES` → disabled) and use `--reuse-db`.
- **Query-count tests:** every list endpoint must have a test that asserts a fixed query count regardless of result size (see §6.9).
- **Never hit external APIs in tests.** Mock the Google client using `responses` or `respx`. Mock the OpenAI client (Phase 3+) the same way.
- **Celery tests:** `CELERY_TASK_ALWAYS_EAGER = True` in test settings. Test the service function directly, not the task wrapper.
- **Channels tests:** use `channels.testing.WebsocketCommunicator` for consumer tests. Cover authenticated, unauthenticated, and cross-tenant connection attempts.
- **AI cost tests:** `pricing.py` has unit tests covering: zero cached tokens, all-cached prompt, mid-window pricing transition, decimal precision.

---

## 17. Pre-commit Rules

All code must pass pre-commit hooks before merge. Install once with `pre-commit install`.

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=500"]
      - id: debug-statements       # catches pdb/ipdb
      - id: detect-private-key
      - id: mixed-line-ending

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.11
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/adamchainz/django-upgrade
    rev: 1.22.2
    hooks:
      - id: django-upgrade
        args: [--target-version, "6.0"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - django-stubs[compatible-mypy]
          - djangorestframework-stubs
        args: [--config-file=pyproject.toml]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.0
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]
        additional_dependencies: ["bandit[toml]"]

  - repo: https://github.com/rtts/djhtml
    rev: 3.0.7
    hooks:
      - id: djhtml          # formats Django templates
      - id: djcss

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks        # prevents secret leaks

  - repo: local
    hooks:
      - id: missing-migrations
        name: Check for missing migrations
        entry: python manage.py makemigrations --check --dry-run
        language: system
        pass_filenames: false
        types: [python]
```

### Ruff configuration (in `pyproject.toml`)

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
extend-exclude = ["migrations", "static", "media", "node_modules"]

[tool.ruff.lint]
select = [
  "E", "W",     # pycodestyle
  "F",          # Pyflakes
  "I",          # isort
  "UP",         # pyupgrade
  "B",          # flake8-bugbear
  "C4",         # flake8-comprehensions
  "DJ",         # flake8-django
  "SIM",        # flake8-simplify
  "RUF",        # ruff-specific
  "S",          # bandit-lite
  "N",          # pep8-naming
  "T20",        # flake8-print (no print statements)
  "PT",         # pytest style
  "TID",        # tidy imports
]
ignore = [
  "E501",       # line-length handled by formatter
  "S101",       # allow assert in tests
]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101", "S106", "ARG"]
"**/migrations/**" = ["E501", "N806"]
"**/settings/**" = ["F403", "F405"]
"apps/*/apps.py" = ["F401"]     # signals import

[tool.ruff.lint.isort]
known-first-party = ["apps", "config"]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Mypy configuration

```toml
[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["mypy_django_plugin.main", "mypy_drf_plugin.main"]
exclude = ["migrations/", "venv/", ".venv/"]

[tool.django-stubs]
django_settings_module = "config.settings.local"
```

---

## 18. Git & Commit Conventions

- **Branch naming:** `feat/`, `fix/`, `chore/`, `refactor/`, `docs/` prefixes. e.g. `feat/org-list-filters`.
- **Commit messages:** Conventional Commits.
  - `feat(organisations): add store count adjustment flow`
  - `fix(reviews): handle expired Google refresh token`
  - `refactor(accounts): extract invitation service`
- **PRs:** one logical change per PR. Include: summary, screenshots for UI changes, migration note, rollout plan if non-trivial.
- **Migrations:** one migration per PR when possible. Name them descriptively, not `0014_auto_20260101`.

---

## 19. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` must run on every PR and include:
1. `pre-commit run --all-files`
2. `mypy`
3. `pytest --cov=apps --cov-fail-under=85`
4. `python manage.py makemigrations --check --dry-run`
5. `python manage.py check --deploy` (production settings)
6. Celery smoke test — verify a sample task completes within 30 seconds via the eager runner (Phase 3+)

`.github/workflows/deploy.yml` runs on merge to `main`:
1. Build Docker image
2. Push to Google Artifact Registry
3. Deploy **all three services** (web, worker, beat) to Cloud Run (staging) — Phase 3+
4. Run smoke tests
5. Manual approval gate → production deploy

---

## 20. Docker

- **Base image:** `python:3.12-slim` (multi-stage build).
- **Non-root user** in the final image.
- **`.dockerignore`** must exclude: `.git`, `.venv`, `node_modules`, `__pycache__`, `.env*`, `media/`.
- **Healthcheck endpoint:** `/healthz/` returns 200, `/readyz/` checks DB + Redis (and Channels layer in Phase 3+).
- **Single image, multiple entry commands.** The same image runs `web`, `worker`, and `beat` services with different `CMD`:
  - Web: `daphne -b 0.0.0.0 -p 8000 config.asgi:application` (Phase 3+; previously `gunicorn config.wsgi`)
  - Worker: `celery -A config worker -Q google-sync,ai-enrichment,default --concurrency=8`
  - Beat: `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler`
- **docker-compose** for local dev runs: `web`, `db` (postgres:16), `redis` (redis:7-alpine), `mailhog` (captures outgoing email locally — see §15.2). Phase 3+ adds: `worker`, `beat`, optionally `flower` (port 5555).

---

## 21. Logging & Monitoring

- Use **structured JSON logging** in production (`python-json-logger`).
- Include `request_id`, `user_id`, `organisation_id` in every log record via middleware.
- **Sentry:** auto-capture unhandled exceptions in web AND Celery worker processes. Scrub PII (emails, names) before send.
- **Better Stack / Datadog:** ship logs via sidecar or direct HTTP. Tag by environment and service (web / worker / beat).
- **Phase 3+ metrics:** queue depth per Celery queue, task throughput, task latency p50/p95/p99, retry rate, failure rate, OpenAI token consumption per organisation per day, sync completion time per shop.
- **Never log:** passwords, tokens, API keys, full request bodies of auth endpoints, raw OpenAI prompts containing PII, AWS credentials, OAuth refresh tokens.

---

## 22. Security Checklist (enforced in CI where possible)

- `DEBUG = False` in production
- `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000` with includeSubDomains + preload
- `ALLOWED_HOSTS` set explicitly
- `CSP` middleware enabled (Django 6 built-in)
- Secrets from GCP Secret Manager, never in `.env` in production
- `bandit` passes with no medium/high findings
- `pip-audit` / `safety` in CI for CVE scanning
- Never use `mark_safe` on untrusted input
- Always use DRF serializer validation; never trust `request.data` directly
- **Phase 3+:** every Celery task that handles user-scoped data verifies `organisation_id` matches the entity it's operating on
- **Phase 3+:** every Channels consumer enforces auth + tenant scope on connect (see §13.4)
- **Phase 3+:** Flower is never deployed to production
- **Phase 3+:** OpenAI prompts containing review content must NOT be logged at INFO or above (treat review text as user PII)

---

## 23. Common Commands

```bash
# Local dev
make up                  # docker-compose up (web, db, redis, mailhog, worker, beat)
make migrate             # run migrations
make makemigrations      # create new migrations
make shell               # django shell
make test                # pytest
make lint                # pre-commit run --all-files
make typecheck           # mypy .
make seed                # load fixtures / demo data
make worker              # run a celery worker locally
make beat                # run celery beat locally
make flower              # run flower locally on :5555

# Inside container
python manage.py createsuperuser
python manage.py refresh_google_tokens
celery -A config inspect active           # show running Celery tasks
celery -A config inspect reserved         # show queued tasks
```

---

## 24. When You (Claude Code) Are Asked to Add Code

This repo ships purpose-built **subagents** (`.claude/agents/`, catalogued in §27) that already know these conventions. Use them: launch `architect` for the design **before** step 1 on any non-trivial feature, and the relevant review/test subagents at step 12. They are read-only advisors — apply their findings yourself.

Follow this order, every time:

**Requirements first (MANDATORY — before step 0, no exceptions).** When a user asks for a feature, do **not** start building it until it is captured as a requirement:

- Confirm it maps to a REQ-ID in `.planning/REQUIREMENTS.md` (or the active spec under `docs/in-progress/`). If it does, proceed.
- If it does **not** exist yet, **add/update the requirement first** — a REQ-ID (+ acceptance criteria) in `.planning/REQUIREMENTS.md` and, where it belongs to a milestone/spec, the relevant spec doc and `ROADMAP.md` — then build. For substantial features this means routing through the GSD flow (`/gsd-new-milestone` or `/gsd-phase` → discuss → plan → execute), not ad-hoc coding.
- **Never ship a feature that isn't in the requirements registry.** Building outside it is exactly how the off-roadmap features in `docs/completed/Off-Roadmap_Features.md` (Reports, Reply Templates, Review Targets, Mobile/JWT, Action Item Categories) ended up untraceable. If a one-off side-track (e.g. a `superpowers` plan/spec) is unavoidable, **fold it back into `.planning/REQUIREMENTS.md` + ROADMAP in the same change.**

0. **Design first (non-trivial change):** launch the `architect` subagent for a structure proposal, build order, and the §-constraints that apply, before writing code.
1. **Read** the relevant app's existing `models.py`, `services/`, `selectors/`, `views.py`, `tasks.py`, `consumers.py` before writing anything.
2. **Add models** → create migration → verify migration is reversible.
3. **Write services and selectors** with full type annotations.
4. **Write tests first** for services and selectors. Factories go in `tests/factories.py`.
5. **Wire up serializers and views.** Keep them thin.
6. **Add URLs** under the app's `urls.py`, include in `config/urls.py`.
7. **Add permissions.** Never ship a new view without an explicit permission class.
8. **For background work (Phase 3+):** add a thin Celery task that calls the service. Choose the right queue. Configure retries.
9. **For real-time (Phase 3+):** if a new Channels consumer is needed, update §13 and get explicit sign-off — Channels surface area must stay small.
10. **Verify query counts.** Add a `CaptureQueriesContext` test for every list endpoint.
11. **Add/update** the OpenAPI schema (via `drf-spectacular`).
12. **Review before PR.** Run `code-reviewer`, plus `orm-performance-auditor` for any query/model/serializer/migration change and `tenant-security-auditor` for any auth/scoping change (§27). Use `test-author` to fill coverage gaps. Then **run** `pre-commit run --all-files` and `pytest` before declaring done.

### Never
- Skip tests "because it's small"
- Call `.objects.filter()` directly from a view for anything beyond trivial read
- Add a field to a model without an explicit `db_index` decision
- Add an endpoint without pagination if it returns a list
- Add an endpoint without throttling
- Use `print()` for debugging — use `logger`
- Commit a `.env` file
- Disable a pre-commit hook without discussion
- Put business logic inside Celery task bodies (Phase 3+) — use service functions
- Add a new Channels consumer without updating §13 first (Phase 3+)
- Bypass the `AiUsageLog` write when calling OpenAI (Phase 3+)
- Hit OpenAI in tests without mocking (Phase 3+)
- Run multiple Celery Beat instances (Phase 3+)
- Deploy Flower to production (Phase 3+)

---

## 25. Terraform Code Location (temporary)

Infrastructure-as-code for this project lives in the **sibling workspace
folder** `../review-master-terraform/` (registered as an additional working
directory). It will be extracted into its own dedicated Terraform repo after
the current audit and removed from this workspace.

Rules while it lives here:

- Do **not** add `.tf`, `.tfvars`, or `terraform/` files inside this repo.
- When working on infra, edit files in the sibling folder only.
- That folder has its own lifecycle — when it's time to plan infra work,
  run `/gsd-new-project` from **inside** `review-master-terraform/`, not
  from this repo's `.planning/`.
- The knowledge graph is per-repo; the sibling folder will not appear in
  this project's graph.

---

## 26. Brand Assets & Logo

All logo and favicon files live in `logo/` at the repo root.

| File | Purpose |
|------|---------|
| `logo/dashboard_logo.png` | logo — use in sidebar |
| `logo/favicon.ico` | Legacy `.ico` favicon |
| `logo/main_logo.png` | Main logo used in login page and emails |

### Usage in templates

```html
{% load static %}
<img src="{% static 'logo-nobackground.png' %}" alt="Review Master" class="w-8 h-8 object-contain">
```

Favicons are declared in `templates/partials/head.html` and included on every page via `{% include "partials/head.html" %}`.

### Login screen

Located at `templates/registration/login.html`. Django's built-in `LoginView` serves it at `/accounts/login/`. Relevant settings in `config/settings/base.py`:
- `LOGIN_URL = "/accounts/login/"`
- `LOGIN_REDIRECT_URL = "/dashboard/"`
- `LOGOUT_REDIRECT_URL = "/accounts/login/"`

---

## 27. Subagents (`.claude/agents/`)

This repo ships **purpose-built subagents** that encode the conventions in this file. Prefer them over ad-hoc exploration — they already know the architecture, the `code-review-graph` MCP tools, and the governance rules above. Launch one via the Task/Agent tool with the matching `subagent_type`. They have **no Edit/Write access** — they return findings, proposals, and context; you apply the changes.

| Subagent | Invoke it… | When |
|---|---|---|
| `architect` | **Before** writing code for a new feature, module, or cross-cutting change — for a design proposal with trade-offs, build order, and the §-constraints that apply. Complements `code-reviewer` (after the fact); this works at design altitude before the fact. | design-time |
| `code-reviewer` | **After** writing/changing backend code and **before** opening a PR — reviews against THIS file's conventions (thin views §5, services/selectors, DRF §8, permissions §9, throttling, pagination). | review-time |
| `orm-performance-auditor` | After any change to models, selectors, serializers, list endpoints, migrations, or queryset-iterating templates — hunts N+1 (§6, blocker-level), missing indexes, unsafe migrations, and missing query-count tests. | review-time |
| `tenant-security-auditor` | For **any** auth/scoping change — tenant isolation (§9), RBAC, action-item brand-vs-shop scope, Channels consumers (§13.4), Celery tasks handling user data (§22). The highest-risk surface in this repo. | review-time |
| `test-author` | After adding a service/selector/view, or when coverage dips below the 85% target (§16) — writes pytest + pytest-django with factory-boy, query-count, and mocking conventions. | build-time |
| `ai-enrichment-specialist` | **Before** touching anything under `apps/integrations/openai/` or reviews enrichment — the enrichment service/task, prompts, parser, `AiUsageLog`/`AiPricing` cost logging, LangSmith tracing, idempotency (§12.4, §14), or AI reply generation. | build-time |
| `frontend-react-builder` | For embedded React widgets under `frontend/` — the Vite-per-widget entrypoint pattern, the Django bootstrap-data handoff, Tailwind, and the brand palette (§26). Any work in `frontend/src` or a React-backed template. | build-time |
| `deployment-helper` | For GCP deploys — building/pushing the Docker image, the web/worker/beat Cloud Run services (§20), the GitHub Actions deploy workflow (§19), secrets, health checks, and release/rollback. | deploy-time |

**Rules of thumb**
- New feature → `architect` first, build per §24, then `code-reviewer` + the relevant auditor(s).
- Any change touching queries → `orm-performance-auditor`. Any change touching auth/scope → `tenant-security-auditor`. These two are non-negotiable for their surfaces.
- Adding a new subagent (or changing one's remit) → update this section so the catalogue stays the single source of truth.

---

## 28. Requirements & Spec Docs (`docs/`)

Product requirement specs live under `docs/` and are **Markdown only — never `.docx`**.

### Doc conventions

- **Markdown is the source of truth.** No `.docx` (or other binary office formats) in the repo. If a spec arrives as `.docx`, convert it to `.md` and **delete the `.docx`** in the same change.
  - There is no pandoc/python-docx in this project's env; a dependency-free stdlib converter (`zipfile` + `xml.etree` over `word/document.xml`) is sufficient for these structured specs — preserve headings, tables, lists, and bold, and strip redundant bold from heading lines.
- **Three-folder spec layout** (by lifecycle status):
  - `docs/in-progress/` — the spec for the **milestone currently being built** (e.g. the v0.8 Canonical Tag spec).
  - `docs/pending/` — specs for milestones **not started / not done yet** (backlog / future work, e.g. Direct Reviews).
  - `docs/completed/` — specs for **shipped milestones** (Superadmin, OrgAdmin, phase-3, Dashboard, …).
  - As a milestone moves through its lifecycle, **move its spec between these folders**: `pending/` → `in-progress/` when work starts, `in-progress/` → `completed/` when it ships.
- **Tie spec moves to the GSD milestone lifecycle (REQUIRED):**
  - When a **new milestone starts** (e.g. `/gsd-new-milestone`), move its spec `docs/pending/<spec>.md` → `docs/in-progress/`.
  - When a **milestone completes** (e.g. `/gsd-complete-milestone`, all its phases verified + archived), move its spec `docs/in-progress/<spec>.md` → `docs/completed/` **as part of the completion change**, and update every reference (see next bullet). Completing a milestone without relocating its spec leaves `docs/in-progress/` falsely advertising shipped work.
- **Keep references in sync on every convert/move.** Update every `.planning/` reference (PROJECT.md, REQUIREMENTS.md, `research/SUMMARY.md`, any phase `*-CONTEXT.md` / `*-RESEARCH.md` / `*-UI-SPEC.md`) **and** any §29-style CLAUDE.md mention to the new `.md` path. Section anchors (`§4.1`, `§6.4`) keep working because conversion preserves the numbered headings. Verify with `grep -rn '\.docx' .planning/` returning nothing, and that no reference points at a stale folder (`grep -rn 'docs/in-progress' .planning/` after a completion should return nothing for the just-shipped spec).
- The base `docs/` folder holds **non-spec** working material (e.g. `cost.md`, `sre/`, `superpowers/`) — those are not milestone specs and stay where they are.

---

## 29. Canonical Tag System (v0.8 — milestone "Canonical Tag System")

A per-organisation, self-organising canonical tag vocabulary, built and evolved **inside the existing single GPT enrichment call** — no extra API call, no vector DB. Spans Phases 22–26. This section is the authoritative summary; the binding spec is `docs/in-progress/ReviewBee_Canonical_Tag_Requirements_v1.0.md` (read with the relational reconciliation in `.planning/research/SUMMARY.md` — the spec's §4 JSONB shape is superseded).

### 29.1 Data model (`apps/reviews/models.py`)

- **`OrgCanonicalTag`** — one row per `(organisation, label)` (unique, case-insensitively deduped). Fields: `label` (the canonical string — Title Case, ≤3 words for GPT-proposed labels), `polarity_type` (`always_positive` / `always_negative` / `mixed`), `review_count` (denormalized cache), `polarity_reclassified_at`, timestamps.
- **`ReviewTag.canonical_tag`** — nullable FK → `OrgCanonicalTag` (`on_delete=SET_NULL`). **Label is FK-only**: the canonical string lives ONLY on `OrgCanonicalTag`, never denormalized onto `ReviewTag`. `ReviewTag.label` is the *raw* per-review tag (lowercase) — a separate field, not the canonical label.

### 29.2 Non-negotiable invariants

- **One GPT call.** Canonical mapping happens in the single enrichment prompt (the org's capped vocabulary is injected; GPT maps each tag to an existing canonical label or proposes a new one with a `polarity_type`). Never add a second OpenAI call or a vector DB. Still exactly **one `AiUsageLog` row per enriched review**.
- **`review_count` is derive-on-read.** It is **never incremented inline** in the enrichment hot path (the delete-then-`bulk_create` re-enrichment path would double-count). It is refreshed from a single aggregate by the finalising/merge tasks (and may be recomputed in the weekly job). When writing `OrgCanonicalTag` via `bulk_update`, the field list **must exclude `review_count`** unless you are the refresh path.
- **Rename is O(1).** Renaming a canonical tag updates exactly one `OrgCanonicalTag.label` row; mapped reviews reflect it via the FK join. Do **not** fan out updates across `ReviewTag` rows.
- **Canonical work is org-scoped.** Every aggregation, merge, and reclassification filters by `organisation_id` (§9/§22) — a flip/merge in org A must never read or write org B.
- **No-N+1.** Polarity/count aggregates are single grouped queries (`values(...).annotate(Count(...))`), proven by a `CaptureQueriesContext` query-count test (§6). The canonical analog to copy is `apps/reviews/services/finalise.py::_refresh_review_counts`.

### 29.3 Pipeline & jobs

- **Enrichment fold-in** (`apps/reviews/services/enrichment.py`) — canonical lookup/insert + FK population happen inside the existing `_persist_success` `transaction.atomic()` block: batch `SELECT` + `bulk_create(ignore_conflicts=True)` + re-`SELECT` (race-safe, no transaction poisoning), then set `canonical_tag` on each `ReviewTag`.
- **Initial sync = 4 steps** (Phase 23, §13.5): Fetch → **sequential seed** (first `SEED_PHASE_SIZE` newest reviews, vocabulary stabilises) → **parallel bulk** → **finalising** (`finalize_canonical_tags_task`, `tag-merge` queue: case-insensitive dedup merge, straggler backfill, `review_count` refresh).
- **Daily incremental** routes enrichment to `ai-enrichment-low`; new canonical tags auto-add, no approval.
- **Weekly polarity reclassification** (`reclassify_polarity_task`, Phase 24, `default` queue, Sunday 03:00 UTC): DB-only job flips `always_*` → `mixed` (one-way, sticky) when the opposite `ReviewTag.polarity` exceeds `POLARITY_RECLASSIFY_THRESHOLD` of the tag's reviews over `POLARITY_RECLASSIFY_WINDOW_DAYS`, gated by `POLARITY_RECLASSIFY_MIN_REVIEWS`. Each flip writes one `AuditLog` row.
- **Manual merge** (Phase 25): `merge_canonical_tags` on `tag-merge` under a per-org lock; the user-chosen **target** wins (not higher-count), source re-points + deletes, `review_count` refreshed via aggregate. Progress is a durable `TagMergeJob` row, **HTTP-polled** (no WebSocket — §13.2).

### 29.4 Audit logging — `AuditLog` (`apps/common/models.py`)

The general-purpose audit/event model (Phase 21), surfaced in the Org Activity Log viewer. Reused across the platform (e.g. `review.fetched`, `action_item.*`) and by canonical work. Fields: `organisation`, nullable `actor` (null = system/automated event), `entity_type`, `entity_id`, `action`, `before_data` / `after_data` (JSON). Polarity reclassification writes `entity_type="canonical_tag"`, `action="polarity_reclassified"`, `actor=None`. **Prefer writing to `AuditLog` over a bespoke log model** for user-visible domain events.

### 29.5 Settings (`config/settings/base.py`)

| Setting | Default | Purpose |
|---|---|---|
| `CANONICAL_VOCAB_INJECT_LIMIT` | 200 | Top-N canonical labels (by `review_count`) injected into the prompt — token-growth guardrail |
| `ENRICHMENT_RATE_LIMIT` | `125/m` | **Per-worker** Celery `rate_limit` on `enrich_review_task` (secondary guard) |
| `OPENAI_GLOBAL_RATE_LIMIT` | 500 | **Cross-worker global** OpenAI cap (Redis token bucket, `rate:openai:org`, §7.7) |
| `SEED_PHASE_SIZE` | 50 | Reviews enriched sequentially in the seed pass (newest-first) |
| `POLARITY_RECLASSIFY_THRESHOLD` | 0.15 | Opposite-polarity fraction that flips `always_*` → `mixed` (strict `>`) |
| `POLARITY_RECLASSIFY_WINDOW_DAYS` | 30 | Trailing window (by `Review.review_create_time`) |
| `POLARITY_RECLASSIFY_MIN_REVIEWS` | 10 | Minimum sample before the weekly job acts |

---

## 30. Path-Scoped Rules (`.claude/rules/`)

Committed, glob-scoped instruction files that load **only when a matching file is in context** — keeping the always-loaded CLAUDE.md lean while surfacing per-file reminders exactly when relevant. Each has YAML frontmatter `paths:` (globs) + a short body.

| Rule | `paths:` (loads when working on…) | Reinforces |
|---|---|---|
| `testing-python.md` | `apps/**/tests/*.py`, `**/conftest.py` | §16, §6.9 |
| `testing-frontend.md` | `frontend/**/*.test.tsx` | §16, §26 |
| `selectors.md` | `apps/**/selectors/*.py` | §5, §6 |
| `drf-views.md` | `apps/**/views.py` / `serializers.py` / `*urls.py` | §5, §8, §9, §22 |
| `migrations.md` | `apps/**/migrations/*.py` | §6, §18 |
| `openai-enrichment.md` | `apps/integrations/openai/**`, reviews enrichment/reclassify/finalise services | §14, §29 |

**Convention (so rules and CLAUDE.md don't drift):**

- **Don't duplicate.** CLAUDE.md sections are the **canonical, always-on policy** (your baseline when designing before any file is open). A scoped rule is a **concise per-file checklist that references its CLAUDE.md section** — not a second copy. When a rule and its section conflict, the CLAUDE.md section wins; fix the rule.
- Keep rule bodies short and actionable. Adding a new rule (or changing its `paths:`) → add a row here so this catalogue stays the single source of truth (mirrors §27 for subagents).
- Rules live under `.claude/rules/` and are **committed** (un-ignored in `.gitignore`, like `.claude/agents/`) so the whole team gets them. Personal/local Claude state stays ignored.

---

## 31. Project Skills (`.claude/skills/`)

User-invocable workflows (`/<name>`) that **orchestrate** the subagents (§27) + the knowledge graph + the conventions in this file. Committed and shared (un-ignored in `.gitignore`). A skill = a `SKILL.md` with frontmatter (`name`, `description` with clear WHEN triggers) + an actionable body.

| Skill | Invoke when… | What it does |
|---|---|---|
| `security-checklist` | before a PR / merging any auth, scoping, query, OpenAI, Channels, or deploy change; "security review", "check tenant isolation", "audit permissions" | Runs the project §22 + multi-tenant + Channels/Celery/OpenAI-PII checklist over the diff; delegates to `tenant-security-auditor` / `orm-performance-auditor`; runs bandit/pip-audit; blocks on HIGH. Complements the built-in `/security-review` (generic). |
| `feature-impact` | after building a feature, before "done"/PR; "check impact", "what else needs updating", "run regressions", "did I miss anything" | Computes blast radius via the code-review-graph impact tools, walks the model→…→test→docs layer checklist, runs affected + **full** test suite + `makemigrations --check`, delegates to `orm-performance-auditor` / `tenant-security-auditor` / `test-author`. |

**Conventions:** keep skills as orchestration (don't re-implement what a subagent or `/gsd-*` flow already does); descriptions need explicit trigger phrases so they surface at the right moment; adding/changing a skill → update this catalogue. Skills compose with §24's requirements-first gate, §27 subagents, and §30 rules.
