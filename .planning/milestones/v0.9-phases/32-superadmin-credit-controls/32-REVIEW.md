---
phase: 32-superadmin-credit-controls
reviewed: 2026-11-11T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - apps/credits/api_urls.py
  - apps/credits/exceptions.py
  - apps/credits/serializers.py
  - apps/credits/views.py
  - apps/credits/services/allocation.py
  - apps/credits/services/bonus.py
  - apps/credits/selectors/balances.py
  - apps/credits/selectors/shop_credits.py
  - apps/organisations/admin.py
  - apps/organisations/serializers.py
  - apps/organisations/views.py
  - apps/organisations/services/organisations.py
  - apps/organisations/selectors/organisations.py
  - config/settings/base.py
  - config/urls.py
  - frontend/src/entrypoints/org-management.tsx
  - frontend/src/widgets/org-management/CreateOrgModal.tsx
  - frontend/src/widgets/org-management/EditOrgModal.tsx
  - frontend/src/widgets/org-management/ManageCreditsModal.tsx
  - frontend/src/widgets/org-management/OrgTable.tsx
  - frontend/src/widgets/org-management/ViewOrgModal.tsx
  - frontend/src/widgets/org-management/creditHint.ts
  - frontend/src/widgets/org-management/creditsApi.ts
  - frontend/src/widgets/org-management/types.ts
  - frontend/src/widgets/org-management/useCreditShops.ts
  - docs/sre/v0.9-credits-rollout.md
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-11-11
**Depth:** standard
**Files Reviewed:** 26 (24 source files plus the types and rollout doc)
**Status:** issues_found

## Summary

I traced the core money paths and found no blockers.

- **CRED-06 materialisation at the old value.** `update_organisation` reads the old value under the org row lock with FOR NO KEY UPDATE, then materialises balances before saving the new field. The "next month" semantics hold.
- **D-18 immediate case.** The backend rule (`old == 0` and no current-month row with allocation > 0) matches the frontend `saved === 0 && thisMonth === 0` rule. This is true for every scenario I walked: 100 -> 0 -> 50, bonus-created zero rows, and untouched shops.
- **Bonus atomicity.** The `F()` increment, the ledger row and the audit row share one atomic block. The lock order is org row -> balance row, consistent with `update_organisation`.
- **Audit writes.** Audit rows are written only on a real change. Bonus audit data carries no free-text reason, only `has_reason`.
- **Permissions, throttling and pagination.** Both new views use `IsAuthenticated` + `IsSuperadmin`, scoped throttles and a fixed page size of 10.
- **N+1.** The shop list uses a single FilteredRelation join plus a correlated Subquery. No N+1 found.
- **Admin.** The allocation field is read-only in admin, so the service path cannot be bypassed there.

The remaining issues are narrow races, an ordering inconsistency, and frontend robustness gaps. The concurrent `ensure_balance` race (WR-01) is the one I would fix before ship, because it can leave a shop at 0 credits for a whole month after an "immediate" enable.

## Warnings

### WR-01: `ensure_balance` seeds from an allocation read outside any lock, so a concurrent 0 -> N edit can leave a stuck zero row

**File:** `apps/credits/services/allocation.py:45-56` (interacts with `apps/organisations/services/organisations.py:239-262`)

**Issue:**
- `ensure_balance` reads `organisation__monthly_credit_allocation` in a plain query before entering its `atomic()` block.
- The consumption path (`consumption.py:127`) calls it with no organisation lock. Only the bonus path holds the org lock first.
- Race: T1 (a first-use generate on a shop with no row) reads allocation 0. T2 (`update_organisation` 0 -> N) takes the org lock, finds no zero rows to raise, saves N, writes an audit row saying `effective: "immediate"`, and commits.
- T1 then inserts its row with `allocated_credits=0` and no INITIAL ledger row. Its FK check needs only KEY SHARE, which does not conflict with FOR NO KEY UPDATE.
- The shop is stuck at 0 and "not_enabled" for the rest of the month, although the org is enabled and the audit says immediate.
- The N -> M direction is safe. The org-edit bulk insert waits on the same unique-index entry and the row keeps the old value.
- The window is small, but it is a real money-correctness gap in the new "immediate" promise. The Postgres race tests do not appear to cover it.

**Fix:** Take the read under a conflicting row lock inside the atomic block, then re-read. Sketch:

```python
with transaction.atomic():
    # blocks while update_organisation holds FOR NO KEY UPDATE; READ COMMITTED then sees the new value
    allocation = (
        Organisation.objects.select_for_share(of=("self",))
        .filter(pk=organisation_id)
        .values_list("monthly_credit_allocation", flat=True)
        .get()
    )
    balance, created = ShopCreditBalance.objects.get_or_create(...defaults allocated_credits=allocation)
```

Add a two-connection Postgres test for the 0 -> N versus first-use interleaving. If `select_for_share` interacts badly with the lock order, instead have `raise_zero_balances` also re-check for zero rows after the field save. Either way, add the regression test.

### WR-02: Shop availability (active shop, non-DELETED org) is checked outside the transaction and org lock

**File:** `apps/credits/services/bonus.py:70-77`

**Issue:**
- The `is_active` and `status != DELETED` check runs before `transaction.atomic()` and before the org lock.
- A shop deactivated, or an org deleted, between that check and the lock still receives a bonus. The call returns 201 instead of the documented 404.
- The org-lock-first design exists precisely to make state stable, but the availability check does not use it.

**Fix:** After taking the org lock, re-validate inside the atomic block. For example, re-query `Shop.objects.filter(pk=shop_id, is_active=True)` plus the org status, with `select_for_update(of=("self",), no_key=True)` joined on the org. Raise `ShopNotAvailableError` from inside the atomic block (it rolls back cleanly).

### WR-03: A stale-period request on an inactive shop returns 409 with a balance snapshot instead of 404

**File:** `apps/credits/services/bonus.py:62-68`

**Issue:**
- The period-mismatch branch runs before the availability check.
- For an inactive shop (or a shop of a DELETED org) with a stale period, `get_shop_credit_balance` succeeds. The caller gets 409 `period_mismatch` plus the balance.
- The UI then repaints, the user retries, and only then gets 404. The D-19 contract is "404 inactive shop".
- The 409 balance leak is Superadmin-only, so low severity, but the two contracts conflict.

**Fix:** Run the availability query first, then the period check. Use the same `org_id` lookup for both.

### WR-04: Bonus POST has no idempotency, and the generic-error path invites a double credit

**File:** `frontend/src/widgets/org-management/ManageCreditsModal.tsx:224-226` (and `creditsApi.ts:110-124`)

**Issue:**
- A network error (fetch rejects), a timeout, or a 5xx after the server committed is shown as "Something went wrong. Please try again."
- Typed values are kept, so a retry credits the shop twice. There is no client request id and no list reload.
- This is a money-affecting append-only ledger, so the double credit is permanent.

**Fix:**
- For non-HTTP failures and 5xx, call `reload()` and change the toast to say the allocation may have been applied, so the user should check the shop balance before retrying.
- Optionally add an `Idempotency-Key` header stored on the `CreditTransaction` and rejected on duplicates.

### WR-05: Credit shop list is stuck on a 404 when the page index goes out of range

**File:** `frontend/src/widgets/org-management/useCreditShops.ts:31-50`

**Issue:**
- DRF returns 404 for a page beyond the last page, for example after a shop is deactivated while the Superadmin is on page 2.
- The hook sets `error`. "Retry" re-requests the same page and never recovers. The user must close the modal.
- The same applies after the bonus 404 path calls `reload()` on a shrunken list.

**Fix:** In the catch handler, if the error is a 404 and `page > 1`, call `setPageState(1)` (which triggers a refetch) instead of setting `error`. Do not do this for the org-level 404.

## Info

### IN-01: Shop search has no length bound

**File:** `apps/credits/views.py:78`

**Issue:** `search` is passed straight into `name__icontains`. The org list has the same pattern, but this is a new endpoint.

**Fix:** Slice to a sensible maximum, for example `request.query_params.get("search", "")[:100]`.

### IN-02: Deferred hint prints the raw "keep" number

**File:** `frontend/src/widgets/org-management/creditHint.ts:121,126`

**Issue:** `thisMonth` is interpolated unformatted ("Shops keep 1000"). `ViewOrgModal`, `OrgTable` and `ManageCreditsModal` all use `formatCount` for the same value ("1,000"). The inconsistency is cosmetic.

**Fix:** Use `formatCount(thisMonth)`, and update the matching tests.

### IN-03: Double-submit guard depends on React state

**File:** `frontend/src/widgets/org-management/ManageCreditsModal.tsx:160`

**Issue:** `if (submitting ...) return` reads state from the render closure. A synthetic double click before the re-render is mostly safe (discrete events flush synchronously), but a `useRef` flag would be a deterministic guard, given that the endpoint is not idempotent (WR-04).

**Fix:** Set a `submittingRef.current` flag at the top of `handleAllocate` and clear it in `finally`.

### IN-04: Shops created after an allocation change take the new value this month

**File:** `apps/credits/services/allocation.py:149-207` and `apps/organisations/services/organisations.py:257-262`

**Issue:**
- Materialisation only covers shops that exist at edit time.
- A shop created later in the same month has no row and reads or seeds from the new live allocation, ahead of the "next month" rule shown in the hint and the rollout doc.
- The effect is bounded (one shop, one month) and arguably desirable. The behaviour is undocumented.

**Fix:** Document it in `docs/sre/v0.9-credits-rollout.md`, or, if undesired, materialise on shop creation.

---

_Reviewed: 2026-11-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
