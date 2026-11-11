---
phase: 33-credit-visibility-staff-scoping
reviewed: 2026-11-12T00:00:00Z
depth: standard
files_reviewed: 57
files_reviewed_list:
  - apps/common/selectors/audit_logs.py
  - apps/common/serializers.py
  - apps/common/tests/test_audit_log_api.py
  - apps/common/tests/test_audit_log_selectors.py
  - apps/credits/api_urls.py
  - apps/credits/serializers.py
  - apps/credits/services/periods.py
  - apps/credits/tests/test_periods.py
  - apps/credits/tests/test_phase33_flow.py
  - apps/credits/tests/test_scope_sweep.py
  - apps/credits/tests/test_settings.py
  - apps/credits/tests/test_shop_credits_view.py
  - apps/credits/views.py
  - apps/reviews/tests/test_views.py
  - apps/reviews/views.py
  - apps/shops/selectors/shops.py
  - apps/shops/serializers.py
  - apps/shops/tests/test_selectors.py
  - apps/shops/tests/test_views.py
  - apps/shops/views.py
  - CLAUDE.md
  - config/settings/base.py
  - docs/sre/v0.9-credits-rollout.md
  - frontend/src/entrypoints/shop-management.tsx
  - frontend/src/widgets/audit-log/AuditLogTable.test.tsx
  - frontend/src/widgets/audit-log/AuditLogTable.tsx
  - frontend/src/widgets/audit-log/TypePill.tsx
  - frontend/src/widgets/audit-log/types.ts
  - frontend/src/widgets/credits/BuyMoreCreditsModal.test.tsx
  - frontend/src/widgets/credits/BuyMoreCreditsModal.tsx
  - frontend/src/widgets/credits/contact.test.ts
  - frontend/src/widgets/credits/contact.ts
  - frontend/src/widgets/credits/CreditBadge.test.tsx
  - frontend/src/widgets/credits/CreditBadge.tsx
  - frontend/src/widgets/credits/creditBand.test.ts
  - frontend/src/widgets/credits/creditBand.ts
  - frontend/src/widgets/credits/creditsApi.ts
  - frontend/src/widgets/credits/CreditsCard.test.tsx
  - frontend/src/widgets/credits/CreditsCard.tsx
  - frontend/src/widgets/credits/creditsStore.test.ts
  - frontend/src/widgets/credits/creditsStore.ts
  - frontend/src/widgets/credits/format.test.ts
  - frontend/src/widgets/credits/format.ts
  - frontend/src/widgets/credits/mailto.test.ts
  - frontend/src/widgets/credits/mailto.ts
  - frontend/src/widgets/review-management/api.ts
  - frontend/src/widgets/review-management/ReplyComposer.test.tsx
  - frontend/src/widgets/review-management/ReplyComposer.tsx
  - frontend/src/widgets/shop-management/ShopDetailsModal.tsx
  - frontend/src/widgets/shop-management/ShopModals.test.tsx
  - frontend/src/widgets/shop-management/ShopModals.tsx
  - frontend/src/widgets/shop-management/ShopTable.test.tsx
  - frontend/src/widgets/shop-management/ShopTable.tsx
  - frontend/src/widgets/shop-management/types.ts
  - frontend/src/widgets/shop-management/useShops.ts
  - templates/reviews/review_list.html
  - templates/shops/shop_list.html
findings:
  critical: 0
  high: 0
  warning: 3
  info: 4
  total: 7
severity_buckets:
  critical: 0
  high: 0
  medium: 2
  low: 5
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-11-12
**Depth:** standard
**Files Reviewed:** 57
**Status:** issues_found

## Summary

Reviewed the Phase 33 diff (`4b4d7bc..HEAD`) across the backend credits/shops/audit-log surface, the React credits widgets, and their tests. The security-critical parts hold up:

- Tenant and Staff scoping is centralised in `restrict_to_staff_scope` and `get_accessible_shop_for_credits`. The organisation filter is applied before the Staff filter, which matters because region expansion in `get_accessible_shop_ids` is not org-bounded.
- Out-of-scope, cross-organisation and unknown shops all return the same 404.
- Credit audit rows are only added to the Org selector. The Staff selector still binds `entity_type` to `entity_id`, so credit rows stay hidden from Staff.
- The shop-name subquery is gated on `entity_type="shop"`, bound to the row's own organisation, and compared as text.
- `ShopCreditsView` is read-only and sets `no-store`. The mailto builder strips CR/LF and URL-encodes all values.

No critical or high-severity defects found. The findings below are functional gaps and robustness issues, mainly around the Activity Log filters, what credit audit rows expose to Org Admins, and some unreachable Staff code paths.

Severity buckets: critical 0, high 0, medium 2, low 5. WR-01 and WR-02 map to medium; WR-03 and all Info items map to low.

## Warnings

### WR-01: Activity Log filters cannot reach credit rows (entity_type whitelist and shop filter)  [medium]

**File:** `apps/common/filters.py:13-17` and `apps/common/filters.py:60-72` (behaviour consumed by the changed `apps/common/selectors/audit_logs.py:44-83`)

**Issue:** Phase 33 adds `shop` / `organisation` credit rows to the Org Admin Activity Log, but `AuditLogFilterSet` was not updated:

1. `ENTITY_TYPE_CHOICES` is still only `review` and `action_item`. `?entity_type=shop` and `?entity_type=organisation` return 400, so an Org Admin cannot isolate credit events. The frontend type filter (`AuditLogFilters.tsx`) therefore cannot offer a "Credits" option even though `TypePill` now renders one.
2. `filter_shop` unconditionally does `qs.filter(entity_type="review", entity_id__in=review_ids)`. Filtering the log by a shop silently drops every `shop.credits.*` row for that shop. This is a surprising result for a feature (CVIS-05) whose rows are named per shop.
3. The OpenAPI description and enum in `apps/common/views.py` (lines 156-170) still say "review/reply + action_item events" and `enum=["review", "action_item"]`.

The Phase 33 tests (`test_phase33_flow.py` step 6) only exercise the unfiltered list, so none of this is covered.

**Fix:** Extend `ENTITY_TYPE_CHOICES` with `("shop", "Credits")` and `("organisation", "Credits")`, or add a single `credits` pseudo-type mapped to `CREDIT_AUDIT_FILTER`. Staff must never match it, which is already guaranteed because the Staff selector does not include credit rows. Make `filter_shop` return `Q(review rows for shop) | Q(entity_type="shop", entity_id=str(value))` for non-Staff callers. Update the OpenAPI enum and description, and add a test for `?shop=<id>` returning the shop's credit rows.

### WR-02: Credit audit rows expose internal identifiers and Superadmin identity to Org Admins  [medium]

**File:** `apps/common/selectors/audit_logs.py:36-41` and `apps/common/serializers.py:17-37` (data written in `apps/credits/services/consumption.py:219-231, 365-379`, `apps/credits/services/bonus.py:105-120`, `apps/organisations/services/organisations.py:72-89`)

**Issue:** `AuditLogReadSerializer` returns `after_data` verbatim, and `actor_name` is resolved for every row. Making the credit actions visible to Org Admins means the tenant now receives:

- `ai_usage_log_id`, `transaction_id` and the internal `reason` (for example `no_capacity`) from `shop.credits.consumed` and `late_commit` rows. These are platform-internal cost-tracking identifiers and failure reasons that were never meant for tenant eyes.
- The Superadmin's `actor_name` on `shop.credits.bonus_allocated` and `organisation.credits.set` rows, and the Superadmin's id and full name in the actor dropdown seeded by `audit_log_view` (`apps/common/views.py:252-289`, which now includes `list_audit_logs_for_org` credit rows).

The Superadmin leak is a minor tenant-boundary concern: platform staff identities appear in a customer-facing view.

**Fix:** Project credit rows to an allow-list before serialisation. For example, for `entity_type in {"shop", "organisation"}` return only `credits`, `amount`, `outcome`, `period_year`, `period_month` and the resulting balances, and drop `ai_usage_log_id`, `transaction_id`, `new_transaction_id` and `reason`. Mask or relabel the actor as "ReviewBee" when the actor role is `SUPERADMIN`, and exclude Superadmin actors from the dropdown query.

### WR-03: Credit columns on `ShopReadSerializer` are null for retrieve / create / update but populated for list  [low]

**File:** `apps/shops/serializers.py:13-28`, `apps/shops/views.py:233, 312, 334, 341, 375`

**Issue:** `credits_allocated`, `credits_bonus`, `credits_remaining` and `credits_total` are only annotated when `list_shops(with_credits=True)` is used. `retrieve` (via `get_queryset`), the 201 response from `create`, the `update` / `activate` / `deactivate` / `reconnect` responses, and `organisations/views.py:216` all serialise un-annotated shops. They silently report `null`, indistinguishable from "no credits data", while `GET /shops/{id}/credits/` has the real values. The frontend currently hides this by firing `shop:refresh` after every mutation, but any API or mobile consumer reading the detail endpoint gets inconsistent data.

**Fix:** Either annotate in `get_queryset()` for `retrieve` (use `annotate_credit_state`), or document and test that the credit fields are list-only. If kept list-only, split a `ShopListReadSerializer` so the fields are not advertised on endpoints that never populate them.

## Info

### IN-01: Staff-only code paths on the Shops page are unreachable  [low]

**File:** `frontend/src/widgets/shop-management/ShopTable.tsx:146-165`, `frontend/src/entrypoints/shop-management.tsx:42-45`, `apps/shops/views.py:99-103`

**Issue:** `shop_list` is decorated with `@org_admin_required`, and `apps/shops/tests/test_views.py:1178` confirms Staff are redirected. The new `isOrgAdmin` prop, the "No shops assigned" Staff empty state, and the `user=user` Staff scoping passed from the template view can therefore never execute for Staff. The Staff scoping that matters is on the DRF viewset, which is covered. The fallback `modalsRoot ? ... : true` also defaults to Org Admin when the root is missing.

**Fix:** Remove the dead Staff branch, or add a comment that it is forward-looking for when the Shops page opens to Staff. Do not claim Staff coverage in the docs for the HTML page.

### IN-02: Buy More modal handles an empty support email poorly  [low]

**File:** `frontend/src/widgets/credits/BuyMoreCreditsModal.tsx:66-68`, `frontend/src/widgets/credits/mailto.ts:63`, `frontend/src/widgets/credits/contact.ts:14-34`

**Issue:** `readCreditContact` deliberately returns an empty `supportEmail` when the bootstrap script is missing or malformed. The modal then renders "write to ." with an empty `select-all` span, and "Contact Admin" opens `mailto:?subject=...` with no recipient. The comment in `contact.ts` says the caller "can treat" this as unavailable, but no caller does. Separately, `supportEmail` is concatenated unencoded into the `mailto:` URL, which is safe only because it is operator-controlled server config.

**Fix:** When `supportEmail` is empty, hide the "write to" sentence and disable or hide "Contact Admin". Optionally validate it against a simple address pattern in `buildCreditRequestMailto`.

### IN-03: Minor consistency and coupling issues in the credits widgets  [low]

**File:** `frontend/src/widgets/credits/CreditsCard.tsx:133-158`, `frontend/src/widgets/credits/format.ts:1`, `frontend/src/widgets/credits/mailto.ts:1`, `frontend/src/widgets/review-management/ReplyComposer.tsx:55`

**Issue:**
- `CreditsCard` prints `credits.remaining`, `credits.total`, `allocated` and `bonus` as raw numbers, while the badge and composer use `formatCount` / `creditsLabel`. A balance of 1500 shows as "1500 / 2000" in the card and "1,500 credits" in the badge.
- `credits/*` imports `formatCount` and `MONTH_NAMES_SHORT` from `org-management/creditHint`, a Superadmin-widget module. Shared formatting should live under `credits/`.
- `ReplyComposer` calls `readCreditContact()` (a DOM lookup plus `JSON.parse`) on every render rather than once. `ShopModals` correctly memoises it.

**Fix:** Use `formatCount` in the card. Move the shared formatters into `credits/format.ts` and import from there. Wrap `readCreditContact()` in `useMemo` or `useState(() => ...)` in the composer.

### IN-04: OpenAPI and docs drift after Phase 33  [low]

**File:** `apps/common/views.py:156-171`, `docs/sre/v0.9-credits-rollout.md`

**Issue:** The audit-log OpenAPI `description` and `entity_type` enum still describe only review and action_item events and do not mention `shop_name` or credit rows. The Staff behaviour change in the SRE runbook is documented, but there is no note that Org Admins now see credit rows and Superadmin actors in the Activity Log (see WR-02).

**Fix:** Update the `extend_schema` description and enum alongside the WR-01 fix, and add a line to the rollout doc.

---

_Reviewed: 2026-11-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
