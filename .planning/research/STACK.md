# Stack Research: Organisation Admin Module

**Domain:** Django 6 multi-tenant SaaS — Org Admin module (Google OAuth, encryption, team scoping)
**Researched:** 2026-04-27
**Confidence:** MEDIUM-HIGH overall (package versions verified via web search; Django 6 compatibility verified for new additions)

---

## Context: What Already Exists (Do Not Re-add)

The following are locked in `pyproject.toml` and must not be duplicated or replaced:

| Package | Pinned Version | Role |
|---------|---------------|------|
| `django` | 6.0.2 | Framework |
| `djangorestframework` | 3.17.1 | API layer |
| `django-redis` | 5.4.0 | Cache + locks |
| `psycopg[binary]` | 3.2.3 | PostgreSQL driver |
| `django-environ` | 0.11.2 | Config from env |
| `django-ses` | 4.3.0 | Transactional email |
| `boto3` | 1.35.0 | AWS SDK (SES) |
| `python-json-logger` | 3.2.0 | Structured logging |
| `drf-spectacular` | 0.28.0 | OpenAPI schema |
| `django-vite` | 3.1.0 | Vite integration |

---

## New Packages Required for This Milestone

### (A) Field-Level Encryption for OAuth Tokens and API Keys

**Decision: `django-fernet-encrypted-fields` (jazzband) — NOT `django-cryptography`**

`django-cryptography` (the original) is effectively abandoned — last PyPI release was April 2022 (version 1.1), which only supports Django up to 4.0 and Python up to 3.10. A PR adding Python 3.12 support (#108) has not been merged. Two forks exist (`django-cryptography-5`, `django-cryptography-django5`) but neither has verified Django 6.0 support.

`django-fernet-encrypted-fields` from jazzband is the actively maintained successor. Version 0.3.1 (released November 2025) explicitly supports Django 6.0 and Python 3.12. It is maintained under the Jazzband cooperative, which gives it long-term maintenance continuity.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `django-fernet-encrypted-fields` | `==0.3.1` | Encrypted model fields (EncryptedTextField, EncryptedCharField) for refresh tokens and API keys | Jazzband-maintained; Django 6.0 + Python 3.12 verified; uses cryptography (Fernet) under the hood; field-transparent (read/write as normal Django fields) |
| `cryptography` | `>=43.0.0` | Fernet primitives — pulled in as a dependency of django-fernet-encrypted-fields | Do not pin independently; let the encrypted-fields package drive the version |

**Key integration notes:**

- Configure `FERNET_KEYS` in settings (list of base64-encoded 32-byte keys). First key encrypts new data; all keys attempted on decrypt (rotation support built in).
- In production, the primary Fernet key is read from GCP Secret Manager, never from `.env`. The Django `SECRET_KEY` must NOT be used as a Fernet key in production — it is too short and changes on rotation would silently break all encrypted values.
- `EncryptedTextField` is the right field type for both OAuth refresh tokens (long strings) and API keys. Store ciphertext in a `TextField`/`BinaryField` column.
- Encrypted fields cannot be filtered or sorted at the database level — this is correct behaviour for secrets. Never index an encrypted field.

**Mypy:** `django-fernet-encrypted-fields` does not currently ship type stubs. Add an `ignore_missing_imports` override in `pyproject.toml` for `fernet_encrypted_fields.*`.

---

### (B) Google Business Profile OAuth (Authorization Code Flow with Popup)

**Decision: Google Identity Services (GIS) in the frontend + `google-auth-oauthlib` + `google-api-python-client` in the backend**

The OAuth popup flow works as follows:
1. Frontend loads GIS via CDN (`accounts.google.com/gsi/client`) and calls `google.accounts.oauth2.initCodeClient({ ux_mode: "popup", callback: ... })`.
2. GIS opens a popup, the user grants consent, and GIS delivers an authorization `code` to a JavaScript callback (not a redirect).
3. The JS callback posts the `code` to a Django endpoint (`/integrations/google/oauth/callback/`) via `fetch()`, with `X-Requested-With: XMLHttpRequest` header (CSRF-safe + popup-mode indicator).
4. The Django view exchanges the code for access + refresh tokens using `google_auth_oauthlib.flow.Flow.fetch_token()` and persists the encrypted refresh token to the `Shop` model.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `google-auth` | `==2.49.2` | Core Google authentication primitives (Credentials, refresh, token storage) | Latest stable as of April 2026; Python 3.12 verified |
| `google-auth-oauthlib` | `==1.3.1` | OAuth 2.0 flow for server-side code exchange | Latest stable (Mar 2026); wraps oauthlib for Google APIs; `Flow.fetch_token()` handles code-for-token exchange |
| `google-api-python-client` | `==2.194.0` | Google Business Profile API calls (list reviews, account info) | Latest stable (Apr 2026); weekly release cadence; discovery-based client for Business Profile API |

**Key integration notes:**

- Store the `client_secrets.json` content (or its individual fields) in GCP Secret Manager — never in the repo or `.env`.
- The GIS popup flow replaces the deprecated `gapi.auth` implicit flow. Use `ux_mode: "popup"` with `callback`, not `redirect_uri`.
- The Django OAuth callback endpoint must validate the `state` parameter (set at initiation) to prevent CSRF on the token exchange. Use `django.core.signing` to generate and verify state.
- On `401 invalid_grant`, set `shop.google_connection_status = "expired"` and email the Org Admin via the existing `send_transactional_email` helper.
- Scope required: `https://www.googleapis.com/auth/business.manage` — this is the only scope for Business Profile API access.
- The `google-api-python-client` discovery service makes a network call on first use; cache the discovery document using Django's Redis cache backend to avoid cold-start latency.

**Mypy:** Add `google-auth-stubs` (dev dependency) to get type stubs for `google.auth` and `google.oauth2`. Separately, `google-api-python-client-stubs` covers the client library. `types-oauthlib` covers the underlying oauthlib dependency.

---

### (C) Google Places API — Shop Creation Validation

**Decision: Direct HTTP via `httpx` — no Google wrapper library**

The Google Places API (New) accepts plain HTTPS requests. Adding `google-api-python-client` (already included for Business Profile) does not cover Places API without additional discovery document setup. The cleanest approach is a thin `places_client.py` service in `apps/integrations/google/` that makes a direct HTTPS call using `httpx`.

The Places API (New) place details endpoint:
```
GET https://places.googleapis.com/v1/places/{place_id}
X-Goog-Api-Key: {api_key}
X-Goog-FieldMask: id,displayName,formattedAddress,types
```

A `200` response with a matching `id` validates the Place ID. `NOT_FOUND` or `INVALID_REQUEST` status signals an invalid/stale Place ID.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `httpx` | `==0.28.1` | HTTP client for Places API validation calls | Sync API sufficient for this use case; cleaner than `requests` for testing (respx mock support); no Google SDK overhead |
| `tenacity` | `==9.1.4` | Retry with exponential backoff for all Google API calls | Framework-agnostic; works with synchronous calls; `wait_exponential` + `retry_if_exception_type` covers transient 429/503 responses |

**Key integration notes:**

- Validation call happens at shop creation time in the service layer (`apps/stores/services/shops.py`), not in the serializer.
- Wrap the Places API call with `@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.TransportError))`.
- Also apply `tenacity` to all `google-api-python-client` calls (Business Profile API).
- The server-side Places API key is the "manual fallback" key stored encrypted in the `Organisation` or global settings — this is separate from the per-shop OAuth token. Use `EncryptedTextField` for this key too.
- Place ID format: starts with `ChIJ` (legacy) or `places/...` (New API). Accept both; validate via Places API (New) which resolves both formats.
- Do NOT add `google-maps-services-python` — it pulls in `requests` as a hard dependency and wraps an outdated HTTP interface. The direct `httpx` approach is cleaner and testable.

---

### (D) Race-Condition-Safe Region ID Auto-Generation

**Decision: `django-sequences` — NOT application-level max()+1**

The Region auto-ID (e.g., `R-001`, `R-042`) must be gapless and collision-free. PostgreSQL's own `SERIAL`/`IDENTITY` columns skip values on rollback. Application-level `max() + 1` under concurrent load produces duplicate IDs.

`django-sequences` uses a single-row advisory table with `SELECT ... FOR UPDATE` inside `transaction.atomic()` to issue gapless sequential integers — the correct approach for human-readable identifiers.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `django-sequences` | `==3.0` | Gapless per-organisation region sequence | Version 3.0 from aaugustin; supports PostgreSQL; works inside `transaction.atomic()`; no gap on rollback |

**Django 6 compatibility note:** Version 3.0 lists Django 3.2–5.0 in its tested matrix. Django 6 support is not yet explicitly listed (confirmed gap in the search results — LOW confidence on out-of-box support). Mitigation: the package is pure Python with no Django internals coupling; it uses `django.db.models` and raw SQL. A quick smoke test (`get_next_value("region_ids")`) in the test suite will confirm compatibility. If it fails, the fallback is a hand-rolled equivalent using `select_for_update()` on a dedicated `Sequence` model — a 30-line implementation that is trivially correct.

**Usage pattern:**

```python
# apps/organisations/services/regions.py
from django.db import transaction
from django_sequences import get_next_value

@transaction.atomic
def create_region(*, organisation, name: str) -> Region:
    seq = get_next_value(f"region_ids_org_{organisation.pk}")
    region_id = f"R-{seq:03d}"
    return Region.objects.create(
        organisation=organisation,
        name=name,
        region_id=region_id,
    )
```

---

## Dev Dependencies (New)

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest-httpx` | `>=0.35.0` | Mock `httpx` calls in tests (replaces `responses` for httpx-based clients) |
| `google-auth-stubs` | latest | Mypy type stubs for `google.auth`, `google.oauth2` |
| `google-api-python-client-stubs` | latest | Mypy type stubs for the discovery client |
| `types-oauthlib` | latest | Mypy stubs for oauthlib (transitive dependency) |

**Note on `responses` (already in dev stack from v1.0 STACK.md):** Keep `responses` for mocking `requests`-based calls if any remain, but prefer `pytest-httpx` for the new `httpx`-based Places client.

---

## Installation (uv)

```bash
# Production dependencies — add to [project.dependencies] in pyproject.toml
uv add django-fernet-encrypted-fields==0.3.1
uv add google-auth==2.49.2
uv add google-auth-oauthlib==1.3.1
uv add google-api-python-client==2.194.0
uv add httpx==0.28.1
uv add tenacity==9.1.4
uv add django-sequences==3.0

# Dev dependencies — add to [dependency-groups] dev
uv add --dev pytest-httpx
uv add --dev google-auth-stubs
uv add --dev google-api-python-client-stubs
uv add --dev types-oauthlib
```

**pyproject.toml additions:**

```toml
[project]
dependencies = [
  # ... existing pins ...
  "django-fernet-encrypted-fields==0.3.1",
  "google-auth==2.49.2",
  "google-auth-oauthlib==1.3.1",
  "google-api-python-client==2.194.0",
  "httpx==0.28.1",
  "tenacity==9.1.4",
  "django-sequences==3.0",
]

[dependency-groups]
dev = [
  # ... existing dev deps ...
  "pytest-httpx>=0.35.0",
  "google-auth-stubs",
  "google-api-python-client-stubs",
  "types-oauthlib",
]
```

**mypy overrides to add:**

```toml
[[tool.mypy.overrides]]
module = ["fernet_encrypted_fields.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["googleapiclient.*"]
ignore_missing_imports = false  # covered by google-api-python-client-stubs
```

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `django-cryptography` | Abandoned — last release 2022, no Django 6 support, PR #108 not merged | `django-fernet-encrypted-fields==0.3.1` |
| `django-cryptography-5` / `django-cryptography-django5` | Community forks — no verified Django 6 support, uncertain maintenance | `django-fernet-encrypted-fields==0.3.1` |
| `django-allauth` | Full auth replacement — overkill for per-shop Google OAuth that is not login-based | `google-auth-oauthlib` directly |
| `social-auth-app-django` | Same issue — replaces auth for login; this is API connection auth, not user login | `google-auth-oauthlib` directly |
| `google-maps-services-python` | Pulls in `requests` as hard dep; wraps Places API with legacy interface; last updated infrequently | Direct `httpx` call to Places API (New) |
| `requests` (new addition) | Already using `httpx` for Google Places; avoid mixing HTTP clients | `httpx` |
| `django-oauth-toolkit` | OAuth *provider* toolkit — for when Django acts as an OAuth server; this project is an OAuth *consumer* | `google-auth-oauthlib` |
| `python-jose` / `PyJWT` | JWT handling — not needed; session auth established; Google tokens are opaque to the app | Not needed |
| `celery` / `django-celery-beat` | Phase 2 item — not in scope for this milestone | Django management commands + Cloud Scheduler (existing pattern) |
| Inline Fernet via `cryptography` package directly | Error-prone; no Django field integration; key management DIY | `django-fernet-encrypted-fields` |

---

## Alternatives Considered

| Category | Chosen | Alternative | Why Not Chosen |
|----------|--------|-------------|----------------|
| Field encryption | `django-fernet-encrypted-fields` | `django-cryptography` | Abandoned, no Django 6 support |
| Field encryption | `django-fernet-encrypted-fields` | Custom `Fernet` in `save()` / `from_db()` | Fragile; migration pain; key rotation manual |
| OAuth library | `google-auth-oauthlib` | `django-allauth` with Google provider | allauth replaces auth for user login; this is per-shop API access, not user SSO |
| Google Places validation | `httpx` direct | `google-maps-services-python` | Pulls `requests`; heavier than needed for one validation call |
| Sequence generation | `django-sequences` | `F() + update()` on a counter field | F() is correct for increments but doesn't guarantee gaplessness across rollbacks for human-readable IDs |
| Sequence generation | `django-sequences` | PostgreSQL `SEQUENCE` via raw SQL migration | Works but bypasses Django ORM; harder to test; `django-sequences` wraps it cleanly |
| Retry | `tenacity` | `backoff` library | tenacity is more actively maintained with richer wait strategies; both are valid |

---

## Version Compatibility Matrix

| New Package | Requires | Compatible With | Notes |
|-------------|----------|-----------------|-------|
| `django-fernet-encrypted-fields==0.3.1` | Python >=3.10, Django >=4.2 | Django 6.0, Python 3.12 | Verified — Django 6.0 in test matrix per jazzband |
| `google-auth==2.49.2` | Python >=3.7 | Python 3.12 | Latest stable Apr 2026 |
| `google-auth-oauthlib==1.3.1` | Python >=3.9 | Python 3.12 | Latest stable Mar 2026 |
| `google-api-python-client==2.194.0` | Python >=3.7 | Python 3.12 | Latest stable Apr 2026; weekly releases |
| `httpx==0.28.1` | Python >=3.8 | Python 3.12 | Latest stable |
| `tenacity==9.1.4` | Python >=3.10 | Python 3.12 | Latest stable Feb 2026 |
| `django-sequences==3.0` | Python >=3.8 | Django 3.2–5.0 (Django 6: LOW confidence — needs smoke test) | Pure Python; likely works; see note above |

---

## Settings Changes Required

```python
# config/settings/base.py additions

# Field-level encryption — key loaded from GCP Secret Manager in production
FERNET_KEYS = [env("FERNET_PRIMARY_KEY")]  # base64-encoded 32-byte key

# Google OAuth — client credentials from Secret Manager
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET")

# Google Places API key (for manual fallback validation)
# Do NOT expose this to the frontend. Backend-only.
GOOGLE_PLACES_API_KEY = env("GOOGLE_PLACES_API_KEY")

# Scopes for Business Profile API
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
]
```

---

## Open Questions / Flags for Phase Research

1. **`django-sequences` + Django 6 smoke test** — MUST run `get_next_value("test")` in a test during Phase 1 setup. If it fails, 30-line fallback using `select_for_update()` on a `Sequence` model is ready.
2. **GIS popup + Safari/iOS** — Third-party cookie restrictions in Safari may block the GIS popup on some iOS versions. Fallback: `ux_mode: "redirect"` on mobile user-agents. Flag for QA in the Shops phase.
3. **google-api-python-client discovery caching** — The discovery document fetch on first API call adds ~200ms. Cache in Redis with a 24-hour TTL. Document this in the integrations app.
4. **Fernet key rotation procedure** — When rotating the Fernet key, the old key must remain in `FERNET_KEYS` list until all rows are re-encrypted. Document the rotation runbook before going live.
5. **Business Profile API status** — The Google Business Profile API requires application review/approval from Google for production access. This is a process step, not a code step — confirm status before the Shops phase ships.

---

## Sources

- [django-fernet-encrypted-fields — PyPI](https://pypi.org/project/django-fernet-encrypted-fields/) — version 0.3.1 (Nov 2025), Django 6.0 compatibility
- [jazzband/django-fernet-encrypted-fields — GitHub](https://github.com/jazzband/django-fernet-encrypted-fields) — test matrix confirms Django 6.0
- [django-cryptography — PyPI](https://pypi.org/project/django-cryptography/) — last release 2022 v1.1; Django 4.0 max
- [django-cryptography PR #108 — GitHub](https://github.com/georgemarshall/django-cryptography/pull/108) — Python 3.12 support not merged (LOW confidence)
- [google-auth — PyPI](https://pypi.org/project/google-auth/) — v2.49.2 (Apr 2026); Python 3.12 verified
- [google-auth-oauthlib — PyPI](https://pypi.org/project/google-auth-oauthlib/) — v1.3.1 (Mar 2026)
- [google-api-python-client — PyPI](https://pypi.org/project/google-api-python-client/) — v2.194.0 (Apr 2026)
- [Google GIS Use Code Model docs](https://developers.google.com/identity/oauth2/web/guides/use-code-model) — popup code flow pattern (Jan 2026)
- [Google Business Profile OAuth docs](https://developers.google.com/my-business/content/implement-oauth) — per-store OAuth requirements
- [Places API (New) Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details) — FieldMask, validation responses
- [httpx — PyPI](https://pypi.org/project/httpx/) — v0.28.1; Python >=3.8
- [tenacity — PyPI](https://pypi.org/project/tenacity/) — v9.1.4 (Feb 2026); Python >=3.10
- [django-sequences — PyPI](https://pypi.org/project/django-sequences/) — v3.0; Django 6 not yet in test matrix (LOW confidence)
- [django-sequences — GitHub](https://github.com/aaugustin/django-sequences) — aaugustin; gapless sequence via advisory lock
- [Django Forum: race condition in auto-incrementing value](https://forum.djangoproject.com/t/race-condition-in-auto-incrementing-value/16594) — confirms max()+1 is unsafe under concurrency

---

*Stack research for: Organisation Admin module — Google OAuth, field encryption, Places validation, region sequencing*
*Researched: 2026-04-27*
