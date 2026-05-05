# Project Retrospective

A living document updated after each milestone. Lessons feed forward into future planning.

---

## Milestone: v0.2-org-admin — Organisation Admin Module

**Shipped:** 2026-04-30
**Phases:** 4 (6–9) | **Plans:** 17 | **Timeline:** 3 days
**Files:** 248 changed | **Insertions:** 34,438 | **Tests:** 438 passing

### What Was Built

- Org Admin shell — 6-item sidebar, personalised dashboard, profile reuse, tenant security scaffold (TenantScopedViewSet + IsOrgScoped)
- Regions CRUD — race-safe auto-ID generation (django-sequences), deletion guard when shops assigned
- Shops — Google OAuth popup flow with COOP/Safari/Redis-polling fallback, Fernet-encrypted tokens, allocation enforcement, searchable listing picker
- Team — invite/edit/enable/disable/remove with Manager/Staff scoping, self-protection, last-manager guard, 5 production email templates
- Cross-module guards — deactivated shops excluded from Staff scope selectors, allocation counter transactional under concurrent sessions

### What Worked

- Services/selectors pattern kept views thin and business logic easily testable across all 4 phases
- TenantScopedViewSet established in Phase 6 paid off immediately — Phases 7–9 got cross-tenant isolation for free
- Gap-closure plans (08-06, 08-07) were the right call: shipping MANUAL connection method first, then removing it cleanly, was faster than designing it out upfront
- django-sequences smoke test in Phase 6 resolved the only blocking unknown before Regions work started
- CustomEvent bus pattern for React modal orchestration scaled cleanly across Shops and Team widgets without prop-drilling

### What Was Inefficient

- Phase 7 plan/summary files were not created in the `.planning/phases/07-regions/` directory — Regions work was executed without GSD tracking artifacts, causing gsd-tools to report 0 plans for the phase
- ROADMAP checkbox state drifted from disk reality (07-01, 07-03 marked [x] in ROADMAP but no files on disk)
- MANUAL shop connection method was designed and partially implemented before being removed — the scope decision could have been made earlier

### Patterns Established

- `conftest.py` re-exporting shared fixtures from `apps.common.tests.fixtures` required in every app's test directory for auto-discovery
- `to_attr='prefetched_scopes'` pattern for StaffAccessScope prefetch avoids shadowing the relation manager with a plain list
- 409-as-data pattern for blocked deletions: service returns a typed error object instead of raising, caller type-guards to choose the correct popup variant
- Per-view COOP header override for OAuth views — global `same-origin` policy untouched in production settings

### Key Lessons

1. Always create GSD plan/summary files even for phases executed outside the formal plan workflow — gsd-tools relies on disk artifacts for progress tracking
2. Scope decisions (include vs. exclude a feature) are cheapest before implementation begins; gap-closure plans work but add overhead
3. django-sequences smoke test as the first plan of the phase that needs it is the right pattern — resolves unknowns before they become blockers mid-phase

---

## Milestone: v0.3 — Reviews and Action Items

**Shipped:** 2026-05-05
**Phases:** 4 (10–13) | **Plans:** 37 | **Timeline:** 4 days
**Requirements:** 77/77

### What Was Built

- Celery + Celery Beat + Channels infrastructure — `google-sync`, `ai-enrichment`, `default` queues; Flower (dev/staging only); Redis distributed lock helper; retry/backoff utilities; Beat seed migration
- Google review fetching — initial backfill (paginated, rate-limited) + 6-hour incremental sync; real-time progress via WebSocket (SyncProgressConsumer); TopbarBell sync indicator with stage-aware state (fetching → enriching); reply submission to Google with 409/502 error mapping
- AI enrichment pipeline — GPT-4o-mini single-prompt JSON; AiUsageLog + time-versioned AiPricing; LangSmith tracing (best-effort); cost calculator locked at write time; three-layer idempotency; skip path for comment-less reviews (no OpenAI call, no cost row)
- Action Items — AI promotion via `bulk_create(ignore_conflicts=True)` with partial unique constraint; manual creation; brand/shop scoping with Staff exclusion enforced at selector + permission + UI layers; status workflow (open → in_progress → resolved/dismissed); assignment with AuditLog; notes; ≤5 query budget on list
- Notification bell — HTTP polling (60s); CustomEvent bridge (`notifications:refresh`) for immediate post-sync update; unread count + popover; mark-read / mark-all-read; `transaction.on_commit` dispatch hooks (never fire on rollback)

### What Worked

- Three-layer idempotency pattern (Redis lock + status flag + `select_for_update`) proved robust — enrichment retries and concurrent workers never caused duplicate OpenAI calls or double-billing
- Keeping Channels surface to a single consumer (SyncProgressConsumer) made the real-time layer easy to audit; notification bell deliberately uses HTTP polling per mandate
- `transaction.on_commit` for all notification dispatch eliminated phantom rows during rollbacks — cleaner than signal-based dispatch
- CustomEvent bridge between two React roots (TopbarBell ↔ NotifBell) was the minimal-coupling solution without introducing a shared state store
- Thin Celery task wrappers over service functions kept background job logic fully testable without a worker

### What Was Inefficient

- STATE.md decision log accumulated 100+ entries during the milestone — individual decision granularity useful during execution, but hard to scan in retrospective; Key Decisions table in PROJECT.md is the right long-term home
- sync.complete responsibility moved from sync.py to enrichment.py mid-milestone (Phase 12) — the emitter boundary should have been decided in Phase 10 planning when the Channels consumer was first added
- `v0.3-REQUIREMENTS.md` had 7 stale unchecked checkboxes at milestone close — all were implemented but requirement status tracking drifted; verify checkbox state during each phase summary, not only at milestone end

### Patterns Established

- `transaction.on_commit` wrapping all side-effect dispatch (notifications, events) — prevents phantom rows; adopt for all future lifecycle hooks
- Single combined GPT prompt per review returning structured JSON — no multi-call chains; token-efficient and cost-predictable
- `enrichment_version` incremented on both SUCCESS and FAILURE — doubles as attempt counter for Beat-scheduled retry cap
- Partial unique constraint `WHERE source=AI` for AI-promoted action items — enables safe idempotent `bulk_create(ignore_conflicts=True)` without touching manually-created rows

### Key Lessons

1. Define the WebSocket event emitter boundary (which service sends `sync.complete`) in the Phase 10 infrastructure plan — not discoverable mid-enrichment phase
2. Requirement checkbox drift happens when plan summaries skip the requirements audit step — add an explicit requirements-updated checkpoint to the phase summary template
3. Skip paths (comment-less review → no OpenAI call) must be placed AFTER the idempotency status flip so the guard protects the skip path identically to the main path

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
| --------- | ------ | ----- | ---------- |
| v1.0 | 5 | 24 | Initial GSD workflow established |
| v0.2-org-admin | 4 | 17 | TenantScopedViewSet base established; React CustomEvent bus pattern for modals |
| v0.3 | 4 | 37 | Celery/Channels infra; AI pipeline; on_commit dispatch pattern; CustomEvent inter-root bridge |

### Cumulative Quality

| Milestone | Tests | Requirements | Notes |
| --------- | ----- | ------------ | ----- |
| v1.0 | ~200 | 52/52 | Superadmin control plane |
| v0.2-org-admin | 438 | 57/57 | Org Admin operational layer |
| v0.3 | TBD | 77/77 | Reviews, AI enrichment, Action Items, notifications |

### Top Lessons (Verified Across Milestones)

1. Establish shared test fixtures and base classes in the first phase of a milestone — all subsequent phases inherit them for free
2. Gap-closure plans are acceptable but scope decisions made before implementation are cheaper
3. GSD disk artifacts (PLAN.md, SUMMARY.md) must be created for every plan regardless of execution style
4. Requirement checkbox state drifts — verify against implementation at each phase summary, not only at milestone end
5. Side-effect dispatch (notifications, events) must use `transaction.on_commit` — signals fire pre-commit and create phantom rows on rollback
