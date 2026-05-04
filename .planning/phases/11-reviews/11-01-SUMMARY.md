---
phase: 11-reviews
plan: "01"
subsystem: reviews
tags: [models, migrations, review, audit-log, shop, django-filter, fts]
dependency_graph:
  requires: []
  provides:
    - apps/reviews/models.py — Review model with constraints + GIN index + SearchVectorField
    - apps/reviews/managers.py — ReviewQuerySet with active/for_organisation/for_shops/replied
    - apps/common/models.py — AuditLog generic model (reusable across Phase 12-13)
    - apps/shops/models.py — google_account_name + google_location_name fields
    - apps/reviews/tests/factories.py — ReviewFactory + AuditLogFactory for downstream tests
  affects:
    - apps/reviews/migrations/0001_initial.py
    - apps/common/migrations/0002_auditlog.py
    - apps/shops/migrations/0005_shop_google_account_name_shop_google_location_name.py
tech_stack:
  added:
    - django-filter==24.3
    - django.contrib.postgres (INSTALLED_APPS)
  patterns:
    - ReviewQuerySet.as_manager() for fluent queryset chaining
    - SearchVectorField + GinIndex for Phase 11 FTS readiness
    - Generic AuditLog (entity_type/entity_id string keys) for cross-phase reuse
key_files:
  created:
    - apps/reviews/models.py
    - apps/reviews/managers.py
    - apps/reviews/migrations/0001_initial.py
    - apps/reviews/migrations/__init__.py
    - apps/reviews/tests/factories.py
    - apps/reviews/tests/test_models.py
    - apps/common/migrations/0002_auditlog.py
    - apps/shops/migrations/0005_shop_google_account_name_shop_google_location_name.py
  modified:
    - apps/common/models.py
    - apps/shops/models.py
    - config/settings/base.py
    - config/settings/test.py
    - pyproject.toml
    - uv.lock
    - .pre-commit-config.yaml
decisions:
  - "Integer PK (BigAutoField) kept on Review — consistent with existing Shop/Organisation models"
  - "google_account_name/google_location_name use blank=True + default='' to avoid NULL handling in GBP API paths"
  - "AuditLog uses string entity_type/entity_id (not GenericForeignKey) — avoids content-type overhead and works for non-model entities like external IDs"
  - "SearchVectorField added now but populated in Plan 11-07 — index exists, data is null until sync runs"
  - "django.contrib.postgres added to both base.py and test.py INSTALLED_APPS (test.py overrides INSTALLED_APPS entirely)"
  - "pyproject.toml dependencies sorted alphabetically to prevent future duplicate entries"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 14
---

# Phase 11 Plan 01: Review Model Foundation Summary

One-liner: Review + AuditLog + Shop GBP fields established with three migrations, ReviewFactory, and 6 passing constraint tests; django-filter wired as global DRF filter backend.

## What Was Built

### Review model (`apps/reviews/models.py`)
Full GBP field set: `google_review_id`, `star_rating`, reviewer fields, `comment`, timestamps, reply fields, `enrichment_status` (PENDING default), `search_vector` (SearchVectorField for FTS), `deleted_at` (soft-delete). Unique constraint on `(shop, google_review_id)`. Three composite indexes for common filter patterns + GIN index for full-text search.

### ReviewQuerySet (`apps/reviews/managers.py`)
Methods: `active()` (excludes soft-deleted), `for_organisation()`, `for_shops()`, `replied()`.

### AuditLog model (`apps/common/models.py`)
Generic audit trail with `organisation` FK, optional `actor` FK, `entity_type`/`entity_id` (string keys), `action`, `before_data`/`after_data` JSONField. Two composite indexes. Designed for reuse across Phase 12-13 without new migrations.

### Shop GBP fields (`apps/shops/models.py`)
`google_account_name` and `google_location_name` added after `place_id`. Both blank=True, default="", with help_text describing GBP resource path format.

### django-filter integration
- `django-filter==24.3` added to `pyproject.toml` and installed via `uv sync`
- `django_filters` added to INSTALLED_APPS
- `DEFAULT_FILTER_BACKENDS` set to DjangoFilterBackend + OrderingFilter
- `ScopedRateThrottle` added to DEFAULT_THROTTLE_CLASSES
- `review_reply: 30/minute` throttle scope registered

### Migrations generated
| Migration | App | Content |
|-----------|-----|---------|
| `0001_initial.py` | reviews | Review model, constraint, 3 indexes + GIN index |
| `0002_auditlog.py` | common | AuditLog model, 2 indexes |
| `0005_shop_google_account_name_shop_google_location_name.py` | shops | AddField x2 |

Note: Shops migration is `0005` not `0006` as the plan anticipated — only 4 prior shops migrations existed. Django auto-numbering accepted per plan instructions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] django.contrib.postgres missing from INSTALLED_APPS**
- **Found during:** Task 1 — makemigrations failed with `postgres.E005` SystemCheckError
- **Issue:** SearchVectorField requires `django.contrib.postgres` in INSTALLED_APPS; it was not present
- **Fix:** Added `"django.contrib.postgres"` to both `base.py` and `test.py` INSTALLED_APPS (test.py overrides the entire list)
- **Files modified:** `config/settings/base.py`, `config/settings/test.py`
- **Commit:** c73b9ad (included in previous agent's commit)

**2. [Rule 3 - Blocking] pre-commit mypy hook missing psycopg**
- **Found during:** Task 1 commit — pre-commit mypy hook raised `ModuleNotFoundError: No module named 'psycopg'`
- **Issue:** The mypy hook's isolated environment needs psycopg to import `django.contrib.postgres.search`
- **Fix:** Added `psycopg[binary]==3.2.3` and `django-filter==24.3` to pre-commit mypy `additional_dependencies`
- **Files modified:** `.pre-commit-config.yaml`
- **Commit:** c73b9ad + 819ba03

**3. [Rule 1 - Bug] pyproject.toml had duplicate django-ses entry after manual edit**
- **Found during:** Task 2 — editing pyproject.toml introduced a duplicate `django-ses==4.3.0` entry
- **Fix:** Rewrote dependencies list sorted alphabetically to eliminate duplicate and ensure correct format
- **Files modified:** `pyproject.toml`
- **Commit:** 819ba03

**4. [Scope note] Task 1 was pre-committed by a concurrent agent run (plan 11-02)**
- The previous agent executing plan 11-02 included all Task 1 model/migration files in commit `c73b9ad`. This plan verified those files meet all acceptance criteria and proceeded directly to Task 2.

## Commits

| Hash | Task | Description |
|------|------|-------------|
| c73b9ad | Task 1 | Review model, managers, AuditLog, Shop GBP fields, migrations, test_models.py (committed by plan 11-02 agent) |
| 819ba03 | Task 2 | django-filter, throttle scope, ReviewFactory, AuditLogFactory, settings updates |

## Self-Check

Files verified:
- apps/reviews/models.py: FOUND, contains Review(TimeStampedModel)
- apps/reviews/managers.py: FOUND, contains ReviewQuerySet
- apps/common/models.py: FOUND, contains AuditLog
- apps/shops/models.py: FOUND, contains google_account_name
- apps/reviews/migrations/0001_initial.py: FOUND, contains review_unique_per_shop
- apps/common/migrations/0002_auditlog.py: FOUND, contains AuditLog
- apps/shops/migrations/0005_...: FOUND, contains google_account_name
- apps/reviews/tests/factories.py: FOUND, contains ReviewFactory + AuditLogFactory
- apps/reviews/tests/test_models.py: FOUND, 6 tests all passing

Test results: 6/6 passed (`pytest apps/reviews/tests/test_models.py`)
System check: 0 issues (`python manage.py check`)
Migration check: No pending migrations (`makemigrations --check`)

## Self-Check: PASSED
