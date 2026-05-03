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
- **Background jobs (Phase 3+):** Celery + Celery Beat with two named queues (`google-sync`, `ai-enrichment`)
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
| `rate:openai:org:{organisation_id}` | Per-org OpenAI call counter (token bucket safety net) | rolling 1 min |
| `rate:google:project` | Global Google API call counter (token bucket) | rolling 1 min |

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
- **Two named queues** with separate worker pools:
  - `google-sync` — Google API operations (review fetch, token refresh)
  - `ai-enrichment` — OpenAI calls (slower, must not block faster queues)
  - `default` — everything else (notifications, lightweight fan-outs)

### 12.2 Configuration

```python
# config/settings/base.py
CELERY_BROKER_URL = env("REDIS_URL") + "/3"
CELERY_RESULT_BACKEND = env("REDIS_URL") + "/4"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task":   {"queue": "google-sync"},
    "apps.reviews.tasks.enrich_review_task":      {"queue": "ai-enrichment"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment"},
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
| `retry_failed_enrichments_task` | `ai-enrichment` | Every 6 hours |
| `refresh_google_tokens_task` | `google-sync` | Hourly |

### 12.6 Deployment

- Celery worker, Celery Beat, and the web server run as **separate Cloud Run services** (or separate processes in a GKE pod set).
- All three use the **same Docker image**; the entry command differs per service.
- **Beat instance count: exactly 1.** Multiple Beat instances = duplicate jobs. Enforce at the deployment template.
- **Worker instance count:** scales horizontally per queue based on queue depth. Different scaling profiles per queue (e.g., `ai-enrichment` workers can scale slower since OpenAI is the bottleneck).
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

| Event | Payload Fields | When Sent |
|---|---|---|
| `sync.fetch.progress` | `shop_id, fetched, total_estimate` | After every Google API page is persisted |
| `sync.enrichment.progress` | `shop_id, enriched, fetched` | After every batch of reviews is enriched |
| `sync.complete` | `shop_id, total_fetched, total_enriched, duration_seconds` | When initial sync finishes successfully |
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

Follow this order, every time:

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
12. **Run** `pre-commit run --all-files` and `pytest` before declaring done.

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

## 25. Brand Assets & Logo

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
