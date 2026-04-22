# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

---

## 1. Project Overview

This is a **multi-tenant SaaS platform** for managing organisations, their stores, and Google Business Profile reviews. It supports three user roles: **Superadmin**, **Organisation Admin**, and **Staff Admin**.

- **Backend:** Django 6.0+ with Django REST Framework (DRF)
- **Frontend:** Django templates + Tailwind CSS, with React components embedded for complex interactive views (data tables, modals, dashboards)
- **Database:** PostgreSQL
- **Cache / Rate Limiting / Queue backing:** Redis
- **Background jobs (Phase 1):** Django management commands + GCP Cloud Scheduler
- **Background jobs (Phase 2, future):** Celery + Celery Beat
- **External API:** Google Business Profile API (OAuth 2.0, per-store connection)
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
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   ├── celery.py                    # added in Phase 2
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
│   │   ├── tasks.py                 # management-command entry points / Celery tasks
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
│   ├── reviews/                     # Google reviews storage + sync logic
│   │   └── management/
│   │       └── commands/
│   │           ├── fetch_google_reviews.py
│   │           └── refresh_google_tokens.py
│   ├── integrations/                # Google Business Profile API client
│   │   └── google/
│   │       ├── client.py
│   │       ├── oauth.py
│   │       └── exceptions.py
│   └── common/                      # shared utilities, base models, mixins
│       ├── models.py                # TimeStampedModel, UUIDModel
│       ├── pagination.py
│       ├── exceptions.py
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

### Never
- Put business logic in serializers (they validate + shape data only)
- Put business logic in model `save()` (override only for trivial normalization)
- Put multi-step workflows in views
- Call `.objects.create()` directly from a view for anything with side effects

---

## 6. Database — Query Optimization (Strict No-N+1 Policy)

N+1 queries are a **blocker-level bug**. Every list view, every serializer, every template must be audited.

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

**6.12 Use `select_for_update()` inside transactions for row-level locking on critical updates** (e.g., decrementing store allocation counters).

---

## 7. Redis Usage

Redis has three roles in this project. Keep them logically separated by DB index.

| Redis DB | Purpose |
|---|---|
| `0` | Django cache (`django-redis` backend) |
| `1` | DRF throttling / rate limiting |
| `2` | Session store (if not using DB sessions) |
| `3` | Celery broker (Phase 2) |
| `4` | Celery result backend (Phase 2) |

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
        "invite": "5/hour",           # scoped throttle for invite endpoints
        "google_sync": "60/minute",
    },
}
```

### 7.6 Distributed locks (for Google API sync jobs)
Use `redis-py`'s lock primitive to prevent duplicate concurrent syncs per store:
```python
from django_redis import get_redis_connection

def sync_store_reviews(store_id: int):
    r = get_redis_connection("default")
    lock = r.lock(f"lock:google_sync:store:{store_id}", timeout=300, blocking=False)
    if not lock.acquire():
        return   # another worker is already syncing this store
    try:
        _do_sync(store_id)
    finally:
        lock.release()
```

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
- **Invitation tokens:** use `django.core.signing.TimestampSigner` with a 48-hour max age. Store token hash in DB, mark single-use.
- **Password policy:** Django's built-in validators, minimum length 10.

---

## 10. Background Jobs

### Phase 1 (current): Management Commands + Cloud Scheduler
- Each job is a **thin management command** under `apps/<app>/management/commands/`.
- The command calls a **service function**. Business logic stays in the service.
- GCP Cloud Scheduler hits a secured HTTP endpoint (`/internal/jobs/<job_name>/`) that runs the command's service function. Secure with a shared secret header + IP allowlist.
- Jobs must be **idempotent**. Design them to re-run safely.
- Always acquire a Redis lock before processing per-entity jobs (see §7.6).

### Phase 2: Celery + Celery Beat
When migrating: wrap existing service functions with `@shared_task`. Do **not** rewrite business logic in the task.

---

## 11. Google Business Profile Integration

- All Google API code lives in `apps/integrations/google/`.
- OAuth flow is **per-store** (each store owner authorizes the app to access that store's reviews).
- Store refresh tokens **encrypted at rest** using `django-cryptography` or Fernet with a key from GCP Secret Manager.
- Wrap every API call with retry + exponential backoff (`tenacity`).
- Respect Google's rate limits. Use token bucket in Redis.
- Always log `request_id` from Google responses for debugging.
- On `401 invalid_grant`, mark the store's connection as expired and notify the Org Admin.

---

## 12. Transactional Email — Amazon SES

All outbound email goes through Amazon SES. This covers Org Admin invitations, invitation resends, password resets, and any future notification emails.

### 12.1 Integration approach

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

### 12.2 Local development

- **Never send real email from local dev.** Use MailHog (already in `docker-compose.yml`) by overriding the backend in `config/settings/local.py`:
  ```python
  EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
  EMAIL_HOST = "mailhog"
  EMAIL_PORT = 1025
  EMAIL_USE_TLS = False
  ```
- In `config/settings/test.py`, use `django.core.mail.backends.locmem.EmailBackend` so tests capture outgoing mail in `django.core.mail.outbox`.

### 12.3 From-address & domain setup

- **Production from-address:** `noreply@<your-domain>` — must be verified in SES.
- **Domain verification:** complete DKIM + SPF records in DNS before going live. Without DKIM, emails land in spam.
- **Start in the SES sandbox** (can only send to verified addresses). Request production access from AWS before launch.
- **Reply-to:** set a monitored mailbox (e.g. `support@<your-domain>`) so users can reply.

### 12.4 Service-layer usage

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

### 12.5 Templates

- Store email templates under `templates/emails/<name>.html` and `templates/emails/<name>.txt`.
- Always ship **both** plain-text and HTML versions. SES penalises HTML-only senders.
- Use a base template `templates/emails/base.html` with brand colours (yellow primary, black CTA) and a clear support / unsubscribe footer.
- Inline CSS (use `premailer` or `django-premailer`) — email clients ignore `<style>` blocks inconsistently.
- Keep HTML width at **600px** max for mobile compatibility.

### 12.6 Sending must be resilient and async-safe

- **Never block a web request on `send()` for more than a single attempt.** Wrap the call in try/except and log failures.
- In Phase 1 the invitation email is small enough to send synchronously. If latency becomes noticeable, move sending to Django 6's built-in Tasks framework:
  ```python
  from django.tasks import task

  @task()
  def send_invitation_email_task(invitation_id: int) -> None:
      ...
  ```
- In Phase 2+, Celery tasks wrap the same service function. No logic duplication.

### 12.7 Bounces, complaints, and suppression

- Configure an SNS topic for SES bounce, complaint, and delivery notifications.
- Set up an internal webhook endpoint (e.g. `/webhooks/ses/`) secured by SNS signature verification.
- On hard bounce or complaint: mark the user's email as `email_suppressed=True`. Do not attempt to send to suppressed addresses again.
- Never remove suppressions automatically — requires manual review or user-driven re-opt-in.

### 12.8 Rate limits & throttling

- SES has account-level send quotas (starts at 200/day in sandbox, scales after production access).
- Use Redis (see §7) to track per-minute send counts as a safety net — circuit-break and log if the app approaches the SES limit.
- Batch transactional sends are **not** appropriate here; every email is triggered by a discrete user event.

### 12.9 Security

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

### 12.10 Observability

- Log every send with a structured record: `{event: "email.sent", template, to_hash, message_id}`. Hash recipient emails in logs — don't store raw addresses in log aggregators.
- Monitor the SES dashboard for bounce rate (must stay below 5%) and complaint rate (must stay below 0.1%) — exceeding these thresholds leads to SES suspension.
- Alert via Better Stack / Datadog if bounce rate > 3% or complaint rate > 0.05% over a 24-hour window.

### 12.11 Required dependencies

```toml
[project.dependencies]
django-ses = "^4.3.0"
boto3 = "^1.35.0"
premailer = "^3.10.0"     # for CSS inlining at send time if not done at build time
```

### 12.12 Testing

- Use `django.core.mail.backends.locmem.EmailBackend` in tests.
- Every email-sending service must have a test asserting:
  1. An email was sent (`len(mail.outbox) == 1`)
  2. The correct recipient
  3. The correct subject
  4. Key substrings (invitation URL, user's name) appear in both HTML and text bodies
- **Never** let tests hit real SES.

---

## 13. Testing

- **Framework:** `pytest` + `pytest-django`.
- **Factories:** `factory-boy`. One factory per model in `apps/<app>/tests/factories.py`.
- **Coverage:** minimum 85% line coverage on services, selectors, and permissions. Enforced in CI.
- **Structure:** one test file per module (`test_services.py`, `test_selectors.py`, `test_views.py`).
- **Fast tests:** disable migrations in test settings (`MIGRATION_MODULES` → disabled) and use `--reuse-db`.
- **Query-count tests:** every list endpoint must have a test that asserts a fixed query count regardless of result size (see §6.9).
- **Never hit external APIs in tests.** Mock the Google client using `responses` or `respx`.

---

## 14. Pre-commit Rules

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

## 15. Git & Commit Conventions

- **Branch naming:** `feat/`, `fix/`, `chore/`, `refactor/`, `docs/` prefixes. e.g. `feat/org-list-filters`.
- **Commit messages:** Conventional Commits.
  - `feat(organisations): add store count adjustment flow`
  - `fix(reviews): handle expired Google refresh token`
  - `refactor(accounts): extract invitation service`
- **PRs:** one logical change per PR. Include: summary, screenshots for UI changes, migration note, rollout plan if non-trivial.
- **Migrations:** one migration per PR when possible. Name them descriptively, not `0014_auto_20260101`.

---

## 16. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` must run on every PR and include:
1. `pre-commit run --all-files`
2. `mypy`
3. `pytest --cov=apps --cov-fail-under=85`
4. `python manage.py makemigrations --check --dry-run`
5. `python manage.py check --deploy` (production settings)

`.github/workflows/deploy.yml` runs on merge to `main`:
1. Build Docker image
2. Push to Google Artifact Registry
3. Deploy to Cloud Run (staging)
4. Run smoke tests
5. Manual approval gate → production deploy

---

## 17. Docker

- **Base image:** `python:3.12-slim` (multi-stage build).
- **Non-root user** in the final image.
- **`.dockerignore`** must exclude: `.git`, `.venv`, `node_modules`, `__pycache__`, `.env*`, `media/`.
- **Healthcheck endpoint:** `/healthz/` returns 200, `/readyz/` checks DB + Redis.
- **docker-compose** for local dev runs: `web`, `db` (postgres:16), `redis` (redis:7-alpine), `mailhog` (captures outgoing email locally — see §12.2).

---

## 18. Logging & Monitoring

- Use **structured JSON logging** in production (`python-json-logger`).
- Include `request_id`, `user_id`, `organisation_id` in every log record via middleware.
- **Sentry:** auto-capture unhandled exceptions. Scrub PII (emails, names) before send.
- **Better Stack / Datadog:** ship logs via sidecar or direct HTTP. Tag by environment and service.
- **Never log:** passwords, tokens, API keys, full request bodies of auth endpoints.

---

## 19. Security Checklist (enforced in CI where possible)

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

---

## 20. Common Commands

```bash
# Local dev
make up                  # docker-compose up
make migrate             # run migrations
make makemigrations      # create new migrations
make shell               # django shell
make test                # pytest
make lint                # pre-commit run --all-files
make typecheck           # mypy .
make seed                # load fixtures / demo data

# Inside container
python manage.py createsuperuser
python manage.py fetch_google_reviews --store-id=<id>
python manage.py refresh_google_tokens
```

---

## 21. When You (Claude Code) Are Asked to Add Code

Follow this order, every time:

1. **Read** the relevant app's existing `models.py`, `services/`, `selectors/`, `views.py` before writing anything.
2. **Add models** → create migration → verify migration is reversible.
3. **Write services and selectors** with full type annotations.
4. **Write tests first** for services and selectors. Factories go in `tests/factories.py`.
5. **Wire up serializers and views.** Keep them thin.
6. **Add URLs** under the app's `urls.py`, include in `config/urls.py`.
7. **Add permissions.** Never ship a new view without an explicit permission class.
8. **Verify query counts.** Add a `CaptureQueriesContext` test for every list endpoint.
9. **Add/update** the OpenAPI schema (via `drf-spectacular`).
10. **Run** `pre-commit run --all-files` and `pytest` before declaring done.

### Never
- Skip tests "because it's small"
- Call `.objects.filter()` directly from a view for anything beyond trivial read
- Add a field to a model without an explicit `db_index` decision
- Add an endpoint without pagination if it returns a list
- Add an endpoint without throttling
- Use `print()` for debugging — use `logger`
- Commit a `.env` file
- Disable a pre-commit hook without discussion
