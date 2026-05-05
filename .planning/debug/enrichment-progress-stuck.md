---
status: awaiting_human_verify
trigger: "Progress modal shows '101 of 109' enriched even though all 109 reviews are in the DB with SUCCESS status. The sync.complete WebSocket event is never fired, leaving the UI spinner running forever."
created: 2026-05-05T00:00:00Z
updated: 2026-05-05T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED. Two separate bugs found:
  BUG 1 (primary): enrich_review() in enrichment.py lines 329-338 returns early (idempotency guard) for reviews already SUCCESS/IN_PROGRESS, WITHOUT calling _emit_enrichment_progress. The counter never increments for those reviews.
  BUG 2 (secondary): sync.py lines 421-434 overwrites the progress snapshot with status="success" and enriched=0 IMMEDIATELY after the fetch loop ends, before enrichment tasks finish. This corrupts the fetched value used by _emit_enrichment_progress._
test: confirmed by reading all three files fully
expecting: fix must call _emit_enrichment_progress in the idempotent-skip return path too
next_action: Apply fix to enrichment.py — call _emit_enrichment_progress after the early return for SUCCESS reviews; do NOT emit for IN_PROGRESS (another worker is handling it)

## Symptoms

expected: After all reviews are enriched, progress shows "109 of 109" and sync.complete event fires, closing/completing the modal.
actual: Progress stuck at "101 of 109". DB has all 109 reviews with enrichment_status=SUCCESS. The Redis enriched counter stopped at 101. sync.complete never fires.
errors: No errors, just silent incomplete counter.
reproduction: Run a full initial sync for a shop that has some previously-enriched reviews (mixed PENDING + already-SUCCESS reviews in the batch).
started: After the enrichment race condition fix that introduced the Redis atomic INCR counter (increment_enriched_counter in apps/reviews/services/progress.py).

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-05-05T00:01:00Z
  checked: apps/reviews/services/enrichment.py lines 329-338
  found: enrich_review() has an early return inside transaction.atomic() when enrichment_status is SUCCESS or IN_PROGRESS. The return statement exits the entire function without calling _emit_enrichment_progress.
  implication: Reviews that were already SUCCESS before the sync (pre-enriched reviews) never increment the Redis enriched counter, causing a permanent mismatch.

- timestamp: 2026-05-05T00:01:00Z
  checked: apps/reviews/services/sync.py lines 374-386 (fetch loop) vs lines 421-434 (end of fetch loop)
  found: The fetch loop at lines 374-386 only enqueues reviews with enrichment_status=PENDING via enrich_review_task.delay(). Already-SUCCESS reviews are NOT enqueued. The final snapshot written at lines 421-434 sets fetched=total_persisted (ALL 109 reviews from Google) but enriched=0.
  implication: The progress snapshot's fetched=109 represents all Google-fetched reviews, but only 101 PENDING reviews will ever call _emit_enrichment_progress. The counter can never reach 109 because the 8 pre-enriched SUCCESS reviews were never enqueued and their idempotent skip path never calls _emit_enrichment_progress.

- timestamp: 2026-05-05T00:01:00Z
  checked: apps/reviews/services/sync.py lines 421-434 (success_payload write after fetch loop)
  found: After the fetch loop completes, sync.py writes a snapshot with status="success" and enriched=0. This overwrites the in-progress enriching snapshot. Subsequent _emit_enrichment_progress calls from concurrent enrichment tasks will read fetched from this snapshot (which correctly has fetched=109) but the status="success" written here is premature — enrichment tasks are still running.
  implication: Secondary issue: the snapshot status is set to "success" before enrichment finishes, but _emit_enrichment_progress overwrites it back to "enriching" or "success" based on enriched >= fetched. The fetched=109 value survives correctly. The primary bug is the missing counter increment for pre-enriched reviews.

- timestamp: 2026-05-05T00:01:00Z
  checked: apps/reviews/services/progress.py — increment_enriched_counter and ENRICHED_COUNTER_KEY_TMPL
  found: The Redis enriched counter is a separate key (sync:enriched:{shop_id}), incremented atomically. clear_progress_snapshot deletes both keys. The counter starts at 0 on every fresh sync. This confirms that pre-enriched SUCCESS reviews will not increment the counter (since they are never enqueued and the idempotent skip returns without calling _emit_enrichment_progress).
  implication: With 109 total reviews, 8 pre-enriched SUCCESS, only 101 PENDING enqueued: counter maxes at 101. fetched=109 in snapshot. enriched(101) < fetched(109) so sync.complete never fires.

## Resolution

root_cause: enrich_review() in apps/reviews/services/enrichment.py returned early (idempotency guard) for reviews with enrichment_status=SUCCESS without calling _emit_enrichment_progress. When a shop had pre-enriched reviews (already SUCCESS before the sync), those reviews were never enqueued for enrichment again (sync.py correctly only enqueues PENDING reviews), but the progress snapshot's fetched count included ALL Google-fetched reviews (109). The Redis enriched counter only advanced for the 101 PENDING reviews that ran through _emit_enrichment_progress, leaving a permanent mismatch (enriched=101, fetched=109) and sync.complete never firing.
fix: Split the combined SUCCESS/IN_PROGRESS early-return into two separate checks in enrich_review(). IN_PROGRESS returns immediately as before (another worker owns that review and will emit on completion). SUCCESS sets a flag _already_success, exits the transaction block cleanly, then calls _emit_enrichment_progress AFTER the transaction closes (respecting the no-events-inside-transactions constraint). This advances the counter for pre-enriched reviews so enriched reaches fetched and sync.complete fires.
verification: All 24 enrichment service tests pass. All 4 enrichment progress tests pass. All 9 progress service tests pass. Two new regression tests added: test_idempotent_success_skip_still_emits_progress and test_in_progress_skip_does_not_emit_progress — both pass.
files_changed:
  - apps/reviews/services/enrichment.py
  - apps/reviews/tests/test_enrichment_service.py
