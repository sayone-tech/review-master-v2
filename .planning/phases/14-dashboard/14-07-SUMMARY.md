---
phase: 14-dashboard
plan: "07"
subsystem: frontend/dashboard
tags: [react, typescript, recharts, tanstack-query, kpi-cards, sentiment-donut]
dependency_graph:
  requires: ["14-05"]
  provides: ["KpiCards", "SentimentDonut", "useKpis", "useSentiment"]
  affects: ["dashboard entrypoint"]
tech_stack:
  added: []
  patterns: ["useQuery hook wrapping API functions", "independent loading/error states per card", "recharts PieChart donut with custom tooltip"]
key_files:
  created:
    - frontend/src/widgets/dashboard/useKpis.ts
    - frontend/src/widgets/dashboard/useSentiment.ts
    - frontend/src/widgets/dashboard/KpiCards.tsx
    - frontend/src/widgets/dashboard/SentimentDonut.tsx
  modified:
    - frontend/src/widgets/dashboard/index.ts
decisions:
  - "KpiCards shares one useKpis query across all 3 cards — per-card skeletons satisfy KPI-05 layout without triple network calls"
  - "Half-star renders when fractional part is .25–.74 (not just ≥ 0.5) per KPI-04 spec"
  - "refetch wrapped in void arrow to satisfy TypeScript MouseEventHandler compatibility"
  - "Coverage footer uses literal 'of total' on a single line to pass grep acceptance test"
metrics:
  duration: "3 minutes"
  completed_date: "2026-05-07"
  tasks_completed: 2
  files_changed: 5
---

# Phase 14 Plan 07: KPI Cards and Sentiment Donut Summary

KPI cards (3-card grid with Total Reviews, Average Rating, Negative Reviews) and Sentiment Distribution donut using recharts, both consuming `fullFilters` with independent loading/empty/error states.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | useKpis + useSentiment hooks + KpiCards component | 170c8d9 |
| 2 | SentimentDonut component + index.ts exports | e49bda4 |

## Artifacts Produced

- `frontend/src/widgets/dashboard/useKpis.ts` — React Query hook, queryKey `["dashboard","kpis",filters]`, staleTime 5m
- `frontend/src/widgets/dashboard/useSentiment.ts` — React Query hook, queryKey `["dashboard","sentiment",filters]`, staleTime 5m
- `frontend/src/widgets/dashboard/KpiCards.tsx` — 3-card grid with loading skeleton, empty state, error+retry per card; half-star at .25–.74 frac
- `frontend/src/widgets/dashboard/SentimentDonut.tsx` — recharts PieChart donut, custom tooltip, summary list with progress bars, coverage footer with spinner <50%

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript: refetch function type mismatch on onClick**
- **Found during:** Task 2
- **Issue:** `onClick={refetch}` — React Query's `refetch` returns `Promise<QueryObserverResult>` which is not assignable to `MouseEventHandler<HTMLButtonElement>`
- **Fix:** Changed to `onClick={() => void refetch()}`
- **Files modified:** `SentimentDonut.tsx`
- **Commit:** e49bda4

**2. [Rule 1 - Bug] Coverage footer text split across lines fails grep acceptance test**
- **Found during:** Task 2
- **Issue:** JSX line wrap of `({data.coverage_pct}% of\ntotal)` means grep for `"of total"` fails
- **Fix:** Kept text on single line: `({data.coverage_pct}% of total)`
- **Files modified:** `SentimentDonut.tsx`
- **Commit:** e49bda4

## Self-Check: PASSED

Files verified:
- FOUND: `frontend/src/widgets/dashboard/useKpis.ts`
- FOUND: `frontend/src/widgets/dashboard/useSentiment.ts`
- FOUND: `frontend/src/widgets/dashboard/KpiCards.tsx`
- FOUND: `frontend/src/widgets/dashboard/SentimentDonut.tsx`

Commits verified:
- 170c8d9 — Task 1
- e49bda4 — Task 2

TypeScript: `cd frontend && npx tsc --noEmit` exits 0.
