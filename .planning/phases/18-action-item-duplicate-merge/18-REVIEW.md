---
phase: 18-action-item-duplicate-merge
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - apps/action_items/migrations/0003_actionitem_canonical.py
  - apps/action_items/models.py
  - apps/action_items/selectors/items.py
  - apps/action_items/serializers.py
  - apps/action_items/services/lifecycle.py
  - apps/action_items/tests/test_models.py
  - apps/action_items/tests/test_selectors.py
  - apps/action_items/tests/test_services.py
  - apps/action_items/tests/test_views.py
  - apps/action_items/views.py
  - frontend/src/widgets/action-items/ActionItemManagementWidget.tsx
  - frontend/src/widgets/action-items/ActionItemModal.tsx
  - frontend/src/widgets/action-items/ActionItemTable.tsx
  - frontend/src/widgets/action-items/api.ts
  - frontend/src/widgets/action-items/DuplicatePickerModal.tsx
  - frontend/src/widgets/action-items/MergeModal.tsx
  - frontend/src/widgets/action-items/types.ts
  - frontend/src/widgets/data-table/DataTable.tsx
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 18 adds a self-referential `canonical` FK on `ActionItem`, a `merge_action_items` service with same-org / same-scope / AI-only / no-chain validation, list and detail serializer extensions, a `/merge/` endpoint restricted to Org Admin, and two frontend entry points (multi-select toolbar + detail-view "Mark as duplicate of…"). Tenant scoping and the Layer 1 Staff filter are preserved.

No critical defects were found. There are a handful of warnings around correctness under concurrency, contract drift between the documented D-17 behaviour and what users will actually observe, and a missed observability gap (re-parented sub-duplicates write no audit log). Several minor robustness and UX issues are listed as Info.

## Warnings

### WR-01: D-17 guards on `transition_status` / `assign` / `add_note` are dead code under the new selector

**File:** `apps/action_items/services/lifecycle.py:132,184,230`, `apps/action_items/selectors/items.py:48-55`
**Issue:** `list_action_items` applies `canonical__isnull=True`. `get_action_item` is implemented as `list_action_items(...).filter(pk=pk).first()`, so a merged duplicate is invisible at the ViewSet layer — `get_object()` returns 404 before any guard runs. The `if action_item.canonical_id is not None: raise ValidationError(...)` blocks at the top of `transition_status`, `assign_action_item`, `add_note`, and the `perform_update` check at `views.py:125` will never fire through the HTTP path. The view tests reflect this by accepting either 400 *or* 404 (`test_patch_merged_duplicate_returns_400`, `test_status_transition_merged_duplicate_returns_400`). Per D-17 the documented contract is **400 — "merged duplicate not actionable"**; users (and any external client) will see **404 — "not found"**, which is a different semantic ("the item does not exist for me") and prevents the frontend from showing a meaningful "this item has been merged" message.
**Fix:** Either (a) keep the selector filter only for list views and let `get_action_item` return duplicates so the guards return 400 with a clear message; or (b) drop the now-unreachable guard blocks and the `perform_update` check, and update D-17 in CONTEXT.md to record the actual behaviour (404). Option (a) is preferable because the detail panel's "Also reported in" UI suggests duplicates may still be deep-linked (e.g. from old notification URLs) and the 400 surface is more debuggable.

### WR-02: TOCTOU on canonical_id — merge can race with status / assign / note

**File:** `apps/action_items/services/lifecycle.py:131-138, 184-188, 230-235`
**Issue:** Each guard reads `action_item.canonical_id` from the **pre-lock** instance passed in by the view, then issues `select_for_update().get(pk=...)`. The locked row is never re-checked. A concurrent `merge_action_items` transaction that commits between the view's `get_object()` and `select_for_update()` will not be observed — the guard passes on the stale snapshot, the lock is acquired *after* the merge, and the duplicate is then mutated (status change, assignee change, note added) despite being a merged duplicate. This contradicts D-03 ("Duplicates become read-only context once merged"). The window is small but real, and a note row created this way cannot be undone (notes are append-only).
**Fix:** Move the canonical check to after the lock acquisition, using the locked row's state:
```python
locked = ActionItem.objects.select_for_update().get(pk=action_item.pk)
if locked.canonical_id is not None:
    raise ValidationError("Cannot modify a merged duplicate.")
```
Apply the same change in `assign_action_item` and `add_note`.

### WR-03: Re-parented sub-duplicates in merge are not locked

**File:** `apps/action_items/services/lifecycle.py:324-356`
**Issue:** The function locks `pk__in=all_ids` (primary + selected duplicates) but the re-parent statement on line 353 — `ActionItem.objects.filter(canonical_id__in=duplicate_ids).update(canonical_id=primary_id)` — operates on rows that were never locked. A concurrent merge that selects one of those sub-duplicates as a *primary* in a different transaction could interleave with this update and produce inconsistent canonical chains (e.g. a sub-duplicate becoming a canonical for a different merge while simultaneously being re-parented). The `transaction.atomic` block guarantees isolation only against rows touched within the same statement on a non-serializable isolation level.
**Fix:** Resolve the sub-duplicate IDs and add them to `all_ids` before the `select_for_update`. Example:
```python
sub_dup_ids = list(
    ActionItem.objects.filter(canonical_id__in=duplicate_ids).values_list("pk", flat=True)
)
all_ids = sorted({primary_id, *duplicate_ids, *sub_dup_ids})
```
Then proceed with the existing lock acquisition.

### WR-04: Re-parented sub-duplicates write no audit log

**File:** `apps/action_items/services/lifecycle.py:352-366`
**Issue:** When D-09 re-parents sub-duplicates onto the new primary, no `AuditLog` row records the canonical change for those rows. The single audit entry on the primary's `entity_id` only carries `merged_ids = duplicate_ids` (the directly-selected duplicates), not the sub-duplicates that were silently moved. This breaks the per-entity audit trail — if you query `AuditLog.objects.filter(entity_type="action_item", entity_id=str(sub_dup.pk))`, you cannot see that the sub-duplicate now points at a different canonical, even though it was effectively modified.
**Fix:** After the re-parent, write one audit row per affected sub-duplicate (or one rollup row with the list), action `action_item.canonical_changed`, capturing `before_data={"canonical_id": <old>}` and `after_data={"canonical_id": primary_id}`. Bulk-create these rows to keep query count constant.

### WR-05: `merge_action_items` does not verify primary is `source=AI` explicitly

**File:** `apps/action_items/services/lifecycle.py:343-345`
**Issue:** The loop `for item in locked: if item.source != AI: raise ValidationError(...)` iterates the merged list (primary + duplicates), so practically this is fine. However the error message — "Only AI-sourced action items can be merged" — masks which row was rejected. If a manual primary is supplied alongside AI duplicates, the user sees a generic error and has no clue whether the primary or one of the duplicates is at fault. This impacts the front-end's ability to show a useful toast.
**Fix:** Surface the offending IDs in the message, or check the primary separately:
```python
if primary.source != ActionItem.Source.AI:
    raise ValidationError("Primary must be an AI-sourced action item.")
non_ai_dup_ids = [i.pk for i in locked if i.pk != primary_id and i.source != ActionItem.Source.AI]
if non_ai_dup_ids:
    raise ValidationError(f"Only AI-sourced items can be merged. Non-AI duplicates: {non_ai_dup_ids}")
```

### WR-06: `DuplicatePickerModal` does not exclude items belonging to a different organisation **but does** allow cross-shop SHOP merges with no warning

**File:** `frontend/src/widgets/action-items/DuplicatePickerModal.tsx:43-65`, `apps/action_items/services/lifecycle.py:347-350`
**Issue:** The picker reuses `listActionItems` which is already org-scoped, so cross-org leakage is blocked at the backend. However, for a `SHOP`-scope item the picker returns all SHOP items in the org regardless of `shop_id`. A user can pick a primary belonging to a different shop, and the merge succeeds. The CONTEXT decision D-05 only constrains scope, not shop — so this is "by design" — but the resulting "Also reported in" detail panel renders the duplicate's shop, and the canonical retains its own shop, which is confusing semantically (a `Shop A` action item now has a duplicate whose source review came from `Shop B`). The frontend does not warn the user when picking a different-shop primary.
**Fix:** Either (a) gate the picker query by `shop=currentItem.shop_id` when `currentItem.scope === "SHOP"`, or (b) add a confirmation hint in the picker row when shop differs from the current item's shop. Option (a) aligns with the use-case (same issue across stores → roll up at brand level, not shop level) and matches the "parking facilities" narrative in CONTEXT.md (which is a brand-level rollup, not a shop-to-shop merge).

## Info

### IN-01: Selection is not cleared when `params.review` (deep-link filter) changes

**File:** `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx:122-134`
**Issue:** The `useEffect` that resets `selectedIds` depends on most filter params but omits `params.review`. If the user navigates to `?review=N` while items are selected, the selection survives a filter change that removes some of the selected items from view, allowing a user to confirm a merge that includes items not currently visible.
**Fix:** Add `params.review` to the dependency list.

### IN-02: `MergeModal` calls both `onMerged()` and `onClose()` after success

**File:** `frontend/src/widgets/action-items/MergeModal.tsx:40-41`
**Issue:** `onMerged` already closes the modal via the parent (`setMergeModalOpen(false)`), then `onClose()` is invoked which sets the same flag again. Harmless today, but if a future caller wires `onMerged` for analytics only, the double-close could hide future bugs.
**Fix:** Keep one or the other. Recommended: drop the explicit `onClose()` call — let the parent decide via `onMerged`.

### IN-03: `merge_action_items` returns primary without `duplicate_count` annotation

**File:** `apps/action_items/services/lifecycle.py:368-373`
**Issue:** The re-fetched primary lacks `duplicate_count`. Today the view uses `ActionItemReadSerializer` (no `duplicate_count` field), so this is harmless. If `duplicate_count` is later added to the detail serializer, callers will get `0` or an `AttributeError` depending on the serializer field type.
**Fix:** Either annotate `duplicate_count=Count("duplicates")` on the return queryset, or add a code comment noting the annotation is intentionally omitted for the detail surface.

### IN-04: `MergeSerializer` duplicates validation already present in the service

**File:** `apps/action_items/serializers.py:229-238`
**Issue:** `validate` re-implements the `primary_id in duplicate_ids` and duplicate-ids-uniqueness checks already performed by `merge_action_items`. Drift risk: if one is updated and the other isn't, error messages diverge.
**Fix:** Keep the serializer-level checks (they fail fast with 400 before the DB hit) but extract the shared rules into a single helper called from both places, or remove from the service since the only entry path is via the serializer.

### IN-05: `DuplicatePickerModal` cannot exclude already-merged items beyond client filter

**File:** `frontend/src/widgets/action-items/DuplicatePickerModal.tsx:56-58`
**Issue:** The list endpoint hides duplicates via `canonical__isnull=True`, so the picker results are already valid primaries. The client-side `r.source === "AI"` belt-and-braces filter is good. There is no test that exercises the picker against a row that is somehow a duplicate (e.g. an admin running multiple tabs), but the backend will reject such a merge with the D-08 check ("Primary is already a merged duplicate"). Consider mapping that backend error to a specific toast: today the user sees the generic "Could not merge items. Please try again."
**Fix:** In `MergeModal.handleMergeConfirm` and `ActionItemModal.handleConfirmDetailMerge`, parse `ApiError.data` for backend `ValidationError` messages and surface them in the toast.

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
