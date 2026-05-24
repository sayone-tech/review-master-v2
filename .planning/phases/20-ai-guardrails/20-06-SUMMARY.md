---
phase: 20-ai-guardrails
plan: 06
subsystem: reviews/services/reply_generation
tags: [moderation, reply-generation, guardrails, audit-log]
requires:
  - apps/integrations/openai/guardrails.py  # Plan 20-04
  - apps/integrations/openai/exceptions.py::ContentModeratedException  # Plan 20-04
  - apps/integrations/openai/models.py::AiUsageLog.Status.MODERATED  # Plan 20-03
provides:
  - apps/reviews/services/reply_generation.py::generate_reply_draft (input + output moderation + 300-word truncation)
affects:
  - Plan 20-07 (view layer): ContentModeratedException now propagates from generate_reply_draft → must map to HTTP 422
tech-stack:
  added: []
  patterns:
    - "Lightweight read-only proxy (_ReviewWithModeratedComment) to override one attribute without mutating the source model"
    - "Compute cost BEFORE the moderation gate and inject into usage_data so the audit row carries real cost even when the gate fires"
key-files:
  created: []
  modified:
    - apps/reviews/services/reply_generation.py
    - apps/reviews/tests/test_reply_generation_service.py
    - apps/reviews/tests/factories.py  # Rule 3 fix — see Deviations
decisions:
  - "Adapt prompt assembly via SimpleNamespace-style proxy class (option b in PLAN) — chosen over modifying call_openai_reply_generation signature (b minimizes ripple; client.py untouched) or mutating review.comment in place (rejected — accidental save would persist truncation suffix)."
  - "Cost calculation moved BEFORE moderate_output (was AFTER in Phase 19 code) so usage_data['estimated_cost_usd'] is populated when guardrails writes the MODERATED row. Otherwise the output-moderation audit row would record cost=0 even though the OpenAI call consumed billable tokens."
  - "test_moderate_calls_outside_atomic_block uses @pytest.mark.django_db(transaction=True) to disable pytest-django's default test-wrapping atomic block — otherwise in_atomic_block would always report True and the D-33 regression check would be vacuous."
metrics:
  duration: ~25min
  tasks_completed: 2
  files_modified: 3
  completed_date: 2026-05-23
---

# Phase 20 Plan 20-06: Reply-Generation Moderation Wiring Summary

Wired `moderate_input` + `moderate_output` + `truncate_reply_at_sentence` into `generate_reply_draft` per D-07 / D-08 / D-14 / D-22 / D-29 / D-33, with a runtime regression test for the atomic-block discipline that protects the audit-row integrity.

## Implementation

### Call sequence in `generate_reply_draft` after the change

1. Tone validation (existing).
2. `moderate_input(review.comment, review=review, request_type="reply_generation")` — D-14. Returns truncated text or raises `ContentModeratedException` (which propagates uncaught to the view).
3. `call_openai_reply_generation(review=review_for_prompt, ...)` — the OpenAI call receives a `_ReviewWithModeratedComment` proxy exposing the truncated comment while delegating every other attribute (`shop`, `star_rating`, `pk`, `organisation_id`, `shop_id`) to the wrapped `Review`. The raw `Review.comment` is never mutated.
4. **Cost calculation** (moved earlier from Phase 19's position): `calculate_cost(...)`. The Decimal is injected into `usage_data["estimated_cost_usd"]`.
5. `moderate_output(draft, review=review, request_type="reply_generation", usage_data=usage_data)` — D-07/D-29. The MODERATED audit row written by guardrails on a block carries real tokens AND real cost from `usage_data`.
6. `draft = truncate_reply_at_sentence(draft)` — D-08/D-22. Length cap applied AFTER output moderation (presentation transform of an already-safe draft, not a safety gate).
7. SUCCESS `AiUsageLog` write (existing).
8. Return `draft`.

Steps 2 and 5 are both OUTSIDE any `transaction.atomic` block (D-33).

### `_ReviewWithModeratedComment` proxy

```python
class _ReviewWithModeratedComment:
    __slots__ = ("_review", "comment")

    def __init__(self, review: Review, comment: str) -> None:
        object.__setattr__(self, "_review", review)
        object.__setattr__(self, "comment", comment)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._review, name)
```

Two-attribute `__slots__` so `comment` is a real attribute (Python's attribute-lookup MRO finds it directly without invoking `__getattr__`). All other access falls through to the wrapped Review. Chose this over `types.SimpleNamespace`-copy (would lose the actual model identity for downstream type checks) and over modifying `call_openai_reply_generation`'s signature (would ripple into prompt assembly and Phase 19 tests).

## Tests

`TestGenerateReplyDraftModeration` adds **7 tests** (all in `apps/reviews/tests/test_reply_generation_service.py`):

| # | Test | Decision Covered |
|---|------|------------------|
| 1 | `test_moderate_input_called_before_openai_call` | D-14 (ordering) |
| 2 | `test_input_moderation_block_raises_and_skips_openai` | D-14 (fail-closed) |
| 3 | `test_output_moderation_block_writes_aiusagelog_with_real_tokens` | D-29 (real cost + tokens + `error_code="output_moderated"`) — exercises real `moderate_output` end-to-end, only `_call_moderation_api` is mocked |
| 4 | `test_output_truncation_applied_after_moderation_pass` | D-08/D-22 (320 words → ≤300 + canonical suffix) |
| 5 | `test_short_reply_not_truncated` | D-08 boundary (150 words → unchanged) |
| 6 | `test_truncated_input_flows_into_openai` | D-14 (proxy forwards truncated comment; original Review.comment unmutated) |
| 7 | `test_moderate_calls_outside_atomic_block` | D-33 runtime regression — records `transaction.get_connection().in_atomic_block` at both call sites and asserts `[False, False]`. Uses `@pytest.mark.django_db(transaction=True)` to disable pytest-django's default test-wrapping atomic block. |

All 12 tests in the file (5 existing Phase 19 + 7 new Phase 20) pass:
```
12 passed in 1.08s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Stale `tags: ClassVar[list] = []` in `ReviewFactory`**
- **Found during:** Task 2 first test run
- **Issue:** `ReviewFactory()` raised `TypeError: Direct assignment to the reverse side of a related set is prohibited. Use tags.set() instead.` because the factory still assigned a list to `tags`, which became a reverse FK manager when plan 17-01 replaced `Review.tags` (JSONField) with `ReviewTag` (separate model). Pre-existing bug in this worktree's base; feature/categories already had it dropped.
- **Fix:** `git checkout feature/categories -- apps/reviews/tests/factories.py` — pulls the up-to-date factory without the stale field.
- **Files modified:** apps/reviews/tests/factories.py
- **Commit:** 3d968bb

**2. [Rule 3 — Blocking] Phase 19 tests now needed `moderate_input`/`moderate_output` mocks**
- **Found during:** Task 1 GREEN gate
- **Issue:** After wiring, the 4 existing `TestGenerateReplyDraft` tests called the real `moderate_input` (which initialized the OpenAI client without an `OPENAI_API_KEY` env var) and crashed.
- **Fix:** Added `patch("apps.reviews.services.reply_generation.moderate_input", side_effect=lambda text, **kw: text)` (and `moderate_output` for the success test) to each Phase 19 test so the existing coverage stays green.
- **Files modified:** apps/reviews/tests/test_reply_generation_service.py
- **Commit:** 3d968bb

**3. [Rule 3 — Blocking] Worktree base lacked Phase 17 / 19 / 20-Wave-1+2 commits**
- **Found during:** Setup
- **Issue:** The orchestrator spawned this worktree from a base that predates the feature/categories merges, so `apps/integrations/openai/guardrails.py`, `apps/integrations/openai/models.py::Status.MODERATED`, `apps/reviews/services/reply_generation.py`, migrations 0008-0010 and 0003 etc. were absent — `import` would fail.
- **Fix:** `git checkout feature/categories -- <files>` for the prerequisite files (guardrails, exceptions, models, client, prompts, parser, reply_generation, migrations, models, settings). Committed as a single setup commit (`f184133`).
- **Note:** The orchestrator's downstream 3-way merge will deduplicate these against the canonical feature/categories versions (identical content → no conflict).

### Plan-Level Decision Changes

**1. Cost calculation moved BEFORE `moderate_output`**
- The plan's task ordering placed cost calc inside the SUCCESS branch (Phase 19 layout). Per D-29, the MODERATED row written by `moderate_output` must carry real `estimated_cost_usd`. `guardrails.moderate_output` reads `usage_data["estimated_cost_usd"]`; if missing, it defaults to `Decimal("0")`. So cost is now computed BEFORE `moderate_output` and injected into `usage_data`. This is a strict refinement of D-29 — not a contradiction. Recorded in the decisions frontmatter.

## Known Stubs

None.

## Threat Flags

None. Mitigations T-20-01, T-20-03, T-20-CO, T-20-05 from the plan's threat model are all enforced by the wiring + the regression tests in this plan. No new untracked attack surface introduced.

## TDD Gate Compliance

This plan was executed task-by-task with TDD intent, but the gate commits do not appear in clean RED/GREEN ordering for Task 2 due to a tool/pre-commit interaction that required a re-do. Net audit trail:

- `3e443a9` test(20-06): add TestGenerateReplyDraftModeration failing tests — **early RED commit; superseded** (the test class body was lost during a pre-commit stash/restore cycle; recreated in commit `3d968bb`).
- `3b4d69a` feat(20-06): wire moderate_input + moderate_output + truncation — Task 1 implementation (GREEN target).
- `3d968bb` test(20-06): add TestGenerateReplyDraftModeration + fix stale tags factory — Task 2 (the final tests + Rule 3 fixes; passes against `3b4d69a`).

The final state has 12/12 tests passing. The intermediate RED commit `3e443a9` is left in history (and would be removed by a rebase if the team prefers a cleaner history before merge).

## Self-Check

Verifications:

- Implementation file present: `apps/reviews/services/reply_generation.py` ✓ (5 references to `moderate_input`/`moderate_output`)
- Test class present: `TestGenerateReplyDraftModeration` ✓ (7 tests)
- All commits present in branch: `f184133`, `3e443a9`, `3b4d69a`, `3d968bb` ✓
- Pytest: `12 passed in 1.08s` ✓
- Ruff/mypy/bandit pre-commit hooks: all PASSED on both commits ✓

## Self-Check: PASSED
