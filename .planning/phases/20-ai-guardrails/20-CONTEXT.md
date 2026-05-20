# Phase 20: AI Guardrails - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Add safety and control mechanisms around every OpenAI call in the platform — both the review enrichment pipeline and the reply-generation endpoint (Phase 19). Guardrails operate at two layers: **Input (pre-LLM)** intercepts content before it reaches OpenAI; **Output (post-LLM)** checks the model's response before it is persisted or returned to the user. Additionally, add an org-level AI enable/disable toggle (Superadmin only) and a per-org daily token budget cap.

**Out of scope:** Real-time content moderation of the reviews themselves in the UI, custom moderation model training, per-user AI budgets, keyword allowlists/blocklists as a config UI, groundedness/on-topic checks beyond prompt instruction, third-party guardrail libraries (Guardrails AI, NeMo Guardrails, Presidio), moderation during review sync.

</domain>

<decisions>
## Implementation Decisions

### Moderation tool
- **D-01:** Use OpenAI's **Moderation API** (`omni-moderation-latest`) as the primary guardrail engine — it's free, returns structured category scores in <200ms, and reuses the existing OpenAI client. No third-party moderation vendor in this phase.
- **D-02:** The moderation check is **synchronous and blocking** — a flagged input aborts the OpenAI call; a flagged output is suppressed before the response reaches the caller. Both failures result in a structured error response.

### Input guardrails (pre-LLM)
- **D-03:** **Content length truncation** — review text is capped at **4 000 characters** before being inserted into any prompt. Truncation appends `…[truncated]`. This prevents context-window exhaustion and indirect prompt injection via extremely long reviews.
- **D-04:** **Moderation check on review text** — before calling `call_openai_enrichment()` or `call_openai_reply_generation()`, call `openai.moderations.create(input=review_text)`. If `results[0].flagged is True`, skip the OpenAI call:
  - Enrichment: set `Review.enrichment_status = FAILED` with `error_code="content_moderated"`. Write `AiUsageLog` with `status="moderated"`, zero tokens.
  - Reply generation: return `{"code": "content_moderated", "detail": "This review cannot be used for AI reply generation."}` with HTTP 422.
- **D-05:** **Prompt structure isolation** — the system prompt is always in the `system` role; review text is always in the `user` role (already the case). This structurally separates instruction from untrusted content, providing a hard boundary against direct prompt injection.
- **D-06:** No additional PII scrubbing of review text before sending — reviews are publicly visible content on Google Business Profile, so the original text is not considered private. The prompt itself never contains user credentials or org-internal data beyond brand/shop name.

### Output guardrails (post-LLM)
- **D-07:** **Moderation check on generated replies** — after `call_openai_reply_generation()` returns a draft, run the generated text through the Moderation API. If flagged: return `{"code": "output_moderated", "detail": "AI generation failed. Please write your reply manually."}` with HTTP 422. Do NOT return the flagged text.
- **D-08:** **Length enforcement on generated replies** — if the generated reply exceeds **300 words**, truncate at the last sentence boundary before the 300-word mark and append ` (Please review and complete before sending.)`. Log at WARNING.
- **D-09:** **Enrichment structural validation** — Pydantic already validates enrichment output. No additional moderation check on enrichment output (tags and action item titles are low-risk structured data, not user-facing prose).
- **D-10:** **Groundedness / on-topic check** — not implemented. The prompt instruction "Do not invent facts" combined with the review text provided as context is the sole groundedness control. No post-LLM factuality or keyword-overlap check. Revisit after Phase 20 ships if real outputs reveal issues.

### Org-level AI toggle
- **D-11:** Add `ai_features_enabled = models.BooleanField(default=True)` to `Organisation`. Migration included. Superadmin can toggle on org edit form (same pattern as `allow_custom_sync_depth`).
- **D-12:** When `ai_features_enabled=False` for an org:
  - Enrichment: `enrich_review()` returns immediately without calling OpenAI. No `AiUsageLog` row. `Review.enrichment_status` stays `PENDING` indefinitely.
  - Reply generation: view returns `{"code": "ai_disabled", "detail": "AI features are not enabled for your organisation."}` with HTTP 403.
- **D-13:** The `ai_features_enabled` check happens in the **service layer**, not the view — `generate_reply_draft()` and `enrich_review()` both check the org flag at entry.

### Per-org daily token budget

- **D-14:** Add `daily_ai_token_budget = models.PositiveIntegerField(null=True, blank=True)` to `Organisation`. `null` = unlimited — there is **no platform-wide default**. New orgs are uncapped until a Superadmin explicitly sets a limit. This avoids surprising existing orgs on upgrade.
- **D-15:** Token counter key: `ai:tokens:org:{org_id}:{YYYY-MM-DD}` in Redis (TTL = 25 hours, rolls over naturally). Counter is incremented by `total_tokens` after each successful OpenAI call, inside `AiUsageLog` write.
- **D-16:** Budget enforcement: if `(existing_daily_count + estimated_prompt_tokens) > daily_ai_token_budget` → abort the call:
  - Enrichment: skip enrichment, set `enrichment_status=FAILED`, `error_code="budget_exceeded"`.
  - Reply generation: return `{"code": "budget_exceeded", "detail": "Daily AI usage limit reached for your organisation."}` with HTTP 429.
- **D-17:** Estimation uses prompt token count only (before the call). Actual total (including completion) is recorded post-call. Budget accounting is best-effort — over-counting is acceptable; under-counting is not. In practice, reply prompts are small and estimation is close.
- **D-18:** A new helper `check_and_reserve_ai_budget(organisation_id, estimated_tokens)` in `apps/integrations/openai/guardrails.py` centralises budget check + Redis increment. Returns `True` (OK) or raises `AiBudgetExceededError`.

### Moderation timing

- **D-19a:** Moderation runs **only at call time** — i.e., immediately before `call_openai_enrichment()` or `call_openai_reply_generation()`. It does **not** run during `fetch_and_persist_reviews()` (the Celery sync task). Reviews with harmful text are stored and displayed normally; they are simply not enriched and cannot generate AI replies.
- **D-19b:** No third-party guardrail library (Guardrails AI, NeMo Guardrails, Presidio, Azure Content Safety) is added. The OpenAI Moderation API covers the safety surface needed; additional libraries add dependency weight without proportionate benefit for single-turn review interactions.

### Guardrails module
- **D-19:** New file `apps/integrations/openai/guardrails.py` with three public functions:
  - `moderate_input(text: str) -> None` — raises `ContentModeratedException` if flagged
  - `moderate_output(text: str) -> str` — raises `ContentModeratedException` if flagged; returns text unchanged if clean
  - `check_and_reserve_ai_budget(organisation_id: int, estimated_tokens: int) -> None` — raises `AiBudgetExceededError` if over budget; increments Redis counter
- **D-20:** Call order in `generate_reply_draft()`:
  1. Check `org.ai_features_enabled` → 403 if False
  2. `moderate_input(review.text)` → 422 if flagged
  3. `check_and_reserve_ai_budget(org_id, estimated_tokens)` → 429 if over budget
  4. `call_openai_reply_generation(...)` → 502 on OpenAI failure
  5. `moderate_output(draft)` → 422 if flagged
  6. Truncate if > 300 words → return draft
- **D-21:** Call order in `enrich_review()`:
  1. Check `org.ai_features_enabled` → exit cleanly if False
  2. `moderate_input(review.text)` → set FAILED + return if flagged
  3. `check_and_reserve_ai_budget(org_id, estimated_tokens)` → set FAILED + return if over budget
  4. Existing OpenAI call + Pydantic parse
  5. (No moderation check on enrichment output — D-09)

### New exceptions
- **D-22:** `ContentModeratedException(Exception)` and `AiBudgetExceededError(Exception)` in `apps/integrations/openai/exceptions.py`. Views catch these and map to appropriate HTTP responses.

### Superadmin UI updates
- **D-23:** Add `ai_features_enabled` checkbox and `daily_ai_token_budget` number field to Create/Edit Org modals in Superadmin UI (same pattern as `allow_custom_sync_depth` from Phase 15).
- **D-24:** Org detail (view mode) shows: "AI Features: Enabled / Disabled" and "Daily Token Budget: Unlimited / {N} tokens/day".

### Mobile API impact
- **D-25:** `generate_reply` endpoint (Phase 19) accessible to JWT clients (already confirmed). Guardrails apply equally — same service function, same budget, same moderation checks.
- **D-26:** Enrichment is a background Celery task — no mobile-specific change needed. The org AI toggle and budget checks inside `enrich_review()` apply regardless of trigger.

### Observability
- **D-27:** Log every moderation flag at WARNING with `{event: "ai.moderation.flagged", entity_type, entity_id, stage: "input|output", categories: [...]}`. Never log the review text itself at WARNING or above (PII / content sensitivity — CLAUDE.md §22).
- **D-28:** `AiUsageLog.status` gains a new value `"moderated"` (alongside `"success"` and `"failed"`). When moderation fires before the OpenAI call, tokens = 0 and cost = 0.
- **D-29:** Budget exhaustion events are logged at WARNING: `{event: "ai.budget.exceeded", organisation_id, date, limit, current_count}`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend
- `apps/organisations/models.py` — `Organisation` model (add `ai_features_enabled`, `daily_ai_token_budget`)
- `apps/integrations/openai/client.py` — `call_openai_enrichment()`, `call_openai_reply_generation()` (add moderation calls around them)
- `apps/integrations/openai/exceptions.py` — add `ContentModeratedException`, `AiBudgetExceededError`
- `apps/reviews/services/enrichment.py` — `enrich_review()` (add guardrail call sequence)
- `apps/reviews/services/reply_generation.py` — `generate_reply_draft()` (add guardrail call sequence — Phase 19 file)
- `apps/reviews/views.py` — `ReviewViewSet.generate_reply` action (map new exceptions to HTTP responses)
- `apps/integrations/openai/models.py` — `AiUsageLog` (add `"moderated"` to status field if choices= is set)
- `config/settings/base.py` — no new settings; Redis already configured

### New file
- `apps/integrations/openai/guardrails.py` — `moderate_input()`, `moderate_output()`, `check_and_reserve_ai_budget()`

### Architecture constraints
- `CLAUDE.md` §5 — guardrail functions are service-layer utilities; never call Moderation API from views directly
- `CLAUDE.md` §14 — `AiUsageLog` must be written even when moderation fires (with `status="moderated"`, zero tokens)
- `CLAUDE.md` §16 — never hit real OpenAI Moderation API in tests; mock `moderate_input` and `moderate_output`
- `CLAUDE.md` §21 — never log review text at WARNING or above; log only category names when flagged
- `CLAUDE.md` §24 — order: model + migration → service/guardrails → view → serializer → frontend/Superadmin UI

</canonical_refs>

<code_context>
## Existing Code Insights

### OpenAI client pattern to follow
```python
# apps/integrations/openai/client.py — current pattern
def call_openai_enrichment(review, model):
    ...  # lazy singleton client, @traceable, exception mapping

# New: moderation call shape (no tracing needed — it's a safety check, not a billable generation)
def _call_moderation_api(text: str) -> openai.types.ModerationCreateResponse:
    client = _get_client()
    return client.moderations.create(input=text, model="omni-moderation-latest")
```

### AiUsageLog status field check
- Search for `status=` writes in `client.py` to determine if `status` is a free CharField or constrained — if constrained, add migration for new `"moderated"` value.

### Redis pattern for budget counter
```python
# apps/integrations/openai/guardrails.py
import redis
from django.conf import settings
from datetime import date

def _budget_key(org_id: int) -> str:
    return f"ai:tokens:org:{org_id}:{date.today().isoformat()}"

def check_and_reserve_ai_budget(organisation_id: int, estimated_tokens: int) -> None:
    # get org.daily_ai_token_budget
    # get current count from Redis
    # compare; if over budget raise AiBudgetExceededError
    # increment by estimated_tokens (INCRBY); set TTL if first write
```

### Organisation model import pattern
- `apps/organisations/models.py` — add fields alongside `allow_custom_sync_depth` (Phase 15 precedent)

</code_context>

<deferred>
## Deferred Ideas

- **Custom keyword blocklists per org** — org-specific forbidden terms (competitor names, sensitive topics) — requires a config UI and a separate filter layer
- **PII scrubbing of review text** — detect and mask emails/phone numbers in review text before sending to OpenAI — deferred because reviews are public GBP content
- **Factuality / groundedness check** — post-LLM fact-check against shop data — requires embedding similarity or a secondary LLM call; high cost, deferred
- **Per-user AI budgets** — finer-grained than per-org; requires extending AiUsageLog and budget counter by user
- **AI moderation admin dashboard** — Superadmin table of moderation events — deferred; logs are sufficient for now
- **Tone-specific guardrails** — different content policies for Professional vs Friendly tone — unnecessary complexity for two tones

</deferred>

---

*Phase: 20-ai-guardrails*
*Context gathered: 2026-05-21*
