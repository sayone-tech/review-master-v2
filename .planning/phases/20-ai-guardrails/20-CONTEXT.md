# Phase 20: AI Guardrails - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>

## Phase Boundary

Add safety and control mechanisms around every OpenAI call in the platform — both the review enrichment pipeline and the reply-generation endpoint (Phase 19). Guardrails operate at two layers: **Input (pre-LLM)** intercepts content before it reaches OpenAI; **Output (post-LLM)** checks the model's response before it is persisted or returned to the user.

**Phase 20 MVP scope:** OpenAI Moderation API input/output checks + content length truncation. Token budget and org AI toggle are captured as decisions but **deferred to a future pricing phase** — the platform will onboard stores without usage caps first; caps will be introduced alongside a feature-based pricing plan (e.g. Plan A: 500 reviews, Plan B: higher limits).

**Out of scope:** Real-time content moderation in the UI, custom moderation model training, per-user AI budgets, keyword allowlists/blocklists as a config UI, groundedness/on-topic checks beyond prompt instruction, third-party guardrail libraries (Guardrails AI, NeMo Guardrails, Presidio), moderation during review sync, per-org token budget cap (deferred to pricing phase), org-level AI enable/disable toggle (deferred to pricing phase).

</domain>

<decisions>

## Implementation Decisions

### Moderation tool

- **D-01:** Use OpenAI's **Moderation API** (`omni-moderation-latest`) as the primary guardrail engine — it's free, returns structured category scores in <200ms, and reuses the existing OpenAI client. No third-party moderation vendor in this phase.
- **D-02:** The moderation check is **synchronous and blocking** — a flagged input aborts the OpenAI call; a flagged output is suppressed before the response reaches the caller. Both failures result in a structured error response.

### Input guardrails (pre-LLM)

- **D-03:** **Content length truncation** — review text is capped at **4 000 characters** before being inserted into any prompt. Truncation appends `…[truncated]`. This prevents context-window exhaustion and indirect prompt injection via extremely long reviews.
- **D-04:** **Moderation check on review text** — before calling `call_openai_enrichment()` or `call_openai_reply_generation()`, run `openai.moderations.create(input=review_text)`. If `results[0].flagged` is `True`, skip the OpenAI call:
  - Enrichment: set `Review.enrichment_status = FAILED` with `error_code="content_moderated"`. Write `AiUsageLog` with `status="moderated"`, zero tokens.
  - Reply generation: return `{"code": "content_moderated", "detail": "This review cannot be used for AI reply generation."}` with HTTP 422.
- **D-05:** **Prompt structure isolation** — the system prompt is always in the `system` role; review text is always in the `user` role (already the case). This structurally separates instruction from untrusted content, providing a hard boundary against direct prompt injection.
- **D-06:** No additional PII scrubbing of review text before sending — reviews are publicly visible content on Google Business Profile, so the original text is not considered private. The prompt itself never contains user credentials or org-internal data beyond brand/shop name.

### Output guardrails (post-LLM)

- **D-07:** **Moderation check on generated replies** — after `call_openai_reply_generation()` returns a draft, run the generated text through the Moderation API. If flagged: return `{"code": "output_moderated", "detail": "AI generation failed. Please write your reply manually."}` with HTTP 422. Do NOT return the flagged text.
- **D-08:** **Length enforcement on generated replies** — if the generated reply exceeds **300 words**, truncate at the last sentence boundary before the 300-word mark and append the text `" (Please review and complete before sending.)"`. Log at WARNING.
- **D-09:** **Enrichment structural validation** — Pydantic already validates enrichment output. No additional moderation check on enrichment output (tags and action item titles are low-risk structured data, not user-facing prose).
- **D-10:** **Groundedness / on-topic check** — not implemented. The prompt instruction "Do not invent facts" combined with the review text provided as context is the sole groundedness control. No post-LLM factuality or keyword-overlap check. Revisit after Phase 20 ships if real outputs reveal issues.

### Moderation timing

- **D-11:** Moderation runs **only at call time** — i.e., immediately before `call_openai_enrichment()` or `call_openai_reply_generation()`. It does **not** run during `fetch_and_persist_reviews()` (the Celery sync task). Reviews with harmful text are stored and displayed normally; they are simply not enriched and cannot generate AI replies.
- **D-12:** No third-party guardrail library (Guardrails AI, NeMo Guardrails, Presidio, Azure Content Safety) is added. The OpenAI Moderation API covers the safety surface needed; additional libraries add dependency weight without proportionate benefit for single-turn review interactions.

### Guardrails module

- **D-13:** New file `apps/integrations/openai/guardrails.py` with two public functions:
  - `moderate_input(text: str) -> None` — raises `ContentModeratedException` if flagged
  - `moderate_output(text: str) -> str` — raises `ContentModeratedException` if flagged; returns text unchanged if clean
- **D-14:** Call order in `generate_reply_draft()`:
  1. `moderate_input(review.text)` → 422 if flagged
  2. `call_openai_reply_generation(...)` → 502 on OpenAI failure
  3. `moderate_output(draft)` → 422 if flagged
  4. Truncate if > 300 words → return draft
- **D-15:** Call order in `enrich_review()`:
  1. `moderate_input(review.text)` → set FAILED + return if flagged
  2. Existing OpenAI call + Pydantic parse
  3. (No moderation check on enrichment output — D-09)

### New exceptions

- **D-16:** `ContentModeratedException(Exception)` in `apps/integrations/openai/exceptions.py`. Views catch it and map to HTTP 422 with a user-facing message.

### Mobile API impact

- **D-17:** `generate_reply` endpoint (Phase 19) accessible to JWT clients (already confirmed). Moderation guardrails apply equally — same service function, same checks.
- **D-18:** Enrichment is a background Celery task — no mobile-specific change needed.

### Observability

- **D-19:** Log every moderation flag at WARNING with `{event: "ai.moderation.flagged", entity_type, entity_id, stage: "input|output", categories: [...]}`. Never log the review text itself at WARNING or above (CLAUDE.md §22).
- **D-20:** `AiUsageLog.status` gains a new value `"moderated"` (alongside `"success"` and `"failed"`). When moderation fires before the OpenAI call, tokens = 0 and cost = 0.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend

- `apps/integrations/openai/client.py` — `call_openai_enrichment()`, `call_openai_reply_generation()` (moderation calls wrap these)
- `apps/integrations/openai/exceptions.py` — add `ContentModeratedException`
- `apps/reviews/services/enrichment.py` — `enrich_review()` (add moderation call sequence)
- `apps/reviews/services/reply_generation.py` — `generate_reply_draft()` (add moderation call sequence — Phase 19 file)
- `apps/reviews/views.py` — `ReviewViewSet.generate_reply` action (map `ContentModeratedException` to HTTP 422)
- `apps/integrations/openai/models.py` — `AiUsageLog` (add `"moderated"` to status field if choices= is set)
- `config/settings/base.py` — no new settings; Redis and OpenAI client already configured

### New file

- `apps/integrations/openai/guardrails.py` — `moderate_input()`, `moderate_output()`

### Architecture constraints

- `CLAUDE.md` §5 — guardrail functions are service-layer utilities; never call Moderation API from views directly
- `CLAUDE.md` §14 — `AiUsageLog` must be written even when moderation fires (with `status="moderated"`, zero tokens)
- `CLAUDE.md` §16 — never hit real OpenAI Moderation API in tests; mock `moderate_input` and `moderate_output`
- `CLAUDE.md` §21 — never log review text at WARNING or above; log only flagged category names
- `CLAUDE.md` §24 — order: guardrails module → service updates → view exception mapping → tests

</canonical_refs>

<code_context>

## Existing Code Insights

### OpenAI client pattern to follow

```python
# apps/integrations/openai/client.py — current pattern
def call_openai_enrichment(review, model):
    ...  # lazy singleton client, @traceable, exception mapping

# New: moderation call shape (no tracing — safety check, not a billable generation)
def _call_moderation_api(text: str) -> openai.types.ModerationCreateResponse:
    client = _get_client()
    return client.moderations.create(input=text, model="omni-moderation-latest")
```

### AiUsageLog status field check

- Search for `status=` writes in `client.py` to determine if `status` is a free CharField or has `choices=`. If constrained, add a migration for the new `"moderated"` value.

### Organisation model

- No new fields on `Organisation` in Phase 20 MVP — budget + toggle deferred to pricing phase.

</code_context>

<deferred>

## Deferred Ideas

- **Per-org daily token budget + org AI enable/disable toggle** — deferred to a future pricing phase. Plan: onboard ~500 stores first, then introduce feature-based pricing plans (e.g. Plan A: 500 reviews/month synced, Plan B: higher limits). At that point, `Organisation.daily_ai_token_budget` (PositiveIntegerField, null=unlimited) and `Organisation.ai_features_enabled` (BooleanField) will be added as Superadmin-controlled fields, with a Redis counter `ai:tokens:org:{id}:{date}` tracking daily usage.
- **Custom keyword blocklists per org** — org-specific forbidden terms — requires config UI and a separate filter layer
- **PII scrubbing of review text** — reviews are public GBP content; deferred unless private channels are added
- **Factuality / groundedness check** — post-LLM fact-check against shop data — high cost, own phase
- **Per-user AI budgets** — finer-grained than per-org; extends AiUsageLog and budget counter by user
- **AI moderation admin dashboard** — Superadmin table of moderation events — application logs are sufficient for now
- **Tone-specific guardrails** — different content policies per tone — unnecessary complexity for two tones

</deferred>

---

*Phase: 20-ai-guardrails*
*Context gathered: 2026-05-21*
