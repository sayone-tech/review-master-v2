---
gsd_state_version: 1.0
milestone: v0.4
milestone_name: — Dashboard
status: unknown
stopped_at: Completed 14-05-PLAN.md
last_updated: "2026-05-07T08:52:28.732Z"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 8
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** Phase 14 — dashboard

## Current Position

Phase: 14 (dashboard) — EXECUTING
Plan: 2 of 8

## Performance Metrics

**Velocity:**

- Total plans completed: 37
- Average duration: ~9 minutes
- Total execution time: ~5.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v0.3 avg (phases 10–13) | 37 | ~330m | ~9m |

**Recent Trend:**

- Last 5 plans: 8m, 13m, 3m, 8m, 12m
- Trend: stable

*Updated after each plan completion*
| Phase 14 P01 | 2 | 3 tasks | 13 files |
| Phase 14 P02 | 10 | 2 tasks | 4 files |
| Phase 14 P03 | 8 | 2 tasks | 6 files |
| Phase 14 P04 | 7 | 2 tasks | 5 files |
| Phase 14 P05 | 1 | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v0.4 research]: Cache key MUST include `accessible_shop_ids` hash — Staff Admin A's cached data must never be served to Staff Admin B (DASH-C1)
- [v0.4 research]: `IsOrgScoped` used on APIView directly, not TenantScopedViewSet — dashboard views are pure-read APIViews with no queryset class attribute
- [v0.4 research]: Two filter objects in React — `fullFilters` for KPI+Sentiment, `dateOnlyFilters` for Top Performers+Highlights — prevents DASH-C2
- [v0.4 research]: `@tanstack/react-query` v5 added (overrides STACK.md) — five parallel endpoints with shared filter state require declarative refetch; 13.4 KB gzipped accepted
- [v0.4 research]: `recharts@^3.8.1` only new chart library — React 19 peer dep verified; covers both BarChart and PieChart needs
- [v0.4 research]: `history.replaceState` (not pushState) for URL filter state — prevents browser history pollution
- [v0.4 research]: UTC-only date windows with explicit "Dates are shown in UTC" notice — User.timezone field deferred
- [Phase 14]: validate_filter_params branches on user.role for ORG_ADMIN vs STAFF_ADMIN accessible shop resolution
- [Phase 14]: filter_hash includes shop_ids list to enforce cross-user cache isolation (DASH-C1)
- [Phase 14 P02]: _base_qs applies region+shop+date filters; _date_only_qs skips region/shop to enforce TOP-01 date-only scope
- [Phase 14 P02]: negative_count uses Q(sentiment='negative', enrichment_status=SUCCESS) not star_rating — locks in KPI-03
- [Phase 14 P02]: trend_direction='none' guard: prev_total < MIN_REVIEWS_FOR_RANKING => skip comparison (STORE-03)
- [Phase 14]: DashboardApiView base class: single security+cache gate shared by all 5 endpoints via inheritance
- [Phase 14]: handler404/handler500 as module-level string paths after urlpatterns in config/urls.py
- [Phase 14]: get_accessible_shop_ids uses user_id (not user object) — function signature preserved from Phase 11
- [Phase 14]: recharts and @tanstack/react-query installed as production deps with ^ semver range; patch versions locked in package-lock.json
- [Phase 14]: buildDateOnlyQs for top-performing/highlights/your-store — no region/shop params (DASH-C2)
- [Phase 14]: FilterBar is a pure controlled component — all state in useFilterState hook

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8 (carried forward): GBP API production approval from Google is a non-code prerequisite for production launch.
- Phase 14: Minimum review threshold for Top Performers — requirements doc specifies ≥3 reviews (TOP-02, TOP-06); confirmed at 3.

## Session Continuity

Last session: 2026-05-07T08:52:28.730Z
Stopped at: Completed 14-05-PLAN.md
Resume file: None
