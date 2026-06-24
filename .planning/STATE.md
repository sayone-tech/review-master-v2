---
gsd_state_version: 1.0
milestone: v0.8
milestone_name: Canonical Tag System
status: verifying
stopped_at: Phase 25 UI-SPEC approved
last_updated: "2026-06-24T07:24:19.838Z"
last_activity: 2026-06-24
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 26
  completed_plans: 26
  percent: 86
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-08)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** Phase 26 — v0-8-post-uat-polish-sync-fixes

## Current Position

Phase: 26 (v0-8-post-uat-polish-sync-fixes) — EXECUTING
Plan: 2 of 2
Next: Phase 24 (polarity-auto-reclassification) — discussing
Status: Phase complete — ready for verification
Last activity: 2026-06-24

### v0.8 phase map (Phases 22–26)

| Phase | Name | Requirements |
|-------|------|--------------|
| 22 | Canonical Tag Foundation & Mapping Pipeline | CTAG-01..08, QUEUE-02 |
| 23 | Four-Step Initial Sync, Seeding & Queue Split | SEED-01..04, DSYNC-01, QUEUE-01 |
| 24 | Polarity Auto-Reclassification | POL-01..03 |
| 25 | Org Admin Tag Management & Dashboard Polarity | TMGT-01..06, TDASH-01..02 |
| 26 | Superadmin Data Reset & Re-Sync | RESET-01..03 |

## Performance Metrics

**Velocity (v0.3–v0.4 baseline):**

- Total plans completed: 61
- Average duration: ~9 minutes
- Total execution time: ~6.75 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v0.3 avg (phases 10–13) | 37 | ~330m | ~9m |
| v0.4 (phase 14) | 8 | ~72m | ~9m |
| 17 | 4 | - | - |
| 18 | 4 | - | - |
| 22 | 6 | - | - |
| 24 | 2 | - | - |
| Phase 25 P03 | 20 | 3 tasks | 13 files |
| Phase 26 P01 | 34 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Decisions carried forward (relevant to v0.8):

- [v0.8]: Tag-merge progress uses HTTP polling, NOT a new WebSocket consumer — keeps Channels surface narrow per §13.2
- [v0.8]: Superadmin data reset is a hard wipe — deliberate one-time pre-production exception to §11 soft-delete rule
- [v0.8 reconciliation]: Tags are the relational `ReviewTag` model (not JSONB); no `canonical_tag_id` exists today — canonical mapping attaches as a nullable FK on `ReviewTag`; new `OrgCanonicalTag` model carries a direct `organisation` FK
- [v0.8 reconciliation]: Canonical lookup/insert folds into the existing single GPT call + post-enrichment `ReviewTag` write inside enrichment.py's existing `transaction.atomic()`; exactly one `AiUsageLog` row per call — never a separate GPT call for mapping
- [v0.4]: Cache key MUST include `accessible_shop_ids` hash — cross-user cache isolation (DASH-C1)
- [v0.4]: `IsOrgScoped` used on APIView directly, not TenantScopedViewSet — for pure-read views
- [Phase ?]: emitToast uses {kind, title, msg} not {kind, title, body} — matched actual lib/toast.ts signature

### Pending Todos

None.

### Blockers/Concerns

- Phase 8 (carried forward): GBP API production approval from Google is a non-code prerequisite for production launch.
- [v0.8]: Queue split (QUEUE-01) touches deploy config in multiple places — routes, `CELERY_QUEUE_NAMES`, worker `-Q`, queue-depth metric; plan Phase 23 with that breadth in mind.

## Session Continuity

Last session: 2026-06-24T07:24:19.832Z
Stopped at: Phase 25 UI-SPEC approved
Resume file: None
