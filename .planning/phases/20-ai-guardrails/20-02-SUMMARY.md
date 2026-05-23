---
phase: 20-ai-guardrails
plan: 02
subsystem: integrations/openai
tags: [exception, guardrails, contract]
requires: [OpenAIError]
provides: [ContentModeratedException]
affects: [apps/integrations/openai/exceptions.py]
tech-stack:
  added: []
  patterns: [typed-exception-signal]
key-files:
  created: []
  modified:
    - apps/integrations/openai/exceptions.py
decisions:
  - "Honored D-32: ContentModeratedException inherits from OpenAIError, not bare Exception"
  - "Pure signal class — no constructor, no payload; audit context lives in AiUsageLog (D-33)"
  - "Suppressed ruff N818 with file-local noqa since the class name is fixed by the plan contract; renaming to *Error would break downstream plans 20-04/20-07 which import this exact symbol"
metrics:
  duration: ~5min
  completed: 2026-05-23
---

# Phase 20 Plan 02: ContentModeratedException Summary

One-liner: Added the `ContentModeratedException(OpenAIError)` signal class that connects the guardrail layer (Plan 20-04) to the HTTP view layer (Plan 20-07) via a typed `except` clause.

## What Was Built

- New class `ContentModeratedException` in `apps/integrations/openai/exceptions.py` (line 31).
- Inherits from `OpenAIError` so callers can broadly `except OpenAIError` or narrowly `except ContentModeratedException`.
- Single-line docstring referencing the plan's locked decisions (D-16, D-32).
- No constructor, no attributes — by design a pure signal class.

## How Verified

- `grep -nE "class ContentModeratedException\(OpenAIError\)" apps/integrations/openai/exceptions.py` → exactly one match at line 31.
- Python AST parse succeeded.
- Pre-commit hooks all passed (ruff check, ruff format, mypy, bandit, django-upgrade, secrets scan, missing-migrations check).
- Inheritance chain `Exception ← OpenAIError ← ContentModeratedException` is visible by source inspection (single-file module, no dynamic class construction).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking lint] ruff N818 rejected the prescribed class name**

- **Found during:** Task 1 first commit attempt (pre-commit hook).
- **Issue:** Ruff's `N818` rule requires exception class names to end in `Error`, but the plan and its downstream consumers (20-04, 20-07) hard-code `ContentModeratedException`. Renaming would silently break plan contracts captured in `must_haves.artifacts` and `key_links`.
- **Fix:** Added a single-line `# noqa: N818` suppression with a comment citing the plan ID and the locked decisions (D-16/D-32). This is the minimal-surface fix — the lint suppression is local to one line and self-documenting.
- **Files modified:** `apps/integrations/openai/exceptions.py`
- **Commit:** dc52428

## Threat Flags

None — no new network surface, no new auth path, no new trust boundary.

## Self-Check: PASSED

- File exists: `apps/integrations/openai/exceptions.py` — FOUND
- Commit exists: `dc52428` — FOUND
- Class match: `class ContentModeratedException(OpenAIError):` at line 31 — FOUND
- Pre-commit hooks: all PASSED
