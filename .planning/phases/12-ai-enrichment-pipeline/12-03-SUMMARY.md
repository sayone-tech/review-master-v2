---
plan: 12-03
phase: 12
status: complete
completed_at: "2026-05-02T16:26:00Z"
duration_minutes: 4
tasks_completed: 2
files_created: 4
files_modified: 1
key-decisions:
  - "@traceable wrapper uses get_current_run_tree() at runtime (not run_tree param injection) — portable across langsmith versions; some older versions don't auto-inject run_tree as a function parameter"
  - "usage_data uses Chat-Completions key names (prompt_tokens/completion_tokens/cached_tokens) not Responses API names — keeps pricing.calculate_cost and Plan 04 call sites stable across SDK API changes (RESEARCH.md Pitfall 2)"
  - "input_tokens_details may be None — guarded with getattr returning 0 to prevent AttributeError (OpenAI SDK community issue #2544)"
  - "Two-path design: traced path via @traceable + untraced direct fallback — non-OpenAI exceptions (LangSmith failures) fall back without raising; openai SDK errors always propagate as custom exceptions"
  - "Lazy _get_client() singleton — defers OpenAI() construction to first real call so module-level import doesn't fail when OPENAI_API_KEY is empty in test settings"
  - "Raw openai.RateLimitError/APIStatusError caught and re-mapped in call_openai_enrichment — they can propagate from the traced path bypassing _do_responses_parse's own mapping"
requirements:
  - ENRCH-01
  - ENRCH-11
  - ENRCH-12
tags:
  - openai
  - langsmith
  - enrichment
  - client
  - tracing
dependency_graph:
  requires:
    - "apps/integrations/openai/parser.py (EnrichmentResult schema)"
    - "apps/integrations/openai/prompts.py (build_enrichment_messages)"
    - "apps/integrations/openai/exceptions.py (custom exception hierarchy)"
  provides:
    - "call_openai_enrichment(review, model) -> (EnrichmentResult, usage_data)"
    - "configure_langsmith() — LangSmith env var setup"
    - "OpenaiConfig.ready() hook"
  affects:
    - "Plan 04 enrichment service (calls call_openai_enrichment)"
tech_stack:
  added:
    - "langsmith @traceable decorator for LangSmith tracing"
    - "langsmith.run_helpers.get_current_run_tree for trace_id capture"
  patterns:
    - "Lazy singleton for SDK client initialization"
    - "Two-path tracing design with best-effort fallback"
    - "Token field name normalization (Responses API -> Chat-Completions naming)"
key_files:
  created:
    - apps/integrations/openai/client.py
    - apps/integrations/openai/tracing.py
    - apps/integrations/openai/tests/test_client.py
    - apps/integrations/openai/tests/test_tracing.py
  modified:
    - apps/integrations/openai/apps.py
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  completed_date: "2026-05-02"
---

# Phase 12 Plan 03: OpenAI Client Wrapper + LangSmith Tracing Summary

## One-Liner

JWT-free OpenAI client wrapper with @traceable LangSmith tracing, Chat-Completions token naming, and best-effort fallback using openai 2.x Responses API structured output parsing.

## What Was Built

Built `call_openai_enrichment(review, model) -> (EnrichmentResult, usage_data)` — the SDK boundary that Plan 04's enrichment service will call. A single GPT call via `client.responses.parse(text_format=EnrichmentResult)` with a two-path design: a `@traceable` path for LangSmith and a direct fallback path when LangSmith is unavailable.

### Files Created

- `apps/integrations/openai/client.py` — main client wrapper with `call_openai_enrichment`, `_call_openai_with_tracing` (@traceable), `_do_responses_parse` (SDK boundary), `_extract_usage` (token field normalization), `_map_openai_error` (exception mapping), and lazy `_get_client()` singleton
- `apps/integrations/openai/tracing.py` — `configure_langsmith()` sets `LANGSMITH_TRACING` env var from `settings.LANGSMITH_ENABLED`; idempotent, safe to call multiple times
- `apps/integrations/openai/tests/test_client.py` — 8 tests covering ENRCH-01, ENRCH-04, ENRCH-11, ENRCH-12
- `apps/integrations/openai/tests/test_tracing.py` — 3 tests covering disabled/enabled/no-key configure_langsmith scenarios

### Files Modified

- `apps/integrations/openai/apps.py` — added `ready()` hook that deferred-imports and calls `configure_langsmith()`

## Key Decisions

### 1. `get_current_run_tree()` over `run_tree` parameter injection

The `@traceable` decorator can auto-inject a `run_tree` parameter when the decorated function declares it. However, not all langsmith versions do this reliably, and the injection depends on the function calling convention. Using `get_current_run_tree()` inside the function body is the portable fallback that works across versions. Both approaches are documented in the plan's interface spec; `get_current_run_tree()` was chosen as the sole method to avoid confusion.

### 2. Chat-Completions key names for usage_data

The OpenAI Responses API uses `input_tokens` / `output_tokens` while the older Chat Completions API uses `prompt_tokens` / `completion_tokens`. The `usage_data` dict returned by `call_openai_enrichment` normalizes to Chat-Completions names. This keeps `pricing.calculate_cost()` (which accepts `prompt_tokens`, `completion_tokens`, `cached_tokens`) and Plan 04's `AiUsageLog` write stable — if the SDK API changes again, only `_extract_usage()` needs updating.

### 3. `input_tokens_details` may be None

The OpenAI SDK's `input_tokens_details` attribute is `None` when no tokens were cached. The extraction code guards: `getattr(details, "cached_tokens", 0) or 0` with a `details` null check. This mirrors the community-reported issue (openai-python #2544) and is explicitly tested in `test_cached_tokens_default_zero_when_details_missing`.

### 4. Two-path tracing design with best-effort fallback

`call_openai_enrichment` has two paths:
1. **Traced path**: calls `_call_openai_with_tracing` (decorated with `@traceable`). If this succeeds, `trace_id` is captured from `get_current_run_tree()`.
2. **Fallback path**: if the traced path raises a non-OpenAI exception (LangSmith library failure, network error), logs a WARNING and calls `_do_responses_parse` directly. `trace_id` becomes `None`.

OpenAI SDK errors (`RateLimitError`, `APIStatusError`) are explicitly re-raised from both paths without falling through to the LangSmith fallback path.

### 5. Lazy `_get_client()` singleton

Module-level `OpenAI()` construction fails when `OPENAI_API_KEY` is empty (as in test settings). Deferring client construction to the first call keeps the module importable in tests where `_do_responses_parse` is always patched before any real call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Raw SDK errors not re-mapped from traced path**

- **Found during:** Task 2 (test failure: `test_rate_limit_raises_transient`)
- **Issue:** `_do_responses_parse` maps `openai.RateLimitError` → `OpenAITransientError`, but when patched to raise the raw `RateLimitError` directly (bypassing the mapping), `call_openai_enrichment` treated the raw SDK error as a LangSmith failure and hit the fallback path instead of re-raising as `OpenAITransientError`.
- **Fix:** Added explicit `except (openai.RateLimitError, openai.APIStatusError)` clause in `call_openai_enrichment` to catch and re-map raw SDK errors that may propagate from the traced path.
- **Files modified:** `apps/integrations/openai/client.py`
- **Commit:** f5058eb

**2. [Rule 3 - Blocking] Module-level OpenAI client construction fails in tests**

- **Found during:** Task 1 import verification
- **Issue:** `OpenAI()` without a key raises `openai.OpenAIError` at import time when `OPENAI_API_KEY` is empty string in test settings.
- **Fix:** Changed to lazy `_get_client()` singleton pattern — client construction deferred to first actual call.
- **Files modified:** `apps/integrations/openai/client.py`
- **Commit:** 4e0cf7f

## Self-Check: PASSED
