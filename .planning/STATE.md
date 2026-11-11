---
gsd_state_version: "1.0"
milestone: v0.9
milestone_name: AI Reply Credits
current_phase: 29
current_phase_name: Credits Ledger Foundation
status: planning
stopped_at: Phase 29 context gathered
last_updated: "2026-11-11T11:37:59.533Z"
last_activity: 2026-11-11
last_activity_desc: v0.9 roadmap created; 5 phases (29–33), 27/27 requirements mapped
state_head: 1aca7f3354a498b8ae8c197e9e8957c4336e5649
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 3
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-11)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — and AI reply spend is capped by a visible per-shop monthly credit budget that Superadmin controls.
**Current focus:** v0.9 AI Reply Credits — roadmap created (Phases 29–33); next step is `/gsd-discuss-phase 29` or `/gsd-plan-phase 29`.

## Current Position

Phase: 29 (Credits Ledger Foundation) — READY TO EXECUTE
Plan: —
Status: Roadmap created, awaiting phase planning
Last activity: 2026-11-11 — v0.9 roadmap created; 5 phases (29–33), 27/27 requirements mapped

### v0.9 phase map (Phases 29–33)

| Phase | Name | Requirements | Depends on | UI contract |
|-------|------|--------------|------------|-------------|
| 29 | Credits Ledger Foundation | CRED-02..05, CQA-01 | Phase 27 (v0.8) | — |
| 30 | Metered AI Reply Generation | CCON-01..08, CQA-02 | 29 | — (backend only) |
| 31 | Monthly Renewal & Reservation Reaper | CREN-01..03 | 30 | — |
| 32 | Superadmin Credit Controls | CRED-01, CRED-06, CSUP-01..02 | 29 | `/gsd-ui-phase 32` |
| 33 | Credit Visibility & Staff Scoping | CVIS-01..05, SCOPE-01 | 30, 32 | `/gsd-ui-phase 33` |

**Dependency waves:** A: 29 → B: 30 ∥ 32 → C: 31 ∥ 33. Numeric order 29 → 33 is a valid sequential fallback.
**Model split:** planning/discuss on Opus; execution (`gsd-executor`, `gsd-debugger`, `gsd-doc-writer`) on latest Sonnet, via `.planning/config.json` `models`.

### v0.8 phase map (Phases 22–27) — SHIPPED 2026-06-30

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 22 | Canonical Tag Foundation & Mapping Pipeline | CTAG-01..08, QUEUE-02 | ✅ Complete |
| 23 | Four-Step Initial Sync, Seeding & Queue Split | SEED-01..04, DSYNC-01, QUEUE-01 | ✅ Complete |
| 24 | Polarity Auto-Reclassification | POL-01..03 | ✅ Complete |
| 25 | Org Admin Tag Management & Dashboard Polarity | TMGT-01..06, TDASH-01..02 | ✅ Complete |
| 26 | v0.8 Post-UAT Polish & Sync Fixes | TMGT-07/08, SEED-05/06, NAV-01 | ✅ Complete |
| 27 | Sync Progress Reliability | SYNC-REL-01/02 | ✅ Complete |
| 28 | Superadmin Data Reset & Re-Sync | RESET-01..03 | ⏸ Deferred (pre-launch) |

## Performance Metrics

**Velocity (v0.3–v0.4 baseline):**

- Total plans completed: 63
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
| Phase 27-sync-progress-reliability P01 | 45m | 2 tasks | 8 files |
| 27 | 2 | - | - |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Decisions for v0.9 (AI Reply Credits):

- [v0.9 roadmap]: Coarse granularity — research's six-phase plan compressed to five: Read API + Org Admin/Staff frontend merged into one vertical slice (Phase 33); Superadmin backend + UI kept together (Phase 32). The consumption core (Phase 30) is never merged with a UI phase.
- [v0.9 roadmap]: `Organisation.monthly_credit_allocation`, `ensure_balance()`, and the virtual-balance selectors land in Phase 29 so Phases 32 and 33 build on them independently; the Superadmin-facing set/audit/UI (CRED-01) is Phase 32.
- [v0.9 roadmap]: CQA-01 (Postgres CI + `pg_concurrency`) lands in Phase 29 with the first-use race test; CCON-02 (Phase 30) and CREN-03 (Phase 31) add their concurrency tests to the same job.
- [v0.9 roadmap]: SCOPE-01 resolves research option (b) — `list_shops` gains real Staff scoping (Staff stop seeing out-of-scope shops), not null-field masking.
- [v0.9]: "Manager" = Org Admin; cost from trimmed `Review.comment`; cost function in `apps/credits/services/credit_cost.py`; BigAutoField PKs; generate-reply throttle stays 10/min; no click-confirmation (cost on button label); refund on OpenAI failure + input-moderation block, consume on output-moderation block; §9.3 shop-switcher badge deferred (CFUT-03).
- [v0.9]: Rollout = deploy note (CQA-02), no backfill — orgs start at 0 credits; Superadmin enables via CRED-06 (0 → N is immediate; N → M applies next month).

Decisions carried forward (from v0.8 and earlier):

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
- [v0.9 rollout]: Default allocation 0 disables AI replies for every existing org on deploy — Superadmin must set allocations at deploy time per the CQA-02 deploy note; the 402 gate must not reach production without it.
- [v0.9 Phase 30]: Research flags — client-disconnect settlement under Daphne, reply-path `with_options` timeout vs LangSmith wrapper, late-commit policy. Mandatory `ai-enrichment-specialist` review.
- [v0.9 Phase 32]: Superadmin shop-credits surface has no precedent (no Superadmin Shop Details screen) — largest scope risk; UI-SPEC first.
- [v0.9 Phase 33]: Activity Log Staff-scoping change not verified in depth; `list_shops` Staff scoping is a behaviour change. Mandatory `tenant-security-auditor` + `orm-performance-auditor`.
- [v0.9 Phase 31]: Beat "lapse not complete by 00:30 UTC" alert is infra outside this repo — flag to deployment owner.

## Session Continuity

Last session: 2026-11-11T10:55:38.138Z
Stopped at: Phase 29 context gathered
Resume file: .planning/phases/29-credits-ledger-foundation/29-CONTEXT.md
