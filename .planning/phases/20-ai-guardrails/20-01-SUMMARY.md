---
phase: 20-ai-guardrails
plan: 01
subsystem: openai-integration
tags: [settings, guardrails, openai, configuration]
requires: []
provides:
  - "settings.OPENAI_REVIEW_TEXT_MAX_CHARS (int, default 4000)"
affects:
  - "config/settings/base.py"
  - ".env.example"
tech_stack:
  added: []
  patterns:
    - "django-environ env.int() with default for tunable integer settings"
key_files:
  created: []
  modified:
    - config/settings/base.py
    - .env.example
decisions:
  - "D-21: OpenAI input length cap is env-configurable (OPENAI_REVIEW_TEXT_MAX_CHARS) with default 4000 characters"
metrics:
  duration: "~5 min"
  completed: "2026-05-23"
  tasks_completed: 1
  files_created: 0
  files_modified: 2
---

# Phase 20 Plan 01: OPENAI_REVIEW_TEXT_MAX_CHARS Setting Summary

**One-liner:** Adds the env-configurable `OPENAI_REVIEW_TEXT_MAX_CHARS` setting (default 4000) so downstream guardrails (Plan 20-04) can truncate review text before OpenAI calls without a code change.

## What was built

- `config/settings/base.py`: Added `OPENAI_REVIEW_TEXT_MAX_CHARS = env.int("OPENAI_REVIEW_TEXT_MAX_CHARS", default=4000)` immediately after `OPENAI_MAX_RETRIES`, with a comment referencing D-21.
- `.env.example`: Added matching documented entry `OPENAI_REVIEW_TEXT_MAX_CHARS=4000` in the existing `OPENAI_*` block, with explanatory comment.

## Tasks executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add OPENAI_REVIEW_TEXT_MAX_CHARS setting + .env.example entry | cea801b | config/settings/base.py, .env.example |

## Verification

- `grep -c "OPENAI_REVIEW_TEXT_MAX_CHARS" config/settings/base.py` → 1
- `grep -c "OPENAI_REVIEW_TEXT_MAX_CHARS=4000" .env.example` → 1
- Python AST syntax check on `config/settings/base.py` → OK
- Pre-commit hooks all passed (ruff-check, ruff-format, mypy, bandit, django-upgrade, missing-migrations check)

**Runtime Django check note:** `python manage.py check --settings=config.settings.local` was not run directly because the agent's host environment has no Python venv (project runs in docker; no project containers were active in the worktree). Pre-commit's `mypy` hook executed against the changed file (which imports `env`) and passed, demonstrating the setting is type-correct. The setting follows the identical pattern of adjacent `OPENAI_MAX_RETRIES`, which is already loaded successfully in production.

## Decisions Made

- **D-21 (locked in CONTEXT):** OpenAI input length cap is env-tunable. Default 4000 chars is conservative for GPT-4o-mini's context window while well above the 99th-percentile review length.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: `config/settings/base.py` (OPENAI_REVIEW_TEXT_MAX_CHARS line present)
- FOUND: `.env.example` (OPENAI_REVIEW_TEXT_MAX_CHARS=4000 line present)
- FOUND: commit `cea801b` (`git log --oneline -1` confirms)
- FOUND: SUMMARY.md at `.planning/phases/20-ai-guardrails/20-01-SUMMARY.md`
