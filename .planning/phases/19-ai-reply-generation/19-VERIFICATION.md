---
phase: 19-ai-reply-generation
verified: 2026-05-22T10:57:15Z
status: human_needed
score: 25/25 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Generate with AI button + tone pills end-to-end in browser"
    expected: "Per 19-03-PLAN Task 3 checkpoint: empty-textarea pill flow, non-empty overwrite confirmation, loading spinner, success fill + focus, error inline copy + focus, toggle close, Cancel restores focus on Generate button."
    why_human: "Visual layout, focus ordering, copy rendering and live OpenAI 502 path cannot be programmatically verified — checkpoint:human-verify task in Plan 19-03 was explicitly deferred to end-of-phase."
---

# Phase 19: AI Reply Generation — Verification Report

**Phase Goal:** Add an "Generate with AI" button to ReplyComposer that calls GPT-4o-mini with review context + selected tone (Professional / Friendly), fills the textarea with the generated draft, tracked via AiUsageLog. Synchronous HTTP, throttled, user reviews before submitting.

**Verified:** 2026-05-22T10:57:15Z
**Status:** human_needed (all automated must-haves pass; one deferred UI checkpoint remains)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (D-01 .. D-25)

| # | Decision | Truth | Status | Evidence |
|---|---|---|---|---|
| D-01 | Two tones only | Only "professional"/"friendly" accepted | VERIFIED | `_REPLY_PROMPTS_BY_TONE` in prompts.py:88; `TONE_CHOICES = ["professional", "friendly"]` in serializers.py:93; service `_ALLOWED_TONES` in reply_generation.py:35 |
| D-02 | No auto-suggest by rating | Both pills visually equal, no rating-based pre-selection | VERIFIED | ReplyComposer.tsx:334 maps `["professional","friendly"]` without inspecting `row.star_rating` |
| D-03 | Tone is UI-only, not persisted | Tone only sent in request body | VERIFIED | Request body validated by GenerateReplySerializer; tone not stored in any model |
| D-04 | Prompt receives brand/shop/rating/text | `build_reply_generation_messages` builds user payload | VERIFIED | prompts.py:117-122 — "Brand:", "Shop:", "Star rating:", "Review text:" |
| D-05 | Professional system prompt verbatim | Exact D-05 wording | VERIFIED | prompts.py:74-79 matches D-05 character-for-character |
| D-06 | Friendly system prompt verbatim | Exact D-06 wording | VERIFIED | prompts.py:81-86 matches D-06 character-for-character |
| D-07 | `chat.completions.create` with `response_format={"type":"text"}` | Plain-text (not structured) | VERIFIED | client.py:287-303 `_do_chat_completions_create` uses chat.completions.create with `response_format={"type":"text"}` |
| D-08 | REPLY_GENERATION_PROMPT_VERSION=1 | Module constant | VERIFIED | prompts.py:72 `REPLY_GENERATION_PROMPT_VERSION = 1` |
| D-09 | New endpoint POST /reviews/{id}/generate-reply/ as @action | DRF action on ReviewViewSet | VERIFIED | views.py:237-243 `@action(detail=True, methods=["post"], url_path="generate-reply")` |
| D-10 | Request body validated by GenerateReplySerializer | ChoiceField tone | VERIFIED | serializers.py:93 GenerateReplySerializer with tone ChoiceField |
| D-11 | Response shapes (200 draft, 400, 429, 502) | All status paths | VERIFIED | views.py:269-278 (502); 400 via serializer.is_valid(raise_exception=True); 200 with `{"draft": draft}` |
| D-12 | Throttle "generate_reply": 10/minute | Scoped throttle | VERIFIED | settings/base.py:333 `"generate_reply": "10/minute"`; views.py:251 `self.throttle_scope = "generate_reply"` |
| D-13 | Permission = existing review permission | No new permission class | VERIFIED | Action inherits ReviewViewSet permissions; Staff scope verified in test_staff_admin_inaccessible_shop_returns_404 |
| D-14 | generate_reply_draft in services/reply_generation.py | Service function | VERIFIED | reply_generation.py:61 `def generate_reply_draft(*, review, tone)` |
| D-15 | call_openai_reply_generation mirroring call_openai_enrichment | Client function | VERIFIED | client.py:354 `call_openai_reply_generation` with `@traceable` and lazy `_get_client()` |
| D-16 | Writes AiUsageLog with request_type="reply_generation" | Cost tracking | VERIFIED | reply_generation.py:92-105 success log; :41-56 failure log; both with `request_type="reply_generation"` |
| D-17 | All exceptions → 502 ai_unavailable; FAILED log written | Exception mapping | VERIFIED | views.py:258 catches `(OpenAITransientError, OpenAIPermanentError, Exception)` → 502; service `_write_failure_log` for transient/permanent/generic |
| D-18 | View does NOT auto-submit reply | Returns draft only | VERIFIED | views.py:278 returns `{"draft": draft}`; no call to `submit_reply()` |
| D-19 | Generate button to LEFT of Use template | Toolbar layout | VERIFIED | ReplyComposer.tsx:275-285 Generate button rendered before the pickerRef div inside `flex items-center gap-2` |
| D-20 | Empty textarea → tone pills inline | State logic | VERIFIED | ReplyComposer.tsx:323-371 pill row gated by `generatorOpen`; no confirmation span/cancel when `comment.trim()===""` |
| D-21 | Non-empty textarea → confirmation row | "Replace your draft..." | VERIFIED | ReplyComposer.tsx renders span "Replace your draft with AI reply?" + Cancel when `comment.trim() !== ""` |
| D-22 | Success: fill textarea, collapse pills, focus textarea | Success flow | VERIFIED | ReplyComposer.tsx:72-77 `setComment(draft); setGeneratorOpen(false); setGeneratingTone(null); document.getElementById('reply-textarea-${row.id}').focus()` |
| D-23 | Error: inline error message, pills collapse | Error flow | VERIFIED | ReplyComposer.tsx:78-86 catches error, sets errorMessage, collapses pills, focuses generator button. 429 mapped to rate-limit copy. |
| D-24 | generatorOpen, generatingTone state | New state vars | VERIFIED | ReplyComposer.tsx:30-31 |
| D-25 | generateReply(reviewId, tone) in api.ts | API client function | VERIFIED | api.ts:116 `export async function generateReply` POSTs to `/api/v1/reviews/{id}/generate-reply/` |

**Score:** 25/25 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| apps/integrations/openai/prompts.py | REPLY_GENERATION_PROMPT_VERSION + build_reply_generation_messages | VERIFIED | constant + function present, prompts verbatim |
| apps/integrations/openai/client.py | call_openai_reply_generation | VERIFIED | new function + private helpers (_call_openai_reply_with_tracing, _extract_reply_usage, _do_chat_completions_create) |
| apps/reviews/services/reply_generation.py | generate_reply_draft writes AiUsageLog | VERIFIED | file present, exception handling per D-17 |
| apps/reviews/serializers.py | GenerateReplySerializer | VERIFIED | tone ChoiceField restricted to two values |
| apps/reviews/views.py | generate_reply @action + select_related N+1 guard | VERIFIED | action wired with throttle scope + `select_related("shop__organisation")` in get_queryset |
| config/settings/base.py | "generate_reply": "10/minute" | VERIFIED | line 333 |
| frontend/src/widgets/review-management/api.ts | generateReply() | VERIFIED | exported, POSTs JSON body, uses CSRF helper |
| frontend/src/widgets/review-management/ReplyComposer.tsx | Generator button + pills + state | VERIFIED | imports Sparkles/Loader2/generateReply, full state machine, focus management |
| tests: test_prompts.py / TestCallOpenAiReplyGeneration / test_reply_generation_service.py / TestGenerateReplyEndpoint | 6 + 4 + 5 + 9 = 24 tests | VERIFIED | All 24 pass under `pytest` (see Behavioral Spot-Checks) |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| reply_generation.py | client.py | call_openai_reply_generation() | WIRED |
| reply_generation.py | AiUsageLog model | AiUsageLog.objects.create(request_type="reply_generation") | WIRED (both success and failure paths) |
| views.py | reply_generation.py | generate_reply_draft(review=, tone=) | WIRED (line 257) |
| views.py | serializers.py | GenerateReplySerializer(data=request.data) | WIRED (line 253) |
| ReplyComposer.tsx | api.ts | generateReply(row.id, tone) | WIRED (line 72) |
| api.ts | backend endpoint | POST /api/v1/reviews/{id}/generate-reply/ | WIRED (api.ts:116) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 19 backend test suite | `pytest apps/integrations/openai/tests/test_prompts.py apps/integrations/openai/tests/test_client.py::TestCallOpenAiReplyGeneration apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_views.py::TestGenerateReplyEndpoint -q` | 24 passed | PASS |
| Frontend type-check | `cd frontend && npx tsc --noEmit` | exit 0, no output | PASS |
| Prompt wording match D-05 | grep verbatim string in prompts.py | exact match | PASS |
| Prompt wording match D-06 | grep verbatim string in prompts.py | exact match | PASS |
| Throttle wiring | grep `"generate_reply": "10/minute"` in settings/base.py | line 333 | PASS |

### Anti-Patterns Found

None. Service uses a single `_write_failure_log` helper rather than inline duplication. Generic `except Exception` in views.py:258 is intentional per D-17 (uniform 502 mapping) and follows the same pattern flagged as `# noqa: BLE001` in the plan. No TBD/FIXME/XXX markers in any modified file. Stub-pattern scan (`return null`, hardcoded empty data) clean.

### Requirements Coverage

Plan frontmatter `requirements: []` for all three plans. No REQUIREMENTS.md IDs claimed; coverage is via the D-01..D-25 decisions in 19-CONTEXT.md, all verified above.

### Human Verification Required

The Plan 19-03 Task 3 checkpoint (`type="checkpoint:human-verify" gate="blocking"`) was deferred to end-of-phase per the scope note. It requires running the live stack (`make up`) and visually walking through:

1. Toolbar — "Generate with AI" appears LEFT of "Use template", with Sparkles icon.
2. Empty-textarea path — clicking Generate shows `[Professional] [Friendly]` pills (no pre-selection); clicking a pill shows spinner on that pill, other pill disabled; on 200 textarea fills, pills collapse, textarea has focus.
3. Overwrite path — typing text then Generate shows "Replace your draft with AI reply?" + pills + Cancel; Cancel collapses and returns focus to Generate.
4. Error path — temporarily removing OPENAI_API_KEY → click pill → inline red error "AI generation failed. Please try again or write your reply manually.", pills collapse, focus on Generate.
5. Toggle — clicking Generate twice opens then closes the pill row.

All underlying code paths are programmatically verified; what remains is visual/UX confirmation that cannot be auto-checked.

### Gaps Summary

No gaps. All 25 D-01..D-25 decisions are observably implemented in the codebase. All 24 backend tests pass; TypeScript compiles cleanly; prompt wording is verbatim; AiUsageLog writes wired on both success and failure paths; N+1 guard (`select_related("shop__organisation")`) present and protected by a query-count test (≤4 queries). The phase is functionally complete pending the deferred manual UI checkpoint.

---

*Verified: 2026-05-22T10:57:15Z*
*Verifier: Claude (gsd-verifier)*
