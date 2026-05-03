---
phase: 12-ai-enrichment-pipeline
plan: "09"
subsystem: reviews/enrichment
tags: [openai, cost-optimization, gap-closure, idempotency]
gap_closure: true
dependency_graph:
  requires:
    - 12-04  # enrich_review service (three-layer idempotency)
  provides:
    - rating_to_sentiment helper for comment-less review sentiment derivation
    - _persist_success_no_comment skip path that incurs zero OpenAI billing
  affects: []
tech_stack:
  added: []
  patterns:
    - Empty-comment short-circuit AFTER PENDING -> IN_PROGRESS transition (preserves Layer 3 idempotency)
    - Local sentiment derivation from star_rating bucket map
key_files:
  created: []
  modified:
    - apps/reviews/services/enrichment.py
    - apps/reviews/tests/test_enrichment_service.py
decisions:
  - Empty/whitespace-only comments use `(review.comment or "").strip() == ""` so both '' and '  \n\t' map to skip path
  - Skip branch placed AFTER PENDING -> IN_PROGRESS transition (not before lock acquisition) so concurrent re-entry cannot bypass Layer 3 status guard
  - RATING_TO_SENTIMENT exposed as module-level constant + helper function for direct unit testing
  - Skip path emits same sync.enrichment.progress event as OpenAI path so live ProgressModal is indistinguishable
  - enrichment_version bumped exactly once on skip path (matches normal SUCCESS semantics; downstream retry filter unaffected)
  - Historical comment-less reviews already marked SUCCESS are intentionally NOT re-processed (forward-only; out of scope per gap brief)
metrics:
  duration: 2 minutes
  completed_date: "2026-05-03"
  tasks_completed: 3
  files_changed: 2
requirements: [ENRCH-02, ENRCH-03]
---

# Phase 12 Plan 09: Skip OpenAI for Comment-less Reviews Summary

Forward-only gap closure: `enrich_review` now short-circuits when a review has no comment text, deriving sentiment locally from star rating and writing zero `AiUsageLog` rows.

## What Was Built

### Task 1: apps/reviews/services/enrichment.py

Three additions, no removals — the existing OpenAI path is unchanged.

**RATING_TO_SENTIMENT constant + `rating_to_sentiment()` helper** (module-level, lines ~50–66): explicit star-rating-to-sentiment bucketing.

| star_rating | sentiment |
|-------------|-----------|
| 1           | negative  |
| 2           | negative  |
| 3           | neutral   |
| 4           | positive  |
| 5           | positive  |
| (other)     | neutral (defensive fallback) |

**`_persist_success_no_comment(review)` helper** (lines ~116–138): mirror of `_persist_success` minus the OpenAI parts.

- Wraps a single `transaction.atomic()` that updates the Review row to `SUCCESS`, sets `sentiment` from the rating bucket, sets `tags=[]` and `extracted_action_items=[]`, and atomically increments `enrichment_version` via `models.F("enrichment_version") + 1`.
- Does **not** create an `AiUsageLog` row — this is the entire point of the gap closure: zero billable cost on rating-only reviews.
- Calls `_emit_enrichment_progress(review=review)` AFTER the transaction commits, so the live `ProgressModal` counter advances identically to a normal enrichment.

**Skip branch in `enrich_review`** (after PENDING → IN_PROGRESS transition, before the OpenAI try block):

```python
if not (review.comment or "").strip():
    logger.info("enrich_review_skip_no_comment review_id=%s star_rating=%s", review_id, review.star_rating)
    _persist_success_no_comment(review=review)
    return
```

The `(review.comment or "")` guard handles `None` defensively even though the model defines `comment = TextField(blank=True)`. The `.strip() == ""` test treats both `""` and whitespace-only inputs as "no comment".

### Why the skip branch is positioned AFTER the IN_PROGRESS transition

Placing the branch before the lock or before the row read would re-introduce a race: two concurrent calls could both observe `comment=""` and both run the skip path, double-bumping `enrichment_version`. By placing it **after** `select_for_update` has locked the row, the existing Layer 3 status guard (`if status in (SUCCESS, IN_PROGRESS): return`) protects the skip path identically to the OpenAI path. A second call on a comment-less SUCCESS review is a no-op; the test `test_skip_path_idempotent` proves `enrichment_version == 1` after two calls.

### Why no AiUsageLog row is written

The OpenAI billable surface is the API call itself. Skipping the call means there is no token usage, no latency, no trace to log. Writing a "zero-cost" log row would falsely inflate the per-organisation enrichment count and clutter the cost dashboard. The skip path is invisible to billing aggregations and visible only via the `enrich_review_skip_no_comment` log line.

### Task 2: apps/reviews/tests/test_enrichment_service.py

Six new tests appended to the existing 12-test file:

1. `test_rating_to_sentiment_mapping` — parametrized over all 5 star ratings; asserts both the helper return value and the constant mapping.
2. `test_skip_openai_when_no_comment` — `comment=""` + `star_rating=1` → `mock_call.assert_not_called()`, `sentiment=="negative"`, `tags==[]`, `extracted_action_items==[]`, `enrichment_version==1`, AiUsageLog count unchanged.
3. `test_skip_openai_when_whitespace_comment` — `comment="   \n\t  "` + `star_rating=3` → same assertions, `sentiment=="neutral"`.
4. `test_skip_path_does_not_write_ai_usage_log` — `AiUsageLog.objects.filter(review_id=...).count() == 0` after the skip.
5. `test_skip_path_idempotent` — calls `enrich_review` twice on the same comment-less review; second call is a no-op; `enrichment_version` stays at 1; AiUsageLog count stays at 0.
6. `test_normal_path_still_calls_openai_for_reviews_with_comments` — regression guard: review with `comment="Great service!"` triggers the OpenAI mock exactly once.

All six tests reuse the existing `_lock_acquired` helper and `ReviewFactory` from the test module — no new fixtures, no new patterns. The `no_progress_snapshot` autouse fixture (already present) suppresses Redis access in `_emit_enrichment_progress` so tests focus on DB state and AiUsageLog assertions.

### Task 3: Verification only

Ran the full regression slate:
- `ruff check` — passed for both modified files
- `ruff format --check` — both files already formatted
- `pytest apps/reviews/tests/test_enrichment_service.py` — 18 tests passed (12 prior + 6 new)
- `pytest apps/reviews/tests/test_tasks.py` — passed (Celery wrapper untouched)
- `pytest apps/reviews/tests/test_enrichment_progress.py` — passed (progress emission unchanged)
- `python manage.py check` — System check identified no issues (0 silenced).

Combined: **36 tests passed**, zero regressions.

## Key Design Decisions

### Forward-only — historical comment-less reviews are not re-processed

The plan's gap brief explicitly excludes re-processing existing reviews. Reviews that were already enriched (and billed) before this fix remain at their stored `sentiment` value (typically `neutral` from the prompt's default behaviour on empty input). Re-processing would require a data migration that bumps `enrichment_status=PENDING` for all comment-less SUCCESS reviews, plus a one-shot management command — both deliberately out of scope. The cost saving applies forward from this commit onward.

### Why the helper is named `_persist_success_no_comment` rather than `_persist_skip` or `_persist_local_sentiment`

The function's role mirrors `_persist_success` exactly — same DB shape, same post-commit progress emission — minus the OpenAI usage log row. The naming makes it grep-discoverable next to its sibling and signals "this is a SUCCESS persistence path" rather than "this is an alternate flow", which matches its semantic role downstream (Reviews list, retry filter, badge rendering all see it as a normal SUCCESS).

### Why both `""` and whitespace-only comments map to skip

Google Business Profile occasionally returns reviews with comments that are pure whitespace (a newline, a single space). These have the same LLM signal value as truly empty strings: zero. Sending them to OpenAI costs the same as sending real text but produces meaningless output. `.strip() == ""` is the cheapest correct test.

## Tests Written

6 new tests in `apps/reviews/tests/test_enrichment_service.py`:
- `test_rating_to_sentiment_mapping[1-negative]`, `[2-negative]`, `[3-neutral]`, `[4-positive]`, `[5-positive]`
- `test_skip_openai_when_no_comment`
- `test_skip_openai_when_whitespace_comment`
- `test_skip_path_does_not_write_ai_usage_log`
- `test_skip_path_idempotent`
- `test_normal_path_still_calls_openai_for_reviews_with_comments`

## Verification Results

- `pytest apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_tasks.py apps/reviews/tests/test_enrichment_progress.py -q` — **36 passed**
- `python manage.py check` — System check identified no issues
- `pre-commit` hooks (ruff, mypy, bandit, missing-migrations) — all green on both per-task commits

## Deviations from Plan

**1. [Rule 1 — Bug] Ruff PT006 violation in parametrize**
- **Found during:** Task 2 (running ruff after appending tests)
- **Issue:** `pytest.mark.parametrize` first argument as a comma-separated string `"rating,expected"` is flagged by ruff PT006; modern style requires a tuple `("rating", "expected")`.
- **Fix:** Converted to tuple form.
- **Files modified:** apps/reviews/tests/test_enrichment_service.py
- **Commit:** 292af7d (folded into Task 2)

No other deviations — plan executed exactly as written.

## Self-Check: PASSED

Files modified:
- `apps/reviews/services/enrichment.py` — FOUND
- `apps/reviews/tests/test_enrichment_service.py` — FOUND

Commits:
- `53c6450` — feat(12-09): skip OpenAI enrichment for comment-less reviews — FOUND
- `292af7d` — test(12-09): cover empty-comment skip path in enrich_review — FOUND
