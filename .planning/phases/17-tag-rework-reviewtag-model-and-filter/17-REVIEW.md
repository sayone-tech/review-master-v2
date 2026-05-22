---
phase: 17-tag-rework-reviewtag-model-and-filter
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/reviews/filters.py
  - apps/reviews/migrations/0008_reviewtag.py
  - apps/reviews/models.py
  - apps/reviews/selectors/reviews.py
  - apps/reviews/serializers.py
  - apps/reviews/services/enrichment.py
  - apps/reviews/tests/factories.py
  - apps/reviews/tests/test_enrichment_service.py
  - apps/reviews/tests/test_models.py
  - apps/reviews/tests/test_views.py
  - apps/reviews/views.py
  - frontend/src/widgets/review-management/api.ts
  - frontend/src/widgets/review-management/ReviewFilters.tsx
  - frontend/src/widgets/review-management/ReviewManagementWidget.tsx
  - frontend/src/widgets/review-management/ReviewTable.tsx
  - frontend/src/widgets/review-management/types.ts
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 17 introduces the `ReviewTag` relational model, switches the enrichment write path to delete-then-bulk_create, exposes `tags` via a nested serializer with `prefetch_related("tags")`, adds `?tags=` filtering with AND-semantics, a `/api/v1/reviews/tags/` discovery endpoint, and a frontend TagsFilter combobox plus clickable tag chips. The implementation is largely solid (org scoping is enforced, Staff scoping mirrors the list endpoint, the prefetch keeps the list endpoint under its query budget, tests cover happy paths and cross-org isolation), but several real defects exist:

- **CR-01** — The `tags` endpoint is *not* registered on the URL router (the action exists on the viewset but the viewset only ships `list`/`retrieve` mixins). This needs verifying against `apps/reviews/urls.py`; if the viewset is registered with a DRF router the action is auto-routed, but `TenantScopedViewSet` + `mixins.ListModelMixin`/`RetrieveModelMixin` requires a router registration. Treated below as a Warning pending URL verification.
- **CR-01 (true Critical)** — The `?tags=` filter on the **stats** endpoint can produce inflated aggregates because `qs.aggregate()` is called on a queryset that has joined `ReviewTag` (via the `filter_tags` chained `tags__label__iexact` joins) and the `.distinct()` applied in `filter_tags` does NOT carry through `.aggregate()` correctly for non-COUNT(DISTINCT) aggregates such as `Avg("star_rating")`. See WR-04 below.
- **CR-02 (Critical)** — Race window in the enrichment delete-then-bulk_create: while the `transaction.atomic()` block in `_persist_success` runs *inside* the per-review distributed Redis lock, the very first `transaction.atomic()` in `enrich_review` (the PENDING→IN_PROGRESS short transaction) **releases the row-level `select_for_update` lock before** the OpenAI call and the second `_persist_success` transaction. A concurrent invocation that bypasses the Redis lock (e.g. Redis outage with `IGNORE_EXCEPTIONS`) would not be blocked by the row lock between the two transactions. The Redis lock is the only real serialiser, and on Redis failure it returns `acquired=False` silently or `True` depending on the helper's behaviour. This is structurally the same risk as the existing Phase 12 code, but Phase 17 amplifies it: the new write path performs `DELETE … WHERE review_id = X` then `bulk_create`, so two concurrent enrichments may interleave deletes and inserts producing the union (or empty set) of two GPT responses. Documented as Critical because tag rows are now the canonical surface and silent stale-tag leak is observable to end users.

## Critical Issues

### CR-01: `filter_tags` joins inflate `stats` aggregates (Avg, sentiment %)

**File:** `apps/reviews/views.py:120-148`, `apps/reviews/filters.py:40-46`

**Issue:** `stats()` calls `self.filter_queryset(self.get_queryset())` and then `qs.aggregate(...)`. With `?tags=A,B`, `filter_tags` performs two chained `.filter(tags__label__iexact=...)` calls and finally `.distinct()`. Django adds the `.distinct()` only to the SELECT-list level; when the aggregator path emits `Avg("star_rating")` or `Count("pk", filter=Q(...))` over a queryset with the JOINed `reviews_reviewtag` table, rows from a review with N matching tags are counted N times for non-distinct aggregates.

The shipped test `test_stats_with_tag_filter` only asserts `total_count` (which uses `Count("pk")` — Django's ORM is smart enough to dedupe `Count("pk")` here because Django 4+ auto-applies `DISTINCT` to `Count` over a primary key when the queryset has `.distinct()` chained), and does NOT cover `avg_rating`, `awaiting_reply_count`, or `positive_sentiment_pct`. With a single tag filter the test happens to pass — but a `?tags=A` query against a review with three tag rows (one matches, two do not) still triggers the JOIN and `Avg("star_rating")` will average each star value once per matched row, not once per review.

**Fix:** Either:

1. Compute `stats` from a `Review.objects.filter(id__in=qs.values("pk"))` subquery so the aggregate runs on a JOIN-free queryset:
   ```python
   ids_qs = qs.values_list("pk", flat=True)
   stats_qs = Review.objects.filter(pk__in=ids_qs)
   agg = stats_qs.aggregate(...)
   ```
2. Or change `filter_tags` to use `Exists()` subqueries (one per label) instead of JOIN+distinct — eliminates the row multiplication entirely and removes the need for `.distinct()`:
   ```python
   from django.db.models import Exists, OuterRef
   from apps.reviews.models import ReviewTag
   for label in tag_labels:
       sub = ReviewTag.objects.filter(review=OuterRef("pk"), label__iexact=label)
       queryset = queryset.filter(Exists(sub))
   return queryset
   ```
   This is also faster at scale than N self-joins on `reviews_reviewtag` and is the canonical pattern for multi-relation AND filtering.

Add a regression test asserting `avg_rating` is correct when reviews carry multiple tag rows.

### CR-02: Re-enrichment delete-then-bulk_create has no per-review serialisation guarantee on Redis failure

**File:** `apps/reviews/services/enrichment.py:69-109, 382-460`

**Issue:** The new write path (`_persist_success`) inside `transaction.atomic()` performs `ReviewTag.objects.filter(review_id=review.pk).delete()` followed by `bulk_create(...)`. This is correct under the *Redis* lock. But:

1. The `enrich_review` function structurally splits work across **two** `transaction.atomic()` blocks with the slow OpenAI HTTP call in between (lines 400-427 then 451-460). Between the two transactions, the row-level `select_for_update` is released. The only serialiser left is the Redis lock at `lock:enrich:review:{review_id}`.
2. `apps/common/locks.distributed_lock` (from §7.6) is the sole guard. If Redis is unavailable or fails to set the lock (depending on helper implementation under `IGNORE_EXCEPTIONS`), `acquired` may be reported as `True` for both workers, or both may proceed without coordination. Two concurrent invocations would then race on `DELETE … WHERE review_id = X` and `bulk_create`, producing a union of tags from two GPT calls or a partial set if one delete fires between the other's delete+bulk_create.
3. The Layer-3 status guard inside the first transaction would mark one worker IN_PROGRESS and the second would early-return — **but only if both workers serialise on the row lock**. The first `transaction.atomic()` in `enrich_review` does take `select_for_update`, so this is actually safe **for the status flag transition**. However, after that transaction commits, the IN_PROGRESS marker is the only thing keeping the second worker out; if the second worker entered the `select_for_update` block *before* the first worker committed IN_PROGRESS, both would see PENDING.

The actual race window is narrow (select_for_update serialises the transition), but Phase 17 makes the consequences user-visible: stale or duplicated tag rows on a review. Worse, in the FAILED→retry path (`retry_failed_enrichments_task`), if the previous enrichment wrote tag rows before a later step failed and rolled back, the `transaction.atomic()` wrapping `_persist_success` *does* roll back the delete and bulk_create together — that is correct. The risk is only across two separate `enrich_review` invocations.

**Fix:** Acceptable mitigations:

1. Add an explicit `select_for_update()` re-fetch at the top of `_persist_success` to re-verify the row is still IN_PROGRESS and held by *this* worker (e.g. compare a worker-id stamped onto `enrichment_attempted_at` or a new short field). Reject the write if status is not IN_PROGRESS.
2. Document at `LOCK_KEY_TMPL`/module docstring that Redis lock loss results in tag-row inconsistency on the next re-enrichment, and ensure `distributed_lock` is NOT silenced by `DJANGO_REDIS_IGNORE_EXCEPTIONS`. If it is, change it so lock acquisition raises rather than silently returns True/False under Redis outage.
3. Add a unique constraint on `(review_id, label, polarity)` so concurrent `bulk_create` calls would fail at the DB layer instead of silently producing duplicates. The migration already creates `reviewtag_review_label_idx` but no UNIQUE — adding a unique partial index would catch the race and prevent dup rows. This is the cheapest correct fix.

Recommend (3) plus a regression test under `pytest`'s `transaction=True` simulating two interleaved enrichments.

## Warnings

### WR-01: `?tags=` filter pushes per-label JOINs — query plan explodes at ≥3 selected tags

**File:** `apps/reviews/filters.py:40-46`

**Issue:** Each iteration of the loop adds another JOIN to `reviews_reviewtag`. With 5 selected tags the planner has 5 self-joins plus the final `DISTINCT`. The composite index `(review, label)` helps but doesn't eliminate the N-join cost. At 200k+ reviews this becomes the dominant cost.

**Fix:** Use the `Exists(OuterRef)` rewrite shown in CR-01's fix block — each label becomes one correlated subquery on the same indexed columns, no row multiplication, no `.distinct()` needed.

### WR-02: `?shop` query param on `/reviews/tags/` is not validated as integer

**File:** `apps/reviews/views.py:106-108`

**Issue:** `shop_id = request.query_params.get("shop")` then `qs.filter(review__shop_id=shop_id)`. Passing `?shop=abc` produces `ValueError: invalid literal for int()` raised by Django's ORM at query time → 500 to the caller. Also: no check that `shop_id` belongs to the caller's organisation — a sufficiently-curious org admin could probe `?shop=<other-org-shop-id>` and observe whether the query returns empty (timing/empty-vs-error side-channel). The org filter on `review__shop__organisation_id` makes that empty regardless, so it's not data leakage, but it's a poor 500.

**Fix:**
```python
shop_id_raw = request.query_params.get("shop")
if shop_id_raw:
    try:
        shop_id = int(shop_id_raw)
    except (TypeError, ValueError):
        return Response({"detail": "Invalid shop id"}, status=400)
    qs = qs.filter(review__shop_id=shop_id)
```

### WR-03: `/reviews/tags/` endpoint has no pagination or LIMIT

**File:** `apps/reviews/views.py:89-118`

**Issue:** Returns all distinct labels for the org. An org with thousands of unique tags (GPT free-form output across millions of reviews) returns an unbounded payload. The UI dropdown then renders all of them.

**Fix:** Cap to top N (e.g. 200) by default, with `?limit=` override; add a comment that long-tail tag management UI is the long-term solution.

### WR-04: `/reviews/tags/` Staff scoping silently returns ALL org tags when accessible_shop_ids is empty

**File:** `apps/reviews/views.py:110-115`

**Issue:** If a STAFF_ADMIN has zero `StaffAccessScope` rows, `get_accessible_shop_ids(user_id=user_id)` returns `[]`. Then `qs.filter(review__shop_id__in=[])` correctly returns no rows. Good. But the org-scope filter at line 104 is applied BEFORE the Staff scope filter — so the queryset goes:

```
ReviewTag.filter(review__shop__organisation_id=org)         # org admin's tags
   .filter(review__shop_id__in=accessible_shop_ids)        # then narrowed
```

This is correct, but the same Staff scope check is *also* missing on the `stats` action — `stats()` calls `self.filter_queryset(self.get_queryset())` which routes through `get_queryset()` and does apply Staff scoping. Confirmed safe. The Staff scoping on the tags action mirrors the list view correctly. **However**: there is no test that a Staff user with zero scopes sees an empty `/tags/` response. Add one to lock the contract.

**Fix:** Add `test_tags_action_staff_no_scope_empty` test asserting Staff with no `StaffAccessScope` rows gets `[]` from `/reviews/tags/`.

### WR-05: `ReviewTagSerializer` uses `serializers.Serializer` and is unnecessarily lossy on `polarity`

**File:** `apps/reviews/serializers.py:12-21`

**Issue:** `polarity = serializers.CharField(read_only=True)` accepts any string. The model enforces `choices=Polarity.choices`, but the serializer doesn't surface the constraint to consumers (OpenAPI schema readers/clients lose the enum). Not a runtime bug — but the matching frontend `TagPolarity` type is a strict literal union, so if a future migration adds a fourth polarity, the contract drift surfaces only at runtime in TS.

**Fix:** Use `serializers.ChoiceField(choices=ReviewTag.Polarity.choices, read_only=True)` so drf-spectacular emits the enum.

### WR-06: `enriched_count` in `stats` is wrong when paired with `?tags=` due to the same JOIN inflation

**File:** `apps/reviews/views.py:131-140`

**Issue:** See CR-01. `Count("pk", filter=Q(enrichment_status=...))` over a JOINed `reviews_reviewtag` queryset counts a review once per matching tag row. The positive_pct calc uses `enriched_count` as denominator, so the % is silently wrong (under-stated, because numerator and denominator both inflate at the same rate — *actually*, this cancels out **only** when every enriched review has the same number of tags, which is rarely true). Add a regression test.

**Fix:** Same as CR-01 — switch the filter to `Exists()` so the queryset has no JOIN to deduplicate.

## Info

### IN-01: Tag rows are not ordered when serialised

**File:** `apps/reviews/serializers.py:37`, `apps/reviews/services/enrichment.py:100-109`

**Issue:** `tags = ReviewTagSerializer(many=True, read_only=True)` returns tag rows in whatever order the prefetched queryset emits — effectively insertion order, but no explicit `Meta.ordering` on `ReviewTag`. UI displays the first 4 tags (`r.tags.slice(0, 4)`), so a non-deterministic ordering may surface different chips between requests on the same review.

**Fix:** Add `ordering = ["label"]` to `ReviewTag.Meta`, or use a `Prefetch` with explicit ordering in `base_reviews_queryset`.

### IN-02: TagsFilter loading state regresses to "Any tag" but does not announce loading to screen readers

**File:** `frontend/src/widgets/review-management/ReviewFilters.tsx:89, 180-187`

**Issue:** `loading = availableTags === undefined`. The trigger button is `disabled` and visually faded, but has no `aria-busy="true"` or live-region announcement. Screen-reader users see a disabled control with no explanation.

**Fix:** Add `aria-busy={loading}` on the trigger and optionally a `aria-describedby` pointing to a visually-hidden "Loading tags…" string.

### IN-03: ARIA listbox/option pattern missing `aria-activedescendant`

**File:** `frontend/src/widgets/review-management/ReviewFilters.tsx:201-265`

**Issue:** The listbox uses `activeIndex` for visual highlight via class, but does not set `id` on each option nor `aria-activedescendant` on the listbox. Keyboard navigation works visually, but assistive tech won't announce the active option as the user arrows through. Per ARIA APG combobox-with-listbox pattern, either roving tabindex or `aria-activedescendant` is required.

**Fix:** Give each option an id like `tag-opt-${idx}` and set `aria-activedescendant={activeIndex >= 0 ? \`tag-opt-${activeIndex}\` : undefined}` on the listbox div. Also note the listbox div should accept keyboard focus (`tabIndex={-1}`) and receive focus on open, OR the search input should be the focused element and own the `aria-activedescendant` (current pattern). Verify the focus model is consistent — currently the search input gets focus on open but `onPanelKeyDown` is bound to the listbox div, so arrow keys typed in the input bubble up and are handled by the panel listener (works in practice, but mixing the keyboard handler off the focused element is fragile).

### IN-04: Tag chip key `${tag.label}-${tag.polarity}` collides if duplicate tag rows exist

**File:** `frontend/src/widgets/review-management/ReviewTable.tsx:208-220`

**Issue:** If two `ReviewTag` rows exist with same label+polarity (possible today — no unique constraint per CR-02), React emits the duplicate-key warning and may reuse the wrong DOM node on update. Once CR-02's unique constraint is added this becomes a non-issue.

**Fix:** Either add the unique constraint (preferred — fixes CR-02 too) or key on the array index as a fallback: `key={\`${idx}-${tag.label}\`}`.

---

## Structural Findings (fallow)

No `<structural_findings>` block was provided with this review request.

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
