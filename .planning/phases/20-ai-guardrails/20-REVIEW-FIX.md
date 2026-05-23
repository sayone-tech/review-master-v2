---
phase: 20-ai-guardrails
fixed_at: 2026-05-23T00:00:00Z
review_path: .planning/phases/20-ai-guardrails/20-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 20: Code Review Fix Report

**Fixed at:** 2026-05-23
**Source review:** `.planning/phases/20-ai-guardrails/20-REVIEW.md`
**Iteration:** 1
**Scope:** Warnings only (`WR-01`, `WR-02`, `WR-03`). Info-tier findings
(`IN-01`..`IN-04`) were explicitly out of scope for this run.

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `_moderate_with_retry` failed CLOSED on unexpected exceptions

**Files modified:** `apps/integrations/openai/guardrails.py`
**Commit:** `1006f7a`
**Applied fix:** The retry loop in `_moderate_with_retry` previously caught
only the narrow `_MODERATION_TRANSIENT_EXCEPTIONS` tuple
(`RateLimitError`, `APIStatusError`, `APIConnectionError`). Broadened the
except clause to bare `Exception` so any non-transient raise (httpx
errors, generic `OpenAIError` subclasses, `AttributeError` from a future
SDK shape change) now follows D-24's fail-open contract verbatim instead
of crashing the enrichment task / returning HTTP 502 from the reply view.

The one-retry-with-1s-sleep loop is unchanged (D-24 still mandates exactly
one retry). The narrow tuple is retained as documentation with a comment
explaining why the actual catch is broader. Per CLAUDE.md §21, the
fail-open ERROR log records only the error class name + sanitized message
— never the moderation input text. A docstring paragraph documents the
intentional broadness.

### WR-02: Enrichment mutated `review.comment` in memory

**Files modified:**
- `apps/integrations/openai/guardrails.py` (hoisted proxy class)
- `apps/reviews/services/enrichment.py` (uses proxy)
- `apps/reviews/services/reply_generation.py` (uses shared proxy, drops local copy)

**Commit:** `10f2bb1`
**Applied fix:** `_ReviewWithModeratedComment` was hoisted out of
`reply_generation.py` into `apps.integrations.openai.guardrails` as the
public `ReviewWithModeratedComment` class. `enrich_review` now constructs
a `ReviewWithModeratedComment(review, truncated_text)` proxy and passes
it to `call_openai_enrichment` instead of mutating `review.comment` in
place. A future refactor that switches `Review.objects.filter(pk=...).update(...)`
to `review.save()` can no longer silently persist the `…[truncated]`
suffix into the database. The reply-generation service was updated to
import the shared class and drop its private definition, eliminating
duplication.

### WR-03: Test gap — no coverage for non-transient fail-open path

**Files modified:** `apps/integrations/openai/tests/test_guardrails.py`
**Commit:** `1ae2df1`
**Applied fix:** Added
`TestFailOpenRetry.test_fail_open_non_transient_exception_still_fails_open`
that patches `_call_moderation_api` with `RuntimeError("unexpected boom")`,
asserts `moderate_input` returns the input unchanged, asserts the 1s
retry sleep was invoked exactly once, and asserts the
`ai.moderation.errored` ERROR log was emitted. This pins WR-01's broader
`Exception` catch — re-narrowing the except clause will now break this
test. Full suite (21 tests) passes.

## Skipped Issues

None — all in-scope warnings were fixed.

### Out-of-scope (Info tier, not attempted)

The following Info-tier findings are noted in the source REVIEW.md and
were intentionally **not** addressed in this run per `fix_scope`:

- **IN-01** — `_persist_moderated_log` does not forward `latency_ms` /
  `langsmith_trace_id` for output-moderated rows.
- **IN-02** — `_persist_moderated` in enrichment does not bump
  `enrichment_version`.
- **IN-03** — Re-running `enrich_review` on a FAILED-moderated review
  re-bills moderation + writes duplicate audit row.
- **IN-04** — `truncate_reply_at_sentence` fallback ends mid-thought
  without a sentence delimiter before the canonical suffix.

If desired, schedule a follow-up `/gsd:code-review --fix --all` pass to
address these.

## Verification

- `pytest apps/integrations/openai/tests/test_guardrails.py` → 21 passed
- `pytest apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_reply_generation_service.py` → all passed (run together with guardrails: 64 passed)
- D-24 fail-open contract honoured (one retry, 1s sleep, broad catch).
- D-30 underscore-form `BLOCKING_MODERATION_CATEGORIES` untouched.
- D-33 `_persist_moderated_log` still outside `transaction.atomic()`.
- Pitfall 1–4 from RESEARCH.md unaffected (regression tests still green).

---

_Fixed: 2026-05-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
