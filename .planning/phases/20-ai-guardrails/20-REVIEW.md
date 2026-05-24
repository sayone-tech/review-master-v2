---
phase: 20-ai-guardrails
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/integrations/openai/guardrails.py
  - apps/integrations/openai/exceptions.py
  - apps/integrations/openai/models.py
  - apps/integrations/openai/migrations/0003_add_moderated_status_choice.py
  - apps/integrations/openai/tests/test_guardrails.py
  - apps/reviews/services/enrichment.py
  - apps/reviews/services/reply_generation.py
  - apps/reviews/views.py
  - apps/reviews/tasks.py
  - apps/reviews/models.py
  - apps/reviews/migrations/0010_add_enrichment_error_code.py
  - apps/reviews/tests/test_enrichment_service.py
  - apps/reviews/tests/test_reply_generation_service.py
  - apps/reviews/tests/test_views.py
  - apps/reviews/tests/test_tasks.py
  - config/settings/base.py
  - .env.example
  - .planning/phases/20-ai-guardrails/20-CONTEXT.md
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-05-23
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 20 wires OpenAI Moderation guardrails around enrichment and reply generation.
All four explicit RESEARCH.md pitfalls were verified as correctly handled:

- **Pitfall 1** (slash vs underscore): `BLOCKING_MODERATION_CATEGORIES` uses underscore form
  consistent with default `Categories.model_dump()`. Locked by a dedicated regression test.
- **Pitfall 2** (status casing): `AiUsageLog.Status.MODERATED = "MODERATED"` and the
  persisted row carries the uppercase literal — verified by test.
- **Pitfall 3** (atomic discipline): both `moderate_input` and `moderate_output` are
  called OUTSIDE any `transaction.atomic()` block. Runtime savepoint-depth and
  `in_atomic_block` regression tests pin the contract.
- **Pitfall 4** (retry task): `retry_failed_enrichments_task` correctly chains
  `.exclude(enrichment_error_code="content_moderated")` and both positive and
  negative regressions cover it.

HTTP 422 mapping order is correct (`ContentModeratedException` caught BEFORE
`OpenAITransient/Permanent`). Output-moderation accounting writes REAL tokens
and cost. SUCCESS short-circuit in `enrich_review` correctly precedes the
`moderate_input` call, preventing re-billing on already-enriched reviews.
Migrations have correct dependencies and are non-locking on Postgres.

The findings below are quality/robustness concerns — none are correctness
defects in the locked decisions. The most important is **WR-01**: the
fail-open retry path catches only three SDK exception types and will
hard-fail (not fail-open) on any other exception from the Moderation API.

## Warnings

### WR-01: `_moderate_with_retry` fails CLOSED on unexpected exceptions instead of fail-open

**File:** `apps/integrations/openai/guardrails.py:81-175`
**Issue:** `_MODERATION_TRANSIENT_EXCEPTIONS` is the narrow tuple
`(openai.RateLimitError, openai.APIStatusError, openai.APIConnectionError)`.
The `try/except` in `_moderate_with_retry` only suppresses these three.
D-24 specifies a fail-open contract: "if the `client.moderations.create(...)`
call raises (network, 5xx, rate limit), retry once... If the retry also fails,
proceed with the OpenAI call". The phrasing is broad — "if the call raises".

Today, any other exception raised from `_call_moderation_api` (for example a
generic `Exception`, a `httpx.RequestError`, a Python `AttributeError` from a
shape change in the SDK response, or `openai.OpenAIError` subclasses that don't
inherit from those three — e.g. `openai.APIError` is the root and has subclasses
outside this tuple) will propagate uncaught. It will surface as a hard failure
in `moderate_input` / `moderate_output`. For enrichment that means the task
crashes (autoretry_for=(Exception,)) → unnecessary retries on a moderation
outage. For reply generation it means HTTP 502 instead of the documented
fail-open behaviour.

**Fix:**
```python
# Broaden the catch to satisfy the D-24 contract verbatim.
_MODERATION_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    openai.OpenAIError,  # parent of RateLimitError / APIStatusError / APIConnectionError
    Exception,           # belt-and-braces: any unexpected raise should still fail open
)
```
Or restructure with a bare `except Exception as exc:` around the call, with the
sleep/continue/break logic unchanged. Add a test that patches
`_call_moderation_api` with `side_effect=RuntimeError("boom")` (or
`ValueError`) and asserts `moderate_input("...")` returns the truncated text
and emits `ai.moderation.errored`.

---

### WR-02: Enrichment mutates `review.comment` in memory — asymmetric with the safer pattern used in reply generation

**File:** `apps/reviews/services/enrichment.py:483-485`
**Issue:** After successful moderation, `enrich_review` does:
```python
review.comment = truncated_text
```
This relies on the convention "Not saved — purely a prompt-assembly hand-off."
A future contributor who adds `review.save()` anywhere downstream — or, more
plausibly, switches from `Review.objects.filter(pk=...).update(...)` to
`review.save()` (a single-line, plausible refactor) — would silently persist
the `…[truncated]` suffix into the database. The reviewer's actual review text
would be corrupted.

The reply-generation service avoids this exact risk with the
`_ReviewWithModeratedComment` wrapper proxy
(`apps/reviews/services/reply_generation.py:51-69`). The same pattern should
apply here.

**Fix:** Replace the in-place mutation with the proxy pattern:
```python
class _ReviewWithModeratedComment:
    """Reuse from reply_generation or hoist to a shared module."""
    __slots__ = ("_review", "comment")
    def __init__(self, review, comment):
        object.__setattr__(self, "_review", review)
        object.__setattr__(self, "comment", comment)
    def __getattr__(self, name):
        return getattr(self._review, name)

# ...
review_for_prompt = _ReviewWithModeratedComment(review, truncated_text)
result, usage_data = call_openai_enrichment(review=review_for_prompt)
```
The two `_ReviewWithModeratedComment` definitions are otherwise identical —
extract once into `apps/integrations/openai/guardrails.py` or a small shared
helper module.

---

### WR-03: Test gap — no coverage for the WR-01 failure mode (non-transient exception in moderation)

**File:** `apps/integrations/openai/tests/test_guardrails.py:269-309`
**Issue:** `TestFailOpenRetry` exercises only `RateLimitError` /
`APIConnectionError`. No test patches `_call_moderation_api` with a generic
`Exception` (or `RuntimeError`, `ValueError`). The current pass-state of these
tests therefore masks WR-01: a regression that introduces a non-transient
exception path would not break this suite.

**Fix:** Add a regression test that pins the D-24 contract:
```python
def test_fail_open_non_transient_exception_still_fails_open(self, caplog) -> None:
    with (
        patch(_PATCH_TARGET, side_effect=RuntimeError("unexpected")),
        patch(_SLEEP_TARGET),
        caplog.at_level("ERROR", logger="apps.integrations.openai.guardrails"),
    ):
        result = moderate_input("clean review")
    assert result == "clean review"
    assert any("ai.moderation.errored" in rec.message for rec in caplog.records)
```
After WR-01 is fixed this test will pass; before WR-01 is fixed it will fail
with `RuntimeError` — exactly the regression coverage needed.

## Info

### IN-01: `_persist_moderated_log` does not record `latency_ms` for output-moderated rows

**File:** `apps/integrations/openai/guardrails.py:178-211`, `apps/reviews/services/reply_generation.py:167-172`
**Issue:** Output-moderation passes `usage_data` to `_persist_moderated_log`,
which forwards `prompt_tokens`, `completion_tokens`, `cached_tokens`,
`total_tokens`, and `estimated_cost_usd` — but not `latency_ms` or
`langsmith_trace_id`. CLAUDE.md §14.3 lists both as part of the canonical
`AiUsageLog` row, and the OpenAI call did consume that latency before
moderation fired. Cost dashboards that join on these fields will see NULL
where data was available.

**Fix:** Extend `_persist_moderated_log`'s signature with
`latency_ms: int | None = None` and `langsmith_trace_id: str = ""`, forward
them from `usage_data` in `moderate_output`, and pass through to
`AiUsageLog.objects.create(...)`.

---

### IN-02: `_persist_moderated` in enrichment does not bump `enrichment_version`

**File:** `apps/reviews/services/enrichment.py:234-251`
**Issue:** `_persist_failure` increments `enrichment_version` (line 266) so
`retry_failed_enrichments_task`'s `enrichment_version__lt=3` cap works.
`_persist_moderated` does not. Today this is safe because the same task
also `.exclude(enrichment_error_code="content_moderated")`, so moderated
rows are skipped regardless. But the asymmetry is a footgun: if the
exclusion is ever loosened (e.g., to also retry moderated rows after an
admin-driven recategorisation flow), the `version=0` rows would loop
forever inside the cap. The two persistence helpers should keep parity.

**Fix:** Wrap `_persist_moderated` in `transaction.atomic()` (single-row
save is already atomic at SQL level, but the wrapper documents intent) and
use the same `Review.objects.filter(pk=...).update(enrichment_version=F('enrichment_version')+1, ...)`
shape as `_persist_failure` so the version bump happens.

---

### IN-03: Re-running `enrich_review` on a FAILED-moderated review re-bills moderation and writes a duplicate audit row

**File:** `apps/reviews/services/enrichment.py:432-498`
**Issue:** The Layer-3 short-circuit only checks `SUCCESS` and `IN_PROGRESS`.
A review in `FAILED + enrichment_error_code=content_moderated` will fall
through to `moderate_input` again on every direct `enrich_review_task.delay(pk)`
invocation (the Beat retry task correctly skips it via the `.exclude(...)`,
but the protection is on the task — not the service). Each invocation
hits the Moderation API and writes a fresh MODERATED `AiUsageLog` row.

Moderation API is free (D-01), so the cost surface is zero — but duplicate
audit rows muddy the safety-event ledger and reflect a leak in the
idempotency story.

**Fix:** Extend the Layer-3 guard to also short-circuit when the row is
already `FAILED + enrichment_error_code=content_moderated`:
```python
if (
    review.enrichment_status == Review.EnrichmentStatus.FAILED
    and review.enrichment_error_code == "content_moderated"
):
    logger.info("enrich_review_already_moderated review_id=%s", review_id)
    return
```
Add a test that calls `enrich_review` twice on a moderated review and
asserts `AiUsageLog.objects.filter(review=review, status=MODERATED).count() == 1`.

---

### IN-04: `truncate_reply_at_sentence` fallback returns the cap suffix without a sentence delimiter

**File:** `apps/integrations/openai/guardrails.py:102-129`
**Issue:** When the first sentence already exceeds 300 words (rare but
possible — e.g. a draft with no punctuation), the fallback hard-cuts at the
word boundary and appends `" (Please review and complete before sending.)"`.
The resulting text ends like `... word300 (Please review ...)` — there is
no period before the parenthetical suffix, so the output ends mid-thought
without sentence punctuation. CONTEXT D-08 doesn't mandate a period, but the
user-visible UX is awkward.

**Fix:** Append `"..."` (or a period) before the suffix on the fallback
branch:
```python
return " ".join(words[:_REPLY_WORD_CAP]) + "..." + _REPLY_SUFFIX
```
Optional. Low priority unless reviewed UX is poor.

---

_Reviewed: 2026-05-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
