---
phase: 20-ai-guardrails
verified: 2026-05-23T00:00:00Z
status: passed
score: 8/8 success criteria verified
overrides_applied: 0
---

# Phase 20: AI Guardrails — Verification Report

**Phase Goal:** Add input/output safety controls around all OpenAI calls — OpenAI Moderation API checks (category-aware blocking) and content length truncation. MVP scope: NO token budget, NO org AI toggle (deferred).

**Verified:** 2026-05-23
**Status:** passed
**Re-verification:** No — initial verification
**Test Surface:** 110 tests across `test_guardrails.py`, `test_enrichment_service.py`, `test_reply_generation_service.py`, `test_views.py`, `test_tasks.py` — **ALL PASSED** (`110 passed in 467.50s`)

---

## Goal Achievement — Per Success Criterion

### SC-1: Review text >4000 chars truncated with `…[truncated]` before any OpenAI call

| Layer | Evidence |
| ----- | -------- |
| Setting | `config/settings/base.py:160` — `OPENAI_REVIEW_TEXT_MAX_CHARS = env.int("OPENAI_REVIEW_TEXT_MAX_CHARS", default=4000)` |
| Env example | `.env.example:37` — `OPENAI_REVIEW_TEXT_MAX_CHARS=4000` |
| Implementation | `apps/integrations/openai/guardrails.py:91-99` — `_truncate_input` appends `…[truncated]` suffix when `len(text) > cap` |
| Wiring (enrichment) | `apps/reviews/services/enrichment.py:476-478` — `moderate_input(review.comment, …)` returns truncated text; line 485 flows truncated text into prompt |
| Wiring (reply gen) | `apps/reviews/services/reply_generation.py:118-123` — `truncated_comment = moderate_input(...)` then wrapped via `_ReviewWithModeratedComment` proxy at line 123 |
| Tests | `test_guardrails.py:70-87` (`TestTruncateInput.test_long_text_truncated_with_suffix`), `test_enrichment_service.py::TestEnrichReviewModeration` (input flow), `test_reply_generation_service.py::TestGenerateReplyDraftModeration` |

**Status:** ✓ VERIFIED

### SC-2: High-severity moderation blocks enrichment + sets `enrichment_status=FAILED` with `enrichment_error_code="content_moderated"`

| Layer | Evidence |
| ----- | -------- |
| Blocking set (underscore form) | `guardrails.py:65-73` — `BLOCKING_MODERATION_CATEGORIES = frozenset({"sexual_minors","hate_threatening","violence_graphic","self_harm_intent","self_harm_instructions"})` |
| Block raises exception | `guardrails.py:241-249` — when `blocked`, persists log then `raise ContentModeratedException("input flagged")` |
| Service catches + persists | `enrichment.py:479-481` — `except ContentModeratedException: _persist_moderated(review); return` |
| Persist logic | `enrichment.py:234-251` — `_persist_moderated` sets `enrichment_status = FAILED` and `enrichment_error_code = "content_moderated"` |
| Model field | `apps/reviews/models.py:81` — `enrichment_error_code = models.CharField(max_length=32, blank=True, default="")` |
| Migration | `apps/reviews/migrations/0010_add_enrichment_error_code.py` — adds field |
| Tests | `test_enrichment_service.py::TestEnrichReviewModeration` — confirms FAILED + error_code on blocked input |

**Status:** ✓ VERIFIED

### SC-3: Reply generation — input moderation, output moderation, >300 word sentence truncation with canonical suffix

| Layer | Evidence |
| ----- | -------- |
| Input moderation BEFORE OpenAI | `reply_generation.py:118-122` — `moderate_input(...)` called before `call_openai_reply_generation` |
| OpenAI call | `reply_generation.py:126-130` |
| Output moderation BEFORE returning draft | `reply_generation.py:167-172` — `moderate_output(draft, review=review, request_type="reply_generation", usage_data=usage_data)` |
| Sentence-boundary truncation @300 words | `guardrails.py:102-129` — `truncate_reply_at_sentence` splits on `[.!?]\s+`, accumulates sentences up to 300 words, suffix ` (Please review and complete before sending.)` |
| Truncation applied AFTER output moderation | `reply_generation.py:177` — `draft = truncate_reply_at_sentence(draft)` |
| Canonical suffix | `guardrails.py:78` — `_REPLY_SUFFIX = " (Please review and complete before sending.)"` |
| Tests | `test_guardrails.py:89-115` (`TestTruncateReplyAtSentence`), `test_reply_generation_service.py::TestGenerateReplyDraftModeration` |

**Status:** ✓ VERIFIED

### SC-4: `ContentModeratedException` → HTTP 422 with canonical body

| Layer | Evidence |
| ----- | -------- |
| Exception class | `apps/integrations/openai/exceptions.py:31-33` — `ContentModeratedException(OpenAIError)` |
| View imports | `apps/reviews/views.py:25` |
| View handler | `views.py:277-293` — catches `ContentModeratedException`, returns Response with `code: "content_moderated"`, exact detail string `"AI reply isn't available for this review. Please write your reply manually."`, status `HTTP_422_UNPROCESSABLE_ENTITY` |
| Catch ordering | `views.py:277` — Caught BEFORE `OpenAITransient/PermanentError` (most-specific first); comment at lines 278-282 documents this |
| Tests | `test_views.py::TestGenerateReplyEndpoint` — content_moderated cases assert 422 + body |

**Status:** ✓ VERIFIED

### SC-5: Moderation API outage — fail-open with one retry after 1s; ERROR log on second failure

| Layer | Evidence |
| ----- | -------- |
| Retry loop | `guardrails.py:150-175` — `_moderate_with_retry`: `for attempt in (1, 2)` |
| 1-second delay | `guardrails.py:166` — `time.sleep(1.0)` on first failure |
| Transient exception set | `guardrails.py:81-85` — `RateLimitError, APIStatusError, APIConnectionError` |
| Fail-open return | `guardrails.py:175` — `return False, []` (unblocked, no categories) |
| ERROR log | `guardrails.py:169-174` — `logger.error("ai.moderation.errored stage=%s entity_id=%s error=%s", ...)` |
| Tests | `test_guardrails.py:269-307` (`TestFailOpenRetry`): `test_fail_open_first_call_succeeds_no_retry`, `test_fail_open_first_call_fails_retry_succeeds`, `test_fail_open_both_calls_fail_returns_unblocked_and_logs_error` |

**Status:** ✓ VERIFIED

### SC-6: AiUsageLog rows for moderated events — input zero tokens; output real tokens + `error_code="output_moderated"`

| Layer | Evidence |
| ----- | -------- |
| Status enum | `apps/integrations/openai/models.py:56-59` — `MODERATED = "MODERATED", "Moderated"` |
| Migration | `apps/integrations/openai/migrations/0003_add_moderated_status_choice.py` |
| Input row — zero tokens | `guardrails.py:241-249` (input branch calls `_persist_moderated_log` with default `prompt_tokens=0, completion_tokens=0, cached_tokens=0, total_tokens=0`) |
| Input row — error_code | `guardrails.py:197` — `error_code = "content_moderated" if stage == "input" else "output_moderated"` |
| Output row — real tokens + cost | `guardrails.py:280-294` — pulls `prompt_tokens`, `completion_tokens`, `cached_tokens`, `total_tokens`, `estimated_cost_usd` from `usage_data` |
| Cost computed BEFORE moderate_output | `reply_generation.py:147-161` — `calculate_cost(...)` runs before `moderate_output`; `usage_data["estimated_cost_usd"] = cost` injected at line 161 |
| Tests | `test_guardrails.py:182-225` (input log w/ zero tokens, uppercase status), `test_guardrails.py:240-267` (`test_moderate_output_writes_aiusagelog_with_real_tokens`) |

**Status:** ✓ VERIFIED

### SC-7: `retry_failed_enrichments_task` excludes `enrichment_error_code="content_moderated"`

| Layer | Evidence |
| ----- | -------- |
| Implementation | `apps/reviews/tasks.py:233-242` — `.exclude(enrichment_error_code="content_moderated")` |
| Decision comment | `tasks.py:233` — `# D-25: skip content_moderated rows — reviewer text is immutable, retry is pure waste.` |
| Tests | `test_tasks.py` retry exclude moderated tests (passed) |

**Status:** ✓ VERIFIED

### SC-8: All moderation AiUsageLog writes OUTSIDE `transaction.atomic()`

| Layer | Evidence |
| ----- | -------- |
| Documented invariant | `guardrails.py:178-196` — `_persist_moderated_log` docstring: "NOT wrapped in a Django atomic block per D-33: if the caller is inside an atomic block that later rolls back, this audit row must still survive". Module docstring lines 35-36: "NEVER wrapped in a Django atomic block." |
| Enrichment call site | `enrichment.py:472-481` — `moderate_input` invoked AFTER the short status-transition `transaction.atomic()` block exits at line 449; the only atomic block that touches the row (lines 422-449) commits before moderation runs. `_persist_moderated` at line 234-251 is a single `review.save(update_fields=...)` with no atomic wrapper. |
| Reply generation call site | `reply_generation.py:118` (input) and 167 (output) — both calls at module scope; `generate_reply_draft` has no `transaction.atomic()` anywhere in the function body. Verified by reading lines 100-195. |
| No atomic in guardrails | `guardrails.py` — `grep transaction.atomic` returns no matches; `_persist_moderated_log` uses plain `AiUsageLog.objects.create(...)` at line 198-211 |

**Status:** ✓ VERIFIED

---

## Pitfall Regression Check

| Pitfall | Check | Result |
| ------- | ----- | ------ |
| **P1 (HIGH) — Underscore form** | `grep "sexual_minors" guardrails.py` → found at line 67; `grep "sexual/minors"` → ZERO matches. All 5 blocking categories present (lines 67-72) in underscore form. | ✓ PASS |
| **P2 — `MODERATED == "MODERATED"`** | `models.py:59` literal `"MODERATED"`; migration `0003` choice tuple `("MODERATED", "Moderated")` line 17. Test `test_moderate_input_aiusagelog_status_uppercase` (line 206) asserts uppercase. | ✓ PASS |
| **P3 (HIGH) — Moderation OUTSIDE atomic** | `enrichment.py`: moderate_input at line 476 sits AFTER the `transaction.atomic()` block at lines 422-449 closes; `_persist_moderated` (line 234-251) has no `atomic()` wrapper. `reply_generation.py`: `generate_reply_draft` (lines 100-195) contains zero `transaction.atomic()` blocks. `guardrails.py` contains zero `transaction.atomic()` blocks. | ✓ PASS |
| **P4 — Underscore-vs-slash comment** | `guardrails.py:61-64` — `# Underscore form matches Pydantic field names (default model_dump); slash form is the SDK JSON alias and only appears with model_dump(by_alias=True). Do NOT "fix" to slash form — see RESEARCH.md Pitfall 1 + D-30.` Test `test_blocking_categories_constant_underscore_form` (line 137) locks the set. | ✓ PASS |

All pitfalls explicitly defended in both code and tests. No regressions.

---

## Quality Gates

| Gate | Status | Evidence |
| ---- | ------ | -------- |
| All 8 SUMMARYs present | ✓ | `ls .planning/phases/20-ai-guardrails/20-0{1..8}-SUMMARY.md` returns 8 files |
| ROADMAP.md Phase 20 markable [x] | ✓ | All 8 success criteria verified; line 266 currently `0/8 | Not started` — ready to flip to `8/8 | Complete`. (Verifier does not modify ROADMAP; orchestrator does.) |
| Full Phase 20 test surface passes | ✓ | `pytest` on `test_guardrails.py`, `test_enrichment_service.py`, `test_reply_generation_service.py`, `test_views.py`, `test_tasks.py` → **110 passed in 467.50s** |
| No real OpenAI calls in tests | ✓ | `test_guardrails.py` uses `unittest.mock.patch("apps.integrations.openai.guardrails._get_client")` throughout. No `respx`/network calls. |

## CLAUDE.md Compliance

| Section | Requirement | Verdict |
| ------- | ----------- | ------- |
| §5 — service layer | guardrails functions live in `apps/integrations/openai/guardrails.py` (service layer); view (`views.py:277-293`) only catches exception and returns Response — no business logic. | ✓ |
| §14 — AiUsageLog for moderation | Input + output moderation paths each write one `AiUsageLog` row with correct `Status.MODERATED` enum (`guardrails.py:198-211`). | ✓ |
| §16 — no real OpenAI in tests | All guardrails tests mock `_get_client`; client calls patched. | ✓ |
| §21 — no review text in WARNING+ logs | `guardrails.py:234-240` and `271-278` log only `entity_id`, `categories`, `blocked` — never the review text. `ai.moderation.errored` (line 169-174) logs only `stage`, `entity_id`, `error`. | ✓ |
| §22 — 422 not 500 | `views.py:292` returns `HTTP_422_UNPROCESSABLE_ENTITY`. Catch ordering before generic exceptions ensures 422 wins over 502. | ✓ |

---

## D-ID Coverage (Action Decisions Only)

Decisions D-05, D-06, D-09, D-10, D-11, D-12, D-17, D-18, D-19, D-22, D-27 are non-action (documentation/no code change) — excluded.

Action decisions verified above:
- **D-03 / D-21** (truncation char cap + flow into prompt) → SC-1
- **D-04 / D-15 / D-23 / D-30 / D-31** (input block + categories + persist FAILED) → SC-2
- **D-07 / D-08** (output moderation + reply length cap) → SC-3
- **D-16 / D-26 / D-32** (HTTP 422 + canonical body + ContentModeratedException) → SC-4
- **D-24** (fail-open one retry + ERROR log) → SC-5
- **D-29 / D-33** (real tokens on output-moderated row; OUTSIDE atomic) → SC-6, SC-8
- **D-25** (retry excludes content_moderated) → SC-7
- **D-14** (moderated text flows into prompt, not persisted) → reply_generation.py:51-69 `_ReviewWithModeratedComment` proxy

All action D-IDs have a verifiable manifestation.

---

## Final Verdict

All 8 ROADMAP success criteria are observably true in the codebase, each backed by both implementation evidence and test evidence. The four critical pitfalls (underscore form, uppercase MODERATED, audit row outside atomic, decision comment) have explicit defences in code AND lockdown tests. The full 110-test surface passes. CLAUDE.md compliance is clean across §5, §14, §16, §21, §22.

No gaps. No regressions. No human verification items (all behaviours are mocked + asserted programmatically; no UI/visual surface in this phase).

## VERIFICATION PASSED
