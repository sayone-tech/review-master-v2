# Review Master

A multi-tenant SaaS platform for managing organisations, their stores, and Google Business Profile reviews. Org Admins and Staff can view, respond to, and action reviews — backed by Celery background sync, AI enrichment (GPT-4o-mini), and an action items workflow.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.2, Python 3.12, Django REST Framework 3.17 |
| Database | PostgreSQL 16 |
| Cache / broker / queue | Redis 7 |
| Background jobs | Celery 5.6, Celery Beat (django-celery-beat), two named queues |
| Real-time | Django Channels 4.3 (WebSocket sync progress) |
| AI enrichment | OpenAI GPT-4o-mini via `openai` SDK, LangSmith tracing, Pydantic response parsing |
| Frontend | Django templates + Tailwind CSS v4, React 18 widgets (Vite) |
| Transactional email | Amazon SES via `django-ses`, MailHog locally |
| Monitoring | Sentry (errors), structured JSON logging |
| Auth | Django session auth, custom User model with role enum |
| Token encryption | `django-fernet-encrypted-fields` (Google OAuth refresh tokens) |
| CI/CD | GitHub Actions — lint → type-check → test → deploy |
| Hosting | Google Cloud Run / GKE, Docker |

---

## User Roles

| Role | Access |
|---|---|
| **Superadmin** | Global control plane — creates and manages organisations, allocates store slots, manages Org Admin accounts |
| **Org Admin** | Full access within their organisation — manages regions, shops, team members, views all reviews, creates brand and shop action items |
| **Staff Admin** | Scoped to assigned shops — views shop-level reviews and shop-scoped action items only; brand-scoped items are never visible |

---

## What's Shipped

### v1.0 — Superadmin module
- Login, logout, password reset, session management
- Organisation list — search, filter by status/type, pagination
- Create, view, edit, enable, disable, delete (soft-delete) organisations
- Store allocation adjustment per organisation
- Invitation token flow — send on create, resend; atomic invalidate + re-issue
- Org Admin account activation — token-gated, password strength indicator
- Superadmin profile — name edit in place, password change

### v0.2 — Org Admin module
- Org Admin dashboard with personalised welcome card and zero-regions setup banner
- Regions — list, create (race-safe auto-ID via `django-sequences`), edit, delete (blocked when shops exist)
- Shops — list, connect via Google OAuth popup (COOP/Safari/Redis-polling handled), view/edit/activate/deactivate/reconnect; Fernet-encrypted tokens
- Team — invite Manager or Staff (region+store scoped), edit, enable/disable (immediate session termination), remove, resend; self-protection + last-manager guards
- 6 transactional emails — all HTML + plain-text via Amazon SES

### v0.3 — Reviews and Action Items
- **Celery infrastructure** — `google-sync` and `ai-enrichment` queues, Celery Beat (DB-backed schedules), Flower (dev only), Redis distributed locks, Channels WebSocket layer
- **Review sync** — initial backfill with real-time progress UI (WebSocket), 6-hour incremental sync, reply submission
- **Reviews list** — filters (shop, rating, sentiment, source, date range, search), pagination, inline reply, AI enrichment tags and sentiment badges
- **AI enrichment pipeline** — GPT-4o-mini single combined call per review (sentiment + tags + action items), `AiUsageLog`, `AiPricing` (time-versioned), LangSmith tracing, cost calculator
- **Action Items** — brand/shop scoped, manual creation, status workflow (To Do → In Progress → Complete / Won't Do), assignee, due date, notes, priority, inline reply preview
- **Notification bell** — in-app bell with unread count, summary notifications per sync batch (not per review)

---

## Architecture

### Pattern: Services / Selectors

Views are thin. Business logic lives in two module types:

- **Services** (`apps/<app>/services/`) — write-side functions that change state, always wrapped in `@transaction.atomic` when touching multiple tables
- **Selectors** (`apps/<app>/selectors/`) — read-side functions that return data; no mutations

Celery tasks are thin wrappers that call service functions. Business logic never lives in task bodies.

### App layout (`apps/`)

```
apps/
├── accounts/          # Custom User model, auth, invitations
├── organisations/     # Organisation model, Superadmin management
├── stores/            # Store model, per-org, Google Place linkage
├── reviews/           # Reviews, replies, sync, enrichment orchestration
│   ├── tasks.py       # Celery tasks (thin wrappers)
│   ├── consumers.py   # Channels SyncProgressConsumer
│   └── services/      # sync.py, replies.py, enrichment.py
├── action_items/      # Action items — lifecycle, extraction, selectors
├── notifications/     # In-app bell, delivery model
├── integrations/
│   ├── google/        # OAuth client, token refresh, API calls
│   └── openai/        # SDK wrapper, prompts, parser, pricing, tracing
└── common/            # TimeStampedModel, locks, retry, throttling, pagination
```

### Celery queues

| Queue | Workers | Used for |
|---|---|---|
| `google-sync` | Scale horizontally | Google API calls — review fetch, token refresh |
| `ai-enrichment` | Scale conservatively | OpenAI calls |
| `default` | Standard | Notifications, lightweight fan-outs |

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
docker-compose -p review-master up
```

> Runs in the foreground so you see logs in the terminal. Add `-d` to run detached.
> The `-p review-master` flag pins the Compose **project name** so container and volume
> names (e.g. `review-master_static_css`) stay stable regardless of the directory you cloned
> into. `make up` and the other `make` targets apply this automatically.

This starts: `db` (PostgreSQL 16), `redis` (Redis 7), `mailhog` (email capture), `vite` (Tailwind + React dev server), `web` (Django), `worker` (Celery), `beat` (Celery Beat).

Django automatically runs migrations on startup. The app is available at **http://localhost:8000**.

### Create a superadmin

```bash
docker-compose -p review-master exec web python manage.py createsuperuser
```

### Seed demo data (optional)

```bash
make seed
```

### Seed AI pricing (required for enrichment to work)

After a fresh database or after `manage.py flush`, the `AiPricing` table is empty and enrichment tasks will crash. Seed it:

```bash
docker exec -i review-master-web-1 python manage.py shell < scripts/seed_pricing.py
```

This creates a GPT-4o-mini pricing row at the published rates ($0.15 / $0.60 / $0.075 per 1M tokens). Safe to run multiple times — idempotent.

### Common make targets

```bash
make up              # docker-compose -p review-master up  (foreground — shows logs)
make down            # docker-compose -p review-master down
make rebuild         # clean rebuild — removes stale static volume, rebuilds images, starts stack
make migrate         # run migrations
make makemigrations  # create new migrations
make shell           # Django shell
make test            # pytest (runs inside web container)
make lint            # pre-commit run --all-files
make typecheck       # mypy
make fmt             # ruff format + ruff check --fix
make seed            # load fixtures/demo.json
make worker          # start the Celery worker (foreground)
make beat            # start Celery Beat (foreground)
make flower          # start Flower on :5555 (dev only)
```

### Rebuilding Docker (styles disappear after rebuild)

Tailwind CSS and React bundles are gitignored, so they are built inside Docker:

- The **Dockerfile** bakes CSS and JS into the image via a frontend build stage (Node 22 → `npm run css:build` → `vite build`).
- In local dev, a **named Docker volume** (`static_css`) is shared between the `vite` and `web` containers so vite's css:watch keeps the CSS live without needing a host filesystem write.

If you rebuild and styles disappear, it means the `static_css` volume has a stale file. Use:

```bash
make rebuild
```

This removes the stale volume, rebuilds the images, and starts the stack — Docker re-seeds the volume from the freshly built image. **Do not use `docker-compose up --build` directly** after changing CSS-related files; always use `make rebuild`.

> **Note:** `make rebuild` only removes the `static_css` volume — your database (`postgres_data`) and Redis data are preserved.

### Email

All outgoing email is captured by MailHog in local dev. No real emails are sent.

- MailHog UI: **http://localhost:8025**

---

## Environment Variables

Copy `.env.example` to `.env` and fill in what you need. Most are optional locally.

```bash
cp .env.example .env
```

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Change for production |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `GOOGLE_OAUTH_CLIENT_ID` | For shop connect | From Google Cloud Console |
| `GOOGLE_OAUTH_CLIENT_SECRET` | For shop connect | From Google Cloud Console |
| `GOOGLE_OAUTH_REDIRECT_URI` | For shop connect | Must match Google Console exactly |
| `FERNET_SALT_KEY` | For shop connect | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `OPENAI_API_KEY` | For AI enrichment | Leave empty to skip enrichment |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini-2024-07-18` |
| `LANGSMITH_API_KEY` | No | Leave empty to disable LangSmith tracing |
| `SENTRY_DSN` | No | Leave empty locally |
| `AWS_ACCESS_KEY_ID` | Production only | SES credentials — MailHog is used locally |
| `AWS_SECRET_ACCESS_KEY` | Production only | |
| `AWS_SES_FROM_EMAIL` | Production only | Must be SES-verified |

---

## Testing

```bash
make test
# or with coverage
docker-compose -p review-master exec web pytest apps/ --cov=apps --cov-report=term-missing
```

- Minimum 85% line coverage on services, selectors, and permissions — enforced in CI
- External APIs (Google, OpenAI) are always mocked in tests
- Celery tasks run synchronously in tests (`CELERY_TASK_ALWAYS_EAGER = True`)

---

## Production Architecture

Three separate Cloud Run services, all using the same Docker image with different entry commands:

| Service | Command |
|---|---|
| Web | `daphne -b 0.0.0.0 -p 8000 config.asgi:application` |
| Worker | `celery -A config worker -Q google-sync,ai-enrichment,default --concurrency=8` |
| Beat | `celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler` |

> **Beat must run as exactly one instance.** Multiple Beat instances cause duplicate jobs.

> **Flower must never be deployed to production.** Dev/staging only.

### Healthchecks

- `/healthz/` — returns 200
- `/readyz/` — checks DB + Redis

---

## Key Workflows

### Adding a new shop

1. Org Admin navigates to Shops → Add Shop
2. Google OAuth popup opens; user authorises the app for that Google Business Profile location
3. Encrypted refresh token is stored; shop is marked connected
4. `initial_backfill_task` is enqueued on the `google-sync` queue
5. Real-time progress UI (WebSocket) shows fetch + enrichment progress
6. Once complete, reviews appear in the Reviews list

### Review enrichment

Each review triggers `enrich_review_task` on the `ai-enrichment` queue. The task calls `enrich_review()` which:

1. Acquires a Redis lock (`lock:enrich:review:{id}`)
2. Checks `enrichment_status` — returns immediately if already `SUCCESS`
3. Calls GPT-4o-mini with a single combined prompt (sentiment + tags + action items)
4. Parses the structured JSON response via Pydantic
5. Persists results, writes to `AiUsageLog`, transitions status to `SUCCESS`
6. Extracted action items are created as `ActionItem` rows

### Notifications

- Summary notification per sync batch (not per review) — "5 new reviews at Shop Name"
- Initial backfill never generates notifications — only incremental syncs
- Org Admins see all notifications; Staff see only shop-scoped notifications

---

## Project Milestones

| Milestone | Status | Phases | Features |
|---|---|---|---|
| v1.0 | Shipped 2026-04-27 | 1–5 | Superadmin control plane |
| v0.2-org-admin | Shipped 2026-04-30 | 6–9 | Org Admin — regions, shops, team |
| v0.3-reviews-and-action-items | In progress | 10–13 | Reviews, AI enrichment, action items |

---

## Known Dev Environment Notes

- After `manage.py flush`, both `AiPricing` data and Celery Beat schedules are wiped. Re-seed `AiPricing` with `scripts/seed_pricing.py`. Beat schedules are re-created from the data migration on the next `migrate`.
- The Google Business Profile API requires production approval from Google before shop connections work in production. In local dev you can test OAuth flow if you register `http://localhost:8000/oauth/google/callback/` as an authorised redirect URI in Google Cloud Console.
- Tailwind CSS and React bundles are gitignored build artifacts. If the site loads without styles after a Docker rebuild, run `make rebuild` — not `docker-compose up --build`. See the "Rebuilding Docker" section above.
