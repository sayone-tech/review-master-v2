---
paths:
  - "apps/**/tests/*.py"
  - "apps/**/tests/**/*.py"
  - "**/conftest.py"
---

# Python Test Rules (pytest + pytest-django)

Scope: backend tests under `apps/<app>/tests/`. Reinforces CLAUDE.md §16 + §6.9.

## Naming & structure
- Descriptive test names: `test_<behavior>_when_<condition>` (e.g. `test_returns_403_when_staff_user`).
- One test file per module: `test_models.py`, `test_services.py`, `test_selectors.py`, `test_views.py`, `test_tasks.py`.
- Use `factory-boy` factories from `apps/<app>/tests/factories.py` — **never** hand-build rows with `.objects.create()` in tests when a factory exists. One factory per model.

## Isolation — never hit the outside world
- **Never hit external APIs.** Mock the Google client with `responses`/`respx`; **mock the OpenAI client** (a real call in a test is a bug) — use the deterministic fixtures in `apps/integrations/openai/tests/fixtures/`.
- Mock **external dependencies, not internal modules** — patch the seam (`apps.reviews.services.enrichment.call_openai_enrichment`, the Google client), not your own services/selectors.
- No real Redis/network: lock/cache/token-bucket helpers are patched. Channels consumers use `channels.testing.WebsocketCommunicator`.
- Celery: rely on `CELERY_TASK_ALWAYS_EAGER` (test settings) and test the **service function**, not the task wrapper.

## Query-count discipline (§6.9 — blocker-level)
- Every list endpoint and every aggregate-heavy path needs a query-count test using `django.test.utils.CaptureQueriesContext`, asserting a **fixed ceiling independent of result size** (`<= N`, not proportional). Prove no-N+1 by asserting the count is identical for, say, 2 vs 5 rows.

## Multi-tenant + coverage
- Cross-tenant tests are mandatory for auth/scoped surfaces: assert org A cannot read/write org B (selectors, viewsets, consumers, tasks).
- Target ≥ 85% line coverage on services, selectors, and permissions.
- Use `@pytest.mark.django_db` (or the `db` fixture); clean side effects via fixtures/`addfinalizer`, not module globals.
