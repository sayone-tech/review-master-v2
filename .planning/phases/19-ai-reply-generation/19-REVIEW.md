---
phase: 19-ai-reply-generation
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - apps/integrations/openai/client.py
  - apps/integrations/openai/prompts.py
  - apps/integrations/openai/tests/test_client.py
  - apps/integrations/openai/tests/test_prompts.py
  - apps/reviews/serializers.py
  - apps/reviews/services/reply_generation.py
  - apps/reviews/tests/test_reply_generation_service.py
  - apps/reviews/tests/test_views.py
  - apps/reviews/views.py
  - config/settings/base.py
  - frontend/src/widgets/review-management/api.ts
  - frontend/src/widgets/review-management/ReplyComposer.tsx
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 19 wires an AI reply-generation endpoint (`POST /api/v1/reviews/{id}/generate-reply/`)
on top of a new OpenAI Chat Completions code path and a service that writes one
`AiUsageLog` row per call. Architecture follows CLAUDE.md §5 (thin view → service →
client) and §14 (AiUsageLog + LangSmith tracing), test coverage is good, and the
React UI handles loading/error states. No CRITICAL defects were found.

Several WARNINGs surface around the view-layer exception handler (it overcatches
DRF control-flow exceptions and produces a misleading 502 for unrelated errors),
duplicate tone validation that drifts from a single source of truth, and a
contract gap on the frontend (429 quota error is not surfaced from the backend —
the backend currently maps 429 to a different shape than the UI assumes). Several
INFO items target code smells and minor test coverage gaps.

---

## Narrative Findings (AI reviewer)

## Critical Issues

None.

## Warnings

### WR-01: View `except` clause silently swallows DRF flow-control exceptions and PII-leaking errors as 502

**File:** `apps/reviews/views.py:258-277`

**Issue:** The exception handler on the `generate_reply` action is:

```python
except (OpenAITransientError, OpenAIPermanentError, Exception) as exc:
    ...
    return Response({"code": "ai_unavailable", "detail": "AI generation failed..."},
                    status=status.HTTP_502_BAD_GATEWAY)
```

Listing `Exception` makes the first two classes redundant and, more importantly,
swallows **every** exception raised inside `generate_reply_draft` — including
classes that should bubble up to DRF's exception handler with a different status
code. Concrete leaks:

1. If `generate_reply_draft` ever raises `rest_framework.exceptions.Throttled`,
   `PermissionDenied`, `NotAuthenticated`, `ValidationError`, or `Http404` (today
   it doesn't, but `call_openai_reply_generation` accesses
   `review.shop.organisation.name` — any unexpected lazy-load failure or
   misconfigured FK becomes a 502 instead of a 500 with a Sentry trace).
2. Any future caller-side bug (e.g., `AttributeError`, `KeyError` in the service)
   is masked as "AI unavailable" and the user is told to retry — but no retry
   will fix a code bug. Sentry still captures the exception (via the `logger.warning`
   path it does NOT — `.warning` is below Sentry's default capture level of ERROR),
   so the bug becomes invisible.
3. `BaseException` subclasses other than `Exception` (KeyboardInterrupt,
   SystemExit) are not caught — that's fine; but the test
   `test_generic_exception_returns_502` proves the broad catch is intentional,
   which conflates "OpenAI failure" with "programmer error."

**Fix:**

```python
from rest_framework.exceptions import APIException

try:
    draft = generate_reply_draft(review=review, tone=tone)
except (OpenAITransientError, OpenAIPermanentError) as exc:
    logger.warning(
        "generate_reply_openai_failed review_id=%s tone=%s exc_type=%s exc=%s",
        review.pk, tone, type(exc).__name__, exc,
    )
    return Response(
        {"code": "ai_unavailable",
         "detail": "AI generation failed. Please try again or write your reply manually."},
        status=status.HTTP_502_BAD_GATEWAY,
    )
except APIException:
    raise  # let DRF handle Throttled, ValidationError, etc.
except Exception:
    logger.exception(  # ERROR-level + traceback => Sentry captures it
        "generate_reply_unexpected review_id=%s tone=%s", review.pk, tone,
    )
    return Response(
        {"code": "ai_unavailable",
         "detail": "AI generation failed. Please try again or write your reply manually."},
        status=status.HTTP_502_BAD_GATEWAY,
    )
```

Bonus: use `logger.exception` (not `.warning`) in the unexpected-error branch so
Sentry captures the traceback. The current `.warning` call passes `%s` formatting
of `exc` only — no traceback and below capture level.

---

### WR-02: Frontend assumes backend returns `{ code: "ai_unavailable" }` on 502 but the same handler is used for 429 — quota UX is wrong

**File:** `frontend/src/widgets/review-management/ReplyComposer.tsx:77-86`

**Issue:** The composer handles a 429 in `handleGenerate`:

```js
if (e instanceof ApiError && e.status === 429) {
  message = "You've reached the AI generation limit. Please wait a moment.";
}
```

But DRF's `ScopedRateThrottle` returns `{"detail": "Request was throttled. Expected
available in N seconds."}` — there is **no `code` field**, and the throttle scope
on the view is set via `self.throttle_scope = "generate_reply"`. The frontend
detection by `e.status === 429` does work, but the user is given a vague "wait a
moment" message even though DRF returns the exact `Retry-After` seconds in the
body. Surface the `Retry-After` header or parse the seconds out of `detail` so
the UI can say "try again in X seconds."

Secondary issue: `throttle_scope` is assigned to `self` inside the action handler
(`self.throttle_scope = "generate_reply"` at views.py:251). This pattern only
works because DRF calls `get_throttles()` before the action method only if
`initial()` reads `throttle_scope`. The default flow reads `view.throttle_scope`
during `initial()` (which runs **before** the action body), so by the time
`self.throttle_scope = "generate_reply"` executes, the throttle has already been
evaluated against the **class-level** value (`"review_reply"`, line 64). Result:
the `generate_reply` action is throttled at 30/minute (the reply rate) instead
of the intended 10/minute (D-12).

**Fix:** Move the scope assignment out of the action body. Either define a
custom `ScopedRateThrottle` subclass per action or override `get_throttles`:

```python
def get_throttles(self):
    if self.action == "generate_reply":
        self.throttle_scope = "generate_reply"
    elif self.action == "reply":
        self.throttle_scope = "review_reply"
    return super().get_throttles()
```

Add a regression test that posts 11 generate-reply calls in a minute and asserts
the 11th returns 429.

---

### WR-03: Duplicate tone allowlist drifts between serializer, service, and prompts module

**File:** `apps/reviews/serializers.py:99-100`, `apps/reviews/services/reply_generation.py:35`, `apps/integrations/openai/prompts.py:88-91`

**Issue:** The set of valid tones is hard-coded in three places:
1. `GenerateReplySerializer.TONE_CHOICES = ["professional", "friendly"]`
2. `_ALLOWED_TONES = frozenset({"professional", "friendly"})` in the service
3. `_REPLY_PROMPTS_BY_TONE` keys in prompts.py

Adding a new tone (e.g., "apologetic") in one place silently allows invalid
inputs to traverse to the next layer where they hit a `ValueError`. CLAUDE.md
§5 ("services and selectors") makes the service the source of truth for business
logic; both serializer and prompts module should import from one place.

**Fix:** Define once in `apps/integrations/openai/prompts.py`:

```python
ALLOWED_REPLY_TONES: tuple[str, ...] = ("professional", "friendly")
```

Then:
- `serializers.py`: `tone = serializers.ChoiceField(choices=ALLOWED_REPLY_TONES)`
- `services/reply_generation.py`: `if tone not in ALLOWED_REPLY_TONES: ...`
- `prompts.py`: `_REPLY_PROMPTS_BY_TONE` keys derived from the same constant.

---

### WR-04: `_write_failure_log` truncates error message at 500 chars but the model field width is unspecified — silent data loss risk

**File:** `apps/reviews/services/reply_generation.py:55`

**Issue:** `error_message=str(exc)[:500]` hardcodes a 500-char truncation. If the
`AiUsageLog.error_message` column is a `TextField` (typical), truncation is
unnecessary and discards diagnostic context. If it's `CharField(max_length=N)`
where N < 500, the truncation could still overflow.

I cannot verify the column type without reading `apps/integrations/openai/models.py`,
which is out of scope here — but the symmetric truncation in
`apps/integrations/openai/services/enrichment.py` (if any) should match.

**Fix:** Either (a) reference a module-level constant from `AiUsageLog` (e.g.,
`AiUsageLog.MAX_ERROR_MESSAGE_LEN`) or (b) confirm the column is `TextField` and
drop the slice. Add a unit test that an error_message > 500 chars round-trips
without DB error.

---

### WR-05: Service writes the AiUsageLog row OUTSIDE a transaction; partial failure leaves dangling state

**File:** `apps/reviews/services/reply_generation.py:73-105`

**Issue:** The success path:
1. Calls `call_openai_reply_generation` → OpenAI charge incurred.
2. Calls `calculate_cost` → may raise if `AiPricing.objects.get_active(model=...)`
   misses (no active pricing row for the model).
3. Writes `AiUsageLog` row.

If step 2 raises (`AiPricing.DoesNotExist` — possible if pricing seed migration
hasn't run, or a model ID is changed at runtime), **no AiUsageLog row is
written**, but the user paid for the OpenAI call. Cost is invisible until
someone notices `AiUsageLog` undercounts.

The matching pattern is also fragile: `calculate_cost` raises (any exception)
→ bubbles out of `generate_reply_draft` → view catches it → returns 502 to the
user. But the OpenAI call already succeeded and the draft was discarded.

**Fix:** Either (a) wrap step 2+3 in `transaction.atomic()` and a try/except so
a missing pricing row still logs the call with `estimated_cost_usd=None` and
status=SUCCESS, OR (b) call `calculate_cost` defensively:

```python
try:
    cost = calculate_cost(model=..., ...)
except Exception:  # pragma: no cover — defensive: missing AiPricing row
    logger.exception("ai_pricing_lookup_failed model=%s", settings.OPENAI_MODEL)
    cost = None  # or Decimal("0")
```

Also: the SUCCESS branch never re-uses `settings.OPENAI_MODEL` (good), but the
FAILED branch in `_write_failure_log` reads `settings.OPENAI_MODEL` again
(reply_generation.py:45). If the user passed `model=` to override, the FAILED
log records the wrong model. The current `generate_reply_draft` doesn't accept
a `model` override — so currently fine — but the indirection between
`call_openai_reply_generation(model=settings.OPENAI_MODEL)` (line 77) and
`_write_failure_log` reading the same setting is fragile if a future refactor
allows overriding.

---

### WR-06: `_call_openai_reply_with_tracing` falls into `except Exception: trace_id = None` which masks bugs in metadata extraction

**File:** `apps/integrations/openai/client.py:349-350`

**Issue:** The traced path swallows every exception from the LangSmith metadata
attach block, including `AttributeError` on `response.choices[0]` if the SDK
shape ever changes. Result: a malformed Chat Completions response would be
returned as `(response, None)` and the downstream code on line 394
(`choices = getattr(response, "choices", None) or []`) would correctly raise
`OpenAIPermanentError`, but **only after silently logging no diagnostic info**.

Combined with the test gap (no test asserts `_call_openai_reply_with_tracing`
metadata block populates `usage_metadata` for the chat-completions path the
same way the enrichment path does), the LangSmith cost-rendering regression
documented in `.planning/debug/resolved/langsmith-cost-not-shown.md` could
silently recur for `request_type="reply_generation"` and no one would notice
until the LangSmith dashboard shows $0.00.

**Fix:** Narrow the catch and log:

```python
except Exception:
    logger.exception("langsmith_metadata_attach_failed_reply")
    trace_id = None
```

Add a test mirroring `test_trace_id_captured_from_run_tree` for the reply path
that patches `get_current_run_tree` and asserts the trace_id is surfaced AND
that `usage_metadata` is populated on the run_tree's metadata dict.

---

## Info

### IN-01: Test class missing `pytestmark = pytest.mark.django_db` — relies on per-test `db` fixture inconsistently

**File:** `apps/reviews/tests/test_views.py:392-543`

**Issue:** `TestGenerateReplyEndpoint` methods take `db` as a positional arg
(line 399, 416, 427, etc.) rather than using `@pytest.mark.django_db` like the
rest of the file's module-level `pytestmark`. This works but is inconsistent
with neighbouring tests in the same module and obscures DB usage at the class
level.

**Fix:** Replace `db` fixture usage with class-level `@pytest.mark.django_db`
or drop the `db` arg since the module already has `pytestmark = pytest.mark.django_db`
on line 25.

---

### IN-02: Unused exception class import path differs between mock paths and real

**File:** `apps/reviews/tests/test_views.py:438`

**Issue:** `mock_generate.side_effect = OpenAITransientError("boom")` works but
the service catches generic `Exception` too. There is no test that distinguishes
the OpenAI-typed-exception path from the generic-Exception path *at the view
layer* — `test_generic_exception_returns_502` uses `ValueError`. Add a test
that simulates an HTTP-layer issue (e.g., the rare case where DRF Throttled is
raised by the service) to lock in the WR-01 fix.

**Fix:** Add a test once WR-01 is fixed asserting `Throttled` and `Http404`
propagate to their natural status codes.

---

### IN-03: `_REPLY_PROMPTS_BY_TONE` is module-private but the test imports `build_reply_generation_messages` lazily inside test bodies — minor smell

**File:** `apps/integrations/openai/tests/test_prompts.py`

**Issue:** Every test does `from apps.integrations.openai.prompts import
build_reply_generation_messages` inside the function. Top-of-file imports are
preferred (CLAUDE.md and PEP 8). The other test file (`test_client.py`) has
the same pattern. Likely a copy-paste hangover.

**Fix:** Hoist the imports to module level.

---

### IN-04: Frontend `generateReply` lacks abort signal — clicking a different tone or closing the composer mid-request still applies the late response

**File:** `frontend/src/widgets/review-management/ReplyComposer.tsx:68-87`

**Issue:** `handleGenerate` doesn't pass an `AbortSignal` to `generateReply`,
so if the user clicks "Professional," then quickly clicks "Friendly," both
requests race. Whichever resolves last overwrites `comment`. Same issue if
the user closes the composer (`onClose`) mid-generation — the late response
calls `setComment` on an unmounted-or-out-of-scope component (React 18+
ignores it but logs a warning in StrictMode).

**Fix:** Wire an `AbortController` into `generateReply` (accept an optional
`signal` parameter in `api.ts`), and either cancel the in-flight request on
re-click or short-circuit the response handler with a `disposed` ref.

---

### IN-05: System prompt placeholder uses `.format(brand_name=brand_name)` — a brand name containing `{...}` would raise KeyError

**File:** `apps/integrations/openai/prompts.py:115`

**Issue:** `template.format(brand_name=brand_name)` will raise `KeyError` if
the brand name itself contains literal `{x}` text (e.g., a marketing brand
"Acme {Coffee}"). This is unlikely but is a latent injection-style fragility.

**Fix:** Use simple string substitution: `template.replace("{brand_name}",
brand_name)` (and document the `{brand_name}` token clearly), or escape the
brand name before formatting. Add a test:

```python
def test_brand_name_with_braces_does_not_raise():
    msgs = build_reply_generation_messages(
        review=_make_review(), tone="professional", brand_name="Acme {Coffee}",
    )
    assert "Acme {Coffee}" in msgs[0]["content"]
```

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
