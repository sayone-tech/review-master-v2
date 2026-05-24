---
phase: 20-ai-guardrails
plan: 07
subsystem: reviews
tags: [view-layer, http-mapping, moderation, error-handling]
requires: [20-02, 20-06]
provides: ["ContentModeratedException → HTTP 422 with canonical body"]
affects: [apps/reviews/views.py, apps/reviews/tests/test_views.py]
tech_stack:
  added: []
  patterns: [DRF Response with explicit status, most-specific-exception-first catch chain]
key_files:
  created: []
  modified:
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py
decisions: [D-16, D-26, D-32]
metrics:
  duration: ~10 min
  completed: 2026-05-23
---

# Phase 20 Plan 07: ContentModeratedException → HTTP 422 Mapping Summary

Mapped `ContentModeratedException` to a single canonical HTTP 422 response in `ReviewViewSet.generate_reply` (D-16/D-26/D-32) and added three regression tests guarding the canonical D-26 body and the T-20-LK information-leakage boundary.

## What changed

### `apps/reviews/views.py`
- Added `ContentModeratedException` to the existing OpenAI exceptions import block (kept alphabetical so ruff isort is satisfied).
- Inserted a new `except ContentModeratedException:` block in `generate_reply` **before** the existing `except (OpenAITransientError, OpenAIPermanentError)` block. Order matters because `ContentModeratedException` inherits from `OpenAIError` — the base also exhaled by the transient/permanent exceptions. If the order were reversed the moderation case would map to 502 instead of 422.
- New block returns `Response({"code": "content_moderated", "detail": "AI reply isn't available for this review. Please write your reply manually."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)`. The detail string is a single-line literal so `grep -F` (per the plan's acceptance criterion) matches.
- Added an INFO-level log `generate_reply blocked by moderation review_id=%s`. INFO-only — no review text, no moderation categories (T-20-LK + CLAUDE.md §22).

### `apps/reviews/tests/test_views.py`
Three new tests appended to `TestGenerateReplyEndpoint`:
- `test_generate_reply_returns_422_on_content_moderated`: full-body equality check.
- `test_generate_reply_422_canonical_detail_string_byte_exact`: byte-exact check on the `detail` field — regression guard against accidental rewording.
- `test_generate_reply_422_does_not_leak_categories_or_review_text`: asserts the JSON keys are exactly `{"code", "detail"}` — T-20-LK information-disclosure mitigation.

Imported `ContentModeratedException` alongside the existing OpenAI exception imports.

## Decisions honoured
- **D-16:** `ContentModeratedException` is the single signal for input-or-output moderation and surfaces to the user as HTTP 422.
- **D-26:** canonical user-facing copy `"AI reply isn't available for this review. Please write your reply manually."` used verbatim.
- **D-32:** catch hierarchy ordered most-specific-first; `ContentModeratedException` before `(OpenAITransientError, OpenAIPermanentError)`.

## Deviations from Plan
None — plan executed as written.

## Verification

| Check | Result |
|---|---|
| `grep -n 'except ContentModeratedException' apps/reviews/views.py` | 1 match at line 277 |
| `grep -n 'except (OpenAITransientError, OpenAIPermanentError)' apps/reviews/views.py` | still present at line 294 |
| Catch-order awk gate | passes (cm=277, tp=294) |
| `grep -F` canonical detail string | 1 match at line 290 |
| `grep -n 'HTTP_422_UNPROCESSABLE_ENTITY'` in views.py | present in new block |
| `python -c "import ast; ast.parse(...)"` | parse OK |
| `ruff check apps/reviews/views.py` | All checks passed |
| `ruff check apps/reviews/tests/test_views.py` | All checks passed |
| `pytest apps/reviews/tests/test_views.py -k "content_moderated or canonical_detail or does_not_leak"` | 3 passed |

## Commits

- `8f3af6a` — feat(20-07): map ContentModeratedException to HTTP 422 in generate_reply
- `21f0e3c` — test(20-07): cover ContentModeratedException -> 422 in generate_reply

(Note: the Task-1 commit also touched `apps/reviews/tests/test_views.py` because the worktree base predated the Phase 11 view+test additions and the file had to be brought up to feature/categories baseline before this plan could land. The substantive plan-20-07 test code was added in commit `21f0e3c`.)

## Threat surface

No new endpoints, schema, or trust boundaries. The change is a single new exception → HTTP response branch within an existing endpoint. The response body is constant (no LLM data flows into it) so T-20-LK is mitigated by construction; a regression test enforces it.

## Self-Check: PASSED
- `apps/reviews/views.py` — exists, contains new catch block, canonical string, HTTP 422 — verified.
- `apps/reviews/tests/test_views.py` — exists, contains three new tests, three pass under pytest — verified.
- Commits `8f3af6a` and `21f0e3c` exist in `git log`.
