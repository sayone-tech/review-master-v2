---
gsd_state_version: "1.0"
milestone: v0.9
milestone_name: AI Reply Credits
status: Awaiting next milestone
stopped_at: Completed 33-07-PLAN.md
last_updated: "2026-11-12T08:53:26.108Z"
last_activity: 2026-11-12
last_activity_desc: Milestone v0.9 completed and archived
state_head: 49de712a942afca458875ff19da82aa6b0c9d538
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 23
  completed_plans: 23
  percent: 100
current_phase: 33
current_phase_name: Credit Visibility & Staff Scoping
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-12)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — and AI reply spend is capped by a visible per-shop monthly credit budget that Superadmin controls.
**Current focus:** Planning next milestone (mobile app). Start with `/gsd-new-milestone`.

## Current Position

Phase: Milestone v0.9 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-11-12 — Milestone v0.9 completed and archived

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
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 29 P01 | 9 min | 3 tasks | 23 files |
| Phase 29 P02 | 22 min | 2 tasks | 10 files |
| Phase 29 P03 | 35 min | 3 tasks | 8 files |
| Phase 29 P04 | 8 min | 2 tasks | 3 files |
| Phase 30 P01 | 28 min | 2 tasks | 9 files |
| Phase 30 P02 | 14 min | 2 tasks | 7 files |
| Phase 30 P03 | 35min | 2 tasks | 6 files |
| Phase 30 P04 | 25 min | 3 tasks | 5 files |
| Phase 31 P01 | 10 min | 3 tasks | 14 files |
| Phase 31 P02 | 12 min | 3 tasks | 11 files |
| Phase 31 P03 | 8 min | 3 tasks | 3 files |
| Phase 32 P01 | 30 min | 3 tasks | 10 files |
| Phase 32 P02 | 11 min | 3 tasks | 11 files |
| Phase 32 P03 | 25 min | 3 tasks | 10 files |
| Phase 32 P04 | 25 min | 3 tasks | 9 files |
| Phase 32 P05 | 9 min | 3 tasks | 6 files |
| Phase 33 P01 | 8 min | 3 tasks | 6 files |
| Phase 33 P33-02 | 6 min | 3 tasks | 8 files |
| Phase 33 P03 | 6 min | 3 tasks | 12 files |
| Phase 33 P04 | 20 min | 3 tasks | 9 files |
| Phase 33 P05 | 15 min | 3 tasks | 6 files |
| Phase 33 P06 | 12 min | 3 tasks | 13 files |
| Phase 33 P07 | 25 min | 3 tasks | 4 files |

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
- [Phase 29]: Organisation.monthly_credit_allocation is IntegerField (not Positive) to avoid Coalesce mixed-type FieldError; shop/org FKs on credits models use db_index=False (composite indexes lead)
- [Phase 29]: 29-02: Ledger append-only enforced in app layer; single status CAS (RESERVED->COMMITTED/REFUNDED) via ledger.transition_status/cas_status, callers pinned by source-scan test
- [Phase 29]: credit_cost is the single pricing source; settings test scans that only credit_cost.py and base.py reference REVIEWBEE_CREDIT_TIERS
- [Phase 29]: Balance selectors use FilteredRelation + Coalesce (1 query for any list size) and never write; unmaterialised shops report live org allocation
- [Phase 30]: 30-01: D-14 ledger link written inside the same CAS UPDATE; no D-12 partial index (balance-row lock serialises in-flight check); late commit re-deducts only REFUNDED + current month + no LAPSED + capacity
- [Phase 30]: Reply path bounded by with_options copy (30s/1 retry); moderation block exception carries only stage and AiUsageLog id; Plan 30-03 must pass timeout/max_retries to both reply-path moderation calls
- [Phase 30]: 30-03: output-stage moderation block consumes, every other non-success outcome refunds; 400/409 bodies carry only {code, detail}, 402 is {code, reason, required, remaining}
- [Phase 30]: 30-04: Postgres races (N vs K, cost 2/3, mixed refunds, same review, commit vs refund, client abort) all pass on PG14 with no production change
- [Phase 31]: lapsed_at marker (not ledger row) is the lapse done-flag; zero-remaining balances are marked with no LAPSED/AuditLog row; late commit reads the marker (D-01/D-02)
- [Phase 31]: Reaper is CAS-only: no skip_locked pre-select and no outer transaction; refund_reservation's per-row CAS arbitrates races with late commits and other reaper runs
- [Phase 31]: Reaper refund that cannot apply (RuntimeError) raises an ids-only Sentry error, leaves the row RESERVED and the balance unlapsed; no quarantine column
- [Phase 31]: 31-03: race tests accept either winner but force both orderings each run (odd-round 3 ms committer delay); no production change needed on Postgres
- [Phase 32]: organisation.credits.set audit: entity_type organisation, after_data {monthly_credit_allocation, effective, shops_touched, period_year, period_month}; create audits only when > 0
- [Phase 32]: Credits hint keys on current_month_credit_allocation (D-21); Create/Edit org forms use noValidate so the inline 0-10,000 error shows; Edit sends monthly_credit_allocation only when changed
- [Phase 32]: Bonus order: period echo 409 (read-only) -> 404 availability -> one atomic (org lock, ensure_balance, balance lock, F() increment, ledger, audit); reason only in CreditTransaction.note
- [Phase 32]: 32-04: 409 period_mismatch applies server balance/period, reloads, keeps typed values and requires a fresh Allocate click; 404 toast copy is D-23 'This shop is no longer active.'
- [Phase 32]: Lock the organisation row FOR NO KEY UPDATE (no_key=True) in update_organisation and allocate_bonus: plain FOR UPDATE deadlocks against a concurrent first-use balance insert FK KEY SHARE (proven on PostgreSQL)
- [Phase 33]: 33-01: get_accessible_shop_for_credits lives in apps/shops (built on list_shops) to keep apps/credits free of apps.reviews imports; Staff scoping keyed off role, not id-list truthiness
- [Phase 33]: 33-02: Credit audit events reach Org Admins via a separate CREDIT_AUDIT_FILTER (Staff selector and shared AUDIT_ENTITY_FILTER untouched); shop_name is an entity_type-gated, org-bounded, text-compared subquery; Superadmin actor names visible to Org Admins accepted (open question 2)
- [Phase 33]: formatUtcDate reuses creditHint.ts month names (Sep) rather than en-GB locale formatting
- [Phase 33]: Balance store keyed by shop_id is a module-level useSyncExternalStore store shared across React roots
- [Phase 33]: 33-04: ShopCreditsView lives in apps/credits at /api/v1/shops/<id>/credits/, gated by get_accessible_shop_for_credits; uniform 404 shop_not_found, no-store, shop_credits 120/minute
- [Phase 33]: 33-05: composer cost only from the server; a 402 keeps the draft and switches the composer state in place (no banner)
- [Phase 33]: 33-06: CreditsCard keys results by shopId and treats another shop's outcome as loading; stacked Buy More is a sibling modal with Shop Details dismissible=false while open; credit dates use formatUtcDate (Sep, not Sept)
- [Phase 33]: 33-07: section 27 reviews run inline (Agent tool unavailable); Superadmin actor names, Staff list scoping and D-17 accepted; ReviewTargetViewSet Staff scoping and allocation_status/has_regions recorded as follow-ups

### Pending Todos

None.

### Blockers/Concerns

- Phase 8 (carried forward): GBP API production approval from Google is a non-code prerequisite for production launch.
- [v0.9 rollout]: Default allocation 0 disables AI replies for every existing org on deploy — Superadmin must set allocations at deploy time per the CQA-02 deploy note; the 402 gate must not reach production without it.
- [v0.9 Phase 30]: Research flags — client-disconnect settlement under Daphne, reply-path `with_options` timeout vs LangSmith wrapper, late-commit policy. Mandatory `ai-enrichment-specialist` review.
- [v0.9 Phase 32]: Superadmin shop-credits surface has no precedent (no Superadmin Shop Details screen) — largest scope risk; UI-SPEC first.
- [v0.9 Phase 33]: Activity Log Staff-scoping change not verified in depth; `list_shops` Staff scoping is a behaviour change. Mandatory `tenant-security-auditor` + `orm-performance-auditor`.
- [v0.9 Phase 31]: Beat "lapse not complete by 00:30 UTC" alert is infra outside this repo — flag to deployment owner.

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| debug_sessions | action-item-category-all-other | diagnosed | 2026-11-12 | v0.9 |
| debug_sessions | docker-compose-startup | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | duplicate-notifications-fruitbae | fixing | 2026-11-12 | v0.9 |
| debug_sessions | enrichment-progress-stuck | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | fixes-not-taking-effect | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | mobile-sidebar-hamburger-no-open | investigating | 2026-11-12 | v0.9 |
| debug_sessions | notification-sync-bugs | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | oauth-popup-no-listing-picker | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | org-admin-ui-three-bugs | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | regions-ui-404-bundle | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | regions-ui-design-mismatch | awaiting_human_verify | 2026-11-12 | v0.9 |
| debug_sessions | regions-ui-empty-state-missing | verifying | 2026-11-12 | v0.9 |
| quick_tasks | 260424-n33-rebrand-frontend-to-review-bee-with-new- | unknown | 2026-11-12 | v0.9 |
| uat_gaps | 01/01-UAT.md | diagnosed, 0 pending | 2026-11-12 | v0.9 |
| uat_gaps | 14/14-UAT.md | testing, 10 pending | 2026-11-12 | v0.9 |
| uat_gaps | 23/23-HUMAN-UAT.md | partial, 0 pending | 2026-11-12 | v0.9 |
| uat_gaps | 25/25-HUMAN-UAT.md | partial, 6 pending | 2026-11-12 | v0.9 |
| uat_gaps | 29/29-UAT.md | testing, 1 pending | 2026-11-12 | v0.9 |
| uat_gaps | 30/30-UAT.md | testing, 3 pending | 2026-11-12 | v0.9 |
| uat_gaps | 31/31-UAT.md | testing, 3 pending | 2026-11-12 | v0.9 |
| uat_gaps | 32/32-UAT.md | testing, 4 pending | 2026-11-12 | v0.9 |
| uat_gaps | 33/33-UAT.md | testing, 5 pending | 2026-11-12 | v0.9 |
| verification_gaps | 01/01-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 11/11-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 13/13-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 19/19-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 21/21-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 23/23-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 25/25-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 26/26-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 29/29-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 30/30-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 31/31-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 32/32-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| verification_gaps | 33/33-VERIFICATION.md | human_needed | 2026-11-12 | v0.9 |
| deferred_items | 13/deferred-items.md: Out-of-Scope Discovery (during 13-01 execution) - apps/notifications/m | acknowledged | 2026-11-12 | v0.9 |

## Session Continuity

Last session: 2026-11-11T19:52:28.852Z
Stopped at: Completed 33-07-PLAN.md
Resume file: None

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
