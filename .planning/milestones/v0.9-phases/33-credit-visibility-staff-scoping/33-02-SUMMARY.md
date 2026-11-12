---
phase: 33-credit-visibility-staff-scoping
plan: 02
subsystem: api
tags: [django, drf, audit-log, credits, selectors, react, tenant-scoping]

requires:
  - phase: 21-audit-log-viewer
    provides: AuditLog model, Org/Staff selectors, Activity Log widget
  - phase: 29-credit-balances
    provides: shop.credits.* and organisation.credits.set audit writers
provides:
  - CREDIT_AUDIT_FILTER (Org-Admin-only credit event filter)
  - org-bounded shop_name annotation on list_audit_logs_for_org
  - AuditLogReadSerializer.shop_name (read-only, null default)
  - Activity Log Credits pill, seven credit ACTION_LABEL entries, shop-name Action cell
affects: [33-07]

actuals:
  tokens: 9000
  tasks: 3
  commits: 3

plan_head_before: 81d8dace036ae0d4f1fda5206e4c754fe8e03568
plan_head_after: dd3abc667a760dfcba537fa0e0e4f7a11037f918

tech-stack:
  added: []
  patterns:
    - "Role-specific audit filters: Org-only Q kept out of the constant shared with the Staff selector"
    - "Untyped entity_id resolved via entity_type-gated, org-bounded, text-compared correlated Subquery"

key-files:
  created:
    - frontend/src/widgets/audit-log/AuditLogTable.test.tsx
  modified:
    - apps/common/selectors/audit_logs.py
    - apps/common/serializers.py
    - apps/common/tests/test_audit_log_selectors.py
    - apps/common/tests/test_audit_log_api.py
    - frontend/src/widgets/audit-log/types.ts
    - frontend/src/widgets/audit-log/TypePill.tsx
    - frontend/src/widgets/audit-log/AuditLogTable.tsx

key-decisions:
  - "Credit events reach Org Admins through a separate CREDIT_AUDIT_FILTER used only by list_audit_logs_for_org; AUDIT_ENTITY_FILTER and the Staff selector are untouched"
  - "shop_name is a Case(When(entity_type=shop)) around a correlated Subquery bound to the row's organisation and compared as text, so collisions, other tenants, deleted shops and non-numeric ids all resolve to null without extra queries"
  - "Superadmin actor names on organisation.credits.set rows are visible to Org Admins (research open question 2, accepted, pinned by test); Staff dropdown excludes them"

requirements-completed: [CVIS-05]

coverage:
  - id: D1
    description: "Org Admin GET /api/v1/audit-logs/ returns shop credit rows with shop_name and the Activity Log renders a Credits pill and 'Credits used' with the shop name"
    requirement: CVIS-05
    verification:
      - kind: integration
        ref: "apps/common/tests/test_audit_log_api.py#test_org_admin_sees_credit_consumed_row_with_shop_name"
        status: pass
      - kind: unit
        ref: "frontend/src/widgets/audit-log/AuditLogTable.test.tsx#should render Credits pill and shop name when row is a shop credit event"
        status: pass
    human_judgment: false
  - id: D2
    description: "All seven credit actions for the caller's org only; non-credit shop/organisation rows excluded"
    requirement: CVIS-05
    verification:
      - kind: unit
        ref: "apps/common/tests/test_audit_log_selectors.py#test_list_audit_logs_for_org_includes_all_seven_credit_actions_for_own_org_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "Staff never receive credit rows, including PK collisions with visible reviews and action items (selector and API)"
    requirement: CVIS-05
    verification:
      - kind: unit
        ref: "apps/common/tests/test_audit_log_selectors.py#test_list_audit_logs_for_staff_excludes_credit_rows_even_on_pk_collision"
        status: pass
      - kind: integration
        ref: "apps/common/tests/test_audit_log_api.py#test_staff_api_never_returns_credit_rows_on_pk_collision"
        status: pass
    human_judgment: false
  - id: D4
    description: "shop_name is null for review/action_item collisions, organisation rows, other-tenant shops, deleted shops and non-numeric entity_id"
    requirement: CVIS-05
    verification:
      - kind: unit
        ref: "apps/common/tests/test_audit_log_selectors.py#test_shop_name_resolves_same_org_shop_and_is_null_everywhere_else"
        status: pass
    human_judgment: false
  - id: D5
    description: "Fixed query count: equal for 1 and 20 credit rows and within the <=5 ceiling"
    requirement: CVIS-05
    verification:
      - kind: integration
        ref: "apps/common/tests/test_audit_log_api.py#test_org_admin_credit_rows_query_count_equal_for_1_and_20"
        status: pass
      - kind: unit
        ref: "apps/common/tests/test_audit_log_selectors.py#test_list_audit_logs_for_org_shop_name_query_count_is_fixed"
        status: pass
    human_judgment: false
  - id: D6
    description: "Actor dropdown includes the Superadmin for Org Admin and never for Staff; Type filter whitelist not extended"
    requirement: CVIS-05
    verification:
      - kind: integration
        ref: "apps/common/tests/test_audit_log_api.py#test_actor_dropdown_includes_superadmin_for_org_admin_not_for_staff"
        status: pass
      - kind: integration
        ref: "apps/common/tests/test_audit_log_api.py#test_type_filter_whitelist_is_not_extended_for_credit_types"
        status: pass
    human_judgment: false
  - id: D7
    description: "UI matrix: seven labels, Credits pill for shop and organisation, Shop #id fallback, label-only organisation row, raw-action fallback, long names wrap, System actor"
    requirement: CVIS-05
    verification:
      - kind: unit
        ref: "frontend/src/widgets/audit-log/AuditLogTable.test.tsx"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-11-12
status: complete
---

# Phase 33 Plan 02: Credit events in the Org Admin Activity Log Summary

**Org Admins now see shop.credits.* and organisation.credits.set events in the Activity Log with a Credits pill and the shop's name, through an Org-only audit filter and an org-bounded shop_name subquery; Staff receive none.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-11-11T19:25Z
- **Tasks:** 3 (tracer, backend matrix, UI matrix)
- **Files modified:** 8 (1 created)

## Accomplishments
- `CREDIT_AUDIT_FILTER` is used only by `list_audit_logs_for_org`; `AUDIT_ENTITY_FILTER` and `list_audit_logs_for_staff` are unchanged, so Staff cannot receive credit rows even when an `entity_id` collides with a visible review or action item PK.
- `shop_name` is one correlated subquery in the same SELECT, gated on `entity_type="shop"`, bound to the row's own organisation and compared as text; 1 and 20 credit rows cost the same number of queries (selector issues 1 query).
- `AuditLogReadSerializer.shop_name` is read-only with a null default, so Staff rows serialise null.
- UI: Credits pill (neutral) for `shop` and `organisation`, seven credit labels, shop suffix in `text-muted break-words` with the `Shop #{id}` fallback, organisation row label-only.

## Task Commits

1. **Task 1: Tracer, credit row end to end** - `04a15a4` (feat)
2. **Task 2: Backend matrix** - `c123a5b` (test)
3. **Task 3: UI matrix** - `dd3abc6` (test)

## Decisions Made
See key-decisions. Task 2 and Task 3 needed no production-code change beyond Task 1; the Task 1 implementation satisfied the full behaviour matrix.

## Deviations from Plan

None - plan executed exactly as written. `apps/common/views.py` and `apps/common/filters.py` are unchanged; the actor dropdown behaved as the behaviour list specified, so nothing needs hand-off beyond the accepted-risk note below.

## Issues Encountered
None.

## Note for Plan 33-07 (tenant-security-auditor disposition)
Open question 2 is accepted and pinned: an Org Admin's actor dropdown and credit rows can show the Superadmin's name on `organisation.credits.set`; Staff dropdown never includes them (`test_actor_dropdown_includes_superadmin_for_org_admin_not_for_staff`). The `shop_name` API test was run under the default test settings; Plan 33-07 should re-run it under `config.settings.test_pg` when available (T-33-09).

## Verification
- `pytest apps/common`: green (all tests); mypy, ruff check, ruff format clean on `apps/common`
- `npx vitest run src/widgets/audit-log`: 14 passed; `npx tsc --noEmit`: clean
- Pre-commit hooks passed on all three commits

## Known Stubs
None.

## Threat Flags
None - no new endpoints or trust boundaries beyond the plan's threat model.

## Next Phase Readiness
Ready for the remaining Wave plans; CVIS-05 Activity Log half is complete.

---
*Phase: 33-credit-visibility-staff-scoping*
*Completed: 2026-11-12*

## Self-Check: PASSED
