---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
stopped_at: "Completed 06-02-PLAN.md"
last_updated: "2026-04-27T11:22:00Z"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 5
  completed_plans: 2
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27)

**Core value:** Organisation Admins can manage their Shops, Regions, and Team — the operational layer built on top of the Superadmin control plane.
**Current focus:** Phase 06 — org-admin-shell

## Current Position

Phase: 06 (org-admin-shell) — EXECUTING
Plan: 3 of 5 (plans 01-02 complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 2
- Average duration: 7.5 minutes
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 6. Org Admin Shell | 2/5 | 15m | 7.5m |
| 7. Regions | 0/3 | - | - |
| 8. Shops | 0/5 | - | - |
| 9. Team | 0/5 | - | - |

**Recent Trend:**

- Last 5 plans: 06-01 (9m), 06-02 (6m)
- Trend: improving

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

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

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8: GBP API production approval from Google is a non-code prerequisite for production launch (code can be built and tested against sandbox first).
- Phase 6: django-sequences Django 6 compatibility RESOLVED — smoke test passed (Plan 02). No blocker.

## Session Continuity

Last session: 2026-04-27T11:22:00Z
Stopped at: Completed 06-02-PLAN.md
Resume file: .planning/phases/06-org-admin-shell/06-03-PLAN.md
