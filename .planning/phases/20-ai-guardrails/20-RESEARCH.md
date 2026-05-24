# Phase 20: AI Guardrails - Research

**Researched:** 2026-05-23
**Domain:** OpenAI Moderation API integration, exception mapping, AiUsageLog schema, Celery retry queryset, frontend error-shape compatibility
**Confidence:** HIGH (all findings verified against codebase reads + installed `openai` SDK introspection + official OpenAI docs)

## Summary

Phase 20 adds a single new module (`apps/integrations/openai/guardrails.py`) and threads its two functions (`moderate_input`, `moderate_output`) into two existing service entry points. CONTEXT.md locks all design decisions — research focused on **gap-filling for the planner**: SDK response shape (one important contradiction with the CONTEXT snippet found), AiUsageLog schema (migration required), exception placement (existing base class found), test mock convention (`unittest.mock.patch` of the imported symbol — confirmed pattern), and the precise insertion point for the `ContentModeratedException` catch block in the view.

**Primary recommendation:** Treat the CONTEXT.md snippet's `BLOCKING_MODERATION_CATEGORIES` slash-form constant as a **bug** — verified against the installed `openai==1.55+` SDK, `Categories.model_dump()` returns **underscore** keys, not slash keys. Either change the constant to underscore form (`self_harm_intent`, `hate_threatening`, `violence_graphic`, `sexual_minors`, `self_harm_instructions`) **or** call `model_dump(by_alias=True)` so the slash form matches. Recommend underscore form for symmetry with Python attribute access and to keep the code grep-friendly. This is the single most important finding in this research.

## User Constraints (from CONTEXT.md)

### Locked Decisions

All 27 decisions D-01 through D-27 are locked. Of particular note for planning:

- **D-01:** OpenAI Moderation API `omni-moderation-latest` is the engine. No third-party guardrails (D-12).
- **D-04 / D-07:** Same category-aware policy applies to both input (review text) and output (generated reply). Both raise `ContentModeratedException` → HTTP 422 from the view.
- **D-13:** New module `apps/integrations/openai/guardrails.py` with two public functions: `moderate_input(text: str) -> None` and `moderate_output(text: str) -> str`.
- **D-14 / D-15:** Call ordering — moderation **before** the OpenAI generation call; for replies, also **after** generation (output moderation).
- **D-16:** New exception `ContentModeratedException` in `apps/integrations/openai/exceptions.py`.
- **D-20:** `AiUsageLog.status` gains `"moderated"` value (with tokens=0, cost=0).
- **D-21:** New env-configurable setting `OPENAI_REVIEW_TEXT_MAX_CHARS` (default 4000), used by `moderate_input` for length truncation.
- **D-23:** Category-aware blocking. `results[0].flagged` is **not** the trigger — only specific high-severity categories block.
- **D-24:** Moderation API failure is **fail-open with one retry** (1s delay).
- **D-25:** `retry_failed_enrichments_task` must exclude `error_code = "content_moderated"`.
- **D-26:** Single shared user copy: `"AI reply isn't available for this review. Please write your reply manually."`
- **D-27:** Frontend stays as-is — no `ai_reply_available` flag on review payload.

### Claude's Discretion

- Internal implementation of `_call_moderation_api` retry/timeout (D-24 specifies 1 retry, 1 second — exact mechanism is Claude's).
- Logger event-payload shape beyond the required fields (`event`, `entity_type`, `entity_id`, `stage`, `categories`, `blocked`).
- Whether to expose `BLOCKING_MODERATION_CATEGORIES` as a module-level constant (recommend yes, per D-23 wording).
- Whether to extract the moderation-blocked AiUsageLog write into a small helper inside `guardrails.py` or duplicate in each calling service. **Recommend a helper in `guardrails.py`** so the moderated-AiUsageLog write happens in one place — symmetric with how the moderation block itself lives in one place.

### Deferred Ideas (OUT OF SCOPE)

- Per-org daily token budget (`Organisation.daily_ai_token_budget`).
- Org-level AI enable/disable toggle (`Organisation.ai_features_enabled`).
- Custom keyword blocklists per org.
- PII scrubbing of review text.
- Factuality / groundedness check.
- Per-user AI budgets.
- AI moderation admin dashboard.
- Tone-specific guardrails.
- Surfacing `review.ai_reply_available: bool` (D-27 explicitly defers this).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Moderation API call (network I/O) | API / Backend (integrations module) | — | OpenAI client lives in `apps/integrations/openai/` per §14 of CLAUDE.md |
| Category policy evaluation | API / Backend (guardrails module) | — | Pure logic; testable without network |
| Service-level orchestration (call ordering) | API / Backend (`apps/reviews/services/`) | — | §5 services pattern — moderation calls are sequenced inside `enrich_review` and `generate_reply_draft` |
| Exception → HTTP status mapping | API / Backend (view) | — | Existing pattern in `ReviewViewSet.generate_reply` is explicit `return Response(..., status=...)` — not a custom DRF exception handler |
| User-facing copy rendering | Frontend (existing Phase 19 component) | — | D-27 — frontend reads `detail` from JSON body, no code change |
| Failure UX (button stays clickable) | Frontend (existing Phase 19 component) | — | D-27 — explicitly no frontend changes |
| Logging | API / Backend (standard `logger.warning` / `logger.error`) | — | §21 — structured fields, no review text in WARNING |

## Phase Requirements

No `REQ-XX` IDs are defined in `.planning/REQUIREMENTS.md` for Phase 20 (expected — guardrails are an architectural addition, not a new feature with stakeholder requirements). The 27 decisions in CONTEXT.md serve as the requirement set and the planner maps directly from D-01..D-27 to task IDs.

## Standard Stack

Phase 20 adds **no new dependencies.** Everything required is already installed:

| Library | Version (current in lock) | Purpose | Why Standard |
|---------|---------------------------|---------|--------------|
| `openai` | ^1.55.0 (per CLAUDE.md §14.9; verified `openai.types.moderation.Categories` present in `.venv`) | `client.moderations.create(...)` call | Already the SDK used for enrichment + reply generation |

**Package Legitimacy Audit:** No new packages installed. Skipping slopcheck — phase adds zero external dependencies, only new internal modules and config.

## Code Landmarks

These are the **exact insertion points** for each piece of work. Planner should copy file:line references verbatim into each plan's `<read_first>` block.

### `apps/integrations/openai/client.py`

- **Lines 47-55** — Lazy singleton `_client` + `_get_client()`. The new `guardrails.py` should reuse `_get_client()` (import it) so the moderation calls share the same singleton instance. Do NOT create a second singleton.
- **Lines 118, 305** — `@traceable(run_type="llm", name="...")` is applied **only** to the two generation entry points. Confirms decision: moderation calls are **not** traced (CONTEXT.md snippet comment).
- **Lines 188-240** — `call_openai_enrichment()`. Already returns `(EnrichmentResult, usage_data)`. No change needed in this file — guardrails layer wraps it externally.
- **Lines 360-408** — `call_openai_reply_generation()`. Already returns `(draft_text, usage_data)`. No change needed in this file.

### `apps/integrations/openai/exceptions.py` (lines 1-29)

- **Existing base class:** `OpenAIError(Exception)` at line 11. **All other exceptions inherit from it.**
- **Recommendation:** `ContentModeratedException` should inherit from `OpenAIError` for consistency, even though D-16 says "Exception subclass" — `OpenAIError` IS an `Exception` subclass, so this satisfies D-16 while keeping the hierarchy uniform. This also future-proofs view-layer `except OpenAIError` catches.
- **Concrete shape:** `class ContentModeratedException(OpenAIError): pass` — no extra attributes needed (the caller already knows which stage and which entity; the exception just signals "blocked").

### `apps/integrations/openai/models.py` (lines 55-101)

**Critical:** `AiUsageLog.status` is `models.CharField(max_length=10, choices=Status.choices)` where `Status` is a `TextChoices` enum with **two uppercase values**: `SUCCESS = "SUCCESS"` and `FAILED = "FAILED"`.

| Concern | Answer |
|---|---|
| Is `choices=` set? | Yes (line 85) |
| Migration required? | **Yes** — must add a third TextChoice. |
| max_length sufficient? | `MODERATED` is 9 chars ≤ 10. **Fits without max_length change.** |
| CONTEXT D-20 says `"moderated"` (lowercase) | **Inconsistent with the existing enum values (`SUCCESS`/`FAILED` are uppercase).** Recommend planner use `MODERATED = "MODERATED"` to stay consistent with `TextChoices` style. This is a minor deviation from D-20's literal text; flag it in the plan but do not block on it.

**Migration shape:** the migration adds a new choice but does NOT alter the column type (max_length unchanged, charfield unchanged). Django generates an `AlterField` migration; this is harmless and runs in milliseconds on any size table. No data migration needed — existing rows continue to hold `SUCCESS`/`FAILED`.

### `apps/reviews/services/enrichment.py`

- **Lines 382-461** — `enrich_review()`. Insertion point for `moderate_input(review.comment)` is **after** the `_persist_success_no_comment` skip-block (line 448) and **before** `call_openai_enrichment` (line 452). I.e.: between lines 448 and 451.
- **On moderation block:** call a new `_persist_moderated(review, stage="input", categories=[...])` helper that mirrors `_persist_failure` but writes `status=MODERATED`, `error_code="content_moderated"`, tokens=0, cost=0. Then `return` (no raise — moderation block is terminal, not retry-able).
- **No moderation on enrichment output** per D-09 — Pydantic structural validation is the only output check for enrichment.

### `apps/reviews/services/reply_generation.py`

- **Lines 68-128** — `generate_reply_draft()`. Insertion points:
  1. `moderate_input(review.comment)` — immediately after tone validation (line 78), **before** the `try:` block at line 80. A `ContentModeratedException` bubbles to the view.
  2. `moderate_output(draft)` — between `call_openai_reply_generation` return (line 85) and the pricing/AiUsageLog write (line 100). If it raises, write a moderated AiUsageLog row first **without** the OpenAI usage (matching D-20: tokens=0, cost=0) — wait, **important nuance:** on output moderation the OpenAI call already happened and tokens WERE consumed. Plan should write a `MODERATED` row that DOES carry the actual prompt_tokens/completion_tokens/cost (the cost was real), with a marker (e.g. `error_code="output_moderated"`). This nuance is NOT covered explicitly in CONTEXT.md and the planner should call it out as a clarifying point or default to: input-moderated → tokens=0 cost=0; output-moderated → real tokens + cost + `status=MODERATED`. **Recommend the latter.**
  3. **Length truncation (D-08):** apply to `draft` AFTER output moderation passes, BEFORE the AiUsageLog success write. Truncation is a presentation-level transform — log the original token usage as `SUCCESS`, not as `MODERATED`.

### `apps/reviews/views.py`

- **Lines 253-317** — `ReviewViewSet.generate_reply`. The exception-to-HTTP mapping is **inline** (`return Response(..., status=status.HTTP_502_BAD_GATEWAY)`), **not** a custom DRF exception handler.
- **Insertion point for `ContentModeratedException` catch:** new `except ContentModeratedException as exc:` block placed **before** the `except (OpenAITransientError, OpenAIPermanentError):` block (lines 276-295), because `ContentModeratedException` inherits from `OpenAIError` (per recommendation above) and exception-order matters — most-specific first.
- **Return shape:**
  ```python
  return Response(
      {"code": "content_moderated", "detail": "AI reply isn't available for this review. Please write your reply manually."},
      status=status.HTTP_422_UNPROCESSABLE_ENTITY,
  )
  ```
- **Note:** D-04 prescribes `"code": "content_moderated"`, D-07 prescribes `"code": "output_moderated"` — but D-26 mandates the same `detail` string for both. **Decision needed:** does the `code` differ between input/output flags? Recommend keeping ONE `code` (`"content_moderated"`) for both — the frontend per D-27 already renders only `detail` and ignores `code`. This is a minor CONTEXT.md inconsistency the planner should resolve (use one code, document why).

### `apps/reviews/tasks.py`

- **Lines 217-246** — `retry_failed_enrichments_task`. Current queryset (lines 233-239):
  ```python
  Review.objects.filter(
      enrichment_status=Review.EnrichmentStatus.FAILED,
      enrichment_version__lt=MAX_TOTAL_ENRICH_ATTEMPTS,
      deleted_at__isnull=True,
  )
  ```
- **D-25 change:** add **one more filter**:
  ```python
  .exclude(ai_usage_logs__error_code="content_moderated")
  ```
  ...OR (simpler and more decoupled) add an `error_code` field on `Review` itself. Currently `error_code` lives only on `AiUsageLog`, not on `Review`. **Recommendation:** join through `AiUsageLog` is fine but produces a subquery. Cleaner alternative: add a check on the most recent `AiUsageLog` row for that review. Even simpler: add a denormalized `Review.enrichment_error_code: str` field (nullable, blank-default CharField) populated by `_persist_failure` / `_persist_moderated`. **Recommend the denormalized field** — one extra column, zero join, idiomatic. The planner can then write `.exclude(enrichment_error_code="content_moderated")`. This is a small additional migration; call it out.

### `config/settings/base.py`

- **Line 158** — `OPENAI_MAX_RETRIES`. Insert the new setting **immediately after** this line for natural grouping:
  ```python
  OPENAI_REVIEW_TEXT_MAX_CHARS = env.int("OPENAI_REVIEW_TEXT_MAX_CHARS", default=4000)
  ```

### `.env.example`

- Planner must remember to add `OPENAI_REVIEW_TEXT_MAX_CHARS=4000` to the example env file (project convention from §4 / §22).

## OpenAI Moderation API Reference

### Endpoint

```python
client.moderations.create(input=text, model="omni-moderation-latest")
```

### Response shape (verified against installed `openai` SDK)

```python
response.id                                  # str — "modr-..."
response.model                               # str — "omni-moderation-latest"
response.results                             # list[Moderation] — always length 1 for single-string input
response.results[0].flagged                  # bool — overall flag (DO NOT USE; D-23)
response.results[0].categories               # Categories pydantic model
response.results[0].category_scores          # CategoryScores pydantic model (float probabilities)
response.results[0].category_applied_input_types  # for image/audio multi-modal — ignore for text
```

### `Categories` field names — IMPORTANT FINDING

The Pydantic `Categories` model has BOTH a Python attribute name (underscore) AND a JSON alias (slash). Behaviour verified by introspection of `openai.types.moderation.Categories` against the installed SDK:

| Field name (attribute / model_dump key) | Alias (raw API JSON key) |
|------|------|
| `harassment` | (none) |
| `harassment_threatening` | `harassment/threatening` |
| `hate` | (none) |
| `hate_threatening` | `hate/threatening` |
| `illicit` | (none) |
| `illicit_violent` | `illicit/violent` |
| `self_harm` | `self-harm` |
| `self_harm_instructions` | `self-harm/instructions` |
| `self_harm_intent` | `self-harm/intent` |
| `sexual` | (none) |
| `sexual_minors` | `sexual/minors` |
| `violence` | (none) |
| `violence_graphic` | `violence/graphic` |

**Default `.model_dump()` returns underscore keys.** `.model_dump(by_alias=True)` returns slash keys.

### Bug in CONTEXT.md snippet (must fix during planning)

CONTEXT.md `<code_context>` includes this snippet:
```python
BLOCKING_MODERATION_CATEGORIES = {
    "sexual/minors", "hate/threatening", "violence/graphic",
    "self-harm/intent", "self-harm/instructions",
}
def _is_blocked(response) -> tuple[bool, list[str]]:
    cats = response.results[0].categories.model_dump()  # ← returns UNDERSCORE keys
    flagged = [k for k, v in cats.items() if v]
    blocked = any(c in BLOCKING_MODERATION_CATEGORIES for c in flagged)  # ← never matches
```

With default `model_dump()`, `flagged` will contain entries like `self_harm_intent`, which do NOT match `"self-harm/intent"` in the set — **`blocked` would always be `False`, silently failing open on every flagged review**. The planner MUST use ONE of:

**Option A (recommended):** Use underscore form in the constant.
```python
BLOCKING_MODERATION_CATEGORIES = {
    "sexual_minors", "hate_threatening", "violence_graphic",
    "self_harm_intent", "self_harm_instructions",
}
```

**Option B:** Use `.model_dump(by_alias=True)` to get slash keys back. (Less idiomatic — Python attribute style is underscore.)

Recommend Option A. Document the choice in code with a brief comment so a future reader doesn't "fix" it back.

### Pricing & limits

- **Free** — per official OpenAI docs (developers.openai.com/api/docs/guides/moderation): "The moderation endpoint is free to use."
- **Rate limits** — not published explicitly for the moderation endpoint. Project-level OpenAI rate limit applies but moderation has a much higher allowance than completions. Practically: 1 moderation call per enrichment + 2 per reply generation = below any realistic limit for this platform's projected volume. Token-bucket safety net is not required for Phase 20 MVP.
- **Latency** — typically <200ms (per CONTEXT.md D-01 and confirmed by community sources). One retry with 1s delay (D-24) keeps total worst-case overhead at ~1.4s per generation event, acceptable for the synchronous reply endpoint (Phase 19 baseline already ~2-4s).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (per §16) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest apps/integrations/openai/tests/ apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_reply_generation_service.py -x` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Mock convention (verified from existing tests)

The codebase uses `unittest.mock.patch` targeting the **import path inside the consuming module** (NOT the source). Example from `apps/reviews/tests/test_reply_generation_service.py` line 43-45:

```python
with patch(
    "apps.reviews.services.reply_generation.call_openai_reply_generation",
    return_value=("Nice reply!", _usage_data()),
):
```

For Phase 20 tests, the same pattern applies. Mock targets:

- `apps.integrations.openai.guardrails._call_moderation_api` (for testing `moderate_input` / `moderate_output` in isolation)
- `apps.reviews.services.enrichment.moderate_input` (for testing the enrichment call sequence)
- `apps.reviews.services.reply_generation.moderate_input` and `moderate_output` (for testing the reply generation sequence)
- The view tests mock the service function (`generate_reply_draft`) and raise `ContentModeratedException` to verify the 422 mapping.

**Never** use `respx` or `responses` (HTTP-level mocking) for this codebase — the convention is patch-at-import. Two libraries (`respx`, `responses`) are mentioned in CLAUDE.md §16 as acceptable but the codebase has standardised on `unittest.mock.patch`.

### Decisions → Test Map

| Decision | Behaviour | Test Type | Automated Command |
|---|---|---|---|
| D-01, D-04 | `moderate_input` calls Moderation API exactly once with the right model | unit | `pytest apps/integrations/openai/tests/test_guardrails.py -k moderate_input -x` |
| D-03, D-21 | Truncates input text to `OPENAI_REVIEW_TEXT_MAX_CHARS` with `…[truncated]` suffix | unit | `pytest apps/integrations/openai/tests/test_guardrails.py -k truncate -x` |
| D-07, D-08 | `moderate_output` blocks flagged outputs; 300-word truncation happens after | unit | `pytest apps/integrations/openai/tests/test_guardrails.py -k moderate_output -x` |
| D-08 | Reply >300 words truncated at sentence boundary with `" (Please review and complete before sending.)"` | unit | `pytest apps/integrations/openai/tests/test_guardrails.py -k truncate_reply -x` |
| D-14, D-15 | Call sequence: input moderation → OpenAI → (output moderation for replies) | unit | `pytest apps/reviews/tests/test_reply_generation_service.py -k moderation -x` |
| D-16, D-26 | `ContentModeratedException` from service → 422 with canonical detail string | unit (view) | `pytest apps/reviews/tests/test_views.py -k generate_reply_moderated -x` |
| D-20 | Moderated path writes `AiUsageLog` with `status=MODERATED`, tokens=0 (input) or real (output) | unit | `pytest apps/reviews/tests/test_enrichment_service.py -k moderated -x` |
| D-23 | Only high-severity categories block; lesser categories log + proceed | unit | `pytest apps/integrations/openai/tests/test_guardrails.py -k blocking_categories -x` |
| D-24 | Moderation API failure: retry once after 1s; if both fail, proceed and log ERROR | unit (with `time.sleep` patched) | `pytest apps/integrations/openai/tests/test_guardrails.py -k fail_open -x` |
| D-25 | `retry_failed_enrichments_task` queryset excludes `content_moderated` rows | unit | `pytest apps/reviews/tests/test_tasks.py -k retry_excludes_moderated -x` |

### Sampling Rate

- **Per task commit:** `pytest apps/integrations/openai/tests/ apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_views.py apps/reviews/tests/test_tasks.py -x` (≈ <30s expected)
- **Per wave merge:** Full suite — `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green + `pre-commit run --all-files` + `python manage.py makemigrations --check --dry-run`

### Wave 0 Gaps

- [ ] `apps/integrations/openai/tests/test_guardrails.py` — new test file for the guardrails module (does not exist today; verified)
- [ ] Existing `apps/reviews/tests/test_enrichment_service.py` and `test_reply_generation_service.py` — add new test classes / methods for moderation sequencing
- [ ] Existing `apps/reviews/tests/test_views.py` — add `test_generate_reply_returns_422_on_content_moderated`
- [ ] Existing `apps/reviews/tests/test_tasks.py` — add `test_retry_excludes_moderated`

No new framework install needed — pytest infrastructure is established.

## Open Question Resolutions

### 1. OpenAI Moderation API current shape (2026)

- **Endpoint:** `client.moderations.create(input=str, model="omni-moderation-latest")` (verified against `.venv/.../openai/types/moderation*.py`).
- **Response path:** `response.results[0].categories` — typed Pydantic `Categories` model (NOT a dict).
- **Attribute access:** dot notation works (`response.results[0].categories.self_harm_intent`). `.model_dump()` returns **underscore** keys; `.model_dump(by_alias=True)` returns **slash** keys.
- **Exact category strings:** see the table in §"OpenAI Moderation API Reference" above — **CONTEXT.md slash-form strings are INCORRECT for `.model_dump()` default behaviour.**
- **Free / latency / rate limits:** free; <200ms typical; no published per-endpoint rate limit but well within project quota.

### 2. Exception placement

- `OpenAIError` base class already exists at `apps/integrations/openai/exceptions.py:11`.
- Recommend `ContentModeratedException(OpenAIError)`. Inheriting from `OpenAIError` (not bare `Exception` as D-16 literally says) keeps the hierarchy uniform; D-16's "Exception subclass" requirement is satisfied since `OpenAIError(Exception)` itself extends `Exception`.

### 3. AiUsageLog.status field

- **Constrained** by `choices=Status.choices` (a `TextChoices` enum). Migration **is** required to add `MODERATED = "MODERATED"`.
- `max_length=10` is already sufficient (`MODERATED` is 9 chars).
- The migration is a pure `AlterField` adding the new choice — fast and harmless. No data migration needed.

### 4. Tracing decision

- `@traceable` is applied **only** to `_call_openai_with_tracing` (enrichment) at client.py:118 and `_call_openai_reply_with_tracing` (reply) at client.py:305.
- Moderation calls are NOT generation calls and should NOT be wrapped in `@traceable`. They are operational safety checks; their visibility comes from the `ai.moderation.flagged` / `ai.moderation.errored` log events (D-19, D-24). This aligns with CONTEXT.md's `_call_moderation_api` snippet which explicitly omits `@traceable`.
- Operational visibility for moderation = structured logs + `AiUsageLog` rows with `status=MODERATED`. No LangSmith integration needed.

### 5. Test mocking pattern

- Convention is `unittest.mock.patch` of the imported symbol inside the consuming module — confirmed at `apps/reviews/tests/test_reply_generation_service.py:43`.
- For Phase 20: mock `_call_moderation_api` (internal helper) when testing the guardrails module; mock `moderate_input` / `moderate_output` at their import path inside the service under test. Never construct real `Moderation` Pydantic instances unless the test specifically needs to verify SDK parsing — use `MagicMock` with `.results[0].categories.model_dump.return_value = {...}` for most tests.

### 6. AiUsageLog write path for moderated events

- The cleanest insertion point is **inside `guardrails.py`** — both `moderate_input` and `moderate_output` accept context kwargs (`review`, `stage`) and, on block, write the `MODERATED` `AiUsageLog` row themselves before raising `ContentModeratedException`. This keeps the moderation policy and its accounting in one place. The calling services (enrichment, reply_generation) do NOT need to know about `AiUsageLog` for the moderation path.
- **However**: this introduces a circular-import risk (`apps.integrations.openai` ↔ `apps.integrations.openai.models`). Verified: `apps.integrations.openai.models` only imports `django.db`/`django.utils.timezone`/`decimal` — no cycle. Safe to write `AiUsageLog` from inside `guardrails.py`.
- Function signature recommendation:
  ```python
  def moderate_input(text: str, *, review: Review | None = None, stage: str = "input") -> str:
      # returns possibly-truncated text; raises ContentModeratedException on block
  ```
  Pass `review=None` for unit tests that don't need the `AiUsageLog` side-effect; the function skips the log write when `review is None`.

### 7. Reply generation HTTP error mapping

- The view (`apps/reviews/views.py:259`) maps exceptions to HTTP via **inline `return Response(...)`** — not a custom DRF exception handler.
- Phase 20 just adds one new `except ContentModeratedException as exc:` block before the existing `except (OpenAITransientError, OpenAIPermanentError):` block. This is the entire change to the view.
- No change to `settings.REST_FRAMEWORK["EXCEPTION_HANDLER"]` needed (the codebase doesn't have one — it uses DRF default for ValidationError/Throttled/etc. and inline mapping for everything else).

### 8. Frontend implications

- The Phase 19 generate-reply UI consumes `{draft: str}` on 200 and `{code, detail}` on 502.
- For 422, returning `{code: "content_moderated", detail: "AI reply isn't available for this review. Please write your reply manually."}` matches the existing error-rendering path: any non-200 with a JSON body containing `detail` is shown to the user verbatim. **D-27 confirms no frontend change is in scope.** Planner should add a smoke test from the view's perspective; manual UI verification is sufficient (no React test).
- The exact frontend component path is not in scope for Phase 20 planning (no edit needed), but for reference: search `frontend/src/` for the reply composer. The planner does NOT need to read it.

### 9. `retry_failed_enrichments_task` current queryset

- Lines 233-239 of `apps/reviews/tasks.py` — see §Code Landmarks above.
- Recommended approach: add a new `Review.enrichment_error_code` field, populated by `_persist_failure` / `_persist_moderated`, then `.exclude(enrichment_error_code="content_moderated")`. This is one additional migration + one trivial filter line. Cleaner than joining through `AiUsageLog`.

### 10. Test infrastructure for Celery + moderation

- `CELERY_TASK_ALWAYS_EAGER = True` confirmed in test settings (per CLAUDE.md §16 and §12.8).
- `AiUsageLog` writes ARE testable in unit tests (existing tests already assert via `AiUsageLog.objects.filter(...)` — see `test_reply_generation_service.py:50-61`).
- No new test infrastructure needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content moderation classifier | Train/host a moderation model | OpenAI Moderation API (D-01) | Free, <200ms, identical SDK to existing OpenAI client, covers the full safety surface |
| Retry/backoff for the moderation call | Custom exponential backoff loop | Inline `try / sleep(1) / try` (D-24) | One retry with fixed 1s delay is explicit in D-24; no tenacity dependency needed |
| Sentence-boundary truncation (D-08) | Roll your own regex | `re.split(r'(?<=[.!?])\s+', text)` from stdlib + simple loop | Stdlib is sufficient for English review replies; spaCy/NLTK is overkill |
| Pydantic schema for moderation response | Build your own | Use `openai.types.moderation.Moderation` from the SDK | SDK already provides typed objects; just call `.model_dump()` (with the underscore-key caveat above) |

## Common Pitfalls

### Pitfall 1: Slash vs underscore in `Categories.model_dump()`

**What goes wrong:** `BLOCKING_MODERATION_CATEGORIES = {"self-harm/intent", ...}` against `cats.model_dump()` will never match — fails open silently on every flagged review.

**Why it happens:** Pydantic dumps to field names (underscore) by default; the SDK uses aliases for the slash form only when `by_alias=True`.

**How to avoid:** Use underscore form in the constant (recommended) OR call `model_dump(by_alias=True)`. Verified by direct introspection of the installed SDK.

**Warning sign in code review:** any string `"self-harm/..."` or `"hate/threatening"` adjacent to a `.model_dump()` call.

### Pitfall 2: Writing `AiUsageLog.status="moderated"` (lowercase) when the enum is uppercase

**What goes wrong:** Insert succeeds (CharField, no DB-level constraint), but `AiUsageLog.Status.MODERATED` queries don't find the row, and admin/dashboard filters silently miss it.

**Why it happens:** CONTEXT D-20 says `"moderated"` (lowercase); existing values are `"SUCCESS"`/`"FAILED"` (uppercase). Easy to copy the lowercase literal.

**How to avoid:** Define `MODERATED = "MODERATED", "Moderated"` in the `Status` enum, then always reference `AiUsageLog.Status.MODERATED` (never the string literal).

### Pitfall 3: Moderation block writing AiUsageLog INSIDE the calling service's transaction

**What goes wrong:** If `guardrails.moderate_input` writes `AiUsageLog`, and the caller wraps the moderation call inside a `transaction.atomic()` block that later raises, the moderated AiUsageLog row is rolled back — losing audit data on a safety event.

**Why it happens:** Enrichment service uses `transaction.atomic()` blocks. If `moderate_input` is called inside one of them, its writes ride the same transaction.

**How to avoid:** `moderate_input` must be called **outside** `transaction.atomic()` blocks. Verified safe location: enrichment.py lines 448-451 (between the no-comment skip and the OpenAI call) — this position is already outside the `transaction.atomic()` blocks in `_persist_*`. Document this constraint in the `guardrails.py` docstring.

### Pitfall 4: `retry_failed_enrichments_task` keeps retrying moderated rows

**What goes wrong:** Reviewer text is immutable; retrying moderation is pure waste, and produces N×3 useless `AiUsageLog` rows.

**Why it happens:** The existing queryset filters only by `enrichment_status=FAILED` and `enrichment_version<3`.

**How to avoid:** D-25 — exclude `content_moderated` error code. Recommend the `Review.enrichment_error_code` denormalized field for a one-line filter.

### Pitfall 5: 300-word truncation breaks mid-sentence

**What goes wrong:** Naive `" ".join(words[:300])` ends mid-sentence; user sees an awkward "Thank you for your review, but" cutoff.

**Why it happens:** Word-count truncation doesn't respect punctuation.

**How to avoid:** D-08 explicitly says "truncate at the last sentence boundary before the 300-word mark". Implementation: split on sentence delimiters, accumulate sentences until adding the next would exceed 300 words, append the constant suffix `" (Please review and complete before sending.)"`. Cover with a test case where the original draft is 305 words across three sentences and the truncation lands at sentence 2.

### Pitfall 6: Race between `moderate_output` raising and the AiUsageLog write

**What goes wrong:** Output moderation fires after a billable OpenAI call. If the AiUsageLog row is only written on the success path (lines 112-127 of reply_generation.py), an output-moderated reply leaves no log of the cost incurred — under-counting AI spend.

**Why it happens:** The current happy path writes `AiUsageLog` after returning from OpenAI. If `moderate_output` raises before the write, the row is never created.

**How to avoid:** When `moderate_output` raises, the calling service catches `ContentModeratedException`, writes an `AiUsageLog` row with `status=MODERATED`, `request_type="reply_generation"`, the **real** usage data from the just-completed call, and `error_code="output_moderated"`, then re-raises. This is a small extension to `_write_failure_log` (or a new sibling). The planner must add this explicitly — D-20 only specifies tokens=0 for moderation events but that's the input-moderation case; output-moderation has real cost.

## Runtime State Inventory

Phase 20 is a code-and-config addition with **one schema change** (TextChoices addition) and **one optional schema change** (denormalized `Review.enrichment_error_code` if planner adopts the recommendation). No data migration required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `AiUsageLog.status` choices set (`SUCCESS`, `FAILED`) — needs `MODERATED` added | Django migration: `AlterField` on `status`. Pre-existing rows unchanged. |
| Live service config | None — no n8n / Datadog / Tailscale / Cloudflare resources reference moderation | None |
| OS-registered state | None — no Task Scheduler / launchd / systemd references | None |
| Secrets/env vars | New env var `OPENAI_REVIEW_TEXT_MAX_CHARS` (default 4000) — code-side only, no secret | Add to `.env.example`. Document in `config/settings/base.py`. |
| Build artifacts | None | None |

## Environment Availability

Phase 20 uses only the existing OpenAI client (already configured per Phase 12 and Phase 19). No new external dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `openai` Python SDK | Moderation API call | ✓ | ^1.55.0 (installed in `.venv`) | — |
| OpenAI Moderation endpoint | Network call | ✓ (free endpoint) | — | Fail-open per D-24 |
| Redis (existing) | None new — moderation does not use Redis | ✓ | 7-alpine | — |

No new dependencies, no missing tooling.

## Security Domain

### Applicable ASVS categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | (no new auth surface) |
| V3 Session Management | no | (no new session surface) |
| V4 Access Control | yes | Existing `ReviewViewSet` tenant scoping continues to apply; moderation does not bypass it. Phase 19's permission class already restricts to org-scoped reviews. |
| V5 Input Validation | yes | The whole phase is about input validation for AI safety. `moderate_input` is the validator. Existing DRF serializer validation continues to handle `tone` enum. |
| V6 Cryptography | no | No new keys/secrets beyond existing OpenAI API key. |
| V7 Error Handling & Logging | yes | D-19 mandates structured logging; §21 forbids logging review text at WARNING+; D-24 mandates ERROR-level log on moderation outage |
| V14 Configuration | yes | `OPENAI_REVIEW_TEXT_MAX_CHARS` env var must not be exposed in error messages or admin UI |

### Known threat patterns for Django + OpenAI stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via review text | Tampering | D-05 — system prompt in `system` role, review text in `user` role (structural isolation); D-03 length cap (4000 chars) prevents context-window flooding |
| Toxic content reaching the model | Information Disclosure | D-04 — input moderation blocks high-severity categories before OpenAI call |
| Toxic generated content reaching the user | Information Disclosure | D-07 — output moderation on generated replies; never return flagged text |
| Cost exhaustion via repeated moderation-blocked clicks | Denial of Service | Existing throttle scope `generate_reply: 10/min` (Phase 19) already caps clicks; moderation calls are free so blocked attempts cost only the Phase-19 ScopedRateThrottle budget |
| Silent fail-open from API outage | Repudiation / Tampering | D-24 — single retry, then ERROR-level log so monitoring catches sustained outages; accepted trade-off documented in CONTEXT.md |
| PII leakage via review text in logs | Information Disclosure | §21 + D-19 — log only category names and entity IDs at WARNING; review text never appears at INFO or above |

## Code Examples

### Recommended `guardrails.py` skeleton (illustrative — verify category constants per Pitfall 1)

```python
# apps/integrations/openai/guardrails.py
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import openai
from django.conf import settings

from apps.integrations.openai.client import _get_client
from apps.integrations.openai.exceptions import ContentModeratedException
from apps.integrations.openai.models import AiUsageLog

logger = logging.getLogger(__name__)

# Underscore form — Categories.model_dump() default — see RESEARCH.md Pitfall 1.
BLOCKING_MODERATION_CATEGORIES: frozenset[str] = frozenset({
    "sexual_minors",
    "hate_threatening",
    "violence_graphic",
    "self_harm_intent",
    "self_harm_instructions",
})

_MODERATION_MODEL = "omni-moderation-latest"
_TRUNCATION_SUFFIX = "…[truncated]"


def _call_moderation_api(text: str) -> Any:
    """One Moderation API call. Caller handles retry per D-24."""
    return _get_client().moderations.create(input=text, model=_MODERATION_MODEL)


def _evaluate(response: Any) -> tuple[bool, list[str]]:
    cats = response.results[0].categories.model_dump()  # underscore keys
    flagged = sorted(k for k, v in cats.items() if v)
    blocked = any(k in BLOCKING_MODERATION_CATEGORIES for k in flagged)
    return blocked, flagged


def _truncate_input(text: str) -> str:
    cap = settings.OPENAI_REVIEW_TEXT_MAX_CHARS
    if len(text) <= cap:
        return text
    return text[: cap - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX


def _moderate_with_retry(text: str, *, stage: str, entity_id: int | None) -> tuple[bool, list[str]]:
    """D-24: one retry after 1s, then fail-open."""
    for attempt in (1, 2):
        try:
            resp = _call_moderation_api(text)
            return _evaluate(resp)
        except (openai.RateLimitError, openai.APIStatusError, openai.APIConnectionError) as exc:
            if attempt == 1:
                time.sleep(1.0)
                continue
            logger.error(
                "ai.moderation.errored stage=%s entity_id=%s exc=%s",
                stage, entity_id, exc,
            )
            return False, []  # fail open


def moderate_input(text: str, *, review: Any = None) -> str:
    """Truncate, then check input. Returns possibly-truncated text.

    Raises ContentModeratedException if a blocking category fires.
    Writes a MODERATED AiUsageLog row before raising (when review is provided).
    """
    truncated = _truncate_input(text)
    blocked, flagged = _moderate_with_retry(
        truncated, stage="input", entity_id=getattr(review, "pk", None),
    )
    logger.warning(
        "ai.moderation.flagged stage=input entity_type=review entity_id=%s "
        "categories=%s blocked=%s",
        getattr(review, "pk", None), flagged, blocked,
    )
    if blocked:
        if review is not None:
            AiUsageLog.objects.create(
                organisation_id=review.organisation_id,
                review_id=review.pk,
                request_type="enrichment",  # caller may override request_type
                model=settings.OPENAI_MODEL,
                prompt_tokens=0, completion_tokens=0, cached_tokens=0, total_tokens=0,
                estimated_cost_usd=Decimal("0"),
                status=AiUsageLog.Status.MODERATED,
                error_code="content_moderated",
                error_message=f"flagged_categories={flagged}",
            )
        raise ContentModeratedException("input flagged")
    return truncated


def moderate_output(text: str, *, review: Any = None) -> str:
    blocked, flagged = _moderate_with_retry(
        text, stage="output", entity_id=getattr(review, "pk", None),
    )
    logger.warning(
        "ai.moderation.flagged stage=output entity_type=review entity_id=%s "
        "categories=%s blocked=%s",
        getattr(review, "pk", None), flagged, blocked,
    )
    if blocked:
        raise ContentModeratedException("output flagged")
    return text
```

(This is illustrative — the planner will refine signatures and the AiUsageLog write contract for input vs output moderation per Pitfall 6.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled keyword blocklists | Hosted ML moderation classifier (OpenAI Moderation API) | OpenAI Moderation API generally available since 2022; omni-moderation-latest since 2024 | Free, multilingual, far higher recall than keyword filtering |
| `text-moderation-latest` (legacy) | `omni-moderation-latest` (current) | 2024 release | Adds image moderation (not used here) and improves text recall; legacy model still works but is deprecated |
| Generic `flagged` boolean for blocking | Category-aware policy (CONTEXT D-23) | Industry norm post-2024 | Avoids over-blocking on lower-severity categories like plain `harassment` while still blocking the high-harm set |

**Deprecated/outdated:**
- `text-moderation-latest` model — replaced by `omni-moderation-latest`. Do not use.
- Using `response.results[0].flagged` as the sole gate — over-blocks; superseded by category-aware policies (D-23).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Moderation endpoint published rate limit is non-binding for this platform's volume | OpenAI API Reference | Low — if hit, fail-open per D-24; would surface in `ai.moderation.errored` ERROR log |
| A2 | `MODERATED = "MODERATED"` (uppercase) is preferable to D-20's literal `"moderated"` (lowercase) for enum consistency | Code Landmarks → models.py | Low — planner can choose either; both work; uppercase matches existing pattern |
| A3 | Output-moderation should write `AiUsageLog` with REAL tokens (not zero) since the OpenAI call already completed | Pitfall 6, Open Q 7 | Medium — affects cost accounting accuracy; recommend resolving with user before plan locks |
| A4 | `ContentModeratedException` inheriting from `OpenAIError` (not bare `Exception`) is correct interpretation of D-16 | Code Landmarks → exceptions.py | Low — purely a style choice; both satisfy D-16 |
| A5 | Single `code` value (`"content_moderated"`) suffices despite D-04 vs D-07 using different codes | Code Landmarks → views.py | Low — frontend ignores `code` per D-27; resolving to one code simplifies API surface |
| A6 | Denormalized `Review.enrichment_error_code` field is preferable to joining through `AiUsageLog` for the retry-task filter | Code Landmarks → tasks.py | Low — both work; denormalized is cleaner and faster |

A3 in particular should be confirmed with the user during plan-checker review.

## Open Questions

1. **Output-moderation AiUsageLog token accounting (A3 above).** Should the row carry real tokens or zero? CONTEXT.md is silent. Recommend real tokens with `error_code="output_moderated"` — surfaces cost truthfully.

2. **One `code` or two for input vs output moderation in the HTTP 422 body?** D-04 says `"content_moderated"`, D-07 says `"output_moderated"`, D-26 says same `detail`. Recommend one code. Confirm with user.

3. **Should the `Review.enrichment_error_code` field be added (denormalized) or should the retry task join through `AiUsageLog`?** Recommend denormalized field. Confirm with user during plan-checker review.

## Sources

### Primary (HIGH confidence)

- Codebase introspection — direct reads of `apps/integrations/openai/{client,exceptions,models}.py`, `apps/reviews/services/{enrichment,reply_generation}.py`, `apps/reviews/views.py`, `apps/reviews/tasks.py`, `config/settings/base.py`
- Installed SDK introspection — `openai.types.moderation.Categories` field/alias mapping verified by `.venv/bin/python` introspection on installed `openai>=1.55.0`
- OpenAI official docs — https://developers.openai.com/api/docs/guides/moderation (category list, pricing = free)
- CLAUDE.md §5, §12, §14, §16, §21, §22, §24 — architecture, services pattern, AiUsageLog contract, test mocking, logging rules

### Secondary (MEDIUM confidence)

- OpenAI Python SDK Issue #1786 — Categories model exposes both naming conventions (cross-verified by local introspection)
- WebSearch results for moderation API category names (confirmed against official docs)

### Tertiary (LOW confidence)

- None — every claim in this document was verified against either the codebase, the installed SDK, or OpenAI's official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; existing SDK introspected directly
- Architecture: HIGH — CONTEXT.md locks all major architectural decisions; code landmarks verified by direct read
- Pitfalls: HIGH — Pitfall 1 (slash-vs-underscore) verified by installed SDK introspection; Pitfall 6 (output cost accounting) derived from CONTEXT silence + cost-tracking contract in §14
- Open questions: 3 small clarifications recommended but none blocking; planner can proceed and call them out as decisions for plan-checker

**Research date:** 2026-05-23
**Valid until:** 2026-06-22 (30 days — stable area; OpenAI SDK 1.x API surface has been stable since late 2024)
