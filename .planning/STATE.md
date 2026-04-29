---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Completed 08-05-PLAN.md
last_updated: "2026-04-29T14:02:33.601Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 12
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-27)

**Core value:** Organisation Admins can manage their Shops, Regions, and Team — the operational layer built on top of the Superadmin control plane.
**Current focus:** Phase 08 — shops

## Current Position

Phase: 08 (shops) — EXECUTING
Plan: 7 of 7

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: 9.5 minutes
- Total execution time: 0.96 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 6. Org Admin Shell | 4/5 | 35m | 8.75m |
| 7. Regions | 0/3 | - | - |
| 8. Shops | 1/5 | 12m | 12m |
| 9. Team | 0/5 | - | - |

**Recent Trend:**

- Last 5 plans: 06-01 (9m), 06-02 (6m), 06-03 (15m), 06-04 (5m)
- Trend: stable

*Updated after each plan completion*
| Phase 06 P05 | 503 | 1 tasks | 4 files |
| Phase 07-regions P01 | 3 | 2 tasks | 11 files |
| Phase 07 P03 | 3 | 2 tasks | 12 files |
| Phase 07-regions P02 | 6 | 2 tasks | 5 files |
| Phase 08-shops P01 | 739 | 3 tasks | 12 files |
| Phase 08-shops P02 | 6 | 3 tasks | 12 files |
| Phase 08-shops P03 | 23 | 2 tasks | 9 files |
| Phase 08-shops P04 | 15 | 2 tasks | 14 files |
| Phase 08-shops P05 | 12 | 3 tasks | 12 files |
| Phase 08-shops P06 | 28 | 4 tasks | 13 files |

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
- [Phase 08-shops]: 08-01: _setting() helper with getattr+cast used instead of direct settings.ATTR — avoids django-stubs attr-defined errors on custom GOOGLE_OAUTH_* settings
- [Phase 08-shops]: 08-01: TOKEN_ENDPOINT constant name triggers bandit B105 + ruff S105 false positives — suppressed with # noqa: S105  # nosec B105
- [Phase 08-shops]: 08-01: Django override_settings cannot decorate plain pytest classes — applied per-method in oauth tests
- [Phase 08-shops]: 08-01: Pre-commit mypy hook requires httpx + tenacity in additional_dependencies to avoid import errors
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
- [Phase 08-shops]: 08-02: SQLite test DB omits FOR UPDATE in SQL — select_for_update test asserts organisations table queried (source code is authoritative)
- [Phase 08-shops]: 08-02: ShopFactory.region changed from None to SubFactory(RegionFactory) — matches production data shape, tests create fully-linked shops by default
- [Phase 08-shops]: 08-02: pytest.raises(ValueError, match=...) required to satisfy PT011 ruff rule on broad ValueError raises
- [Phase 08-shops]: 08-03: ShopViewSet includes RetrieveModelMixin so GET /api/v1/shops/{id}/ returns 404 on cross-tenant (not 405)
- [Phase 08-shops]: 08-03: Test API keys extracted to module-level constants with # gitleaks:allow to pass secret scanner
- [Phase 08-shops]: 08-03: ShopUpdateSerializer LOCKED_FIELDS validate() raises field errors (not silently drops extra fields)
- [Phase 08-shops]: 08-03: Redis best-effort in OAuth callback: postMessage is primary path, Redis failure is non-fatal
- [Phase 08-shops]: 08-04: Inline hex colours used in ConnectionStatusPill and status badge — Tailwind JIT cannot generate dynamic class names from ternary expressions
- [Phase 08-shops]: 08-04: vi.stubGlobal replaces global.fetch in Vitest tests — browser lib tsconfig mode doesn't define global; vi.stubGlobal is the idiomatic Vitest pattern
- [Phase 08-shops]: 08-04: ShopTable CustomEvent bus: 7 events dispatched (shop:open-{details,edit,deactivate,activate,reveal-key,rotate-key,reconnect}); Plan 08-05 subscribes
- [Phase 08-shops]: act() from @testing-library/react required when dispatching CustomEvents that trigger React state in tests — plain dispatchEvent causes act() warnings and test failures
- [Phase 08-shops]: 08-05: ShopModals seeds regions from template context (shop_list view adds regions_json via list_regions + RegionReadSerializer) — avoids extra API call on modal open
- [Phase 08-shops]: 08-06: ShopAuditLog model + Action enum (API_KEY_REVEALED/API_KEY_ROTATED) retained at ORM level — table frozen in place, no service writes after this plan, avoids no-op migration
- [Phase 08-shops]: 08-06: api_key removed from ShopUpdateSerializer LOCKED_FIELDS — column gone, DRF silently ignores undeclared fields for removed columns
- [Phase 08-shops]: 08-06: REQUIREMENTS.md uses [~] status + RETIRED datestamp for retired (not deleted) requirements SHOP-10/19/20

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8: GBP API production approval from Google is a non-code prerequisite for production launch (code can be built and tested against sandbox first).
- Phase 6: django-sequences Django 6 compatibility RESOLVED — smoke test passed (Plan 02). No blocker.

## Session Continuity

Last session: 2026-04-29T14:31:25Z
Stopped at: Completed 08-06-PLAN.md
Resume file: None
