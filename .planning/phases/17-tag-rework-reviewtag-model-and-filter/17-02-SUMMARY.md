---
phase: 17-tag-rework-reviewtag-model-and-filter
plan: 02
status: complete
requirements:
  - TAG-02
key_files:
  modified:
    - apps/reviews/services/enrichment.py
    - apps/reviews/serializers.py
    - apps/reviews/selectors/reviews.py
    - apps/reviews/tests/test_enrichment_service.py
    - apps/reviews/tests/test_views.py
---

# Plan 17-02 Summary — Enrichment Write Path + Read Serializer

## What was built

Switched the enrichment write path off the legacy `Review.tags` JSONField (dropped in 17-01) and onto the new `ReviewTag` relational model. Updated the read serializer to nest an explicit `ReviewTagSerializer` and added `prefetch_related("tags")` on the base reviews queryset so the list endpoint stays within the REVW-14 query ceiling.

## Commits

- `242fe6d` feat(17-02): write ReviewTag rows from enrichment service
- `3750f47` feat(17-02): nest ReviewTagSerializer on review read + prefetch tags

## Task 1 — Enrichment service

- `_persist_success`: removed `tags=` from `Review.objects.filter(...).update(...)`. Inside the existing `transaction.atomic()`, deletes prior `ReviewTag` rows for the review then `ReviewTag.objects.bulk_create` of `[ReviewTag(review=review, label=tag.label.title(), polarity=tag.polarity) for tag in parsed.tags]`. Title-casing the label is performed at write time so the filter API can do case-sensitive equality.
- `_persist_success_no_comment`: removed `tags=` from the `.update(...)` and added a `ReviewTag.objects.filter(review=review).delete()` so comment-less re-enrichment clears any stale tags.
- Re-enrichment idempotency: the delete-then-bulk_create pattern means running the task twice on the same review produces the same final ReviewTag set.

## Task 2 — Serializer + queryset

- Added a plain `ReviewTagSerializer(serializers.Serializer)` returning `{label, polarity}` — preserves the exact JSON shape the frontend already consumes (no shape change for clients).
- `ReviewReadSerializer.tags` now declares `ReviewTagSerializer(many=True)` explicitly, replacing the auto-discovered JSONField (which no longer exists on the model after 17-01).
- `base_reviews_queryset()` adds `.prefetch_related("tags")` — review list responses join in one extra `IN (...)` query rather than N+1.
- Added `test_review_list_tags_shape` regression test asserting tags appear as a list of `{label, polarity}` dicts in the list response.

## Tests

- `apps/reviews/tests/test_enrichment_service.py`: extended with tag-row creation, title-case storage, re-enrichment idempotency (old rows wiped, new rows match new parse), and the comment-less path clears stale ReviewTag rows.
- `apps/reviews/tests/test_views.py`: added `test_review_list_tags_shape` for the read serializer contract.

## Must-haves check

| Must-have | Status |
|---|---|
| `enrich_review()` writes ReviewTag rows instead of `Review.tags` JSONField | ✓ |
| Re-enrichment deletes old tags before creating new (idempotent) | ✓ |
| Comment-less path clears stale ReviewTag rows | ✓ |
| `ReviewReadSerializer` returns `[{label, polarity}]` via `ReviewTagSerializer` | ✓ |
| List queryset prefetches tags (no N+1) | ✓ |

## Deviations

- None. Both task commits landed on the planned files.
- Note: agent process stalled after committing both tasks; orchestrator authored and committed this SUMMARY.md on the same worktree branch.

## Hands off to

- 17-03 — adds `tags` filter and `/api/v1/reviews/tags/` action that joins on the new `ReviewTag` table (runs in parallel in Wave 2).
- 17-04 — frontend consumes the unchanged `[{label, polarity}]` JSON shape for chips and the multi-select dropdown.
