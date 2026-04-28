---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Phase 8 context gathered
last_updated: "2026-04-28T08:14:08.656Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27)

**Core value:** Organisation Admins can manage their Shops, Regions, and Team — the operational layer built on top of the Superadmin control plane.
**Current focus:** Phase 07 — regions

## Current Position

Phase: 07 (regions) — EXECUTING
Plan: 3 of 3

## Performance Metrics

**Velocity:**

- Total plans completed: 4
- Average duration: 8.75 minutes
- Total execution time: 0.58 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 6. Org Admin Shell | 4/5 | 35m | 8.75m |
| 7. Regions | 0/3 | - | - |
| 8. Shops | 0/5 | - | - |
| 9. Team | 0/5 | - | - |

**Recent Trend:**

- Last 5 plans: 06-01 (9m), 06-02 (6m), 06-03 (15m), 06-04 (5m)
- Trend: stable

*Updated after each plan completion*
| Phase 06 P05 | 503 | 1 tasks | 4 files |
| Phase 07-regions P01 | 3 | 2 tasks | 11 files |
| Phase 07 P03 | 3 | 2 tasks | 12 files |
| Phase 07-regions P02 | 6 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- 06-03: Legacy /admin/org-dashboard/ keeps name org_admin_dashboard; new alias /admin/org/dashboard/ gets org_admin_dashboard_v02 — avoids reverse() collision in invite_accept_view
- 06-03: Role override wins over next= param for SUPERADMIN and ORG_ADMIN — deterministic landing pages, no open-redirect risk
- 06-03: org_stub_view uses @org_admin_required (403 for wrong roles); dashboard view has separate custom redirect logic
- 06-02: IsOrgScoped lives in apps/common (not apps/accounts) — cross-cutting role, applies to both ORG_ADMIN and STAFF_ADMIN
- 06-02: org_admin_required returns HttpResponseForbidden (not redirect) for wrong-role users — prevents silent 302 masking auth failures
- 06-02: TenantScopedViewSet returns qs.none() when user has no organisation_id — safe default prevents full-table exposure
- 06-02: django-sequences HIGH compatibility CONFIRMED — smoke test passed against Django 6 + test DB; SequenceCounter fallback not needed
- 06-02: Phase 7-9 tests must explicitly import from apps.common.tests.fixtures — conftest auto-discovers only within apps/common/tests/
- 06-01: django-fernet-encrypted-fields==0.4.0 installed; EncryptedTextField requires null=True for empty-string compatibility
- 06-01: Django 6 renamed CheckConstraint check= to condition=
- 06-01: All 3 tasks committed as single atomic commit (pre-commit mypy hook requires app modules to exist)
- v0.2 init: django-fernet-encrypted-fields==0.3.1 replaces abandoned django-cryptography (no Django 6 support)
- v0.2 init: django-sequences==3.0 needs Django 6 smoke test in Phase 6; select_for_update() fallback ready
- v0.2 init: Cross-Origin-Opener-Policy override scoped to OAuth initiation view only — global same-origin stays
- v0.2 init: InvitationToken expand-contract 3-step: Phase 6 (add purpose column), Phase 9 (backfill + non-null), post-v0.2 (rename)
- v0.2 init: StaffAccessScope lives in apps/accounts to avoid circular imports with regions/shops apps
- [Phase 06-04]: org-less ORG_ADMIN now returns 403 (was redirect to /login/) — aligns with CONTEXT.md wrong-role spec
- [Phase 06-04]: Banner check uses Region.objects.filter(organisation=...).exists() not .count() — short-circuits at first row
- [Phase 06-04]: first_name extracted via user.full_name.split()[0] with fallback to user.email.split('@')[0] when blank/whitespace-only
- [Phase 06-05]: @org_admin_required alone used on org profile views — does not stack with @login_required (decorator wraps it internally)
- [Phase 06-05]: org_profile.html differs from profile.html in exactly 3 lines: extends + 2 url tags — zero business-logic duplication, both call the same services
- [Phase 07-regions]: 07-01: RegionFactory.region_id uses RGN{n:03d} (no hyphen) — matches [A-Z0-9]{2,10} UniqueConstraint
- [Phase 07-regions]: 07-01: perform_create/perform_update return Region instance (not None) — avoids re-fetch, enables RegionReadSerializer response in 201/200
- [Phase 07-regions]: 07-01: RegionViewSet uses GenericViewSet + mixins (not ModelViewSet) — only list/create/partial_update/destroy exposed
- [Phase 07-03]: DataTable uses accessor/label/rowKey API (not render/header) — adapted plan spec to real component interface
- [Phase 07-03]: emitToast uses kind (not type) and msg (not message) — corrected from plan spec to match actual lib/toast.ts API
- [Phase 07-03]: Delete-blocked popup uses plain Modal with amber icon block (not ConfirmModal) — single Got it button, ConfirmModal forces two-button footer
- [Phase 07-03]: 409-as-data: deleteRegion returns RegionBlockedError object instead of throwing — caller type-guards to decide amber vs red popup
- [Phase 07-regions]: 07-02: test_no_save_when_no_changes asserts 2 queries (SAVEPOINT + RELEASE) not 0 — @transaction.atomic overhead inside test outer transaction
- [Phase 07-regions]: 07-02: two_orgs_two_admins fixture returns dict — tests use ['org_a'] key access not positional tuple destructuring
- [Phase 07-regions]: 07-02: conftest.py created in apps/regions/tests/ to re-export assert_query_ceiling and two_orgs_two_admins for auto-discovery

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8: GBP API production approval from Google is a non-code prerequisite for production launch (code can be built and tested against sandbox first).
- Phase 6: django-sequences Django 6 compatibility RESOLVED — smoke test passed (Plan 02). No blocker.

## Session Continuity

Last session: 2026-04-28T08:14:08.648Z
Stopped at: Phase 8 context gathered
Resume file: .planning/phases/08-shops/08-CONTEXT.md
