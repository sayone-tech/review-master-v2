---
phase: "29"
status: issues_found
depth: standard
files_reviewed: 22
diff_base: 9be22e689e041639f243dd9e56d82a292650effc
reviewed: "2026-11-11"
findings:
  critical: 0
  warning: 3
  info: 6
  total: 9
---

# Phase 29 — Code Review

Reviewed 22 non-test source/config files at standard depth (settings, pyproject, Makefile and ci.yml: diff hunks since `9be22e6` only). No blockers. WR-01 was confirmed empirically by the reviewer with a throwaway test (since deleted); the rest is from reading the code. Settings/CI/Makefile/conftest hunks raised nothing. The Organisation update/create serializers do not expose `monthly_credit_allocation` (no org-admin self-grant path).

## Warnings

### WR-01: Append-only guard bypassable by saving a hand-built instance with an existing pk
**File:** `apps/credits/models.py:195-197`
**Issue:** `save()` passes every call through when `self._state.adding` is true and calls `super().save()` unchanged. `BigAutoField` has no default, so with a pk set and no `force_insert` Django attempts an UPDATE first. `CreditTransaction(pk=<existing>, ..., created_at=...).save()` therefore overwrites a committed ledger row via `_base_manager`, bypassing the guarded `QuerySet.update`. Verified: the UPDATE executed and only failed on `NOT NULL created_at` (`auto_now_add` doesn't fire on the update path). A caller supplying `created_at` gets a silent rewrite of `credits_delta`/`status`, defeating D-05.
**Fix:**
```python
if self._state.adding:
    kwargs["force_insert"] = True
    super().save(*args, **kwargs)
    return
```
plus a test constructing `CreditTransaction(pk=existing.pk, created_at=...)` that asserts `IntegrityError`.

### WR-02: `bulk_create(update_conflicts=True)` is an unguarded rewrite path
**File:** `apps/credits/managers.py:15-25`
**Issue:** `INSERT ... ON CONFLICT DO UPDATE` via the same queryset class never hits `update()`/`save()`, so it can overwrite ledger rows. The docstring states `create`/`bulk_create` are "untouched", which leaves this open for Phase 30 code to reach accidentally.
**Fix:** Override `bulk_create` in `CreditTransactionQuerySet` to raise `AppendOnlyViolation` when `update_conflicts` is truthy.

### WR-03: Virtual balance for a past period reports today's allocation
**File:** `apps/credits/selectors/balances.py:68-79`, `:117-121`
**Issue:** For a non-current `period` with no row, the selector returns the org's live `monthly_credit_allocation` as `allocated`/`remaining` (`is_materialized=False`) — an invented balance for a past month. `ensure_balance(period=past)` likewise writes a retroactive INITIAL_ALLOCATION. CRED-05 intent covers only the current period.
**Fix:** Reject non-current `period` in the virtual branch and in `ensure_balance` (e.g. `ValueError`), or document it and restrict the parameter to tests.

## Info

### IN-01: Dead positional-args branch in `save()`
**File:** `apps/credits/models.py:199-200` — Django 6 `Model.save()` is keyword-only; `len(args) > 3` is unreachable and forwarding `*args` would `TypeError`. **Fix:** `def save(self, **kwargs)`.

### IN-02: Status-transition lookup relies on enum name == value
**File:** `apps/credits/models.py:96-101`, `apps/credits/services/ledger.py:25` — `ALLOWED_STATUS_TRANSITIONS` holds `Status` members but is probed with plain strings; works only because names equal values. **Fix:** build the set from `.value` strings.

### IN-03: `credit_cost` does not validate tiers at runtime
**File:** `apps/credits/services/credit_cost.py:33-38`, `config/settings/base.py:234` — empty tiers → `IndexError`; unsorted tiers misprice silently (the settings-shape test covers the shipped value only). **Fix:** Django system check for non-empty/ascending/open-top tiers.

### IN-04: Allocation read outside the transaction in `ensure_balance`
**File:** `apps/credits/services/allocation.py:37-47` — tiny stale-read window if an admin edits the allocation concurrently; tolerable under the next-month rule. **Fix:** move the read inside `atomic()` or document.

### IN-05: Denormalised `shop`/`organisation` on `CreditTransaction` unconstrained
**File:** `apps/credits/models.py:110-118` — consistency relies on `ensure_balance`; Phase 30 CONSUMPTION writers could diverge them and skew tenant-scoped ledger reads. **Fix:** derive both from the balance in the Phase 30 ledger-creation service; add a reconciliation assertion in `tests/helpers.py`.

### IN-06: Inconsistent import discipline for credits → shops
**File:** `apps/credits/services/allocation.py:25`, `apps/credits/selectors/balances.py:69-70` — function-local import in the selector vs module-level in the service. **Fix:** pick one convention and document it.
