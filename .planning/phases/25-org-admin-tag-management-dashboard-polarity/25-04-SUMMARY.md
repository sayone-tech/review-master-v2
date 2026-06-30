---
phase: "25"
plan: "04"
subsystem: dashboard
tags: [dashboard, canonical-tags, recharts, TDASH-01, TDASH-02, polarity]
dependency_graph:
  requires:
    - "25-01 (OrgCanonicalTag model + ReviewTag.canonical_tag FK)"
    - "22 (OrgCanonicalTag, ReviewTag with polarity field)"
  provides:
    - "dashboard_tag_polarity selector"
    - "DashboardTagPolarityView + /api/v1/dashboard/tag-polarity/ endpoint"
    - "TagPolarityChart.tsx (stacked recharts polarity bar chart)"
  affects:
    - "apps/dashboard/ (views, urls, selectors, tests)"
    - "frontend/src/widgets/dashboard/ (types, api, DashboardWidget)"
tech_stack:
  added: []
  patterns:
    - "values().annotate(Count(filter=Q(...))) grouped aggregate (TDASH-02 single-query)"
    - "DashboardApiView subclass pattern (endpoint_name + _fetch)"
    - "recharts stacked BarChart with stackId='a' for mixed polarity split"
    - "cast(list[dict[str, Any]], ...) for mypy compatibility on annotated querysets"
key_files:
  created:
    - "frontend/src/widgets/dashboard/TagPolarityChart.tsx"
  modified:
    - "apps/dashboard/selectors/aggregations.py"
    - "apps/dashboard/tests/test_aggregations.py"
    - "apps/dashboard/views.py"
    - "apps/dashboard/urls.py"
    - "frontend/src/widgets/dashboard/types.ts"
    - "frontend/src/widgets/dashboard/api.ts"
    - "frontend/src/widgets/dashboard/DashboardWidget.tsx"
decisions:
  - "D-09 (TDASH-01): always_positive/always_negative render single-color bar naturally; mixed renders stacked positive/negative split via recharts stackId='a'"
  - "D-10 (TDASH-02): canonical_tag__organisation_id=org_id filter enforces IS NOT NULL + org scope in a single grouped query — no redundant Python null check"
  - "cast(list[dict[str, Any]]) added to satisfy mypy strict mode on values().annotate() queryset (Rule 3 auto-fix)"
  - "TagPolarityChart mounted as full-width third row below existing two-column grid per RESEARCH Open Question 1 recommendation"
metrics:
  duration: "465 seconds (~8 minutes)"
  completed_date: "2026-06-16"
  tasks_completed: 3
  files_modified: 7
---

# Phase 25 Plan 04: Dashboard Tag Polarity Chart Summary

**One-liner:** Stacked recharts polarity bar chart on the dashboard, backed by a single org-scoped grouped ReviewTag aggregate query, with `always_positive`/`always_negative` single-bar and `mixed` stacked split.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | dashboard_tag_polarity selector + TDD tests (RED → GREEN) | d3fde82 | Done |
| 2 | DashboardTagPolarityView + tag-polarity/ URL | 77702aa | Done |
| 3 | TagPolarityChart.tsx + types/api + DashboardWidget wiring | 2a4c0a7 | Done |

## What Was Built

### Backend

**`dashboard_tag_polarity` selector** (`apps/dashboard/selectors/aggregations.py`):

- Single `ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id).values(...).annotate(positive_count=Count(...), negative_count=Count(...), total_count=Count(...)).order_by("-total_count")[:limit+1]` — one DB query.
- `canonical_tag__organisation_id` filter implicitly enforces `canonical_tag IS NOT NULL` (TDASH-02) and org scope (D-10). No redundant Python-side null check.
- Returns `{"tags": [...], "has_more": bool}` with keys `label`, `polarity_type`, `positive_count`, `negative_count`, `total_count`.

**`DashboardTagPolarityView`** (`apps/dashboard/views.py`):

- Subclasses `DashboardApiView`; `endpoint_name = "tag-polarity"`.
- `_fetch` calls `dashboard_tag_polarity(organisation_id=org_id)` — ignores date/shop filter params per TDASH-02.
- Inherits `IsOrgScoped` permission, per-org cache read/write (DASH-C1 key includes org_id + user_id).

**URL** `tag-polarity/` registered in `apps/dashboard/urls.py` → `/api/v1/dashboard/tag-polarity/`.

### Tests

Three new tests in `apps/dashboard/tests/test_aggregations.py`:
- `test_tag_polarity_basic`: mixed tag returns `positive_count > 0` and `negative_count > 0`; always_positive tag returns `negative_count == 0`.
- `test_tag_polarity_excludes_null_canonical`: `ReviewTag` rows with `canonical_tag=None` produce empty result (TDASH-02 enforcement proven).
- `test_tag_polarity_query_count`: `CaptureQueriesContext` asserts ≤2 queries for 5 tags (ceiling includes cache write).

All 34 tests in `apps/dashboard/tests/` pass.

### Frontend

**`types.ts`**: Added `PolarityType`, `TagPolarityBar`, `TagPolarityResponse` interfaces per UI-SPEC Surface 5.

**`api.ts`**: Added `fetchTagPolarity()` — `GET /api/v1/dashboard/tag-polarity/` with `credentials: "same-origin"`.

**`TagPolarityChart.tsx`** (188 lines):
- `useQuery` with `queryKey: ["dashboard", "tag-polarity"]` fetches once per render.
- Recharts `ResponsiveContainer` (height 240) → `BarChart` (barCategoryGap 35%, bottom margin 48).
- `XAxis`: angle -35, 14-char truncate, fontSize 12 `#71717A`.
- `YAxis`: fontSize 12 `#A1A1AA`, no axis/tick lines.
- `Legend`: verticalAlign top, Positive/Negative labels in 12px `#71717A`.
- Two stacked `<Bar>`: `positive_count` (fill `#16A34A`, radius `[0,0,0,0]`) and `negative_count` (fill `#DC2626`, radius `[4,4,0,0]`), both with `stackId="a"`.
- `TagPolarityTooltip`: mixed → pos/neg dot rows; non-mixed → total reviews count.
- Loading skeleton (`bg-line-soft animate-[sk-pulse_...]`), empty state, `has_more` "See all tags" footer link.
- `role="img" aria-label="Tag distribution by polarity bar chart"` on chart wrapper.
- Section heading "Tag Distribution" + subtitle "Top tags by review volume · canonical tags only".

**`DashboardWidget.tsx`**: `TagPolarityChart` mounted as a full-width third row below the existing two-column grid (preserves responsive grid behavior).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Bug] mypy strict-mode incompatibility on `values().annotate()` result**

- **Found during:** Task 1 commit (pre-commit mypy hook)
- **Issue:** `list(ReviewTag.objects...values().annotate()...)` returned an annotated QuerySet type that mypy strict mode rejects as `Iterable[dict[str, Any]]`. Two iterations needed: first attempt used `list[dict[str, Any]]` type annotation on the variable (insufficient); second iteration used `cast(list[dict[str, Any]], list(...))` which satisfies mypy.
- **Fix:** Wrapped `list(...)` call in `cast(list[dict[str, Any]], ...)`. Added `from typing import cast` import.
- **Files modified:** `apps/dashboard/selectors/aggregations.py`
- **Commit:** d3fde82 (final passing commit after two fix attempts)

## Known Stubs

None — `TagPolarityChart` fetches live data from `/api/v1/dashboard/tag-polarity/` backed by a real DB aggregate. No placeholder or hardcoded values.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none) | — | No new trust-boundary surfaces beyond what the plan's threat model covers (T-25-D1, T-25-D2). Cache key includes org_id + user_id (DASH-C1). `canonical_tag__organisation_id` enforces cross-org data isolation at the query level. |

## Self-Check: PASSED

- `apps/dashboard/selectors/aggregations.py` — FOUND (contains `def dashboard_tag_polarity`)
- `apps/dashboard/views.py` — FOUND (contains `class DashboardTagPolarityView`)
- `apps/dashboard/urls.py` — FOUND (`tag-polarity/` registered)
- `frontend/src/widgets/dashboard/TagPolarityChart.tsx` — FOUND (188 lines, ≥40)
- `frontend/src/widgets/dashboard/types.ts` — FOUND (contains `TagPolarityBar`, `TagPolarityResponse`)
- `frontend/src/widgets/dashboard/api.ts` — FOUND (contains `fetchTagPolarity`)
- `frontend/src/widgets/dashboard/DashboardWidget.tsx` — FOUND (contains `TagPolarityChart`)
- Commits d3fde82, 77702aa, 2a4c0a7 — VERIFIED (`git log --oneline -5`)
