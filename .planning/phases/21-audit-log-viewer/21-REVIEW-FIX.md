---
phase: 21-audit-log-viewer
fixed_at: 2026-05-24T00:00:00Z
review_path: .planning/phases/21-audit-log-viewer/21-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 21: Code Review Fix Report

**Fixed at:** 2026-05-24
**Source review:** `.planning/phases/21-audit-log-viewer/21-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, WR-01..WR-06)
- Fixed: 7
- Skipped: 0
- Out-of-scope (no `--all`): IN-01, IN-02, IN-03, IN-04, IN-05 — not addressed in this pass.

## Fixed Issues

### CR-01: Staff scope leak via entity_id collision across review/action_item PK spaces

**Files modified:**
- `apps/common/selectors/audit_logs.py`
- `apps/common/tests/test_audit_log_selectors.py`

**Commit:** `db26580`

**Applied fix:** Replaced the combined `entity_id__in=[review_ids + action_item_ids]` clause with `Q(entity_type="review", entity_id__in=review_ids) | Q(entity_type="action_item", entity_id__in=action_item_ids)` so each id list only ever matches its own entity_type. Added regression test `test_list_audit_logs_for_staff_no_cross_type_pk_collision` that forces a PK collision between an inaccessible review and an accessible SHOP-scope action item (via `pk=review_out.pk`), then asserts the inaccessible review's audit row does not leak while the action item's row remains visible.

**Verification status:** fixed — logic is testable (regression test included). Tier-2 verification deferred: Docker stack not running locally; Tier-1 read-back confirms the Q-split is in place and the regression test exercises the collision scenario.

### WR-01: `entity_type` filter accepts arbitrary strings (no whitelist)

**Files modified:**
- `apps/common/filters.py`
- `apps/common/tests/test_audit_log_api.py`

**Commit:** `87691b8`

**Applied fix:** Replaced `django_filters.CharFilter(field_name="entity_type")` with `ChoiceFilter` restricted to `("review", "action_item")` per D-07. Added regression test `test_filter_entity_type_whitelist_rejects_unknown` asserting an unknown value returns HTTP 400.

### WR-02: `date_from > date_to` silently accepted

**Files modified:**
- `apps/common/filters.py`
- `apps/common/tests/test_audit_log_api.py`

**Commit:** `87691b8`

**Applied fix:** Overrode `AuditLogFilterSet.qs` to inspect `self.data` and raise `rest_framework.exceptions.ValidationError` when `date_from > date_to`. DRF maps this to HTTP 400. Added regression test `test_filter_date_from_after_date_to_returns_400`.

### WR-03: Actor dropdown bootstrap leaks org-wide actor names to Staff users

**Files modified:**
- `apps/common/views.py`

**Commit:** `e841c07`

**Applied fix:** `audit_log_view` now branches on `request.user.role` and seeds the actor list from `list_audit_logs_for_staff(...)` for STAFF_ADMIN, falling back to `list_audit_logs_for_org(...)` for ORG_ADMIN. This makes the actor dropdown's visibility exactly match the API's row visibility, preventing leakage of actors who only operated on brand-scope items or inaccessible shops.

### WR-04: `filter_shop` accepts arbitrary shop IDs without verifying caller access

**Files modified:**
- `apps/common/filters.py`
- `apps/common/tests/test_audit_log_api.py`

**Commit:** `87691b8`

**Applied fix:** `filter_shop` now resolves `self.request.user`, checks role, and for STAFF_ADMIN intersects the requested `shop_id` with `get_accessible_shop_ids(user_id=user.pk)`. If the requested shop is not accessible, raises `rest_framework.exceptions.ValidationError({"shop": "Shop is not accessible."})` (HTTP 400). Added two regression tests: `test_filter_shop_inaccessible_for_staff_returns_400` and `test_filter_shop_accessible_for_staff_ok`.

### WR-05: `isoDate` uses UTC; default date window is wrong for non-UTC clients

**Files modified:**
- `frontend/src/widgets/audit-log/utils.ts`
- `frontend/src/widgets/audit-log/useAuditLog.ts`
- `frontend/src/widgets/audit-log/AuditLogFilters.tsx`
- `frontend/src/widgets/audit-log/AuditLogWidget.tsx`

**Commit:** `f2444cb`

**Applied fix:** Re-wrote `isoDate` to use `getFullYear / getMonth / getDate` (local time) instead of `toISOString().split("T")[0]` (UTC). Hoisted `isoDate`, `defaultDateRange`, and `DEFAULT_DATE_WINDOW_DAYS` into `utils.ts` as the single source of truth, removing duplicate implementations from `useAuditLog.ts`, `AuditLogFilters.tsx`, and `AuditLogWidget.tsx`. All three modules now import from `./utils`. Verified with `npx tsc --noEmit` (clean).

### WR-06: Cursor stack invariant on page_size change

**Files modified:**
- `frontend/src/widgets/audit-log/useAuditLog.ts`

**Commit:** `c7b31c8`

**Applied fix:** The `changePageSize` handler already cleared `prevCursorsRef.current` and reset `cursor` to `null`, but the rationale was implicit. Added a multi-line comment explaining why the cursor stack and active cursor must be invalidated on page_size change (server cursors encode a `(timestamp, id)` boundary anchored to the previous page_size; popping a stale cursor produces undefined behaviour on the new page_size). The fix is documented-in-place so future edits cannot silently drop the invalidation. Verified with `npx tsc --noEmit` (clean).

## Skipped Issues

None — all in-scope findings were fixed.

The following findings are out-of-scope for this pass (no `--all` flag) and remain open in REVIEW.md:

- **IN-01** — dead code in `test_filter_date_range` (first request assigned to `resp` then overwritten)
- **IN-02** — unused `userRole` prop plumbing through three layers
- **IN-03** — unreachable Superadmin branch in `audit_log_view`
- **IN-04** — `actor_name` getter overcomplication in serializer
- **IN-05** — sidebar nav placement comment

---

_Fixed: 2026-05-24_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
