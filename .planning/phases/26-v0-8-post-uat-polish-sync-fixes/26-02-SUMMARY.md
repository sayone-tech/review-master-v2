---
phase: 26-v0-8-post-uat-polish-sync-fixes
plan: "02"
subsystem: frontend
tags: [canonical-tags, tag-management, sync, progress-modal, search-filter, pagination, timing]
dependency_graph:
  requires:
    - 26-01 (backend ?search= param on canonical-tag list; per-step timing fields in sync snapshot)
  provides:
    - debounced server-side search box on tag-management widget (?search= driven)
    - "Tags (N)" header count + "Showing X–Y of N · Rows: N" pagination footer on Tags page
    - "Fetching from Google" step-1 label in sync ProgressModal
    - per-stage duration display in ProgressModal (fetch + vocab stages)
  affects:
    - frontend/src/widgets/tag-management/types.ts
    - frontend/src/widgets/tag-management/api.ts
    - frontend/src/widgets/tag-management/useTagList.ts
    - frontend/src/widgets/tag-management/TagManagementWidget.tsx
    - frontend/src/widgets/review-management/ProgressModal.tsx
tech_stack:
  added: []
  patterns:
    - TeamTable.tsx debounce pattern (300ms useEffect + useRef, eslint-disable exhaustive-deps)
    - TeamTable.tsx buildPageRange helper (ellipsis pagination, verbatim copy)
    - TeamTable.tsx "Showing X–Y of N · Rows: N" footer (start/end/totalPages derivations)
    - team_list.html "Team (N)" header count pattern (adapted to JSX)
    - ProgressModal self-analog surgical edit (interface extension + helper + complete-branch additions)
key_files:
  created: []
  modified:
    - frontend/src/widgets/tag-management/types.ts
    - frontend/src/widgets/tag-management/api.ts
    - frontend/src/widgets/tag-management/useTagList.ts
    - frontend/src/widgets/tag-management/TagManagementWidget.tsx
    - frontend/src/widgets/review-management/ProgressModal.tsx
decisions:
  - "D-01/TMGT-07: search box wired to setSearch which resets page to 1; 300ms debounce in widget; ?search= appended to fetchTags request"
  - "D-02/TMGT-08: buildPageRange helper copied verbatim from TeamTable.tsx; rows options [10,25,50,100]; count=0 renders Showing 0–0 of 0"
  - "D-03/SEED-05a: all three <label> occurrences of step-1 changed to Fetching from Google; the aria-label progressbar text on line 404 retains Fetched from Google (describes percentage on progress bar, not a label element)"
  - "D-04/SEED-05b: only fetch_duration_seconds + vocab_duration_seconds shown (enriching_duration_seconds not in 26-01 backend contract; finalising uses existing duration_seconds on success banner)"
metrics:
  duration_minutes: 8
  completed: "2026-06-24"
  tasks_completed: 3
  files_modified: 5
---

# Phase 26 Plan 02: Frontend Polish — Tag Search, Pagination Footer, ProgressModal Durations Summary

Frontend for Phase 26 polish: debounced server-side tag label search box (`?search=` to the backend endpoint from 26-01), "Tags (N)" header count + "Showing X–Y of N · Rows: N" pagination footer matching the team page, sync ProgressModal step-1 label renamed to "Fetching from Google", and per-stage wall-clock durations rendered from the 26-01 snapshot timing fields.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 (infra) | search?: string in FetchTagsParams + ?search= in fetchTags + setSearch in useTagList | f1dfa7b | types.ts, api.ts, useTagList.ts |
| 2 (UI) | debounced search input + Tags (N) header + Showing X–Y footer + buildPageRange | 74dcc47 | TagManagementWidget.tsx |
| 3 | ProgressModal: Fetching from Google label + formatDuration + per-stage timing display | b3d6671 | ProgressModal.tsx |

## Deviations from Plan

### Minor Commit Structure Deviation

Task 1 and Task 2 both touch `TagManagementWidget.tsx`. Since the search input UI (Task 1's UI) and the header/footer (Task 2) were implemented together in the widget file, they were committed in two logical commits: one for the infrastructure (types/api/hook — Task 1 backend), and one for the widget UI that covers both the search input and the pagination footer (effectively Tasks 1+2 UI). The functional outcome is identical; commit granularity was split as cleanly as possible.

### D-04 Scope Note (Not a Deviation)

The plan's acceptance criteria mention "each completed stage shows its real wall-clock duration". The 26-01 backend contract provides `fetch_duration_seconds` and `vocab_duration_seconds` only. The enriching stage has `enriching_started_at` but no `enriching_duration_seconds` (the enriching-to-finalising transition is computed by `finalise.py`, not written back to the snapshot as a standalone duration field). The finalising stage duration is already covered by `duration_seconds` on the sync.complete success banner. Implementation renders fetch and vocab durations; enriching and finalising are correctly omitted per the backend contract — not a deficit.

## Known Stubs

None — all data is wired to real fields from the backend snapshot and paginated API response.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes:
- Tag search sends `?search=` to the existing `IsOrgAdmin`-guarded endpoint (T-26-05 mitigated per plan threat model).
- ProgressModal timing fields are read-only display from the already-authorised per-shop snapshot (T-26-06 accepted per plan threat model).
- No new npm packages were installed (T-26-SC mitigated).

## Self-Check

**Files exist:**
- frontend/src/widgets/tag-management/types.ts — FOUND (search?: string added to FetchTagsParams)
- frontend/src/widgets/tag-management/api.ts — FOUND (if (params.search) qs.set("search", params.search))
- frontend/src/widgets/tag-management/useTagList.ts — FOUND (search state + setSearch)
- frontend/src/widgets/tag-management/TagManagementWidget.tsx — FOUND (search input + Tags(N) + Showing footer)
- frontend/src/widgets/review-management/ProgressModal.tsx — FOUND (Fetching from Google + formatDuration + duration display)

**Commits exist:**
- f1dfa7b — feat(26-02): add search state + ?search= param to tag-management hook/api (TMGT-07/D-01)
- 74dcc47 — feat(26-02): add search input + Tags(N) header + Showing X-Y footer to tag widget (TMGT-07/TMGT-08/D-01/D-02)
- b3d6671 — feat(26-02): ProgressModal — Fetching from Google label + per-stage durations (SEED-05/D-03/D-04)

**TypeScript:** `cd frontend && npx tsc --noEmit` — PASSED (no errors)

## Self-Check: PASSED
