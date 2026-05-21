---
phase: 17-tag-rework-reviewtag-model-and-filter
plan: 03
subsystem: reviews
tags: [filter, viewset, drf-action, integration-tests, tag-filter]
requires:
  - 17-01 (ReviewTag model + reviews_reviewtag table)
provides:
  - ReviewFilterSet.tags CharFilter with AND-semantics + .distinct()
  - GET /api/v1/reviews/tags/ — org-scoped tag label + count list
  - TAG-03 integration test coverage on ReviewViewSet
affects:
  - apps.reviews.filters (ReviewFilterSet extended with tags field + filter_tags method)
  - apps.reviews.views (ReviewViewSet extended with tags @action)
  - apps.reviews.tests.test_views (9 new TAG-03 tests added)
tech-stack:
  added: []
  patterns:
    - django-filter method-based CharFilter with field_name=""
    - DRF @action(detail=False) directly querying related model with explicit org+staff scoping
    - Chained reverse-FK filter + .distinct() for AND semantics across many-to-one
key-files:
  created: []
  modified:
    - apps/reviews/filters.py
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py
decisions:
  - filter_tags uses chained .filter(tags__label__iexact=label) per label and returns queryset.distinct() to enforce AND semantics with no row multiplication
  - tags @action does NOT delegate to get_queryset() — it queries ReviewTag directly with explicit org scoping (TenantScopedViewSet only scopes Review, not ReviewTag)
  - tags @action uses a local "from apps.reviews.models import ReviewTag" inside the method body to mirror the existing pattern for related-model lookups inside actions
metrics:
  duration: ~10 minutes
  completed_date: 2026-05-21
  tasks_completed: 2
  files_changed: 3
requirements:
  - TAG-03
---

# Phase 17 Plan 03: Filters API + tags Action Summary

Completed the backend half of TAG-03. `ReviewFilterSet` now accepts `?tags=A,B` and applies AND semantics by chaining `.filter(tags__label__iexact=label)` per comma-split label, terminating with `.distinct()` to prevent reverse-FK row multiplication. `ReviewViewSet` exposes `GET /api/v1/reviews/tags/` returning `[{label, count}]` aggregated by `ReviewTag.label`, ordered by count descending, with three layers of scoping: explicit `review__shop__organisation_id` org filter, optional `?shop=<id>` narrowing, and `STAFF_ADMIN`-role restriction via `get_accessible_shop_ids()`. Nine integration tests in `test_views.py` cover all behaviors: org scoping, shop filter, staff scoping, cross-org isolation, empty-state, AND semantics, .distinct() behavior, excludes case, and stats correctness under tag filter.

## Tasks Completed

| Task | Name                                                            | Commit  |
| ---- | --------------------------------------------------------------- | ------- |
| 1    | Add tags CharFilter + filter_tags() method to ReviewFilterSet   | 96b4c71 |
| 2    | Add tags @action to ReviewViewSet and write TAG-03 tests        | 6c441af |

## Verification Run

- `python manage.py check` → System check identified no issues (0 silenced)
- `pytest apps/reviews/tests/test_views.py -k "tag"` → 9 passed, 9 deselected
- `grep -n "filter_tags" apps/reviews/filters.py` → 2 matches (field decl + method)
- `grep -n "field_name=\"\"" apps/reviews/filters.py` → 1 match (tags filter)
- `grep -n ".distinct()" apps/reviews/filters.py` → 1 match (in filter_tags)
- `grep -n "tags__label__iexact" apps/reviews/filters.py` → 1 match
- `grep -n "def tags" apps/reviews/views.py` → 1 match (@action method)
- `grep -n "url_path=\"tags\"" apps/reviews/views.py` → 1 match
- `grep -n "review__shop__organisation_id" apps/reviews/views.py` → 1 match
- `grep -n "STAFF_ADMIN" apps/reviews/views.py` → matches tags + get_queryset paths
- `grep -n "test_tags_action_returns_org_scoped_labels\|test_review_filter_tags_and_semantics\|test_tags_action_staff_scoping" apps/reviews/tests/test_views.py` → 3 matches

## Acceptance Criteria

Task 1:
- [x] `python -c "from apps.reviews.filters import ReviewFilterSet"` succeeds
- [x] `filter_tags` field declaration + method present
- [x] `field_name=""` used (prevents auto-resolution of RelatedManager)
- [x] `.distinct()` applied in filter_tags
- [x] `tags__label__iexact` chained per label

Task 2:
- [x] `pytest apps/reviews/tests/test_views.py -k "tag"` exits 0 — all 9 TAG-03 tests pass
- [x] `def tags` @action method present in ReviewViewSet
- [x] `url_path="tags"` on the action decorator
- [x] Explicit `review__shop__organisation_id` org scoping in the action body
- [x] STAFF_ADMIN role scoping via `get_accessible_shop_ids`
- [x] All three test name patterns from RESEARCH.md present in test_views.py

## Must-Have Truths (from PLAN frontmatter)

- [x] GET /api/v1/reviews/tags/ returns `[{label, count}]` scoped to the caller's organisation
- [x] GET /api/v1/reviews/tags/?shop=<id> filters results to that shop only
- [x] Staff users only see tags from their accessible shops on /api/v1/reviews/tags/
- [x] Cross-org isolation: user from Org A cannot see Org B's tags via the tags endpoint
- [x] GET /api/v1/reviews/?tags=A,B returns only reviews that have BOTH tag A AND tag B (AND semantics)
- [x] Paginated review list with a tag filter does not contain duplicate rows
- [x] Stats endpoint with ?tags= filter returns correct counts (no double-counting)

## Deviations from Plan

None — plan executed exactly as written. The plan's verbatim patterns from PATTERNS.md and RESEARCH.md applied cleanly with no edits required.

## Known Stubs

None.

## Deferred Issues / Out-of-Scope Findings

**REVW-14 query-count test (`test_reviews_list_query_count_org_admin` and `_staff_admin`) currently fails on the wave-2 base.** This is a pre-existing failure introduced by Plan 17-01 (which dropped the `Review.tags` JSONField) and is owned by Plan 17-02 (running in parallel as the other Wave 2 plan). Plan 17-02's deliverables are:

1. Adding explicit `tags = ReviewTagSerializer(many=True, read_only=True)` to `ReviewReadSerializer` (replacing the now-broken JSONField auto-discovery).
2. Adding `.prefetch_related("tags")` to `base_reviews_queryset()` so the new `tags` relation is batched and the <=5 query budget is preserved.

Plan 17-03's `files_modified` frontmatter explicitly scopes work to `apps/reviews/filters.py`, `apps/reviews/views.py`, and `apps/reviews/tests/test_views.py` — none of which can fix the serializer/selector N+1. Per executor SCOPE BOUNDARY rules, this is logged here rather than auto-fixed in this plan. When Plan 17-02 merges, both REVW-14 tests will pass again.

The 9 new TAG-03 tests added by this plan all pass independently of that failure.

## Threat Flags

None. The threat register dispositions T-17-06 (cross-org), T-17-07 (Staff scoping), T-17-08 (param injection), and T-17-09 (DoS via row multiplication) are all mitigated by the implementation and covered by tests `test_tags_action_cross_org_isolation`, `test_tags_action_staff_scoping`, `test_review_filter_tags_single_label` (verifies .distinct()), and `test_stats_with_tag_filter` (verifies no row inflation).

## Self-Check: PASSED

- FOUND: apps/reviews/filters.py (modified — tags CharFilter + filter_tags method)
- FOUND: apps/reviews/views.py (modified — tags @action with explicit scoping)
- FOUND: apps/reviews/tests/test_views.py (modified — 9 TAG-03 tests added)
- FOUND commit: 96b4c71
- FOUND commit: 6c441af
