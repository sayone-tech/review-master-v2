---
paths:
  - "apps/integrations/openai/**/*.py"
  - "apps/reviews/services/enrichment.py"
  - "apps/reviews/services/reclassify.py"
  - "apps/reviews/services/finalise.py"
---

# OpenAI Enrichment & Canonical Tag Rules

Concise reminder — full detail in CLAUDE.md §14 (OpenAI/cost) + §29 (Canonical Tag System).

- **One GPT call per review** — the single combined structured-JSON prompt does sentiment + tags + canonical mapping + action items. **Never** add a second OpenAI call or a vector DB (§14.2, §29.2).
- **Exactly one `AiUsageLog` row per call.** Cost is computed **server-side** from `AiPricing` (never OpenAI's billing API). Never bypass the `AiUsageLog` write (§14.3).
- **Idempotency (§14.7 / §12.4):** if `enrichment_status == SUCCESS` → return immediately (no call, no cost). Per-review Redis lock `lock:enrich:review:{id}`; status transitions under `select_for_update()` in `transaction.atomic()`.
- **`review_count` is derive-on-read — NEVER increment inline.** `bulk_update` field lists must **exclude** `review_count` unless you are the aggregate-refresh path (§29.2). Canonical **label is FK-only** (rename is O(1) on `OrgCanonicalTag`); no per-tag aggregate loops (single grouped query, §6).
- **PII:** never log review text or prompts containing review content at INFO+ (§22). LangSmith is best-effort, non-blocking.
- **Versioned prompts:** bump `ENRICHMENT_PROMPT_VERSION` on wording changes; do **not** trigger bulk re-enrichment.
- **Rate limits:** global Redis token bucket (`rate:openai:org`, `OPENAI_GLOBAL_RATE_LIMIT`) is primary; per-worker Celery `rate_limit` is the secondary guard (§7.7, §29).
- **Tests NEVER hit real OpenAI** — mock with `respx` / the fixtures in `apps/integrations/openai/tests/fixtures/` (§14.10).
