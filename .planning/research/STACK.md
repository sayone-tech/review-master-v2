# Stack Research: Multi-Tenant Review Management Platform

**Domain:** Django 6 multi-tenant SaaS — Superadmin module
**Date:** 2026-04-22
**Confidence:** MEDIUM overall (verify package versions on PyPI before pinning)

---

## Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django | 6.0.x | Web framework | Project constraint |
| djangorestframework | 3.15.x | API layer | Latest DRF; Django 6 compatible |
| drf-spectacular | 0.27.x | OpenAPI schema | Preferred over unmaintained drf-yasg |
| psycopg | 3.2.x | PostgreSQL driver | psycopg3 is Django 6 recommended; async-ready |

## Authentication & Permissions

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django session auth | built-in | Browser auth | Project decision; no JWT in Phase 1 |
| django.core.signing.TimestampSigner | built-in | Invitation tokens | 48-hr expiry, HMAC hash stored in DB for single-use |
| Custom DRF BasePermission classes | built-in | RBAC | Three static roles; zero extra dependencies; fully testable |
| django-axes | 6.x | Brute-force login protection | Rate-limits failed attempts; Redis-backed |

## Cache & Queue

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| django-redis | 5.4.x | Redis cache backend | Standard; IGNORE_EXCEPTIONS=True prevents cache outage cascades |
| redis-py | 5.x | Direct Redis access | Distributed locks; v5 ships async support |

## Email

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| django-ses | 4.x | Amazon SES backend | Project constraint |
| boto3 | 1.35.x | AWS SDK | Required by django-ses |
| premailer | 3.10.x | CSS inlining | Use directly — django-premailer is unmaintained |

## Frontend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tailwind CSS | 4.x | Utility CSS | Standalone CLI; no Node.js required |
| React | 19.x | UI widgets | Project constraint; use createRoot API |
| Vite | 6.x | Frontend build | Fast HMR, ESM-native |
| django-vite | 3.x | Django ↔ Vite integration | `{% vite_asset %}` template tag; dev + prod |
| TypeScript | 5.x | Type safety | Strict mode |

## Observability & Security

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-json-logger | 2.0.x | Structured JSON logs | Queryable in log aggregators |
| sentry-sdk | 2.x | Error tracking | Scrub PII in before_send |
| whitenoise | 6.x | Static file serving | Sufficient for Phase 1 |
| gunicorn | 23.x | WSGI server | Standard for Cloud Run Django |

## Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest + pytest-django | 8.x / 4.9.x | Test runner | Project constraint |
| factory-boy | 3.3.x | Test factories | Project constraint |
| pytest-cov | 5.x | Coverage | Enforces 85% minimum in CI |
| responses | 0.25.x | Mock HTTP | For Google API mocks (Phase 2+) |
| django-debug-toolbar | 4.x | Query inspection | Local only; never production |

## Configuration & Dev

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| django-environ | 0.11.x | .env parsing | Simpler than pydantic-settings for this config surface |
| uv | latest | Dependency management | Significantly faster than pip/poetry |
| ruff | 0.15.x | Lint + format | Project pre-commit spec |
| mypy | 1.13.x | Static types | Project pre-commit spec |

## Phase 2+ Only (do not install in Phase 1)

| Technology | Version | Purpose | When |
|------------|---------|---------|------|
| django-cryptography | 1.1.x | Encrypted fields | Google OAuth refresh tokens |
| tenacity | 9.x | Retry with backoff | Google API calls |
| celery + django-celery-beat | 5.x / 2.x | Async tasks | Phase 2+ background jobs |

---

## What NOT to Use

| Package | Why Not |
|---------|---------|
| `django-guardian` | Object-level permissions not needed in Phase 1; adds DB overhead |
| `django-rules` | Predicate-based system for complex per-object logic; overkill for three static roles |
| `django-tailwind` (pip) | Lags Tailwind releases; targets v3; unnecessary Python wrapper |
| Create React App | Deprecated and abandoned |
| webpack | Slower DX than Vite; no reason for greenfield 2025 project |
| `django-auditlog` | Signal-based write amplification; hot audit table at scale |
| `django-simple-history` | Full model snapshots on every save; expensive |
| `psycopg2` | Legacy driver; Django 6 recommends psycopg3 |
| `django-premailer` | Unmaintained; use `premailer` directly |
| `drf-yasg` | Unmaintained; use `drf-spectacular` |
| SimpleJWT (Phase 1) | Not needed until a separate non-browser client exists |
| HTMX | Project already committed to React; mixing both adds cognitive overhead |

---

## Open Questions (verify before implementation)

1. **django-vite 3.x and Django 6 compatibility** — Highest priority; check GitHub issues/changelog
2. **Tailwind v4 standalone CLI binary distribution** — Verify download mechanism at tailwindcss.com
3. **django-axes Django 6 compatibility** — Verify current release
4. **psycopg `[binary]` vs `[c]` extra** — For Cloud Run, `[binary]` is recommended (pre-compiled, simpler Docker build)
5. **WhiteNoise behind Cloud Run** — Verify cache header behaviour behind GCP load balancer

---

## Roadmap Implications

- **Phase 1:** Install full core stack immediately. Custom permission classes at project start.
- **Phase 1 Tailwind:** Use v4 standalone CLI from day one — v3→v4 migration is non-trivial.
- **Phase 1 React:** Set up django-vite infrastructure even for the first widget — don't retrofit in Phase 2.
- **Phase 2 flag:** Add `django-cryptography` + `tenacity` together when Google OAuth arrives.
- **Phase 3 flag:** Re-evaluate `django-guardian` when Staff Admin per-store permissions are introduced.
