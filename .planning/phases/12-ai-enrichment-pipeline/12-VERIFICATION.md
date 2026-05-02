---
phase: 12-ai-enrichment-pipeline
verified: 2026-05-02T00:00:00Z
status: passed
score: 14/14 requirements verified
re_verification:
  previous_status: gaps_found
  previous_score: 12/14
  gaps_closed:
    - "LangSmith trace metadata now includes organisation_id, review_id, shop_id, model, request_type (ENRCH-11)"
    - "REQUIREMENTS.md ENRCH-08/09/10 checked off and marked Complete in status table"
  gaps_remaining: []
  regressions: []
---

# Phase 12: AI Enrichment Pipeline Verification Report

**Phase Goal:** Build the AI enrichment pipeline — every synced review gets enriched with GPT-4o-mini (sentiment, tags, action items), tracked with cost logging (AiUsageLog + AiPricing), and the frontend shows real-time enrichment progress with a two-stage sync indicator.
**Verified:** 2026-05-02
**Status:** PASS
**Re-verification:** Yes — after gap closure (commit a64d131)

---

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
| ENRCH-02 | VERIFIED | `enrichment.py:194-196` (lock); `sync.py:324-336` (inline enqueue) |
| ENRCH-03 | VERIFIED | `enrichment.py:201-223` (PENDING→IN_PROGRESS); `:65-75` (→SUCCESS); `:103-124` (→FAILED) |
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
120 passed, 33 warnings in 2.38s
```

All 120 tests pass.

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

---

_Verified: 2026-05-02 (re-verification after gap closure commit a64d131)_
_Verifier: Claude (gsd-verifier)_
