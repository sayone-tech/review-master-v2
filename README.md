# Review Master

A multi-tenant SaaS platform for managing organisations, their shops, and Google Business Profile reviews. Org Admins and Staff view, reply to and action reviews — backed by Celery background sync, AI enrichment (GPT-4o-mini), AI reply credits and an action items workflow. Superadmins manage organisations, AI costs and AI pricing.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.2, Python 3.12, Django REST Framework 3.17 |
| Database | PostgreSQL 16 (Amazon RDS in production) |
| Cache / broker / queue | Redis 7 |
| Background jobs | Celery 5.6, Celery Beat (django-celery-beat, DB-backed schedules), five named queues |
| Real-time | Django Channels 4.3 (WebSocket sync progress) |
| AI | OpenAI GPT-4o-mini via the `openai` SDK, LangSmith tracing, Pydantic response parsing |
| Frontend | Django templates + Tailwind CSS v4, React 18 widgets (Vite) |
| Transactional email | Resend (default) or Amazon SES via `django-ses`; MailHog locally |
| Monitoring | Sentry (errors), structured JSON logging, CloudWatch Logs |
| Auth | Django session auth, custom User model with role enum |
| Token encryption | `django-fernet-encrypted-fields` (Google OAuth refresh tokens) |
| CI/CD | GitHub Actions — lint → type-check → test → deploy |
| Hosting | AWS `ap-south-1`: single EC2 running Docker Compose, RDS PostgreSQL, ECR, Caddy (auto-TLS), Secrets Manager |

---

## User Roles

| Role | Access |
|---|---|
| **Superadmin** | Global control plane — organisations, store allocation, Org Admin accounts, AI credits, AI cost and AI pricing |
| **Org Admin** | Full access within their organisation — regions, shops, team, all reviews, brand and shop action items |
| **Staff Admin** | Scoped to assigned shops — shop-level reviews and shop-scoped action items only; brand-scoped items are never visible |

---

## Architecture

### Pattern: Services / Selectors

Views are thin. Business logic lives in two module types:

- **Services** (`apps/<app>/services/`) — write-side functions that change state, wrapped in `@transaction.atomic` when touching multiple tables
- **Selectors** (`apps/<app>/selectors/`) — read-side functions that return data; no mutations

Celery tasks are thin wrappers that call service functions. Business logic never lives in task bodies. Full conventions: [CLAUDE.md](CLAUDE.md).

### App layout (`apps/`)

```text
apps/
├── accounts/          # Custom User model, auth, invitations, team
├── organisations/     # Organisation model, Superadmin management
├── regions/           # Regions within an organisation
├── shops/             # Shops, Google Business Profile connection, review targets
├── reviews/           # Reviews, replies, sync, enrichment, canonical tags
├── action_items/      # Action items — lifecycle, extraction, categories
├── notifications/     # In-app bell, delivery model
├── credits/           # Per-shop monthly AI reply credits + ledger
├── dashboard/         # Org dashboard aggregates
├── reports/           # Reports
├── reply_templates/   # Saved reply templates
├── integrations/
│   ├── google/        # OAuth client, token refresh, API calls
│   └── openai/        # SDK wrapper, prompts, parser, pricing, AI cost + pricing management, LiteLLM sync
└── common/            # TimeStampedModel, AuditLog, locks, retry, throttling, pagination
```

### Celery queues

| Queue | Used for |
|---|---|
| `google-sync` | Google API calls — review fetch, token refresh |
| `ai-enrichment-high` | OpenAI enrichment for a shop's initial sync |
| `ai-enrichment-low` | Daily incremental enrichment and retries |
| `tag-merge` | Canonical tag merge / finalising jobs |
| `default` | Notifications, credits lapse/reaper, weekly jobs, lightweight fan-outs |

### Redis DB allocation

| DB | Purpose |
|---|---|
| 0 | Django cache |
| 1 | DRF rate limiting |
| 2 | Session store |
| 3 | Celery broker |
| 4 | Celery result backend |
| 5 | Channels layer |

---

## Local Development

### Prerequisites

- Docker + Docker Compose
- (Optional) `uv` for running linters/formatters outside containers

### Start everything

```bash
make up        # docker-compose -p review-master up (foreground — shows logs)
```

> Add `-d` to `docker-compose -p review-master up` to run detached. The `-p review-master` flag pins the Compose project name so container and volume names stay stable; all `make` targets apply it.

This starts `db` (PostgreSQL 16), `redis`, `mailhog`, `vite` (Tailwind + React dev server), `web` (Django), `worker` (Celery), `beat` (Celery Beat) and `flower` (dev only, :5555). Migrations run automatically on startup. The app is at **http://localhost:8000**; MailHog at **http://localhost:8025**.

### Create a superadmin

```bash
docker-compose -p review-master exec web python manage.py createsuperuser
```

### Seed demo data (optional)

```bash
make seed
```

### AI pricing

Migrations seed the GPT-4o-mini price, so enrichment works on a fresh database. After `manage.py flush` the table is empty — re-seed it:

```bash
docker exec -i review-master-web-1 python manage.py shell < scripts/seed_pricing.py
```

Prices are managed on the Superadmin **AI Pricing** page (`/admin/ai-pricing/`).

### Common make targets

```bash
make up              # start the stack (foreground)
make down            # stop the stack
make rebuild         # clean rebuild — removes the stale static volume, rebuilds images, starts the stack
make migrate         # run migrations
make makemigrations  # create new migrations
make shell           # Django shell
make test            # pytest (inside the web container)
make lint            # pre-commit run --all-files
make typecheck       # mypy
make fmt             # ruff format + ruff check --fix
make seed            # load fixtures/demo.json
make worker          # Celery worker (foreground)
make beat            # Celery Beat (foreground)
make flower          # Flower on :5555 (dev only)
```

### Styles missing after a rebuild

Tailwind CSS and React bundles are build artifacts (gitignored). Locally, a named volume (`static_css`) is shared between `vite` and `web`. If the site loads without styles after a rebuild, use `make rebuild` — not `docker-compose up --build`. It only removes the `static_css` volume; database and Redis data are kept. If new classes don't appear while the stack is running, run `docker compose exec vite npm run css:build` and hard-reload.

---

## Environment Variables

Copy `.env.example` to `.env`. Most values are optional locally.

```bash
cp .env.example .env
```

**Core**

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Yes | `config.settings.local` locally |
| `DJANGO_SECRET_KEY` | Yes | Change for production |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated |
| `DJANGO_VITE_DEV_MODE` | Local | `True` locally so pages load assets from the vite container |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string (DB index is appended per role) |
| `SITE_URL` | Yes | Used in email links |
| `ENVIRONMENT` | No | `local` / `staging` / `production` (Sentry, LangSmith project name) |
| `SENTRY_DSN` | No | Leave empty locally |

**Google (shop connection)**

| Variable | Required | Notes |
|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | For shop connect | Google Cloud Console → Credentials |
| `GOOGLE_OAUTH_CLIENT_SECRET` | For shop connect | |
| `GOOGLE_OAUTH_REDIRECT_URI` | For shop connect | Must match the console exactly, e.g. `http://localhost:8000/oauth/google/callback/` |
| `FERNET_SALT_KEY` | Production | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

**OpenAI and LangSmith**

| Variable | Required | Notes |
|---|---|---|
| `OPENAI_API_KEY` | Production | Leave empty locally to skip AI calls |
| `OPENAI_MODEL` | No | Default `gpt-4o-mini-2024-07-18`. The model must have a price on the AI Pricing page, or the deploy check fails |
| `OPENAI_MAX_RETRIES` | No | Default `3` |
| `OPENAI_REVIEW_TEXT_MAX_CHARS` | No | Default `4000` |
| `LANGSMITH_API_KEY` | No | Leave empty to disable tracing |
| `LANGSMITH_PROJECT` | No | Default `review-platform-{ENVIRONMENT}` |
| `LANGSMITH_ENDPOINT` | No | `https://aws.api.smith.langchain.com` for the AWS-hosted endpoint |

**Sync and enrichment tuning** (all optional — defaults shown in `.env.example`)

`INITIAL_SYNC_PAGE_SIZE`, `INCREMENTAL_SYNC_INTERVAL_HOURS`, `INCREMENTAL_SYNC_JITTER_MINUTES`, `ENRICHMENT_BATCH_SIZE`, `ENRICHMENT_RATE_LIMIT`, `CANONICAL_VOCAB_INJECT_LIMIT`

**AI pricing** (all optional — defaults built in)

| Variable | Default | Notes |
|---|---|---|
| `AI_PRICING_LOOKBACK_DAYS` | `90` | Usage window for the missing-price alert and the LiteLLM sync |
| `AI_PRICING_KNOWN_FREE_MODELS` | `omni-moderation-latest,text-moderation-latest,text-moderation-stable` | Free models never flagged as missing a price |
| `AI_PRICING_MISSING_CACHE_TTL_SECONDS` | `600` | Missing-price check cache |
| `AI_PRICING_SYNC_SOURCE_URL` | LiteLLM's `model_prices_and_context_window.json` on GitHub | Must be `https://` |
| `AI_PRICING_SYNC_TOLERANCE_USD_PER_1M` | `0.000001` | Price difference treated as unchanged |

The LiteLLM sync on/off switch lives in the database (AI Pricing page), not in the environment.

**Email**

| Variable | Required | Notes |
|---|---|---|
| `DEFAULT_FROM_EMAIL` / `DEFAULT_REPLY_TO` | Yes | |
| `EMAIL_PROVIDER` | Production | `resend` (default) or `ses`. Locally MailHog captures everything |
| `RESEND_API_KEY` | When `resend` | |
| `AWS_SES_REGION_NAME`, `AWS_SES_FROM_EMAIL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SES_CONFIGURATION_SET` | When `ses` | From-address must be SES-verified |

In production all values come from the AWS Secrets Manager secret `review-master/prod` (see [deployment/README.md](deployment/README.md)) — never from a committed `.env`.

---

## Testing

```bash
make test
# or with coverage
docker-compose -p review-master exec web pytest apps/ --cov=apps --cov-report=term-missing
# frontend
cd frontend && npx vitest run
```

- Minimum 85% line coverage on services, selectors and permissions — enforced in CI
- External APIs (Google, OpenAI, LiteLLM) are mocked in tests
- Celery tasks run synchronously in tests (`CELERY_TASK_ALWAYS_EAGER = True`)

---

## Production (AWS)

Full details: [deployment/README.md](deployment/README.md). Infrastructure is Terraform in the sibling `review-master-terraform` repo.

- **Region:** `ap-south-1` (Mumbai)
- **Compute:** one EC2 instance (`t4g.medium`, Graviton) running `deployment/compose/docker-compose.prod.yml` — `caddy`, `web`, `worker`, `beat`, `redis`
- **Database:** Amazon RDS PostgreSQL in private subnets, automated backups
- **TLS / proxy:** Caddy with Let's Encrypt (no ALB)
- **Images:** built by GitHub Actions, pushed to private ECR
- **Secrets:** Secrets Manager `review-master/prod` → `/etc/review-master.env` on deploy; RDS password in SSM Parameter Store
- **Logs:** CloudWatch Logs group `/review-master/prod`
- **Access:** no public SSH — operators use SSM Session Manager

| Service | Command |
|---|---|
| Web | `daphne -b 0.0.0.0 -p 8000 --proxy-headers config.asgi:application` |
| Worker | `celery -A config worker -Q google-sync,ai-enrichment-high,ai-enrichment-low,tag-merge,default` |
| Beat | `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler` |

> **Beat must run as exactly one instance.** Multiple Beat instances cause duplicate jobs.
>
> **Flower is never deployed to production.** Dev/staging only.

**Deploys** (`.github/workflows/deploy.yml` → `deployment/scripts/deploy.sh` over SSM Run Command): pull image → `migrate` → `check --deploy --database default` (fails the deploy if the configured OpenAI model has no price) → `collectstatic` → restart services → healthcheck.

### Healthchecks

- `/healthz/` — returns 200
- `/readyz/` — checks DB + Redis

---

## Key Workflows

### Adding a new shop

1. Org Admin opens Shops → Add Shop
2. Google OAuth popup; the user authorises the app for that Business Profile location
3. Encrypted refresh token is stored; the shop is marked connected
4. `initial_backfill_task` is enqueued on `google-sync`
5. Real-time progress UI (WebSocket): fetch → tag vocabulary → AI enrichment → finalising
6. Reviews appear in the Reviews list

### Review enrichment

Each review runs `enrich_review_task` (`ai-enrichment-high` during initial sync, `ai-enrichment-low` otherwise), which calls `enrich_review()`:

1. Acquires a Redis lock (`lock:enrich:review:{id}`)
2. Returns immediately if `enrichment_status` is already `SUCCESS`
3. Calls GPT-4o-mini once with a combined prompt (sentiment, tags with canonical mapping, action items)
4. Parses the structured JSON via Pydantic
5. Persists results, writes one `AiUsageLog` row (cost from `AiPricing`), marks `SUCCESS`
6. Extracted action items become `ActionItem` rows

### AI cost and pricing (Superadmin)

- **AI Cost** (`/admin/ai-cost/`) — OpenAI spend by organisation, shop, request type and model for any date range
- **AI Pricing** (`/admin/ai-pricing/`) — add or schedule model prices (append-only, no backdating), alerts for models used without a price, and an optional weekly LiteLLM price sync that never overrides hand-set prices

### Notifications

- One summary notification per sync batch (not per review), e.g. "5 new reviews at Shop Name"
- Initial backfill never notifies — only incremental syncs
- Org Admins see all notifications; Staff see only their shops

---

## Known Dev Environment Notes

- `manage.py flush` wipes `AiPricing` data and Celery Beat schedules. Re-seed pricing with `scripts/seed_pricing.py`; Beat schedules come back from their data migrations on the next `migrate`.
- The Google Business Profile API needs Google's production approval before shop connections work in production. Locally you can test OAuth by registering `http://localhost:8000/oauth/google/callback/` as an authorised redirect URI.
- Locally, with an `OPENAI_API_KEY` in `.env`, a few enrichment tests can call OpenAI's moderation endpoint for real; leave the key empty when running the test suite.
