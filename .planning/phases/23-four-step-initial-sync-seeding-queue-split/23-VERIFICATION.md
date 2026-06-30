---
phase: 23-four-step-initial-sync-seeding-queue-split
verified: 2026-06-11T10:00:00Z
status: human_needed
score: 18/18
overrides_applied: 0
human_verification:
  - test: "Trigger an initial sync for a store with more than 50 reviews (seed + bulk + finalising all occur) and watch the ProgressModal"
    expected: "All four steps visible from open (pending steps dimmed at opacity-60), active step shows live X/Y counts, bar colors are yellow (Fetching) → green (Building Tag Vocabulary) → green (AI Enrichment) → amber (Finalising), steps complete in order"
    why_human: "Visual/UX fidelity, step ordering under live event stream, and bar colors cannot be verified programmatically; the modal renders from WebSocket events that require a live backend + frontend stack"
  - test: "Watch the TopbarSyncIndicator sub-label as sync progresses through all four stages"
    expected: "Sub-label advances through 'Fetching reviews from Google…', 'Building tag vocabulary…', 'Analysing reviews with AI…', 'Finalising…' — spinner color changes from text-yellow to text-green to text-green to text-amber"
    why_human: "Requires a live sync stream; spinner color changes cannot be verified from static file inspection"
  - test: "Reload the browser mid-sync (while in the vocab or enriching stage) and reopen the ProgressModal"
    expected: "Modal repaints the correct current step from the reconnect snapshot — step discriminator and per-step counters restore the view at the correct position without waiting for the next event"
    why_human: "Reconnect repaint behavior requires a live WebSocket reconnect against a running backend; static test coverage (test_reconnect_snapshot_carries_4step_keys) only checks the snapshot payload shape, not the visual repaint fidelity"
---

# Phase 23: Four-Step Initial Sync, Seeding & Queue Split — Verification Report

**Phase Goal:** A store's initial sync visibly progresses through four named steps and seeds the org's canonical vocabulary in a careful sequential-then-parallel order, so the vocabulary is coherent from the first 50 reviews onward; daily incremental sync feeds new reviews through the same pipeline; and enrichment/merge work is isolated on dedicated Celery queues.
**Verified:** 2026-06-11
**Status:** human_needed — all automated truths VERIFIED; one deferred human visual gate (Plan 04 Task 3) open per user decision
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CELERY_QUEUE_NAMES lists exactly google-sync, ai-enrichment-high, ai-enrichment-low, tag-merge, default | VERIFIED | `config/settings/base.py:211-215` — exact list confirmed; no bare `"ai-enrichment"` remains |
| 2 | CELERY_TASK_ROUTES routes enrich_review_task and retry_failed_enrichments_task to ai-enrichment-low and finalize_canonical_tags_task to tag-merge | VERIFIED | `base.py:126-128` — all three routes present and correct |
| 3 | SEED_PHASE_SIZE (default 50) and OPENAI_GLOBAL_RATE_LIMIT (default 500) settings exist | VERIFIED | `base.py:196, 199` |
| 4 | A global Redis token bucket (rate:openai:org:{organisation_id}) gates OpenAI calls across all workers | VERIFIED | `progress.py:45` OPENAI_BUCKET_KEY_TMPL, `progress.py:225-250` increment + depleted functions; used in `enrichment.py:561-570` |
| 5 | _wait_for_openai_token helper lives in progress.py, blocks until headroom, never raises | VERIFIED | `progress.py:253` — bounded sleep-and-retry loop; test_rate_limit.py covers never-raises contract |
| 6 | Per-phase vocab and bulk enriched counters exist in Redis and are cleared on snapshot clear | VERIFIED | `progress.py:51-52, 285-313` VOCAB_COUNTER_KEY_TMPL, increment_vocab_counter, increment_bulk_counter; clear_progress_snapshot extended |
| 7 | The finalising pass merges case-insensitive duplicate OrgCanonicalTag rows; winner = higher review_count (tie → earliest created) | VERIFIED | `finalise.py:194-232` _merge_group with select_for_update, order_by("-review_count", "created_at"); test_finalise.py covers merge-winner, tie-break, transitive collapse |
| 8 | Loser's ReviewTag FK re-pointed in single UPDATE (no N+1), loser deleted | VERIFIED | `finalise.py:219-223` — `ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)` + loser.delete(); query-count ceiling test in test_finalise.py |
| 9 | Null canonical_tag stragglers backfilled by case-insensitive match; grouped by canonical_tag_id for bulk UPDATE (CR-03 fix) | VERIFIED | `finalise.py:260-274` — groups dict, `pk__in` UPDATE per canonical_id; no per-row UPDATE loop |
| 10 | After finalising pass, OrgCanonicalTag.review_count equals the ReviewTag aggregate count (never inline incremented) | VERIFIED | `finalise.py:285-315` _refresh_review_counts uses aggregate + bulk_update; test_finalise.py asserts stored == DB aggregate |
| 11 | Finalising pass emits sync.finalising.progress then sync.complete (both after atomic block commits) | VERIFIED | `finalise.py:122-162` — both emits after all mutations; sync.complete payload includes total_fetched/total_enriched/duration_seconds (CR-01 fix) |
| 12 | _dispatch_sync_complete_notifications called from finalise.py (CR-02 fix) | VERIFIED | `finalise.py:164-176` — called after sync.complete with shop_id, organisation_id, total_fetched; no longer orphaned |
| 13 | run_initial_backfill runs four phases: fetch → sequential seed loop → parallel bulk dispatch → finalising dispatch | VERIFIED | `sync.py:591-750` — four-phase structure with SEED_PHASE_SIZE, _wait_for_openai_token, apply_async(queue="ai-enrichment-high"), finalize_canonical_tags_task.apply_async(queue="tag-merge") |
| 14 | Seed loop processes newest N reviews sequentially, pre-acquiring token via _wait_for_openai_token before each enrich_review(skip_rate_limit_guard=True) | VERIFIED | `sync.py:663-686` — _wait_for_openai_token called per iteration, enrich_review called with skip_rate_limit_guard=True |
| 15 | Daily incremental sync dispatches enrichment to ai-enrichment-low | VERIFIED | `sync.py:453-454` — `apply_async(args=[review_id], queue="ai-enrichment-low")` in incremental path |
| 16 | enrich_review bulk path RAISEs on depleted bucket; seed path with skip_rate_limit_guard=True does NOT raise or increment | VERIFIED | `enrichment.py:555-570` — guard gated on `not skip_rate_limit_guard`; test_tasks.py covers both paths |
| 17 | sync.complete no longer fires from enrichment (D-02); finalising pass owns it | VERIFIED | `enrichment.py:429-432` — status always set to "enriching"; sync.complete emission removed; tests updated |
| 18 | ProgressModal renders four named steps with correct event handlers; TopbarSyncIndicator shows four-stage sub-labels (code + TypeScript) | VERIFIED | `ProgressModal.tsx:91,115,268,275,406,536` — sync.vocab.progress + sync.finalising.progress handlers, "Building Tag Vocabulary" and "Finalising" step labels; CR-04 error_at_step fix confirmed at line 22, 211-215; tsc --noEmit passes clean |

**Score:** 18/18 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/settings/base.py` | Queue split + SEED_PHASE_SIZE + OPENAI_GLOBAL_RATE_LIMIT | VERIFIED | Lines 124-215 — all three routes, full CELERY_QUEUE_NAMES list, both new settings |
| `apps/reviews/services/progress.py` | OpenAI token bucket + _wait_for_openai_token + vocab/bulk counters | VERIFIED | Lines 44-313 — all helpers present with keyword-only args |
| `apps/reviews/tests/test_settings.py` | Queue name/route + settings assertions | VERIFIED | File exists; test_settings.py + test_rate_limit.py pass (27 tests) |
| `apps/reviews/tests/test_rate_limit.py` | Token bucket acquire/deplete/expire + _wait_for_openai_token tests | VERIFIED | File exists; all tests pass |
| `apps/reviews/services/finalise.py` | run_finalise_canonical_tags(organisation_id, shop_id) | VERIFIED | Lines 47-192 — full implementation present |
| `apps/reviews/tasks.py` | finalize_canonical_tags_task thin wrapper | VERIFIED | Lines 245-294 — thin wrapper with retry_backoff=60, deferred import |
| `apps/reviews/selectors/canonical_tags.py` | get_duplicate_canonical_tag_groups + get_null_straggler_review_tags | VERIFIED | Lines 29-68 |
| `apps/reviews/tests/test_finalise.py` | Merge/backfill/count + query-count tests | VERIFIED | 26 tests pass |
| `apps/reviews/services/sync.py` | Four-phase run_initial_backfill + ai-enrichment-low incremental dispatch | VERIFIED | Lines 591-750 — full four-phase orchestrator |
| `apps/reviews/services/enrichment.py` | skip_rate_limit_guard + sync.complete decoupled | VERIFIED | Lines 446-570 |
| `apps/reviews/selectors/sync_progress.py` | get_progress_snapshot verbatim pass-through | VERIFIED | Lines 15-35 — no key filtering; docstring names 4-step fields |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | Four-step UI + new event handlers + extended SnapshotState | VERIFIED | Lines 22, 91, 115, 268, 275, 406, 536 |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | Four-stage sub-label + spinner color | VERIFIED | Lines 8, 85-94, 206-214 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `progress.py::_wait_for_openai_token` | Redis rate:openai:org bucket | increment_openai_token_bucket (INCR+EXPIRE) | VERIFIED | `progress.py:253-281` — bounded loop increments once and returns |
| `sync.py::run_initial_backfill seed loop` | `progress.py::_wait_for_openai_token` | pre-acquire token before each enrich_review | VERIFIED | `sync.py:669` — import at top, called per iteration |
| `enrichment.py::enrich_review` | `progress.py token bucket` | RAISE guard on depletion (bulk), skipped when seed pre-acquired | VERIFIED | `enrichment.py:555-570` |
| `sync.py::run_initial_backfill` | `tasks.py::finalize_canonical_tags_task` | `apply_async(queue='tag-merge', countdown=...)` | VERIFIED | `sync.py:740-745` |
| `tasks.py::finalize_canonical_tags_task` | `finalise.py::run_finalise_canonical_tags` | thin task wrapper via deferred import | VERIFIED | `tasks.py:263-294` |
| `finalise.py` | `ReviewTag.canonical_tag` | single update() FK re-point | VERIFIED | `finalise.py:219-223` `ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)` |
| `ProgressModal.tsx ws.onmessage` | `SnapshotState.step` | event-type switch updating step discriminator | VERIFIED | Lines 91-122 — sync.vocab.progress sets step:"vocab", sync.finalising.progress sets step:"finalising" |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `finalise.py::run_finalise_canonical_tags` | total_fetched / total_enriched | `read_progress_snapshot(shop_id=shop_id)` from Redis snapshot written by sync.py + enrichment.py | Yes — Redis snapshot populated by real sync counters | FLOWING |
| `ProgressModal.tsx` | vocab_enriched / vocab_total | WebSocket sync.vocab.progress event from sync.py seed loop | Yes — emitted per review in seed loop | FLOWING |
| `TopbarSyncIndicator.tsx` | stage | WebSocket sync.vocab.progress / sync.finalising.progress events | Yes — emitted from sync.py and finalise.py | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CELERY_QUEUE_NAMES exact list | `grep -n "CELERY_QUEUE_NAMES" config/settings/base.py` | Lines 211-215 — correct 5-element list | PASS |
| No bare ai-enrichment queue name | `grep -rn '"ai-enrichment"' config/settings/base.py` | No output | PASS |
| No enrich_review_task.delay calls | `grep -rn "enrich_review_task.delay" apps/reviews/` | No output | PASS |
| test_settings.py + test_rate_limit.py pass | pytest run | 27 passed | PASS |
| test_finalise.py passes | pytest run | 26 passed | PASS |
| Plan 03 test suites pass | pytest run (test_sync_service, test_tasks, test_consumers, test_progress_service) | 68 passed | PASS |
| TypeScript clean | `npx tsc --noEmit` | No errors | PASS |
| CR-01 payload fix (total_fetched in sync.complete) | `grep "total_fetched" apps/reviews/services/finalise.py` | Lines 127, 136, 156 | PASS |
| CR-02 notifications fix (_dispatch called from finalise) | `grep "_dispatch_sync_complete_notifications" apps/reviews/services/finalise.py` | Lines 168-176 | PASS |
| CR-03 N+1 fix (pk__in bulk UPDATE) | `grep "pk__in" apps/reviews/services/finalise.py` | Line 273 — `filter(pk__in=pk_list).update(...)` | PASS |
| CR-04 error_at_step fix in ProgressModal | `grep "error_at_step" frontend/src/widgets/review-management/ProgressModal.tsx` | Lines 22, 148, 215 | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SEED-01 | 23-03, 23-04 | Initial sync shows four steps with progress text per step | VERIFIED (code) / HUMAN NEEDED (visual) | Four-step modal implemented in ProgressModal.tsx; snapshot pass-through confirmed; visual gate open |
| SEED-02 | 23-03 | Seed phase processes newest N reviews sequentially, re-reads vocabulary before each | VERIFIED | `sync.py:636-686` — newest-first order, per-iteration _wait + enrich_review call |
| SEED-03 | 23-03 | Bulk phase enriches remaining reviews in parallel via ai-enrichment-high | VERIFIED | `sync.py:690-723` — apply_async(queue="ai-enrichment-high") per remaining review |
| SEED-04 | 23-02 | Finalising pass resolves duplicate tags and backfills stragglers | VERIFIED | `finalise.py` — case-insensitive dedup, single-UPDATE FK re-point, straggler backfill |
| DSYNC-01 | 23-03 | Daily incremental sync on ai-enrichment-low, auto-adds canonical tags | VERIFIED | `sync.py:453-454` — apply_async(queue="ai-enrichment-low"); no approval gate added |
| QUEUE-01 | 23-01 | ai-enrichment-high / ai-enrichment-low / tag-merge queue split | VERIFIED | `base.py:211-215, 124-128` — all three queues in CELERY_QUEUE_NAMES and CELERY_TASK_ROUTES |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TBD/FIXME/XXX markers, no placeholder return values, no stub implementations found in any files modified by this phase.

---

### Human Verification Required

Three items require live full-stack verification. These all stem from Plan 04 Task 3, which was explicitly deferred to phase-end human check per user decision (cannot be satisfied until backend Plans 01-03 are running end-to-end).

#### 1. Four-step ProgressModal visual fidelity

**Test:** Trigger an initial sync for a store with more than 50 reviews so seed + bulk + finalising all occur. Watch the ProgressModal.
**Expected:** All four steps visible from open (pending steps dimmed at opacity-60, counter shows "–"). Active step shows live X/Y counts. Bar colors: yellow (Fetching) → green (Building Tag Vocabulary) → green (AI Enrichment) → amber (Finalising). Steps complete in order.
**Why human:** Visual appearance, bar colors, opacity behavior, and step ordering under a live WebSocket event stream cannot be verified programmatically.

#### 2. TopbarSyncIndicator four-stage sub-label and spinner color

**Test:** Watch the TopbarSyncIndicator sub-label during the same sync as above.
**Expected:** Sub-label advances through "Fetching reviews from Google…" → "Building tag vocabulary…" → "Analysing reviews with AI…" → "Finalising…". Spinner colors advance from text-yellow to text-green to text-green to text-amber.
**Why human:** Spinner color fidelity and sub-label timing require a live event stream.

#### 3. Reconnect repaint restores correct step

**Test:** Reload the browser mid-sync (while in the vocab or enriching stage). Reopen the ProgressModal.
**Expected:** Modal repaints the correct current step from the reconnect snapshot — the `step` discriminator and per-step counters restore the view at the correct position without waiting for the next event.
**Why human:** Reconnect repaint behavior requires a live WebSocket reconnect against a running backend. The automated test `test_reconnect_snapshot_carries_4step_keys` covers snapshot payload shape but not visual repaint fidelity.

---

### Gaps Summary

No gaps. All 18 must-have truths are VERIFIED. The four code review critical issues (CR-01 through CR-04) are confirmed fixed in the codebase:

- **CR-01** (sync.complete missing total_fetched/total_enriched/duration_seconds): Fixed at `finalise.py:127-162`
- **CR-02** (orphaned _dispatch_sync_complete_notifications): Fixed at `finalise.py:164-176`
- **CR-03** (N+1 in _backfill_stragglers): Fixed at `finalise.py:260-274` — grouped bulk UPDATE via pk__in
- **CR-04** (error-state step rendering — all steps show "complete" on error): Fixed in `ProgressModal.tsx:22, 141-150, 211-215` with error_at_step field

The only open item is the Plan 04 Task 3 human-verify visual gate, deferred to phase-end per user decision. This is the only reason for `human_needed` status.

---

_Verified: 2026-06-11T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
