---
phase: 30-metered-ai-reply-generation
plan: 02
subsystem: api
tags: [openai, moderation, timeouts, credits, django-settings, pytest]

requires:
  - phase: 30-metered-ai-reply-generation
    provides: "Plan 30-01 metered reserve -> OpenAI -> commit/refund path (same wave, no shared files)"
provides:
  - "ContentModeratedException(message, *, stage, usage_log_id) with both attributes defaulting to None"
  - "moderate_input / moderate_output carry stage and the MODERATED AiUsageLog pk, and accept optional timeout / max_retries"
  - "client._get_reply_client(): bounded with_options copy (30 s, 1 retry) used only by the reply chat call"
  - "client.REPLY_MODERATION_MAX_RETRIES = 0"
  - "APITimeoutError / APIConnectionError on the reply path become OpenAITransientError (one create call, no untraced second call)"
  - "REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS=30, REVIEWBEE_REPLY_OPENAI_MAX_RETRIES=1 and TTL budget tests"
affects: [30-03, 30-04, 31-reaper-lapse]

actuals:
  tokens: 9000
  tasks: 2
  commits: 4
plan_head_before: 9e649fe20b1c022ea72f2a9dff053fb8c248d151
plan_head_after: b19f4c896f9752bb2111697f03b138b07fcd1079

tech-stack:
  added: []
  patterns:
    - "Per-call bounded client via _get_client().with_options(...) read from settings at call time; the shared singleton is never mutated"
    - "Options dict built from only the provided keys so callers that pass nothing see an unchanged call signature"
    - "Settings-margin tests: a pure budget helper with a deliberate violation case and an inclusive-boundary case"

key-files:
  created: []
  modified:
    - apps/integrations/openai/exceptions.py
    - apps/integrations/openai/guardrails.py
    - apps/integrations/openai/client.py
    - apps/integrations/openai/tests/test_guardrails.py
    - apps/integrations/openai/tests/test_client.py
    - apps/credits/tests/test_settings.py
    - config/settings/base.py

key-decisions:
  - "Exception carries only stage and an int id (T-20-LK); no categories or text"
  - "_map_openai_error and _do_responses_parse are untouched; the APIConnectionError mapping lives only in the reply chat call so enrichment keeps Celery retries"
  - "Whole-request budget is 190 s for the configured values (two bounded moderation calls with app retry + 1 s sleep, chat call with SDK retry and 8 s backoff allowance), 110 s under the 300 s TTL"

patterns-established:
  - "test_settings.py imports REPLY_MODERATION_MAX_RETRIES from the OpenAI client (test-only import; credits production code still never imports reviews)"

requirements-completed: [CCON-05, CCON-06, CCON-08]

coverage:
  - id: D1
    description: "Moderation block reports stage and the MODERATED AiUsageLog id (input and output); None id and no row when review is None; bare exception defaults to None; no categories or text on the exception"
    requirement: "CCON-05"
    verification:
      - kind: unit
        ref: "apps/integrations/openai/tests/test_guardrails.py#TestModerationStageAndUsageLog"
        status: pass
    human_judgment: false
  - id: D2
    description: "Moderation can be bounded by timeout / max_retries through with_options; with no options with_options is never called and _call_moderation_api sees no new kwargs; app-level retry still makes 2 attempts"
    requirement: "CCON-08"
    verification:
      - kind: unit
        ref: "apps/integrations/openai/tests/test_guardrails.py#TestModerationOptions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Reply chat client is a bounded copy (timeout 30, max_retries 1, values pass through unchanged, shared client untouched) and enrichment still uses the shared client"
    requirement: "CCON-08"
    verification:
      - kind: unit
        ref: "apps/integrations/openai/tests/test_client.py#TestReplyClient"
        status: pass
    human_judgment: false
  - id: D4
    description: "APITimeoutError and APIConnectionError on the reply path raise OpenAITransientError after exactly one create call"
    requirement: "CCON-08"
    verification:
      - kind: unit
        ref: "apps/integrations/openai/tests/test_client.py#TestReplyTimeoutMapping"
        status: pass
    human_judgment: false
  - id: D5
    description: "Whole-request budget fits inside the reservation TTL; helper flags a 60 s timeout; boundary equality passes; defaults and the 10/minute generate_reply throttle are pinned"
    requirement: "CCON-08"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_settings.py#test_whole_request_budget_fits_inside_reservation_ttl"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-11-11
status: complete
---

# Phase 30 Plan 02: Bounded reply path and moderation stage Summary

**Moderation blocks now say which stage blocked and which MODERATED AiUsageLog row they wrote, the reply chat call runs on a 30 s / 1-retry `with_options` copy, a timeout is a single traced transient error, and a settings test proves the whole request fits inside the 5-minute reservation TTL.**

## Accomplishments

- `ContentModeratedException` takes keyword-only `stage` and `usage_log_id` (default `None`); the enrichment caller ignores both and is unchanged.
- `_persist_moderated_log` returns the new row's pk; `moderate_input` / `moderate_output` raise with `stage="input"` / `"output"` and that pk (None when `review=None`, no row written).
- `moderate_input` / `moderate_output` / `_moderate_with_retry` / `_call_moderation_api` accept `timeout` and `max_retries`; only given keys are forwarded, so existing tests that assert `_call_moderation_api("text")` still hold and enrichment never calls `with_options`.
- `_get_reply_client()` and `REPLY_MODERATION_MAX_RETRIES` added; `_do_chat_completions_create` uses the bounded client and maps `APIConnectionError` (covers `APITimeoutError`) to `OpenAITransientError`, so a timeout cannot reach the untraced fallback that would bill a second call.
- Two settings added next to the TTL; TTL (5) and the `generate_reply` throttle (`10/minute`) untouched.
- Budget tests: helper returns 190 for the configured values, 370 for a 60 s timeout (flagged as a violation), and exactly 300 at the inclusive boundary.

## Task Commits

1. **Task 1 RED:** `a3821bf` (test) - 8 of the new tests failed
2. **Task 1 GREEN:** `7c08438` (feat)
3. **Task 2 RED:** `68a4a04` (test) - collection ImportError on the new symbols
4. **Task 2 GREEN:** `b19f4c8` (feat)

## Verification Results (real output)

| Command | Result |
|---|---|
| `pytest apps/integrations/openai/tests/test_guardrails.py apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_reply_generation_service.py` | 83 passed |
| `pytest test_guardrails.py -k "stage or usage_log or with_options or options"` | 11 passed, 21 deselected |
| `pytest apps/integrations/openai/tests/test_client.py apps/credits/tests/test_settings.py` | 30 passed |
| `pytest apps/integrations/openai apps/credits/tests/test_settings.py apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_enrichment_service.py` | 150 passed |
| `mypy apps/integrations/openai apps/credits config` | Success: no issues found in 59 source files |
| `ruff check` / `ruff format --check` on the same paths | All checks passed / 59 files already formatted |
| `pytest apps/ -q -o addopts=""` (full suite) | **1401 passed, 5 skipped** (baseline 1378 passed after 30-01) |
| pre-commit hooks on every commit (no `--no-verify`) | passed (the RED commit needed one re-stage after ruff-format) |

Acceptance greps: `usage_log_id=usage_log_id` 2, `with_options` in guardrails 2, `usage_log_id` in exceptions 2, `def _get_reply_client` 1, `APIConnectionError` 1, `_get_reply_client().chat.completions.create` 1, `_get_client().chat.completions.create` 0, `_get_client().responses.parse` 1 (invariant held), both new settings present, `"generate_reply": "10/minute"` 1.

Not run: `make test` (Docker unresponsive; used `.venv`), no real OpenAI call (all mocked per CLAUDE.md section 14.10).

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

- The new `TestReplyClient` real-SDK test resets the module `_client` singleton with `monkeypatch` before and after so no client leaks across tests.
- `test_settings.py` imports `REPLY_MODERATION_MAX_RETRIES` from the OpenAI client as a test-only import; the existing tiers-referencer scan is unaffected.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. T-30-08..11 are mitigated as planned.

## Next Phase Readiness

Important for Plan 30-03: the reply service (`apps/reviews/services/reply_generation.py`, lines ~145 and ~194) still calls `moderate_input` / `moderate_output` without `timeout` / `max_retries`. This plan only makes the options available. Plan 30-03's orchestrator must pass `timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS, max_retries=REPLY_MODERATION_MAX_RETRIES` on both calls, otherwise the 190 s budget the test asserts is not actually enforced for moderation (D-15). The exception's `stage` and `usage_log_id` are ready for the consume-versus-refund split.

## Self-Check: PASSED

- Modified files present: exceptions.py, guardrails.py, client.py, test_guardrails.py, test_client.py, test_settings.py, base.py.
- Commits `a3821bf`, `7c08438`, `68a4a04`, `b19f4c8` are ancestors of HEAD; `commits: 4` measured from the persisted ledger.
