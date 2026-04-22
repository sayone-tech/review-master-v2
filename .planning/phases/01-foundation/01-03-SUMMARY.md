---
phase: 01-foundation
plan: 03
subsystem: infra
tags: [docker, vite, tailwind, typescript, alpine, django-vite, templates]

# Dependency graph
requires:
  - phase: 01-01
    provides: Django project scaffold, settings structure, apps/common, pyproject.toml

provides:
  - Multi-stage Dockerfile (builder + runtime, non-root app user, /readyz/ healthcheck)
  - docker-compose.yml with five services: web (8000), db postgres:16 (5432), redis:7 (6379), mailhog (8025/1025), vite node:22 (5173)
  - All compose services have healthchecks; web waits for db/redis/vite via service_healthy
  - frontend/ toolchain: Vite 6, Tailwind v4 via @tailwindcss/vite, TypeScript 5.7, Alpine.js 3.15
  - All 20 UI-SPEC brand tokens in tailwind.config.js (yellow/black/ink/text/... palette)
  - frontend/src/entrypoints/app-shell.ts bundles Alpine.js (no CDN)
  - templates/base.html shell with skip link, Geist fonts, django-vite asset injection
  - templates/partials/shell.html skeleton: bg-black sidebar (240px), bg-bg main, topbar
  - apps/common home view + URL at '/', renders pages/placeholder.html
  - 5 template smoke tests verifying DSYS-01 and DSYS-04 (all passing)

affects:
  - 01-04 (sidebar nav, topbar detail builds on this shell skeleton)
  - 01-05 (component library extends this frontend toolchain)
  - all future plans that render Django templates

# Tech tracking
tech-stack:
  added:
    - Docker multi-stage build (python:3.12-slim)
    - docker-compose v3 with healthchecks + service_healthy
    - Vite 6.0.1
    - "@tailwindcss/vite 4.2.4 (Tailwind v4 Vite plugin)"
    - tailwindcss 4.2.4
    - typescript 5.7.2
    - alpinejs 3.15.11 (bundled via Vite, not CDN)
    - react 19.2.5 + react-dom 19.2.5
    - "@vitejs/plugin-react 6.0.1"
    - lucide-react 1.8.0
    - focus-trap-react 12.0.0
    - django-vite template tags (vite_hmr_client, vite_asset)
    - Geist + Geist Mono fonts via Google Fonts CDN
  patterns:
    - Tailwind v4 uses @tailwindcss/vite plugin, NOT the old postcss pattern
    - Alpine.js bundled through Vite entry (window.Alpine = Alpine; Alpine.start())
    - django-vite dev_mode=True in config/settings/test.py (no build needed for pytest)
    - Shell skeleton: aside.w-sidebar.bg-black + main.bg-bg with data-testid markers

key-files:
  created:
    - Dockerfile
    - docker-compose.yml
    - docker-compose.override.yml
    - frontend/package.json
    - frontend/tsconfig.json
    - frontend/vite.config.ts
    - frontend/postcss.config.js
    - frontend/tailwind.config.js
    - frontend/src/entrypoints/app-shell.ts
    - frontend/src/styles/tailwind.css
    - templates/base.html
    - templates/partials/head.html
    - templates/partials/shell.html
    - templates/pages/placeholder.html
    - apps/common/tests/test_base_template.py
    - static/.gitkeep
  modified:
    - .dockerignore
    - apps/common/views.py (added home view)
    - apps/common/urls.py (registered home at '')
    - config/settings/test.py (added django_vite, DJANGO_VITE dev_mode=True)
    - apps/organisations/managers.py (fixed mypy no-any-return with cast())

key-decisions:
  - "Tailwind v4 @tailwindcss/vite plugin used instead of PostCSS — Tailwind v4 ships its own Vite plugin that replaces the PostCSS approach"
  - "DJANGO_VITE dev_mode=True in config/settings/test.py — avoids requiring a Vite build output (static/dist/manifest.json) during pytest runs"
  - "Alpine.js bundled via Vite app-shell entrypoint — prevents duplicate Alpine instances from CDN + bundle conflict"
  - "static/dist is gitignored (build output) — only static/.gitkeep committed to preserve parent directory"
  - "Shell skeleton uses exact Tailwind classes from UI-SPEC: w-sidebar, bg-black, bg-bg, rounded-logo, border-line"

patterns-established:
  - "Pattern 1: docker-compose depends_on with service_healthy — web service waits for db, redis, and vite to pass healthchecks before starting"
  - "Pattern 2: Django template partials — base.html includes partials/head.html and partials/shell.html for composable layout"
  - "Pattern 3: data-testid attributes on structural elements (sidebar, topbar, main-content) for template smoke tests"
  - "Pattern 4: Tailwind custom tokens declared in tailwind.config.js theme.extend — brand colors referenced as bg-bg, bg-black, text-muted etc."

requirements-completed: [DSYS-01, DSYS-04]

# Metrics
duration: 6min
completed: 2026-04-22
---

# Phase 01 Plan 03: Docker + Vite + Tailwind + Django Shell Summary

**Multi-stage Docker dev stack with Vite 6 + Tailwind v4 + Alpine.js toolchain and Django base template shell rendering the UI-SPEC brand canvas at `/`**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-22T10:15:07Z
- **Completed:** 2026-04-22T10:21:20Z
- **Tasks:** 3
- **Files modified:** 20

## Accomplishments

- Docker dev stack with five services (web, db, redis, mailhog, vite) — all with healthchecks and web waiting on service_healthy conditions
- Frontend toolchain with Vite 6, Tailwind v4 via `@tailwindcss/vite` (NOT the old PostCSS pattern), TypeScript strict, and Alpine.js bundled through Vite
- All 20 UI-SPEC brand tokens declared verbatim in tailwind.config.js (yellow #FACC15 through blue-tint #DBEAFE), plus sidebar/radius/font tokens
- Django shell template with Geist fonts, `{% vite_asset %}` injection, accessible skip link, bg-black sidebar (240px), bg-bg main canvas
- 5 DSYS-01/DSYS-04 template smoke tests passing under config.settings.test with dev_mode=True

## Task Commits

1. **Task 1: Docker dev environment** - `dae77a7` (feat)
2. **Task 2: Vite + Tailwind v4 + TypeScript + Alpine.js** - `c4dc4d5` (feat)
3. **Task 3: Django base template shell + home route + smoke tests** - `0a8193e` (feat)

## Files Created/Modified

- `Dockerfile` - Multi-stage builder + runtime, non-root app user, /readyz/ healthcheck
- `docker-compose.yml` - Five services with healthchecks; web waits for db/redis/vite
- `docker-compose.override.yml` - Local stdin_open/tty for interactive dev
- `.dockerignore` - Added frontend/node_modules, static/dist, .DS_Store
- `frontend/package.json` - Pinned deps: vite 6.0.1, tailwindcss 4.2.4, alpinejs 3.15.11
- `frontend/vite.config.ts` - @tailwindcss/vite plugin, manifest.json build, static/dist outDir
- `frontend/tailwind.config.js` - All 20 brand tokens + fonts + sidebar spacing + border radii
- `frontend/src/entrypoints/app-shell.ts` - Alpine.js bundle entry
- `frontend/src/styles/tailwind.css` - @import "tailwindcss" (Tailwind v4 entrypoint)
- `templates/base.html` - HTML shell with skip link, includes head + shell partials
- `templates/partials/head.html` - Geist fonts preconnect + vite_asset tag
- `templates/partials/shell.html` - Sidebar (bg-black w-sidebar), topbar, main (bg-bg) with data-testids
- `templates/pages/placeholder.html` - Foundation placeholder at /
- `apps/common/views.py` - Added home() view
- `apps/common/urls.py` - Registered home at path('')
- `apps/common/tests/test_base_template.py` - 5 template smoke tests
- `config/settings/test.py` - Added django_vite to INSTALLED_APPS + DJANGO_VITE block with dev_mode=True
- `apps/organisations/managers.py` - Fixed mypy no-any-return via cast()

## Decisions Made

- **@tailwindcss/vite over PostCSS:** Tailwind v4 ships its own Vite plugin. The old PostCSS plugin pattern is deprecated for v4.
- **DJANGO_VITE dev_mode=True in test.py:** Makes `{% vite_asset %}` emit dev tags (http://localhost:5173/...) without needing a built `static/dist/manifest.json`. Keeps test suite fast.
- **Alpine.js via Vite entry:** Bundling Alpine prevents the double-init bug that occurs when CDN + bundle both call `Alpine.start()`. `window.Alpine = Alpine` exposes it for inline `x-data` directives.
- **static/dist gitignored:** The `static/dist/` directory is build output and correctly gitignored. Only `static/.gitkeep` is committed to preserve the parent directory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed mypy no-any-return in apps/organisations/managers.py**
- **Found during:** Task 3 (template shell commit triggered pre-commit mypy)
- **Issue:** `annotate_store_counts()` returned `Any` (from `QuerySet.annotate()` return type in django-stubs). Pre-commit mypy hook failed even though this file was from Plan 02 unstaged work.
- **Fix:** Rewrote managers.py to use `models.QuerySet` without type parameter + `cast(OrganisationQuerySet, self.annotate(...))` to satisfy mypy strict mode. Removed unused `TYPE_CHECKING` import that caused ruff to remove `Organisation` import in a loop.
- **Files modified:** `apps/organisations/managers.py`
- **Verification:** `mypy apps/organisations/ apps/common/ apps/accounts/ config/` → "Success: no issues found in 29 source files"
- **Committed in:** `0a8193e` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Fix was necessary to pass pre-commit hooks. No scope creep — the organisations manager was pre-existing unstaged work from Plan 02 that needed the type fix before it could be committed alongside Task 3 files.

## Issues Encountered

- Ruff's isort/unused-import detection conflicted with the `TYPE_CHECKING` + string annotation pattern in `OrganisationQuerySet(models.QuerySet["Organisation"])` — ruff removed `Organisation` from the `TYPE_CHECKING` import because it didn't see the string usage, leaving `Organisation` undefined for mypy. Resolution: use `models.QuerySet` without generic type parameter + `cast()` pattern.
- `static/dist/.gitkeep` cannot be committed because `static/dist/` is in `.gitignore`. Plan's intent (keep dir in git) is satisfied by `static/.gitkeep` at the parent level; Vite creates `static/dist/` on first build.

## User Setup Required

None — no external service configuration required for this plan. Docker Compose handles all services locally.

## Next Phase Readiness

- `docker-compose up -d` will start all 5 services once the Docker image is built
- Frontend toolchain is ready for Plan 01-04 (sidebar nav, topbar) and 01-05 (component library)
- Shell skeleton has the correct colour classes and data-testid markers; Plan 01-04 fills in nav items and topbar avatar
- Vite production build (`cd frontend && npm run build`) produces `static/dist/manifest.json` with the `app-shell` entry hashed — required for production django-vite mode
- Known follow-up: sidebar nav items, topbar avatar dropdown, responsive collapse — Plan 01-04

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
