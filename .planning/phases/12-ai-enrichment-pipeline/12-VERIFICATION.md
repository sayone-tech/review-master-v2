---
phase: 12-ai-enrichment-pipeline
verified: 2026-05-03T00:00:00Z
status: passed
score: 14/14 requirements verified (delta: 12-09 gap-closure verified)
re_verification:
  previous_status: passed
  previous_score: 14/14
  delta_plan: 12-09
  delta_truths_verified: 7/7
  gaps_closed:
    - "LangSmith trace metadata now includes organisation_id, review_id, shop_id, model, request_type (ENRCH-11)"
    - "REQUIREMENTS.md ENRCH-08/09/10 checked off and marked Complete in status table"
    - "Plan 12-09: comment-less reviews skip OpenAI; sentiment derived from star_rating; zero AiUsageLog cost"
  gaps_remaining: []
  regressions: []
---

# Phase 12: AI Enrichment Pipeline Verification Report

**Phase Goal:** Build the AI enrichment pipeline — every synced review gets enriched with GPT-4o-mini (sentiment, tags, action items), tracked with cost logging (AiUsageLog + AiPricing), and the frontend shows real-time enrichment progress with a two-stage sync indicator.
**Verified:** 2026-05-02 (initial), 2026-05-03 (delta — plan 12-09 gap closure)
**Status:** PASS
**Re-verification:** Yes — delta verification of plan 12-09 (commits include `49f41d9`)

---

## Summary Verdict: PASS — 14/14 requirements verified + plan 12-09 delta verified

Plans 12-01..12-08 were fully verified on 2026-05-02 (see report below). This update appends the **delta verification** of plan 12-09, which tightens ENRCH-02/ENRCH-03 by adding a skip path for comment-less reviews:

- **Old behavior:** Every fetched review (including rating-only reviews with empty `comment`) was sent to OpenAI, billed, and produced meaningless `neutral` sentiment + empty tags/action items.
- **New behavior:** Reviews with empty/whitespace-only `comment` short-circuit before the OpenAI call. Sentiment is derived locally from `star_rating` via `RATING_TO_SENTIMENT`. No `AiUsageLog` row is written → zero cost.
- This is a strict *improvement* — the original goal ("every fetched review is automatically enriched") is preserved; the contract narrows to "every fetched review **with a comment** is enriched by GPT-4o-mini; comment-less reviews are enriched locally with rating-derived sentiment and zero cost."

All 22 tests in `test_enrichment_service.py` pass. Guardrails confirmed unchanged: `tasks.py`, `client.py`, `sync.py`, OpenAI models, prompts.

---

## Plan 12-09 Delta — Observable Truths

| #   | Truth                                                                                       | Status     | Evidence                                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Empty-comment review skips OpenAI call entirely                                             | VERIFIED   | `enrichment.py:271-281` — guard `if not (review.comment or "").strip():` calls `_persist_success_no_comment` and returns BEFORE `call_openai_enrichment` block at `:284` |
| D2  | Whitespace-only comment treated identically to empty                                        | VERIFIED   | `(review.comment or "").strip()` evaluates falsy for `"   \n\t  "`; test `test_skip_openai_when_whitespace_comment` passes                            |
| D3  | Sentiment derived locally from star_rating per `RATING_TO_SENTIMENT` (1-2→neg, 3→neu, 4-5→pos) | VERIFIED   | `enrichment.py:50-56` defines literal mapping; `:59-66` exposes `rating_to_sentiment()` helper; parametrized test covers all 5 ratings              |
| D4  | Skip path writes SUCCESS, sentiment, tags=[], extracted_action_items=[], bumps enrichment_version | VERIFIED   | `enrichment.py:127-134` — `Review.objects.filter(pk=...).update(enrichment_status=SUCCESS, sentiment=..., tags=[], extracted_action_items=[], enrichment_version=F("enrichment_version") + 1)` |
| D5  | Skip path writes ZERO AiUsageLog rows                                                       | VERIFIED   | `_persist_success_no_comment` body (`:116-138`) contains no `AiUsageLog` reference; test `test_skip_path_does_not_write_ai_usage_log` asserts `count() == 0` |
| D6  | Idempotency preserved (Layer 3 status guard) — second call on SUCCESS row is a no-op       | VERIFIED   | Skip branch placed AFTER PENDING→IN_PROGRESS transition (`:267-269`); idempotent guard at `:257-266` re-handles SUCCESS; test asserts `enrichment_version == 1` after twice-called |
| D7  | Reviews WITH comments still hit OpenAI normally (regression guard)                          | VERIFIED   | `test_normal_path_still_calls_openai_for_reviews_with_comments` passes; `mock_call.assert_called_once()` holds                                       |

**Delta score:** 7/7 truths verified

---

## Plan 12-09 Delta — Required Artifacts

| Artifact                                            | Expected                                                                                            | Status   | Details                                                                                                                  |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| `apps/reviews/services/enrichment.py`               | Module-level `RATING_TO_SENTIMENT` dict, `rating_to_sentiment()` helper, `_persist_success_no_comment()`, skip-branch in `enrich_review` | VERIFIED | `:50-56` constant; `:59-66` helper; `:116-138` helper fn; `:271-281` skip branch                                          |
| `apps/reviews/tests/test_enrichment_service.py`     | Tests for skip path, rating mapping, idempotency, no-AiUsageLog, normal path regression           | VERIFIED | Lines 362-495 — six new tests + parametrized rating mapping; all pass (22 total tests in file)                          |

---

## Plan 12-09 Delta — Key Link Verification

| From                                                      | To                                       | Via                                          | Status   | Details                                                                       |
| --------------------------------------------------------- | ---------------------------------------- | -------------------------------------------- | -------- | ----------------------------------------------------------------------------- |
| `enrich_review` (after IN_PROGRESS save)                  | `_persist_success_no_comment`            | empty-comment guard branch                   | WIRED    | `enrichment.py:274-281` — branch invokes helper and `return`s                |
| `enrich_review` skip branch                               | NOT `call_openai_enrichment`             | `return` BEFORE OpenAI try block             | WIRED    | OpenAI call block starts at `:284`, skip `return` at `:281`                  |
| `_persist_success_no_comment`                             | `Review.objects.filter(...).update(...)` | inside `transaction.atomic()`                | WIRED    | `:127-134` with `F("enrichment_version") + 1`                                |
| `_persist_success_no_comment`                             | `_emit_enrichment_progress`              | AFTER atomic block                           | WIRED    | `:138` — same post-commit pattern as `_persist_success`                      |
| `_persist_success_no_comment`                             | NOT `AiUsageLog.objects.create`          | absence verified by grep + test             | WIRED    | grep on function body returns no match; test asserts `count() == 0`          |

---

## Plan 12-09 Delta — Guardrails (Out-of-Scope Discipline)

`git diff` for plan 12-09 commit shows ONLY two source files modified (plus SUMMARY/STATE/ROADMAP docs):

| File                                            | Status     | Verification                                                                                  |
| ----------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------- |
| `apps/reviews/tasks.py`                         | UNCHANGED  | Confirmed by `git diff` — last touch was 12-06                                                |
| `apps/integrations/openai/client.py`            | UNCHANGED  | Confirmed by `git diff` — last touch was 12-11 LangSmith metadata gap (commit a64d131)        |
| `apps/reviews/services/sync.py`                 | UNCHANGED  | Confirmed by `git diff` — last touch was 11-14                                                |
| `apps/integrations/openai/models.py` (AiUsageLog/AiPricing) | UNCHANGED  | No new migrations in this plan                                                       |
| `apps/integrations/openai/prompts.py`           | UNCHANGED  | Not in changed files list                                                                     |

No business logic moved into Celery wrapper. Three-layer idempotency (lock + atomic/select_for_update + status guard) preserved verbatim — skip path inserts AFTER the existing PENDING→IN_PROGRESS transition.

---

## Plan 12-09 Delta — Test Execution

```
docker compose -p review-master exec -T web python -m pytest apps/reviews/tests/test_enrichment_service.py -v
22 passed in 1.89s
```

Targeted gap-closure tests confirmed passing:
- `test_rating_to_sentiment_mapping[1-negative]` PASSED
- `test_rating_to_sentiment_mapping[2-negative]` PASSED
- `test_rating_to_sentiment_mapping[3-neutral]` PASSED
- `test_rating_to_sentiment_mapping[4-positive]` PASSED
- `test_rating_to_sentiment_mapping[5-positive]` PASSED
- `test_skip_openai_when_no_comment` PASSED
- `test_skip_openai_when_whitespace_comment` PASSED
- `test_skip_path_does_not_write_ai_usage_log` PASSED
- `test_skip_path_idempotent` PASSED
- `test_normal_path_still_calls_openai_for_reviews_with_comments` PASSED

Pre-existing flakiness in `test_consumers.py::test_disconnect_cleans_up_group` and `test_asgi.py::test_in_memory_channel_layer_in_tests` is documented as unrelated to 12-09 (failing before this plan; confirmed via revert + re-run during execution).

---

## Plan 12-09 Delta — Requirements Coverage

No new REQ-IDs claimed. 12-09 tightens behavior already covered by:
- **ENRCH-02** (idempotent enrichment with lock + status guard) — still complete; status guard now also covers the skip path's terminal SUCCESS row, so a re-fetched comment-less review is a no-op.
- **ENRCH-03** (sentiment/tags/action_items written to Review under atomic) — still complete; skip path writes the same fields under `transaction.atomic()`.

REQUIREMENTS.md still shows `[x] ENRCH-02`, `[x] ENRCH-03` and "Complete" in the status table (lines 80-81, 197-198). No traceability change required.

---

## Plan 12-09 Delta — Anti-Patterns Found

None. The skip helper:
- Uses `Review.objects.filter(pk=...).update(...)` (not `.save()`) for atomic single-row update — consistent with `_persist_success` pattern.
- Uses `F("enrichment_version") + 1` — race-free increment.
- Calls `_emit_enrichment_progress` AFTER the atomic block — same anti-pattern-avoidance pattern as `_persist_success`.
- Does NOT touch `AiUsageLog` — explicit and verified by grep.

---

# Original Verification Report (2026-05-02) — Plans 12-01..12-08

## Summary Verdict: PASS — 14/14 requirements verified

Both gaps from the initial verification have been resolved:

1. **ENRCH-11 resolved**: `_call_openai_with_tracing` now accepts `review_id`, `organisation_id`, `shop_id` as optional params and calls `run_tree.metadata.update({"request_type": "enrichment", "review_id": ..., "organisation_id": ..., "shop_id": ..., "model": ...})` at `client.py:137-145`. The call site in `call_openai_enrichment` passes `review.pk`, `review.organisation_id`, `review.shop_id`.
2. **ENRCH-08/09/10 doc gap resolved**: `.planning/REQUIREMENTS.md` lines 86-88 now show `[x]` for ENRCH-08/09/10, and lines 203-205 show "Complete" in the status table.

All 120 tests pass.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `call_openai_enrichment` exists with `@traceable` decorator | VERIFIED | `apps/integrations/openai/client.py:115` — `@traceable(run_type="llm", name="enrich_review")` |
| 2 | `enrich_review` has Redis lock + select_for_update + status flag | VERIFIED | `apps/reviews/services/enrichment.py:194-223` — `distributed_lock`, `select_for_update()`, status check for SUCCESS/IN_PROGRESS |
| 3 | `sync.py` enqueues `enrich_review_task.delay` after each page upsert | VERIFIED | `apps/reviews/services/sync.py:324-336` — local import + filter for PENDING + `enrich_review_task.delay(review_id)` per review |
| 4 | Status transitions PENDING→IN_PROGRESS→SUCCESS/FAILED under `transaction.atomic()` | VERIFIED | `enrichment.py:201-223` (PENDING→IN_PROGRESS), `:65-75` (→SUCCESS), `:103-124` (→FAILED) — all wrapped in `transaction.atomic()` |
| 5 | `enrich_review_task` has `autoretry_for=(OpenAITransientError, EnrichmentParseError)`; `OpenAIPermanentError` not in autoretry | VERIFIED | `tasks.py:91` — `autoretry_for=(OpenAITransientError, EnrichmentParseError)`; `OpenAIPermanentError` caught in service and returns silently |
| 6 | FAILED reviews appear in Reviews list; `enrichment_status` in serializer | VERIFIED | `serializers.py:36` — `enrichment_status` in fields list; `extracted_action_items` at line 39; no queryset filter on enrichment_status |
| 7 | `retry_failed_enrichments_task` + Beat seed migration every 6h on ai-enrichment | VERIFIED | `tasks.py:111-137`; `migrations/0005_...py:20-38` — `every=6, period="hours"`, `queue="ai-enrichment"` |
| 8 | `AiUsageLog.objects.create(...)` in both `_persist_success` and `_persist_failure` | VERIFIED | `enrichment.py:76` (`_persist_success`), `enrichment.py:109` (`_persist_failure`) |
| 9 | `calculate_cost()` formula uses the three price fields | VERIFIED | `pricing.py:33-37` — `non_cached_input * input_token_price_per_1m + cached * cached_token_price_per_1m + completion * output_token_price_per_1m` |
| 10 | `AiPricing` has `effective_from`/`effective_to` + `get_active()` | VERIFIED | `models.py:34-35` (fields), `models.py:19-26` (`get_active()` via `effective_to__isnull=True`) |
| 11 | Migration 0002 seeds gpt-4o-mini pricing | VERIFIED | `migrations/0002_seed_aiprice_gpt4o_mini.py` — seeds at $0.15/$0.60/$0.075 per 1M |
| 12 | LangSmith best-effort: OpenAI call proceeds if LangSmith fails | VERIFIED | `client.py:165-172` — `except Exception` catches LangSmith failures, falls back to `_do_responses_parse`, continues |
| 13 | LangSmith trace metadata includes all 5 required fields | VERIFIED | `client.py:137-145` — `run_tree.metadata.update({"request_type": "enrichment", "review_id": review_id, "organisation_id": organisation_id, "shop_id": shop_id, "model": model})` |
| 14 | REQUIREMENTS.md tracking updated for ENRCH-08/09/10 | VERIFIED | `.planning/REQUIREMENTS.md:86-88` show `[x]`; lines 203-205 show "Complete" |

**Score:** 14/14 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/integrations/openai/client.py` | ENRCH-01/11/12: call_openai_enrichment + @traceable + full metadata | VERIFIED | `_call_openai_with_tracing` accepts review_id, organisation_id, shop_id; metadata.update at line 137-145 |
| `apps/integrations/openai/models.py` | ENRCH-08/09/10: AiPricing + AiUsageLog | VERIFIED | Both models with all required fields |
| `apps/integrations/openai/pricing.py` | ENRCH-08: calculate_cost formula | VERIFIED | Correct three-component formula with quantize |
| `apps/reviews/services/enrichment.py` | ENRCH-02/03/04/05/07/12 | VERIFIED | Three-layer idempotency; both AiUsageLog writes |
| `apps/reviews/tasks.py` | ENRCH-04/06: enrich_review_task + retry task | VERIFIED | Correct autoretry_for; retry task re-enqueues FAILED |
| `apps/reviews/services/sync.py` | ENRCH-02 wiring: enqueue after upsert | VERIFIED | Lines 320-336; filters PENDING + calls .delay() |
| `apps/reviews/management/commands/enrich_existing_reviews.py` | ENRCH-13 | VERIFIED | Both --dry-run and --limit flags present |
| `apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py` | ENRCH-06 Beat seed | VERIFIED | every=6, period="hours", queue="ai-enrichment" |
| `apps/integrations/openai/migrations/0002_seed_aiprice_gpt4o_mini.py` | ENRCH-10 | VERIFIED | Seeds at published GPT-4o-mini rates |
| `frontend/src/widgets/review-management/ActionItemChip.tsx` | ENRCH-14 | VERIFIED | Renders amber Sparkles chip with count |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | ENRCH-14 | VERIFIED | Two progress bars; sync.enrichment.progress handler |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | ENRCH-14 | VERIFIED | "Analysing reviews with AI…" text; removes shop on sync.complete only |
| `apps/reviews/serializers.py` | ENRCH-05 | VERIFIED | enrichment_status + extracted_action_items in fields |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sync.py:_persist_page` | `enrich_review_task` | `.delay(review_id)` after upsert | WIRED | Lines 324-336; filters PENDING reviews; enqueues per-review |
| `enrich_review_task` | `enrichment.enrich_review` | service call | WIRED | `tasks.py:107` — `enrich_review(review_id=review_id)` |
| `enrich_review` | `call_openai_enrichment` | direct call | WIRED | `enrichment.py:227` |
| `call_openai_enrichment` | `_call_openai_with_tracing` | try block | WIRED | `client.py:158` — passes review_id, organisation_id, shop_id |
| `_call_openai_with_tracing` | `run_tree.metadata.update` | after get_current_run_tree() | WIRED | `client.py:134-145` — all 5 required fields updated |
| `_persist_success` | `AiUsageLog.objects.create` | in transaction | WIRED | `enrichment.py:76-89` |
| `_persist_failure` | `AiUsageLog.objects.create` | in transaction | WIRED | `enrichment.py:109-124` |
| `_persist_success` | `_emit_enrichment_progress` | after transaction | WIRED | `enrichment.py:92` — correctly AFTER `with transaction.atomic()` closes |
| `_emit_enrichment_progress` | `sync.complete` event | `emit_progress_event` when enriched >= fetched | WIRED | `enrichment.py:174-184` |
| `ProgressModal.tsx` | `sync.enrichment.progress` WS event | `ws.onmessage` handler | WIRED | `ProgressModal.tsx:82-92` |
| `TopbarSyncIndicator` | `sync.enrichment.progress` WS event | `ws.onmessage` stage update | WIRED | `TopbarSyncIndicator.tsx:71-79` |
| `retry_failed_enrichments_task` | Beat PeriodicTask (every 6h) | migration 0005 seed | WIRED | Migration seeds `queue="ai-enrichment"`, `every=6, period="hours"` |

---

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ENRCH-01 | VERIFIED | `client.py:141-187` — `call_openai_enrichment`; `@traceable` at line 115 |
| ENRCH-02 | VERIFIED | `enrichment.py:194-196` (lock); `sync.py:324-336` (inline enqueue); 12-09 skip path inherits same idempotency |
| ENRCH-03 | VERIFIED | `enrichment.py:201-223` (PENDING→IN_PROGRESS); `:65-75` (→SUCCESS); `:103-124` (→FAILED); 12-09 skip path also writes SUCCESS under atomic |
| ENRCH-04 | VERIFIED | `tasks.py:91` (`autoretry_for=(OpenAITransientError, EnrichmentParseError)`); `enrichment.py:231-233` (OpenAIPermanentError silent) |
| ENRCH-05 | VERIFIED | `serializers.py:36,39` — `enrichment_status` + `extracted_action_items` in fields; no queryset filter on status |
| ENRCH-06 | VERIFIED | `tasks.py:111-137`; `migrations/0005_...py` seeds Beat task |
| ENRCH-07 | VERIFIED | `enrichment.py:76` (success log), `enrichment.py:109` (failure log) — both with all token fields |
| ENRCH-08 | VERIFIED | `pricing.py:33-37` (formula); `REQUIREMENTS.md:86` now `[x]`, line 203 "Complete" |
| ENRCH-09 | VERIFIED | `AiUsageLog.estimated_cost_usd` never recomputed; `test_pricing.py:76-100` confirms immutability; `REQUIREMENTS.md:87` now `[x]`, line 204 "Complete" |
| ENRCH-10 | VERIFIED | `migrations/0002_seed_aiprice_gpt4o_mini.py`; `test_pricing.py:25-31` confirms seed values; `REQUIREMENTS.md:88` now `[x]`, line 205 "Complete" |
| ENRCH-11 | VERIFIED | `client.py:120-122` — signature accepts review_id, organisation_id, shop_id; `client.py:137-145` — `run_tree.metadata.update` with all 5 required fields; best-effort fallback at lines 146-147 |
| ENRCH-12 | VERIFIED | `client.py:133-137` (trace_id from `get_current_run_tree()`); `enrichment.py:87,120` (persisted on AiUsageLog) |
| ENRCH-13 | VERIFIED | `management/commands/enrich_existing_reviews.py` — `--dry-run` (line 35), `--limit` (line 43) |
| ENRCH-14 | VERIFIED | `ActionItemChip.tsx`, `ProgressModal.tsx` (two-stage bars + `sync.enrichment.progress`), `TopbarSyncIndicator.tsx` ("Analysing reviews with AI…"), `sync.complete` gated to enrichment completion |

---

## Test Suite

```
uv run pytest apps/integrations/openai/ apps/reviews/tests/ -q
120 passed, 33 warnings in 2.38s   (initial 2026-05-02)

docker compose -p review-master exec -T web python -m pytest apps/reviews/tests/test_enrichment_service.py -v
22 passed in 1.89s                  (delta 2026-05-03 — includes 6 new 12-09 tests)
```

All tests pass.

---

## Anti-Patterns Found

No blockers. No FIXME/TODO/placeholder stubs in the verified files. `_do_responses_parse` raises real exceptions (not stub responses). Both `AiUsageLog.objects.create` calls in `_persist_success` and `_persist_failure` are substantive with all required fields.

One warning-level observation (unchanged from initial verification): `get_active()` uses `effective_to__isnull=True` rather than the full `effective_from <= now AND (effective_to IS NULL OR effective_to > now)` predicate specified in ENRCH-08's description. Functionally equivalent for the designed management pattern (close old row, open new row with `effective_to=None`), but the implementation diverges from the spec text. Tests confirm correct behavior.

---

## Human Verification Required

The following items cannot be verified programmatically:

### 1. ProgressModal two-stage live behavior

**Test:** Connect a shop via OAuth, trigger initial backfill, watch the ProgressModal.
**Expected:** Yellow "Fetched from Google" bar fills first; then green "Processed with AI" bar fills; "Sync complete" banner appears only after both hit 100%.
**Why human:** Requires live WebSocket + running Celery worker with real enrichment flow.

### 2. TopbarBell enrichment stage text

**Test:** Trigger a sync and dismiss the ProgressModal via "Run in background".
**Expected:** Topbar bell row shows green Loader2 + "Analysing reviews with AI…" text during enrichment; shop removed from bell list only after `sync.complete`.
**Why human:** Requires live enrichment in progress.

### 3. ActionItemChip renders on review card

**Test:** Wait for enrichment to complete; navigate to /admin/org/reviews/.
**Expected:** Reviews with `extracted_action_items.length > 0` show amber Sparkles chips with count.
**Why human:** Requires enriched data in the database + rendered review list UI.

### 4. LangSmith trace entity metadata (now resolved in code)

**Test:** Set `LANGSMITH_API_KEY` + `LANGSMITH_PROJECT`; run enrichment on one review; check LangSmith dashboard.
**Expected:** Trace appears with `request_type="enrichment"`, `organisation_id`, `review_id`, `shop_id`, and `model` all present in trace metadata.
**Why human:** Requires live LangSmith API key and visual inspection of trace metadata. Code fix is verified; end-to-end LangSmith rendering requires live credentials.

### 5. (12-09) Live skip-path validation against a comment-less review

**Test:** Sync a shop that has at least one rating-only review (no comment). Inspect AiUsageLog after sync completes.
**Expected:** Comment-less review row in DB has `enrichment_status=SUCCESS`, sentiment derived from rating, tags=[], extracted_action_items=[]. NO AiUsageLog row exists for that review_id.
**Why human:** Requires real Google Business Profile data including a rating-only review.

---

_Verified: 2026-05-02 (initial + first re-verification, commit a64d131)_
_Re-verified: 2026-05-03 (delta verification of plan 12-09 gap closure, commit 49f41d9)_
_Verifier: Claude (gsd-verifier)_
