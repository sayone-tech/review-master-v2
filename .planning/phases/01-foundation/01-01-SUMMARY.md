---
phase: 01-foundation
plan: "01"
subsystem: infra
tags: [django, drf, uv, pre-commit, ruff, mypy, bandit, pytest, python-json-logger]

# Dependency graph
requires: []
provides:
  - Django 6.0.2 project shell with config/ settings package (base/local/production/test)
  - uv-managed Python deps with pinned versions and uv.lock
  - Pre-commit hooks enforcing ruff, mypy, bandit, gitleaks, django-upgrade
  - apps/common with TimeStampedModel, UUIDModel abstract bases
  - Health endpoints /healthz/ and /readyz/ with passing tests
  - Makefile for common dev commands
affects: [02-accounts, 03-organisations, 04-ui, 05-reviews]

# Tech tracking
tech-stack:
  added:
    - django==6.0.2
    - djangorestframework==3.17.1
    - django-redis==5.4.0
    - django-environ==0.11.2
    - drf-spectacular==0.28.0
    - django-vite==3.1.0
    - python-json-logger==3.2.0
    - psycopg[binary]==3.2.3
    - pytest==8.3.3 + pytest-django==4.9.0
    - ruff==0.15.11
    - mypy==1.13.0 + django-stubs==5.1.1
    - bandit==1.8.0
    - factory-boy==3.3.3
    - django-debug-toolbar==4.4.6
  patterns:
    - Split settings package (base/local/production/test) via django-environ
    - Services/selectors pattern (established in CLAUDE.md; apps scaffold ready)
    - apps/ domain-driven layout (one app per bounded context)
    - DisableMigrations class in test settings for speed
    - Health check endpoints as Django views (not DRF) for simplicity

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - manage.py
    - conftest.py
    - Makefile
    - .env.example
    - .gitignore
    - .dockerignore
    - .pre-commit-config.yaml
    - config/__init__.py
    - config/urls.py
    - config/wsgi.py
    - config/asgi.py
    - config/settings/__init__.py
    - config/settings/base.py
    - config/settings/local.py
    - config/settings/production.py
    - config/settings/test.py
    - apps/__init__.py
    - apps/common/__init__.py
    - apps/common/apps.py
    - apps/common/models.py
    - apps/common/exceptions.py
    - apps/common/pagination.py
    - apps/common/throttling.py
    - apps/common/views.py
    - apps/common/urls.py
    - apps/common/tests/__init__.py
    - apps/common/tests/test_health.py
  modified: []

key-decisions:
  - "django-upgrade target set to 5.1 (not 6.0) because django-upgrade 1.22.2 doesn't yet support Django 6.0 as a target-version argument"
  - "django-stubs django_settings_module points to config.settings.test (not local) so pre-commit mypy hook works before apps.accounts/apps.organisations are created"
  - "test.py overrides INSTALLED_APPS and AUTH_USER_MODEL=auth.User to allow tests to run before Plan 02 creates the custom User model"
  - "pythonjsonlogger module path updated from pythonjsonlogger.jsonlogger to pythonjsonlogger.json (new API in python-json-logger 3.x)"
  - "pre-commit mypy hook gets django-environ, djangorestframework, drf-spectacular, django-redis, django-vite, pytest in additional_dependencies for isolated env to work"

patterns-established:
  - "Settings split: config.settings.base (shared) -> local/production/test (overrides)"
  - "Test settings: DisableMigrations class + SQLite in-memory for fast tests"
  - "Health views: plain Django HttpRequest -> JsonResponse (not DRF) for minimal dependencies"
  - "noqa + nosec annotations: S105 for intentional dev/test hardcoded keys"

requirements-completed: [DSYS-01, DSYS-04]

# Metrics
duration: 10min
completed: "2026-04-22"
---

# Phase 01 Plan 01: Django Project Scaffold Summary

**Django 6.0.2 project scaffolded with split settings, uv-managed deps, pre-commit hooks (ruff/mypy/bandit/gitleaks all passing), and apps/common foundation with health endpoints and passing tests**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-22T10:02:14Z
- **Completed:** 2026-04-22T10:12:00Z
- **Tasks:** 2 of 2
- **Files modified:** 28

## Accomplishments

- Full Django 6.0.2 project shell with `config/settings/{base,local,production,test}.py` all importing cleanly
- uv sync completed producing uv.lock with all pinned dependencies
- Pre-commit hooks fully passing: ruff, ruff-format, django-upgrade, mypy, bandit, gitleaks, missing-migrations
- apps/common with TimeStampedModel + UUIDModel abstract bases, health endpoints, 2 passing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold pyproject.toml, Django config package, and dependency lockfile** - `b27d849` (chore)
2. **Task 2: Pre-commit hooks, apps/common foundation, and test infrastructure** - `e7180d5` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `pyproject.toml` - Single source of truth for deps and tool config (django 6.0.2, ruff, mypy, pytest)
- `uv.lock` - Dependency lockfile
- `config/settings/base.py` - Shared Django settings with AUTH_USER_MODEL, REST_FRAMEWORK, CACHES
- `config/settings/local.py` - Dev overrides (MailHog, debug_toolbar, Vite dev mode)
- `config/settings/production.py` - Production security settings + SES backend
- `config/settings/test.py` - Fast test settings (SQLite in-memory, DisableMigrations)
- `apps/common/models.py` - TimeStampedModel + UUIDModel abstract base classes
- `apps/common/views.py` - /healthz/ and /readyz/ liveness/readiness probes
- `apps/common/tests/test_health.py` - 2 passing health endpoint tests
- `.pre-commit-config.yaml` - All quality hooks enforced on commit

## Decisions Made

- **django-upgrade target 5.1 not 6.0**: django-upgrade 1.22.2 CLI doesn't accept "6.0" as target-version yet. Using 5.1 (the closest supported version) since Django 6 is fully backwards compatible with 5.1 upgrade patterns.
- **mypy django_settings_module = config.settings.test**: The pre-commit mypy hook runs in an isolated env that lacks apps.accounts (created in Plan 02). Pointing at test settings avoids `ModuleNotFoundError: No module named 'apps.accounts'`.
- **test.py AUTH_USER_MODEL = auth.User**: Required to run tests before the custom User model exists. Will be reverted in Plan 02 once accounts app is created.
- **pythonjsonlogger.json not pythonjsonlogger.jsonlogger**: python-json-logger 3.x moved the JsonFormatter to pythonjsonlogger.json. Using the new module path to avoid DeprecationWarning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pythonjsonlogger module path**
- **Found during:** Task 2 (test run)
- **Issue:** `base.py` used `pythonjsonlogger.jsonlogger.JsonFormatter` which triggers DeprecationWarning in python-json-logger 3.x
- **Fix:** Changed to `pythonjsonlogger.json.JsonFormatter`
- **Files modified:** `config/settings/base.py`
- **Verification:** Tests pass without warning
- **Committed in:** e7180d5 (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added nosec/noqa annotations to dev/test secrets**
- **Found during:** Task 2 commit (pre-commit hooks)
- **Issue:** bandit B105 and ruff S105 flagged `SECRET_KEY = "test-insecure-secret"` in test.py and `"dev-insecure-secret"` in local.py
- **Fix:** Added `# nosec B105  # noqa: S105` to both intentional test/dev hardcoded values
- **Files modified:** `config/settings/test.py`, `config/settings/local.py`
- **Verification:** bandit and ruff checks pass
- **Committed in:** e7180d5

**3. [Rule 3 - Blocking] Fixed django-upgrade pre-commit config**
- **Found during:** Task 2 commit (pre-commit hook failure)
- **Issue:** `--target-version 6.0` rejected by django-upgrade 1.22.2 (max supported: 5.1)
- **Fix:** Changed target-version to `5.1`
- **Files modified:** `.pre-commit-config.yaml`
- **Verification:** django-upgrade hook passes
- **Committed in:** e7180d5

**4. [Rule 3 - Blocking] Fixed pre-commit mypy isolated environment**
- **Found during:** Task 2 commit (pre-commit hook failure)
- **Issue:** Pre-commit mypy hook can't load Django settings because `apps.accounts` isn't importable yet; also missing `environ`, `pytest` in isolated env
- **Fix:** Added `django-environ`, `djangorestframework`, `drf-spectacular`, `django-redis`, `django-vite`, `pytest` to mypy hook additional_dependencies; pointed django-stubs at `config.settings.test`; added mypy override to ignore missing stubs for environ
- **Files modified:** `.pre-commit-config.yaml`, `pyproject.toml`
- **Verification:** mypy hook passes
- **Committed in:** e7180d5

**5. [Rule 3 - Blocking] Fixed missing-migrations hook**
- **Found during:** Task 2 commit (pre-commit hook failure)
- **Issue:** Hook used bare `python` which isn't in PATH; also uses default settings (local) which references missing apps
- **Fix:** Changed entry to `env DJANGO_SETTINGS_MODULE=config.settings.test uv run python manage.py makemigrations --check --dry-run`
- **Files modified:** `.pre-commit-config.yaml`
- **Verification:** Hook passes
- **Committed in:** e7180d5

---

**Total deviations:** 5 auto-fixed (1 bug, 1 missing critical annotation, 3 blocking)
**Impact on plan:** All auto-fixes necessary for passing pre-commit hooks and test correctness. No scope creep.

## Issues Encountered

- pre-commit mypy hook requires significant additional_dependencies configuration for Django projects — documented as pattern for future plans
- `config.settings.test` required INSTALLED_APPS and AUTH_USER_MODEL overrides because accounts/organisations apps don't exist yet (expected; noted in plan)

## Known Blocker (Expected)

`python manage.py check` with default `config.settings.local` will fail until Plan 02 creates `apps.accounts` and `apps.organisations`. This is documented in the plan's output section as expected behavior. Tests use `config.settings.test` which works fine.

## Next Phase Readiness

- Django 6.0.2 project shell ready
- Pre-commit quality gates enforced and passing
- Test infrastructure works (pytest, factory-boy, coverage configured)
- apps/common foundation ready for use by all subsequent plans
- Plan 02 (accounts) can proceed — needs to create `apps/accounts/` with custom User model and then Plan 03 (organisations)

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
