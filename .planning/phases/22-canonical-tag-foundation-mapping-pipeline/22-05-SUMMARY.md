---
phase: 22-canonical-tag-foundation-mapping-pipeline
plan: 05
status: complete
requirements: [CTAG-06, CTAG-07]
key-files:
  modified:
    - apps/reviews/services/enrichment.py
    - apps/reviews/tests/test_enrichment_service.py
---

# 22-05 — Canonical FK Fold-In (SUMMARY)

## What was built

Folded canonical lookup/insert + `ReviewTag.canonical_tag` population into the
existing `_persist_success` `transaction.atomic()` block — every enriched
review's tags now resolve to an `OrgCanonicalTag`, new labels are created, and
all of it shares the single existing write with exactly one `AiUsageLog` row.

### Task 1 — `_persist_success` extension (`apps/reviews/services/enrichment.py`)
Inside the existing atomic block, after the `ReviewTag` delete and before the
`ReviewTag.bulk_create`:
1. Collect distinct normalized canonical labels from `result.tags` (already
   Title-Cased by the 22-03 validator), remembering the proposed
   `polarity_type` for new labels (first proposal wins; `None` → `MIXED`).
2. **Batch SELECT** `OrgCanonicalTag.objects.filter(organisation_id=org_id, label__in=labels)`.
3. For missing labels, **`bulk_create(..., ignore_conflicts=True)`** — race-safe,
   does not abort the outer transaction (RESEARCH.md Pitfall 4 vs per-tag
   `get_or_create`).
4. **Re-SELECT** only the missing labels to fetch FKs (covers concurrent inserts).
5. `ReviewTag.bulk_create` now sets `canonical_tag=canonical_map[tag.canonical]`.

`org_id = review.organisation_id` reuses the `select_related` load — no extra
org query. `review_count` is **never** written (D-03 — derive-on-read). The
single `AiUsageLog.objects.create` is unchanged (CTAG-07). No new OpenAI call.
The fold-in adds exactly **3 fixed queries** (SELECT + bulk_create + re-SELECT)
regardless of tag count. `_persist_success_no_comment` untouched (no tags).

### Task 2 — tests (`apps/reviews/tests/test_enrichment_service.py`)
- `canonical_fk` — matched existing label reused (same pk, no duplicate); new
  label created exactly once, org-scoped, with GPT's `polarity_type`; each
  `ReviewTag.canonical_tag` resolves correctly.
- `canonical_usage_log` — exactly one `AiUsageLog` row (CTAG-07).
- `canonical_atomic_rollback` — patched `ReviewTag.objects.bulk_create` →
  `IntegrityError`; `pytest.raises`; fresh-queryset asserts Review ≠ SUCCESS and
  the new `OrgCanonicalTag` label count == 0 (rollback unwound the canonical inserts).
- `canonical_idempotent` — re-enrich (status reset to PENDING) creates no
  duplicate canonical rows (count stable at 2) and `review_count` stays `[0, 0]`.
- `canonical_query_count` — proves no-N+1 by asserting the query count is
  **identical for 2 vs 5 tags** and `<= 15`.

## Verification
- `pytest apps/reviews/tests/test_enrichment_service.py` — green (37 tests)
- `pytest apps/reviews apps/integrations/openai` — green (wave merge)
- `mypy apps/reviews/services/enrichment.py` — clean
- `grep review_count apps/reviews/services/enrichment.py` — only a comment, never written (D-03)

## Notes / deviations
- **Query-count ceiling is 15, not the plan's 12.** The plan's per-query budget
  omitted two fixed, tag-independent queries: `AiPricing.get_active()` inside
  `calculate_cost`, and the SAVEPOINT/RELEASE pairs that pytest-django's outer
  transaction turns each `atomic()` block into. The test now also asserts the
  count is *identical* across tag counts, which is the stronger no-N+1 guarantee
  the ceiling was standing in for. The fold-in itself adds exactly 3 queries.
- Executed inline by the orchestrator (Wave 3 single plan); no scope change.

## Self-Check: PASSED
