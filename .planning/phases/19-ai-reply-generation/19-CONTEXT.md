# Phase 19: AI Reply Generation - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Add an "Generate with AI" button to the existing `ReplyComposer` that calls GPT-4o-mini with the review context and a user-selected tone (Professional or Friendly), then fills the reply textarea with the generated draft. The user reviews and edits before submitting normally. This is a synchronous HTTP call (not Celery) — the user waits inline (≤3s expected). Generation goes through `AiUsageLog` for cost tracking.

**Out of scope:** Auto-submit without review, Empathetic/Formal tones, bulk generation, regenerate with different model, reply history/versioning.

</domain>

<decisions>
## Implementation Decisions

### Tones
- **D-01:** Two tones only — **Professional** and **Friendly**. No Empathetic or Formal variants in this phase.
- **D-02:** Professional default for all reviews. No automatic tone suggestion based on star rating (KISS).
- **D-03:** Tone is a UI-only concept — it drives which system prompt is used. The tone value is sent in the API request body (`tone: "professional" | "friendly"`) and is not persisted anywhere.

### Prompts (locked wording)
- **D-04:** Both prompts receive: brand name (= `Organisation.name`), shop name, star rating, review text.
- **D-05 — Professional prompt system instruction:** `"You are a professional customer experience representative replying to a Google Business review on behalf of {brand_name}. Write a formal, concise response that thanks the reviewer, acknowledges their experience, and invites them back. Under 150 words. No emojis. Do not invent facts."`
- **D-06 — Friendly prompt system instruction:** `"You are a warm, friendly team member replying to a Google Business review on behalf of {brand_name}. Write a conversational, personable response that thanks the reviewer, acknowledges their experience, and feels genuinely human. Under 150 words. One emoji maximum. Do not invent facts."`
- **D-07:** The generated reply is plain text (not JSON). Use `client.chat.completions.create(...)` with `response_format={"type": "text"}` — not structured output, since we just want a string back.
- **D-08:** `REPLY_GENERATION_PROMPT_VERSION = 1` constant in `apps/integrations/openai/prompts.py`. Bump it when prompts change (allows future `AiUsageLog` filtering by version).

### API
- **D-09:** New endpoint: `POST /api/v1/reviews/{id}/generate-reply/` on `ReviewViewSet` as a `@action(detail=True, methods=["post"])`.
- **D-10:** Request body: `{"tone": "professional"}` or `{"tone": "friendly"}`. Validated by a small `GenerateReplySerializer(tone = ChoiceField(choices=["professional","friendly"]))`.
- **D-11:** Response: `{"draft": "<generated text>"}` — 200 on success, 400 on invalid tone, 429 on rate limit, 502 on OpenAI failure.
- **D-12:** Throttle scope: `"generate_reply"` → `10/minute` per user (add to `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES` in settings). Uses the existing `ScopedRateThrottle` pattern already on `ReviewViewSet`.
- **D-13:** Permission: same as reply submission — Org Admin and Staff Admin (any user who can see the review). No new permission class needed.

### Backend service
- **D-14:** New function `generate_reply_draft(*, review: Review, tone: str) -> str` in `apps/reviews/services/reply_generation.py` (separate file from `replies.py` to keep it focused).
- **D-15:** The function calls a new `call_openai_reply_generation(review, tone, model)` in `apps/integrations/openai/client.py` — follows the same pattern as `call_openai_enrichment` (lazy singleton client, LangSmith `@traceable` best-effort, maps exceptions).
- **D-16:** Writes one `AiUsageLog` row per call — same fields as enrichment: `request_type="reply_generation"`, `model`, tokens, cost, `langsmith_trace_id`, `review_id`, `organisation_id`.
- **D-17:** Exception mapping: `OpenAITransientError` or network error → view returns 502 with `{"code": "ai_unavailable", "detail": "AI generation failed. Please try again or write your reply manually."}`. `OpenAIPermanentError` → same 502. No Celery retry — this is synchronous and the user can click Generate again.
- **D-18:** The view does NOT call `submit_reply()` — it only returns the draft. Submission is still the user's manual action.

### Frontend — `ReplyComposer.tsx`
- **D-19:** "Generate with AI" button appears in the same toolbar row as "Use template", to the left of it: `[Generate with AI ▾] [Use template ▾]`.
- **D-20:** Clicking "Generate with AI" when textarea IS empty: expands two inline tone pills `[Professional] [Friendly]` immediately below the label row. Clicking a pill triggers the API call (loading spinner on the pill, both pills disabled during load).
- **D-21:** Clicking "Generate with AI" when textarea IS NOT empty: shows an inline confirmation line `"Replace your draft with AI reply? [Professional] [Friendly] [Cancel]"` — the tone pills double as the confirm action. Cancel restores the normal state.
- **D-22:** On success: textarea fills with the generated draft, tone pills collapse, focus moves to textarea. User edits and submits normally.
- **D-23:** On API error: inline error message below textarea (same pattern as submit error). Pills collapse. User can click Generate again.
- **D-24:** New state variables in `ReplyComposer`: `generatorOpen: boolean`, `generatingTone: "professional" | "friendly" | null`.
- **D-25:** New API function `generateReply(reviewId: number, tone: string): Promise<{draft: string}>` in `api.ts`.

### Claude's Discretion
- Exact button/pill styling (follow existing `inputCls` / button patterns in `ReplyComposer.tsx`)
- Whether `generatorOpen` and `generatingTone` are combined into a single `generatorState` union type
- LangSmith trace metadata fields for reply generation (follow enrichment pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend
- `frontend/src/widgets/review-management/ReplyComposer.tsx` — add generator button, tone pills, overwrite guard, API call
- `frontend/src/widgets/review-management/api.ts` — add `generateReply()` function
- `apps/reviews/views.py` — `ReviewViewSet` (add `generate_reply` action)
- `apps/reviews/services/replies.py` — reference for existing reply service pattern; new file `reply_generation.py` follows same shape
- `apps/integrations/openai/client.py` — add `call_openai_reply_generation()` following `call_openai_enrichment()` pattern
- `apps/integrations/openai/prompts.py` — add `REPLY_GENERATION_PROMPT_VERSION` + `build_reply_generation_messages()`
- `apps/integrations/openai/models.py` — `AiUsageLog` (no change; new `request_type="reply_generation"` value added in migration or CharField without choices)
- `config/settings/base.py` — add `"generate_reply": "10/minute"` to `DEFAULT_THROTTLE_RATES`

### Architecture constraints
- `CLAUDE.md` §5 — `generate_reply_draft()` is a service function; view calls it, not inline logic
- `CLAUDE.md` §14 — all OpenAI calls must write `AiUsageLog`; LangSmith is best-effort
- `CLAUDE.md` §16 — never hit real OpenAI in tests; mock `call_openai_reply_generation`
- `CLAUDE.md` §24 — order: service → view → serializer → frontend
- `CLAUDE.md` §22 — throttle every new endpoint; use `ScopedRateThrottle` already on `ReviewViewSet`

</canonical_refs>

<code_context>
## Existing Code Insights

### Slot in ReplyComposer toolbar
- Toolbar row is: `<div className="flex items-center justify-between mb-2">` with label on left, "Use template" button on right
- "Generate with AI" button goes inside a new `<div className="flex items-center gap-2">` wrapping both buttons on the right — keeps layout consistent

### Throttle pattern (existing on ReviewViewSet)
```python
throttle_scope = "review_reply"  # already set
# New: inside generate_reply action, override to "generate_reply" scope
self.throttle_scope = "generate_reply"
```

### AiUsageLog request_type
- Existing value: `"enrichment"` — add `"reply_generation"` as a new valid value
- If `request_type` is a `CharField` without `choices=`, just start using the new string; if it has choices, add the new value in a migration

### call_openai_enrichment shape to mirror
- Takes `(review, model)` → returns `(EnrichmentResult, usage_data)`
- New function: `call_openai_reply_generation(review, tone, model)` → returns `(str, usage_data)`
- Same lazy singleton client, same exception mapping, same LangSmith `@traceable`

</code_context>

<deferred>
## Deferred Ideas

- **Empathetic / Formal tones** — add in a future iteration once Professional/Friendly are validated
- **Auto-suggest tone based on star rating** — Empathetic pre-selected for 1–2 stars
- **Regenerate** — re-generate with same or different tone (would need a "Regenerate" button alongside the filled textarea)
- **Reply quality score** — rate the generated draft before submitting
- **Brand voice customisation** — per-org prompt suffix / style guide injected into the system prompt

</deferred>

---

*Phase: 19-ai-reply-generation*
*Context gathered: 2026-05-18*
