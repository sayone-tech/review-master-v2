---
phase: 19-ai-reply-generation
fixed_at: 2026-05-22T00:00:00Z
review_path: .planning/phases/19-ai-reply-generation/19-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 10
skipped: 1
status: partial
---

# Phase 19: Code Review Fix Report

**Fixed at:** 2026-05-22T00:00:00Z
**Source review:** `.planning/phases/19-ai-reply-generation/19-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (0 critical, 6 warnings, 5 info)
- Fixed: 10
- Skipped: 1

## Fixed Issues

### WR-01: View `except` clause silently swallows DRF flow-control exceptions

**Files modified:** `apps/reviews/views.py`
**Commit:** 6583b7e
**Applied fix:** Split the single `except (OpenAITransientError, OpenAIPermanentError, Exception)` clause into three: (a) OpenAITransientError/OpenAIPermanentError → 502 with `logger.warning`, (b) `APIException` → re-raise so DRF maps `Throttled`/`ValidationError`/`NotAuthenticated` to their natural status codes, (c) generic `Exception` → 502 with `logger.exception` so Sentry captures the traceback at ERROR level. Imported `APIException` from `rest_framework.exceptions`.

### WR-02: `throttle_scope` assigned in action body — generate_reply was throttled at the wrong rate

**Files modified:** `apps/reviews/views.py`, `frontend/src/widgets/review-management/api.ts`, `frontend/src/widgets/review-management/ReplyComposer.tsx`
**Commit:** 030112b
**Applied fix:** Moved per-action throttle_scope assignment into a `get_throttles()` override on `ReviewViewSet`, so DRF picks up `"generate_reply"` (10/min) for `generate_reply` and `"review_reply"` (30/min) for `reply` BEFORE the throttle is evaluated. Removed the stale `self.throttle_scope = "generate_reply"` line from the action body. Frontend now parses `Retry-After` header (and falls back to parsing "Expected available in N seconds." from DRF's `detail`) and surfaces the seconds in the user-facing error message.

### WR-03: Duplicate tone allowlist drifts between serializer, service, and prompts

**Files modified:** `apps/integrations/openai/prompts.py`, `apps/reviews/serializers.py`, `apps/reviews/services/reply_generation.py`
**Commit:** 7146ca3
**Applied fix:** Defined `ALLOWED_REPLY_TONES: tuple[str, ...] = ("professional", "friendly")` in `prompts.py` as the single source of truth. Updated `GenerateReplySerializer.TONE_CHOICES` and `_ALLOWED_TONES` in the service to derive from it. Added an import-time `RuntimeError` guard (replaces the `assert` to satisfy Bandit B101) that fails fast if `_REPLY_PROMPTS_BY_TONE` keys ever drift from `ALLOWED_REPLY_TONES`.

### WR-04: Hardcoded 500-char truncation of `error_message`

**Files modified:** `apps/reviews/services/reply_generation.py`
**Commit:** 8a72c76
**Applied fix:** Verified `AiUsageLog.error_message` is `models.TextField(blank=True)` (no max_length) in `apps/integrations/openai/models.py:87`. Removed the `[:500]` slice — the full exception string is now stored. Added a comment documenting the rationale.

### WR-05: `AiUsageLog` row not written if `calculate_cost` raises

**Files modified:** `apps/reviews/services/reply_generation.py`
**Commit:** 8a72c76 (same commit as WR-04)
**Applied fix:** Wrapped `calculate_cost(...)` in try/except. On failure (e.g., missing `AiPricing` row), the function logs `ai_pricing_lookup_failed` via `logger.exception`, sets `cost = Decimal("0")`, and stamps `error_code="ai_pricing_lookup_failed"` + `error_message=str(exc)` on the SUCCESS-status row. The OpenAI call is no longer billed without an audit row.
**Requires human verification** — the change preserves the original `estimated_cost_usd=Decimal("0")` shape (model field is non-nullable with default 0) but adds error metadata for cost-audit visibility. Confirm this matches the desired data semantics for billing reporting.

### WR-06: LangSmith metadata-attach except masked bugs

**Files modified:** `apps/integrations/openai/client.py`
**Commit:** 8b73193
**Applied fix:** Changed the bare `except Exception: trace_id = None` inside `_call_openai_reply_with_tracing` to also call `logger.exception("langsmith_metadata_attach_failed_reply")` so SDK-shape regressions (analogous to the resolved langsmith-cost-not-shown.md bug) surface in Sentry instead of silently dropping metadata.

### IN-01: Test class uses `db` positional arg instead of module-level `pytestmark`

**Files modified:** `apps/reviews/tests/test_views.py`
**Commit:** 265caec
**Applied fix:** Removed the redundant `, db` parameter from all 9 methods on `TestGenerateReplyEndpoint` (the module already has `pytestmark = pytest.mark.django_db` on line 25, which applies to the class).

### IN-03: Lazy in-function imports in test files

**Files modified:** `apps/integrations/openai/tests/test_prompts.py`, `apps/integrations/openai/tests/test_client.py`
**Commit:** 265caec (same commit as IN-01)
**Applied fix:** Hoisted `from apps.integrations.openai.prompts import REPLY_GENERATION_PROMPT_VERSION, build_reply_generation_messages` to module level in `test_prompts.py`. Hoisted `call_openai_reply_generation` import to module level in `test_client.py` (combined with the existing `call_openai_enrichment` import).

### IN-04: Frontend `generateReply` lacks AbortSignal

**Files modified:** `frontend/src/widgets/review-management/api.ts`, `frontend/src/widgets/review-management/ReplyComposer.tsx`
**Commit:** fbec4e3
**Applied fix:** Added optional `signal?: AbortSignal` parameter to `generateReply`. `ReplyComposer` now tracks the active `AbortController` in `generateAbortRef`, aborts any in-flight request when the user re-clicks a different tone, and aborts on unmount via a cleanup `useEffect`. The success/error handlers short-circuit if `controller.signal.aborted` (and ignore `AbortError`) so a late response never overwrites freshly-edited state.

### IN-05: `template.format(brand_name=...)` raises KeyError on brand names with literal braces

**Files modified:** `apps/integrations/openai/prompts.py`, `apps/integrations/openai/tests/test_prompts.py`
**Commit:** 463ccf7
**Applied fix:** Replaced `template.format(brand_name=brand_name)` with `template.replace("{brand_name}", brand_name)` in `build_reply_generation_messages`. Added regression test `test_brand_name_with_braces_does_not_raise` asserting that a brand name like `"Acme {Coffee}"` round-trips into the system prompt.

## Skipped Issues

### IN-02: Add view-layer test that distinguishes typed exception path from generic-exception path

**File:** `apps/reviews/tests/test_views.py:438`
**Reason:** Test-suite expansion request. WR-01's commit (6583b7e) addresses the underlying behavior by re-raising `APIException` subclasses so DRF maps them naturally — meaning a hypothetical `Throttled` from the service would now produce 429 instead of 502. Constructing a deterministic test that raises `rest_framework.exceptions.Throttled` from inside `generate_reply_draft` would require mocking the service to raise a DRF-internal exception, which is contrived (the service should never raise DRF exceptions). The existing `test_transient_error_returns_502`, `test_permanent_error_returns_502`, and `test_generic_exception_returns_502` cover the three real branches. Deferred to the verifier phase, which can add the additional regression test if the test plan calls for it.
**Original issue:** "There is no test that distinguishes the OpenAI-typed-exception path from the generic-Exception path at the view layer."

---

_Fixed: 2026-05-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
