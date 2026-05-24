---
phase: 19-ai-reply-generation
plan: 01
subsystem: reviews/openai
tags: [ai, openai, reply-generation, service-layer, langsmith, ai-usage-log]
requires:
  - apps.integrations.openai.exceptions (OpenAITransientError, OpenAIPermanentError)
  - apps.integrations.openai.models.AiUsageLog
  - apps.integrations.openai.pricing.calculate_cost
provides:
  - apps.integrations.openai.prompts.REPLY_GENERATION_PROMPT_VERSION (= 1)
  - apps.integrations.openai.prompts.build_reply_generation_messages
  - apps.integrations.openai.client.call_openai_reply_generation
  - apps.reviews.services.reply_generation.generate_reply_draft
affects:
  - apps/integrations/openai/prompts.py (extended)
  - apps/integrations/openai/client.py (extended; existing call_openai_enrichment unchanged)
  - apps/integrations/openai/tests/test_client.py (extended)
  - apps/integrations/openai/tests/test_prompts.py (new)
  - apps/reviews/services/reply_generation.py (new)
  - apps/reviews/tests/test_reply_generation_service.py (new)
tech-stack:
  added: []
  patterns:
    - Chat Completions API (response_format text) — first use in this codebase
    - @traceable LangSmith with best-effort fallback (mirrors enrichment pattern)
    - Service-layer try/except OpenAITransientError|OpenAIPermanentError|Exception → FAILED log + re-raise
key-files:
  created:
    - apps/reviews/services/reply_generation.py
    - apps/reviews/tests/test_reply_generation_service.py
    - apps/integrations/openai/tests/test_prompts.py
  modified:
    - apps/integrations/openai/prompts.py
    - apps/integrations/openai/client.py
    - apps/integrations/openai/tests/test_client.py
decisions:
  - "Cast messages/response_format through Any for chat.completions.create — SDK overloads use heavy TypedDicts that don't accept plain dict[str, str] at static-check time but do at runtime (same workaround as responses.parse uses for input=)"
  - "AiUsageLog FAILED rows for generic exceptions use prompt_tokens=None / cached_tokens=0 / cost=Decimal('0') — request never reached OpenAI so no tokens consumed"
  - "_write_failure_log wraps create() in try/except — defensive guard so a DB write failure inside the failure handler does not mask the original exception"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-22"
---

# Phase 19 Plan 01: AI Reply Generation — Service Layer Summary

**One-liner:** Service-layer scaffolding for AI reply generation — locked Professional/Friendly system prompts, Chat Completions API client function with LangSmith tracing, and a thin service that orchestrates the call and writes AiUsageLog rows (success or failure) on every invocation.

## What was built

### 1. Prompt templates (`apps/integrations/openai/prompts.py`)
- `REPLY_GENERATION_PROMPT_VERSION = 1` constant (D-08)
- `PROFESSIONAL_REPLY_SYSTEM_PROMPT` — exact D-05 wording verbatim
- `FRIENDLY_REPLY_SYSTEM_PROMPT` — exact D-06 wording verbatim
- `build_reply_generation_messages(*, review, tone, brand_name)` returns `[system, user]` ready for `chat.completions.create`. Unknown tones raise `ValueError`.

### 2. OpenAI client (`apps/integrations/openai/client.py`)
- New `call_openai_reply_generation(*, review, tone, model=None)` → `(draft_text, usage_data)`
- Uses `_get_client().chat.completions.create` with `response_format={"type": "text"}` per D-07 (NOT `responses.parse` — this is plain text, not structured JSON)
- New `_call_openai_reply_with_tracing` mirrors `_call_openai_with_tracing` but uses Chat Completions field names. `@traceable(run_type="llm", name="generate_reply")` with best-effort LangSmith fallback to direct call on tracing exceptions
- New `_extract_reply_usage` — separate from `_extract_usage` because Chat Completions uses `prompt_tokens`/`completion_tokens`/`prompt_tokens_details.cached_tokens` (not Responses API's `input_tokens`/`output_tokens`/`input_tokens_details.cached_tokens`)
- New `_do_chat_completions_create` — single SDK entry point with shared `_map_openai_error` exception mapping
- Existing `call_openai_enrichment` and the Responses-API path are untouched

### 3. Service (`apps/reviews/services/reply_generation.py` — new file)
- `generate_reply_draft(*, review: Review, tone: str) -> str`
- Belt-and-braces tone validation (`ValueError` for unknown tones — short-circuits before any OpenAI call so no AiUsageLog row is written)
- On success: computes cost via `calculate_cost`, writes one `AiUsageLog(request_type="reply_generation", status=SUCCESS, ...)` row
- On `OpenAITransientError` or `OpenAIPermanentError`: writes `status=FAILED` row with `error_code = type(exc).__name__`, then re-raises
- On any other exception (e.g. `ConnectionError`, network timeout — D-17): same FAILED-log-then-raise behaviour. View layer (Plan 19-02) maps to HTTP 502
- No Redis lock or three-layer pattern (unlike enrichment) — synchronous user-initiated action, throttled at the view layer (10/min/user, D-12)

## Tests

| File | New test count |
|---|---|
| `apps/integrations/openai/tests/test_prompts.py` | 6 |
| `apps/integrations/openai/tests/test_client.py` (TestCallOpenAiReplyGeneration) | 4 |
| `apps/reviews/tests/test_reply_generation_service.py` | 5 |

All 15 new tests pass. Existing enrichment tests (28 in `test_enrichment_service.py` + 8 in `test_client.py`) remain green — no regressions.

OpenAI is never hit: tests patch `_get_client` (client tests) or `call_openai_reply_generation` (service tests) per CLAUDE.md §16 / §14.10.

## Deviations from Plan

**None.** Plan executed exactly as written.

Minor implementation-detail notes:
- Plan suggested mocking `_get_client` returning a `MagicMock` whose `chat.completions.create` returns the fake response. Implemented exactly that.
- For mypy strictness, the SDK's `chat.completions.create` typing rejects `list[dict[str, str]]` against its heavily-typed TypedDict union and rejects `{"type": "text"}` against `ResponseFormatText`. Used `cast(Any, ...)` for both — same workaround pattern used by the existing `responses.parse` call site.

## Authentication / Auth Gates

None — service layer only, no new endpoints or external auth interactions in this plan.

## Known Stubs

None.

## Threat Flags

No new trust-boundary surface beyond what the plan's `<threat_model>` already covered. Reply text travels to OpenAI (already-classified boundary in T-19-01) and review text is NOT stored in AiUsageLog (T-19-02 disposition: accept).

## Commits

| Task | Type | Hash | Message |
|---|---|---|---|
| 1 (RED)   | test     | 069bdce | test(19-01): add failing tests for reply generation prompts |
| 1 (GREEN) | feat     | da9dad5 | feat(19-01): add reply generation prompt templates |
| 2 (RED)   | test     | 4271643 | test(19-01): add failing tests for call_openai_reply_generation |
| 2 (GREEN) | feat     | b02a847 | feat(19-01): add call_openai_reply_generation client function |
| 3 (RED)   | test     | 1073acc | test(19-01): add failing tests for generate_reply_draft service |
| 3 (GREEN) | feat     | f3a57dd | feat(19-01): add generate_reply_draft service function |

TDD gate compliance: RED → GREEN cycle followed for all three tasks. No REFACTOR commits needed.

## Self-Check: PASSED

- Files created/modified verified present:
  - `apps/integrations/openai/prompts.py` (modified, contains `REPLY_GENERATION_PROMPT_VERSION = 1`)
  - `apps/integrations/openai/client.py` (modified, exports `call_openai_reply_generation`)
  - `apps/reviews/services/reply_generation.py` (new, exports `generate_reply_draft`)
  - `apps/integrations/openai/tests/test_prompts.py` (new)
  - `apps/integrations/openai/tests/test_client.py` (extended with `TestCallOpenAiReplyGeneration`)
  - `apps/reviews/tests/test_reply_generation_service.py` (new)
- All 6 task commits present in `git log`
- Verification script from PLAN passes (`PASS` output)
- `pytest apps/integrations/openai/tests/test_client.py::TestCallOpenAiReplyGeneration apps/integrations/openai/tests/test_prompts.py apps/reviews/tests/test_reply_generation_service.py` → 15 passed
- `pytest apps/reviews/tests/test_enrichment_service.py` → 28 passed (no regressions)
- `import OK` confirmed for both `generate_reply_draft` and `call_openai_reply_generation`
- pre-commit hooks (ruff, ruff-format, mypy, bandit, gitleaks) ran on every commit and passed
