---
phase: 21-audit-log-viewer
plan: 01
subsystem: common
tags: [audit-log, selectors, drf, pagination, filters, rbac]
dependency_graph:
  requires:
    - apps/common/models.py::AuditLog
    - apps/reviews/selectors/reviews.py::get_accessible_shop_ids
    - apps/reviews/models.py::Review
    - apps/action_items/models.py::ActionItem
  provides:
    - apps/common/selectors/audit_logs.py::list_audit_logs_for_org
    - apps/common/selectors/audit_logs.py::list_audit_logs_for_staff
    - apps/common/selectors/audit_logs.py::AUDIT_ENTITY_FILTER
    - apps/common/serializers.py::AuditLogReadSerializer
    - apps/common/pagination.py::AuditLogCursorPagination
    - apps/common/filters.py::AuditLogFilterSet
  affects:
    - Plan 21-02 (viewset + URLs + integration tests) consumes all five
tech_stack:
  added: []
  patterns:
    - Cursor pagination with composite ordering tiebreaker (-created_at, id)
    - Two-step Staff scoping (materialise entity_ids first, then filter generic audit table)
key_files:
  created:
    - apps/common/selectors/__init__.py
    - apps/common/selectors/audit_logs.py
    - apps/common/serializers.py
    - apps/common/filters.py
    - apps/common/tests/test_audit_log_selectors.py
  modified:
    - apps/common/pagination.py
decisions:
  - D-01 enforced via AUDIT_ENTITY_FILTER (review reply + action_item only)
  - D-02 enforced via organisation_id filter from authenticated user (selector signature requires keyword arg)
  - D-03 enforced via two-step Staff scope materialisation
  - D-07 filters: entity_type, actor, date_from, date_to, shop
  - D-08 cursor pagination ordering=("-created_at", "id")
  - D-10 serializer omits before_data
  - D-11 serializer exposes actor_name from User.full_name
metrics:
  duration_minutes: ~25
  tasks_completed: 3
  files_changed: 6
  tests_added: 8
  completed_date: 2026-05-23
---

# Phase 21 Plan 01: Audit Log Backend Data Layer Summary

One-liner: Built the read-side data layer for the Audit Log viewer — selectors with ORG_ADMIN/STAFF_ADMIN scoping, a DRF cursor paginator with a composite ordering tiebreaker, a `before_data`-omitting serializer, and a five-field FilterSet — all unit-tested with N+1 prevention.

## What Shipped

| Artefact | Purpose |
|---|---|
| `apps/common/selectors/audit_logs.py::list_audit_logs_for_org` | Returns the org-scoped queryset of review-reply + action_item events, with `select_related("actor")` to avoid N+1 on actor name. |
| `apps/common/selectors/audit_logs.py::list_audit_logs_for_staff` | Materialises accessible Review PKs (in accessible shops, not soft-deleted) + SHOP-scope ActionItem PKs, then filters `AuditLog.entity_id__in=[...]`. Enforces D-03 two-step scope. |
| `apps/common/selectors/audit_logs.py::AUDIT_ENTITY_FILTER` | `Q` constant reused by both selectors; restricts to `entity_type="action_item"` OR `entity_type="review", action__in=["reply_posted","reply_deleted","reply_failed"]`. |
| `apps/common/serializers.py::AuditLogReadSerializer` | DRF read serializer; explicit field list with no `before_data` (D-10); `actor_name` computed from `User.full_name`, returns `None` for system rows (D-11). |
| `apps/common/pagination.py::AuditLogCursorPagination` | DRF `CursorPagination` subclass; `ordering=("-created_at", "id")` tuple keeps cursors stable when many rows share a timestamp (RESEARCH Pitfall 3). `page_size=50`, `max_page_size=100`. |
| `apps/common/filters.py::AuditLogFilterSet` | django-filter `FilterSet` exposing `entity_type`, `actor` (special value `system` → `actor__isnull=True`; int → `actor_id=...`), `date_from`, `date_to`, and `shop` (two-step: find Review PKs in shop, then filter `entity_id__in`). |

## Tests Added (8)

In `apps/common/tests/test_audit_log_selectors.py`:

1. `test_list_audit_logs_for_org_includes_reply_actions` — three reply actions kept; `shop_sync` row excluded.
2. `test_list_audit_logs_for_org_includes_action_item_events` — action_item rows kept.
3. `test_list_audit_logs_for_org_excludes_other_orgs` — cross-tenant isolation.
4. `test_list_audit_logs_for_staff_excludes_brand_scope_items` — brand-scoped ActionItem audit row absent; SHOP-scope present.
5. `test_list_audit_logs_for_staff_excludes_inaccessible_shop_reviews` — review audit row for shop outside Staff scope absent.
6. `test_serializer_includes_actor_name_excludes_before_data` — verifies actor_name string, no before_data, after_data preserved.
7. `test_serializer_system_actor_name_is_none` — null actor renders as `actor_name=None`.
8. `test_list_audit_logs_for_org_no_n_plus_one` — 5 distinct actors, asserts `<=3` queries, confirming `select_related("actor")`.

All 8 pass in the docker `web` test runner.

## Commits

| Hash | Subject |
|---|---|
| `f478926` | `feat(21-01): add audit log selectors with org + staff scoping` |
| `011f525` | `feat(21-01): add audit log serializer, cursor pagination, filterset` |
| `a680817` | `test(21-01): add audit log selector and serializer unit tests` |

## Verification

```bash
docker-compose exec -T web pytest apps/common/tests/test_audit_log_selectors.py
# 8 passed, 8 warnings in 0.89s

docker-compose exec -T web python manage.py makemigrations --check --dry-run
# No changes detected
```

Pre-commit hooks (ruff-check, ruff-format, django-upgrade, mypy, bandit, gitleaks, missing-migrations) passed on every commit.

## Deviations from Plan

None functionally. Two ruff/mypy nits surfaced during commit hooks and were corrected without changing intent:

- **[Rule 1 - Bug] mypy `type-arg` on `ModelSerializer`** — Added type parameter: `serializers.ModelSerializer[AuditLog]`. Files: `apps/common/serializers.py`. Resolved before commit `011f525`.
- **[Rule 1 - Bug] mypy "Cannot override instance variable with class variable" on `CursorPagination.ordering`** — DRF's base declares `ordering` as an instance attribute; removed the `ClassVar` wrapper. The kept `ordering = ("-created_at", "id")` tuple value satisfies D-08. Files: `apps/common/pagination.py`. Resolved before commit `011f525`.
- **[Rule 1 - Bug] ruff RUF012 on `Meta.fields`** — Added `ClassVar[list[str]]` annotation to `AuditLogReadSerializer.Meta.fields`. Files: `apps/common/serializers.py`. Resolved before commit `011f525`.

Ruff also auto-reformatted long lines in the test file at commit time (formatting only, no logic change).

## Known Stubs

None.

## Threat Flags

None — no new network surface, no new auth paths, no new schema changes. All security-relevant behaviour (D-02 org isolation, D-03 Staff scope) is covered by tests 3, 4, 5.

## Notes for Plan 21-02

- Import the selectors with `from apps.common.selectors.audit_logs import list_audit_logs_for_org, list_audit_logs_for_staff`.
- The viewset's `get_queryset` should dispatch on `self.request.user.role` to choose the selector; both take `organisation_id` from `self.request.user.organisation_id`.
- The `filter_shop` method on `AuditLogFilterSet` only filters review entries by shop. If 21-02 wants action items filterable by shop too, that's an extension — flag during review.
- `actor` query param accepts the literal `system` for null-actor rows; numeric strings become `actor_id`.

## Self-Check: PASSED

- `apps/common/selectors/__init__.py` — FOUND
- `apps/common/selectors/audit_logs.py` — FOUND
- `apps/common/serializers.py` — FOUND
- `apps/common/pagination.py` (modified) — FOUND
- `apps/common/filters.py` — FOUND
- `apps/common/tests/test_audit_log_selectors.py` — FOUND
- Commit `f478926` — FOUND
- Commit `011f525` — FOUND
- Commit `a680817` — FOUND
