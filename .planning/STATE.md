---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: — Configurable Sync Depth
status: planning
stopped_at: Phase 16 UI-SPEC approved
last_updated: "2026-05-15T12:29:25.587Z"
last_activity: 2026-05-15 — Phase 15 complete (4/4 plans, SYNC-01/02/03, SDEP-02/03, BKFL-01/02/03)
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 12
  completed_plans: 12
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-15)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** v0.5 — Configurable Sync Depth (Phase 16 ready to plan)

## Current Position

Phase: 16 of 16 (Org Admin Shop Creation — Conditional Depth Selector)
Plan: — of TBD in current phase
Status: Ready to plan
Last activity: 2026-05-15 — Phase 15 complete (4/4 plans, SYNC-01/02/03, SDEP-02/03, BKFL-01/02/03)

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity (v0.3–v0.4 baseline):**

- Total plans completed: 45
- Average duration: ~9 minutes
- Total execution time: ~6.75 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v0.3 avg (phases 10–13) | 37 | ~330m | ~9m |
| v0.4 (phase 14) | 8 | ~72m | ~9m |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Decisions carried forward:

- [v0.4]: Cache key MUST include `accessible_shop_ids` hash — cross-user cache isolation (DASH-C1)
- [v0.4]: `IsOrgScoped` used on APIView directly, not TenantScopedViewSet — for pure-read views
- [v0.4]: handler404/handler500 as module-level string paths in config/urls.py

### Pending Todos

None.

### Blockers/Concerns

- Phase 8 (carried forward): GBP API production approval from Google is a non-code prerequisite for production launch.

## Session Continuity

Last session: 2026-05-15T12:29:25.579Z
Stopped at: Phase 16 context gathered
Resume file: .planning/phases/16-org-admin-shop-creation-conditional-depth-selector/16-UI-SPEC.md
