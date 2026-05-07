---
gsd_state_version: 1.0
milestone: v0.4
milestone_name: — Dashboard
status: planning
stopped_at: Phase 14 context gathered
last_updated: "2026-05-07T07:13:59.432Z"
last_activity: 2026-05-07 — Roadmap created for v0.4 Dashboard; Phase 14 defined with 8 plans
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** v0.4 Dashboard — Phase 14 ready to plan

## Current Position

Phase: 14 of 14 (Dashboard)
Plan: 0 of 8 in current phase
Status: Ready to plan
Last activity: 2026-05-07 — Roadmap created for v0.4 Dashboard; Phase 14 defined with 8 plans

Progress: [░░░░░░░░░░] 0%

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

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8 (carried forward): GBP API production approval from Google is a non-code prerequisite for production launch.
- Phase 14: Minimum review threshold for Top Performers — requirements doc specifies ≥3 reviews (TOP-02, TOP-06); confirmed at 3.

## Session Continuity

Last session: 2026-05-07T07:13:59.426Z
Stopped at: Phase 14 context gathered
Resume file: .planning/phases/14-dashboard/14-CONTEXT.md
