---
phase: "05-profile-and-hardening"
plan: "04"
subsystem: "security-headers + ci-pipeline"
tags: ["security", "csp", "github-actions", "ci", "hardening"]
dependency_graph:
  requires: ["05-02"]
  provides: ["production-security-headers", "ci-pipeline"]
  affects: ["config/settings/production.py", ".github/workflows/ci.yml"]
tech_stack:
  added: ["django.middleware.csp.ContentSecurityPolicyMiddleware (Django 6 built-in)", "GitHub Actions CI"]
  patterns: ["Django 6 built-in CSP via SECURE_CSP dict", "MIDDLEWARE list extension via unpacking"]
key_files:
  created:
    - ".github/workflows/ci.yml"
  modified:
    - "config/settings/production.py"
decisions:
  - "Used Django 6 built-in ContentSecurityPolicyMiddleware (zero new dependencies) over third-party django-csp package"
  - "CSP uses 'unsafe-inline' for script-src and style-src to accommodate Alpine.js directives and Tailwind CSS — nonce migration deferred"
  - "MIDDLEWARE extended via [*MIDDLEWARE, ...] unpacking (RUF005 compliance) instead of MIDDLEWARE + [...] concatenation"
  - "django-upgrade target remains 5.1 (not bumped to 6.0 in ci.yml)"
  - "CI uses postgres:16-alpine + redis:7-alpine service containers for test isolation"
  - "Deploy-check step uses step-level env override to switch DJANGO_SETTINGS_MODULE to production"
metrics:
  duration: "2m"
  completed_date: "2026-04-24"
  tasks_completed: 2
  files_modified: 2
---

# Phase 05 Plan 04: Production Security Headers + GitHub Actions CI Summary

**One-liner:** Django 6 built-in CSP middleware + X-Frame-Options/XSS headers added to production settings; 5-step GitHub Actions CI pipeline created with coverage gate and deploy-check.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Harden production security headers (XSS filter, X-Frame-Options, CSP) | `18ff71b` | `config/settings/production.py` |
| 2 | Create GitHub Actions CI workflow | `8910445` | `.github/workflows/ci.yml` |

## What Was Built

### Task 1: Production Security Headers

Added three missing security settings to `config/settings/production.py`:

```python
# Extra security headers — HRDG-02 (Phase 05)
SECURE_BROWSER_XSS_FILTER = True  # X-XSS-Protection: 1; mode=block
X_FRAME_OPTIONS = "DENY"  # Clickjacking protection

# Content Security Policy — Django 6 built-in (HRDG-02)
SECURE_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'"],
}

MIDDLEWARE = [*MIDDLEWARE, "django.middleware.csp.ContentSecurityPolicyMiddleware"]
```

**deploy check result** (`DJANGO_SETTINGS_MODULE=config.settings.production DJANGO_SECRET_KEY=ci-check DJANGO_ALLOWED_HOSTS=localhost AWS_SES_FROM_EMAIL=noreply@example.com`):
- Exit code: **0**
- Warnings only (W009 short secret key — expected with stub key; W001 drf-spectacular enum — pre-existing, unrelated)
- No errors

**No new dependencies added** — `django-csp` package was NOT added to `pyproject.toml`. Django 6.0.2's built-in `django.middleware.csp.ContentSecurityPolicyMiddleware` was used.

### Task 2: GitHub Actions CI Workflow

`.github/workflows/ci.yml` created with 5 required steps:

1. `uv run pre-commit run --all-files`
2. `uv run mypy .`
3. `uv run pytest --cov=apps --cov-fail-under=85`
4. `uv run python manage.py makemigrations --check --dry-run`
5. `uv run python manage.py check --deploy` (deploy-check step with production settings env override)

Pipeline features:
- Triggers: `push: branches: [main]` and `pull_request: branches: [main]`
- Service containers: `postgres:16-alpine` (port 5432) and `redis:7-alpine` (port 6379) with health checks
- Job-level env uses `config.settings.test`; deploy-check step overrides to `config.settings.production`
- Stub secrets: `ci-insecure-secret` (test), `ci-deploy-check-secret` (deploy-check) — obviously fake, gitleaks passes
- `uv sync --frozen` for reproducible lockfile-based installs
- django-upgrade target remains 5.1 (pre-commit config not modified)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff RUF005: MIDDLEWARE concatenation style**
- **Found during:** Task 1 pre-commit hook run
- **Issue:** `MIDDLEWARE = MIDDLEWARE + [...]` triggered ruff RUF005 (use iterable unpacking instead of concatenation)
- **Fix:** Changed to `MIDDLEWARE = [*MIDDLEWARE, "django.middleware.csp.ContentSecurityPolicyMiddleware"]`
- **Files modified:** `config/settings/production.py`
- **Commit:** included in `18ff71b`

**2. [Rule 1 - Bug] ruff auto-removed `# noqa: F405` comments**
- **Found during:** Task 1 pre-commit run
- **Issue:** ruff-format removed inline `# noqa: F405` comments during reformatting (they're already handled by per-file-ignores in pyproject.toml for `**/settings/**`)
- **Fix:** The noqa comments were unnecessary — settings files already have F405 in per-file-ignores; removed them
- **Commit:** included in `18ff71b`

## Verification Results

```
config/settings/production.py:
  SECURE_BROWSER_XSS_FILTER = True  ✓
  X_FRAME_OPTIONS = "DENY"          ✓
  SECURE_CSP = {                    ✓
  ContentSecurityPolicyMiddleware   ✓

pyproject.toml:
  django-csp NOT present            ✓

.github/workflows/ci.yml:
  pre-commit run --all-files        ✓
  uv run mypy .                     ✓
  --cov=apps --cov-fail-under=85    ✓
  makemigrations --check --dry-run  ✓
  manage.py check --deploy          ✓
  config.settings.production        ✓
  postgres:16-alpine + redis:7-alpine ✓
  No target-version 6.0             ✓
  No deploy: job                    ✓
  Valid YAML                        ✓
```

## Next Steps

- The next push to `main` will be the first live CI run — Phase 5 UAT expectation is that it comes back green
- Future: refine CSP by migrating Alpine.js inline handlers to external modules and adding nonces (removes `'unsafe-inline'` from script-src)
- Future: add `deploy.yml` workflow for staging/production deploys (deferred per Phase 5 scope)

## Self-Check: PASSED
