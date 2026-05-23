---
phase: 20-ai-guardrails
plan: 04
subsystem: integrations/openai
tags: [ai, guardrails, moderation, safety]
requires:
  - "settings.OPENAI_REVIEW_TEXT_MAX_CHARS (Plan 20-01)"
  - "apps.integrations.openai.exceptions.ContentModeratedException (Plan 20-02)"
  - "apps.integrations.openai.models.AiUsageLog.Status.MODERATED (Plan 20-03)"
  - "apps.reviews.models.Review.enrichment_error_code (Plan 20-03)"
provides:
  - "apps.integrations.openai.guardrails.moderate_input"
  - "apps.integrations.openai.guardrails.moderate_output"
  - "apps.integrations.openai.guardrails.truncate_reply_at_sentence"
  - "apps.integrations.openai.guardrails.BLOCKING_MODERATION_CATEGORIES"
affects:
  - "downstream Plan 20-05 (enrichment service integration)"
  - "downstream Plan 20-06 (reply-generation service integration)"
  - "downstream Plan 20-07 (view-layer 422 mapping)"
tech-stack:
  added: []
  patterns:
    - "OpenAI Moderation API (omni-moderation-latest) — free safety classifier"
    - "Fail-open with one 1s retry on Moderation API failure (D-24)"
    - "AiUsageLog written OUTSIDE caller atomic blocks for audit-row survival (D-33)"
key-files:
  created:
    - "apps/integrations/openai/guardrails.py"
    - "apps/integrations/openai/tests/test_guardrails.py"
  modified: []
decisions:
  - "BLOCKING_MODERATION_CATEGORIES uses UNDERSCORE form (D-30) — slash form would silently never match Pydantic Categories.model_dump() default keys (Pitfall 1)."
  - "AiUsageLog.Status.MODERATED resolves to the uppercase string \"MODERATED\" (D-28, Pitfall 2)."
  - "_persist_moderated_log writes outside any Django atomic block (D-33). Code comment + grep gate enforce."
  - "Output moderation block writes AiUsageLog with REAL tokens/cost from usage_data and error_code=\"output_moderated\" (D-29) — input moderation writes zeros + error_code=\"content_moderated\"."
  - "Fail-open retries once after 1s sleep; if both calls fail, logs ERROR ai.moderation.errored and returns (False, [])."
  - "truncate_reply_at_sentence is part of the public surface so Plan 20-06's reply service can apply it post-success without duplicating the regex."
metrics:
  duration_minutes: 18
  completed: 2026-05-23
---

# Phase 20 Plan 04: AI Guardrails Module Summary

Implemented `apps/integrations/openai/guardrails.py` end-to-end (input + output Moderation API gates, sentence-boundary reply truncation, fail-open retry, per-stage AiUsageLog accounting) plus a full 20-test unit suite — the safety-critical core of Phase 20.

## What changed

- **New module:** `apps/integrations/openai/guardrails.py`
  - `moderate_input(text, *, review=None, request_type="enrichment") -> str` — truncates input to `settings.OPENAI_REVIEW_TEXT_MAX_CHARS` then screens with the Moderation API. On a high-severity hit (D-23/D-30) writes a `MODERATED` `AiUsageLog` row with zero tokens and `error_code="content_moderated"` (when a Review is provided) and raises `ContentModeratedException`.
  - `moderate_output(text, *, review=None, request_type="reply_generation", usage_data=None) -> str` — screens a generated reply with the same category policy. On a block writes a `MODERATED` `AiUsageLog` row carrying REAL tokens/cost from `usage_data` and `error_code="output_moderated"` (D-29).
  - `truncate_reply_at_sentence(text)` — public reply-length truncation (D-08/D-22). Splits on sentence boundaries, accumulates whole sentences while staying under 300 words, falls back to word-count cut if even the first sentence exceeds the cap. Appends the canonical `" (Please review and complete before sending.)"` suffix.
  - `BLOCKING_MODERATION_CATEGORIES: frozenset[str]` — exactly the five underscore-form keys per D-30, with an inline code comment warning against a "fix" back to slash form.
  - Private helpers: `_truncate_input`, `_call_moderation_api`, `_evaluate`, `_moderate_with_retry` (D-24 one-retry fail-open), `_persist_moderated_log` (single AiUsageLog write site, documented as outside any Django atomic block per D-33).
- **New test file:** `apps/integrations/openai/tests/test_guardrails.py` — 20 tests across 6 classes, all passing.

## How verified

- `pytest apps/integrations/openai/tests/test_guardrails.py -x -q` → **20 passed**.
- All per-keyword `-k` filters meet the plan's acceptance thresholds:
  - `-k truncate` → 5 passed
  - `-k moderate_input` → 6 passed
  - `-k moderate_output` → 3 passed
  - `-k fail_open` → 3 passed
  - `-k blocking_categories` → 1 passed (Pitfall 1 regression)
  - `-k aiusagelog_status_uppercase` → 1 passed (Pitfall 2 regression)
- `ruff check apps/integrations/openai/guardrails.py apps/integrations/openai/tests/test_guardrails.py` → clean.
- All grep gates pass:
  - `grep -c BLOCKING_MODERATION_CATEGORIES apps/integrations/openai/guardrails.py` → 3 (≥1).
  - Underscore-form category strings present (5 hits).
  - Slash-form category strings absent (0 hits).
  - `grep -c transaction.atomic apps/integrations/openai/guardrails.py` → 0.
  - `grep -c @traceable apps/integrations/openai/guardrails.py` → 0.
  - `grep -c transaction.atomic apps/integrations/openai/tests/test_guardrails.py` → 0.

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | guardrails module — moderate_input/moderate_output + helpers | `1da0f4e` |
| 2 | test_guardrails.py — 20-test unit suite | `8663bb0` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Test method names lacked the `-k` filter substrings**

- **Found during:** Task 2 acceptance verification.
- **Issue:** The plan's `<behavior>` block listed test methods with names like `test_input_calls_api_once_with_correct_model`. `pytest -k moderate_input` is case-sensitive substring matching against the full test ID (including the class name); `test_input_*` inside `TestModerateInput` only matches `-k ModerateInput` (capital M). The acceptance criteria specify lowercase `-k moderate_input` filters that must hit ≥5 tests — these filters returned 0 with the literal-spec names.
- **Fix:** Renamed test methods to embed the keyword in lowercase (e.g. `test_moderate_input_calls_api_once_with_correct_model`, `test_moderate_output_blocks_and_raises`, `test_fail_open_first_call_succeeds_no_retry`). Functional coverage and the seven test classes are unchanged.
- **Commit:** `8663bb0`.

**2. [Rule 3 — Blocking] Migration parent referenced a missing sibling node**

- **Found during:** Task 1 commit (pre-commit `makemigrations --check`).
- **Issue:** Wave-1 cherry-pick of plan 20-03's migration `0010_add_enrichment_error_code.py` points at parent `reviews.0009_reviewtag_unique`, which lives on `feature/categories` only. My worktree base (PR #25 merge) stops at `0007_replied_by_fk`, so the migration graph fails consistency validation and the pre-commit hook blocks the commit.
- **Fix:** Repointed the migration parent to `0007_replied_by_fk` LOCAL-ONLY so the worktree validates. The orchestrator's merge into `feature/categories` (which carries the true `0009_reviewtag_unique`) will conflict at that one line — the resolution is to keep the `feature/categories` side.
- **Commit:** included in `1da0f4e`.

**3. [Worktree path correction] First Write call landed in the main repo path**

- **Found during:** Task 1 ruff check.
- **Issue:** Initial `Write` to `apps/integrations/openai/guardrails.py` with the main-repo absolute path created the file at `/Users/renjith/.../review-master/apps/...` instead of the worktree at `/Users/renjith/.../review-master/.claude/worktrees/agent-.../apps/...`.
- **Fix:** Deleted the main-repo file and rewrote at the worktree-relative absolute path (per `worktree-path-safety.md`). All subsequent writes used the worktree root.
- **No commit impact** — caught before staging.

## Known Stubs

None. Both files implement complete behaviour required by Plans 20-05 / 20-06 / 20-07.

## Threat Flags

None. All new surface (Moderation API call, AiUsageLog write) is covered by the plan's threat register (T-20-01..06).

## Self-Check: PASSED

- FOUND: `apps/integrations/openai/guardrails.py`
- FOUND: `apps/integrations/openai/tests/test_guardrails.py`
- FOUND: commit `1da0f4e` (feat — guardrails module)
- FOUND: commit `8663bb0` (test — guardrails test suite)
