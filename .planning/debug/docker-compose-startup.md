---
status: awaiting_human_verify
trigger: "Investigate and fix all Docker Compose startup failures for this Django project until every service runs cleanly."
created: 2026-05-02T00:00:00Z
updated: 2026-05-02T00:00:00Z
---

## Current Focus

hypothesis: Three root causes identified. All three need fixing simultaneously.
test: Fix all three and rerun docker compose
expecting: All services start cleanly
next_action: Apply all fixes to docker-compose.yml then verify

## Symptoms

expected: All services (web, worker, beat, flower, vite, db, redis) start cleanly and remain running
actual: Services crash with errors. Most recent error: beat crashes with "relation django_celery_beat_clockedschedule does not exist" because beat starts before web finishes running migrations.
errors: |
  beat-1: relation "django_celery_beat_clockedschedule" does not exist
  worker-1 exited with code 2
  beat-1 exited with code 2
  web-1 exited with code 2 (was fixed)
  flower-1 exited with code 2
reproduction: docker compose -p review-master up --build
started: Multiple rounds of fixes attempted. Current Dockerfile and docker-compose.yml have partial fixes applied.

## Eliminated

- hypothesis: venv path mismatch (web exits code 2)
  evidence: Dockerfile already has correct uv venv /venv and UV_PROJECT_ENVIRONMENT=/venv in runtime stage
  timestamp: 2026-05-02T00:01:00Z

## Evidence

- timestamp: 2026-05-02T00:00:00Z
  checked: Dockerfile
  found: Builder uses `uv venv /venv && uv sync --frozen --no-install-project`. Runtime sets VIRTUAL_ENV=/venv and UV_PROJECT_ENVIRONMENT=/venv. Path is /venv/bin. CMD is python manage.py runserver.
  implication: venv path fix is in place. web service also runs `uv sync --frozen` in its command.

- timestamp: 2026-05-02T00:00:00Z
  checked: docker-compose.yml
  found: worker, beat, flower all depend on `web: condition: service_healthy`. Web healthcheck is readyz at /readyz/ with start_period=60s. readyz only checks DB + Redis connectivity, NOT whether migrations have completed.
  implication: Core timing issue — readyz passes as soon as DB is reachable, but migrations may still be running. beat starts, tries to use django_celery_beat tables that don't exist yet.

## Resolution

root_cause: |
  Four distinct root causes found:
  1. VITE shell `&` precedence: Command `A && B && C & D` makes D run immediately without waiting for A. `npm run dev` ran before `npm install` finished → "sh: vite: not found" (exit 127).
  2. Migrations race: `readyz` only checked DB+Redis connectivity, not whether migrations completed. worker/beat/flower depended on `web: service_healthy` but web became healthy as soon as the DB was reachable (before `migrate` finished). beat then crashed with "relation django_celery_beat_clockedschedule does not exist".
  3. Vite host: `DJANGO_VITE_DEV_SERVER_HOST` was hardcoded to "localhost" in base.py. Inside Docker, vite runs on the `vite` hostname.
  4. Wrong healthchecks for Celery services: beat/worker/flower inherited the Dockerfile HEALTHCHECK (curl to Django's /readyz/) but none of them run a Django web server. beat had no `pgrep` available in the slim image.
fix: |
  1. Fixed vite command: `npm install && ... && (npm run css:watch & npm run dev -- --host 0.0.0.0)` — parens group the concurrent part AFTER npm install completes.
  2. Added `MigrationExecutor` check to `readyz` view: uses `executor.migration_plan()` to detect unapplied migrations and returns 503 until schema is complete.
  3. Added `DJANGO_VITE_DEV_SERVER_HOST: vite` to web service env; updated base.py to read it via `env("DJANGO_VITE_DEV_SERVER_HOST", default="localhost")`.
  4. Added proper per-service healthchecks in docker-compose.yml: worker uses `celery inspect ping` checking for "OK", beat uses `/proc/*/cmdline` grep for "celery.*beat", flower uses `curl /healthcheck`.
  5. Increased Dockerfile HEALTHCHECK start_period from 60s → 120s and retries from 3 → 6 to accommodate migration time.
verification: |
  Clean `docker compose -p review-master up -d` from scratch with volumes deleted. All 8 services (db, redis, mailhog, vite, web, worker, beat, flower) reached status "healthy". readyz returned `{"status":"ready","db":"ok","redis":"ok","migrations":"ok"}`.
files_changed:
  - docker-compose.yml
  - Dockerfile
  - apps/common/views.py
  - config/settings/base.py
