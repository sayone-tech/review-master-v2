---
phase: 14-dashboard
plan: "02"
subsystem: dashboard
tags: [dashboard, selectors, aggregations, query-optimization, security]
dependency_graph:
  requires:
    - apps.dashboard.filters.DashboardFilterParams
    - apps.reviews.models.Review.EnrichmentStatus
    - apps.shops.models.Shop
  provides:
    - apps.dashboard.selectors.aggregations.dashboard_kpis
    - apps.dashboard.selectors.aggregations.dashboard_sentiment_distribution
    - apps.dashboard.selectors.aggregations.dashboard_your_store
    - apps.dashboard.selectors.aggregations.dashboard_top_performing
    - apps.dashboard.selectors.aggregations.dashboard_highlights
    - apps.dashboard.selectors.aggregations.MIN_REVIEWS_FOR_RANKING
  affects:
    - apps.dashboard.tests.test_aggregations
tech_stack:
  added: []
  patterns: [single-query-aggregate, values-annotate-group-by, CaptureQueriesContext-ceiling]
key_files:
  created:
    - apps/dashboard/selectors/__init__.py
    - apps/dashboard/selectors/aggregations.py
    - apps/dashboard/tests/test_aggregations.py
  modified:
    - apps/dashboard/tests/conftest.py
decisions:
  - "_base_qs applies region+shop+date filters; _date_only_qs skips region/shop to enforce TOP-01 date-only scope"
  - "negative_count and negative_pct use Q(sentiment='negative', enrichment_status=SUCCESS) not star_rating — locks in KPI-03"
  - "negative_pct denominator is enriched_count, not total_count — locks in KPI-04"
  - "dashboard_your_store returns None for accessible_shop_ids with > 1 entry (Staff with multi-shop access should not see single-store view)"
  - "trend comparison builds prev window as [date_from - window_days - 1, date_from - 1] — symmetric window"
  - "trend_direction='none' guard: prev_total < MIN_REVIEWS_FOR_RANKING => skip comparison (STORE-03)"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-07"
  tasks_completed: 2
  files_changed: 4
---

# Phase 14 Plan 02: Dashboard Aggregation Selectors Summary

**One-liner:** Five single-query ORM aggregation selectors encoding KPI-03 (AI sentiment not star rating), TOP-01 (date-only scope), TOP-02 (≥3 review threshold), and STORE-03 (trend comparison guard) — locked in by 20 CaptureQueriesContext tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | dashboard_kpis + dashboard_sentiment_distribution + dashboard_your_store | 41ddc62 | apps/dashboard/selectors/aggregations.py, tests/conftest.py, tests/test_aggregations.py |
| 2 | dashboard_top_performing + dashboard_highlights | 069d72f | apps/dashboard/tests/test_aggregations.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong module path for Shop import**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Plan skeleton used `from apps.stores.models import Shop` but the actual module path is `apps.shops.models`.
- **Fix:** Changed to `from apps.shops.models import Shop`.
- **Files modified:** apps/dashboard/selectors/aggregations.py
- **Commit:** 41ddc62

**2. [Rule 2 - Missing critical functionality] mypy type annotations**
- **Found during:** Task 1 commit (pre-commit hook)
- **Issue:** `_base_qs` and `_date_only_qs` lacked return type annotations; `dict` return types needed `dict[str, Any]`; `shop.region.name` triggered `union-attr` error.
- **Fix:** Added `QuerySet[Review]` return types, `dict[str, Any]` signatures, and explicit `region_name` guard with `shop.region is not None` check.
- **Files modified:** apps/dashboard/selectors/aggregations.py
- **Commit:** 41ddc62

## Verification Results

- `pytest apps/dashboard/tests/test_aggregations.py -x -q` — 20 passed
- `grep -q "sentiment=\"negative\", enrichment_status=SUCCESS" apps/dashboard/selectors/aggregations.py` — passes
- `grep -q "_date_only_qs" apps/dashboard/selectors/aggregations.py` — passes
- `grep -q "review_count__gte=MIN_REVIEWS_FOR_RANKING" apps/dashboard/selectors/aggregations.py` — passes
- All CaptureQueriesContext tests assert 1 query (kpis, sentiment, top_performing, highlights)
- dashboard_your_store asserts <= 2 queries (1 Shop fetch + 1 aggregate; trend adds 1 more = 2 total for trend path)

## Self-Check: PASSED
