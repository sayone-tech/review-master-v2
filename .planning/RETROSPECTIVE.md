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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
| --------- | ------ | ----- | ---------- |
| v1.0 | 5 | 24 | Initial GSD workflow established |
| v0.2-org-admin | 4 | 17 | TenantScopedViewSet base established; React CustomEvent bus pattern for modals |

### Cumulative Quality

| Milestone | Tests | Requirements | Notes |
| --------- | ----- | ------------ | ----- |
| v1.0 | ~200 | 52/52 | Superadmin control plane |
| v0.2-org-admin | 438 | 57/57 | Org Admin operational layer |

### Top Lessons (Verified Across Milestones)

1. Establish shared test fixtures and base classes in the first phase of a milestone — all subsequent phases inherit them for free
2. Gap-closure plans are acceptable but scope decisions made before implementation are cheaper
3. GSD disk artifacts (PLAN.md, SUMMARY.md) must be created for every plan regardless of execution style
