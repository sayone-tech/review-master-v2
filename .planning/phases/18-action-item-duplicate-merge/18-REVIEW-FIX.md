---
phase: 18-action-item-duplicate-merge
fixed_at: 2026-05-22T00:00:00Z
review_path: .planning/phases/18-action-item-duplicate-merge/18-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 18: Code Review Fix Report

**Fixed at:** 2026-05-22
**Source review:** `.planning/phases/18-action-item-duplicate-merge/18-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (all Warnings; no Criticals)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### WR-01: D-17 guards on `transition_status` / `assign` / `add_note` are dead code under the new selector

**Files modified:** `apps/action_items/selectors/items.py`, `apps/action_items/views.py`
**Commit:** `1bd882b`
**Applied fix:** Added an `include_duplicates: bool = False` flag to `list_action_items`. The default keeps the list endpoint's behaviour (hide merged duplicates). `get_action_item` passes `include_duplicates=True`. In `ActionItemViewSet.get_queryset`, every action except `list` now also passes `include_duplicates=True`. This restores the D-17 contract: PATCH / transition-status / add-note / merge on a merged duplicate returns HTTP 400 "cannot modify a merged duplicate" instead of a misleading 404, and the detail panel's "Also reported in" deep links resolve. Requires human verification because the existing tests (`test_patch_merged_duplicate_returns_400`, `test_status_transition_merged_duplicate_returns_400`) accept either 400 or 404 — they continue to pass but the actual response is now tightened to 400. The fix narrows a previously loose contract; confirm and consider tightening the test assertions.

### WR-02: TOCTOU on `canonical_id` — merge can race with status / assign / note

**Files modified:** `apps/action_items/services/lifecycle.py`
**Commit:** `0cca02e`
**Applied fix:** Added a post-lock re-check of `locked.canonical_id` inside `transition_status`, `assign_action_item`, and `add_note`. The pre-lock check is kept as a fast-path. `add_note` previously had no `select_for_update` at all — it now acquires the same row lock used by the other mutators before the note insert (this also closes a previously unprotected window for notes, which are append-only and thus particularly damaging if a stale-snapshot insert slips through).

### WR-03: Re-parented sub-duplicates in merge are not locked

**Files modified:** `apps/action_items/services/lifecycle.py`
**Commit:** `982a611`
**Applied fix:** Resolve sub-duplicate IDs BEFORE acquiring the `select_for_update`, then include them in `all_ids` so the lock covers every row the transaction will write to. The existence check is relaxed to apply only to the directly-selected rows (primary + `duplicate_ids`); sub-duplicates may legitimately vanish between resolve and lock and the re-parent UPDATE handles whichever remain. Validation loops (D-05 scope, D-06 source) are restricted to the directly-selected set so sub-duplicates aren't re-checked against checks they passed at their original merge time.

### WR-04: Re-parented sub-duplicates write no audit log

**Files modified:** `apps/action_items/services/lifecycle.py`
**Commit:** `030c05e`
**Applied fix:** After the re-parent UPDATE, bulk-create one `AuditLog` row per affected sub-duplicate with `action="action_item.canonical_changed"`, capturing `before_data={"canonical_id": <old>}` and `after_data={"canonical_id": primary_id}`. The old canonical_id is captured from the already-locked rows before the UPDATE runs, so no extra SELECT is needed. Query count stays constant regardless of sub-duplicate count.

### WR-05: `merge_action_items` does not verify primary is `source=AI` explicitly

**Files modified:** `apps/action_items/services/lifecycle.py`
**Commit:** `9e95581`
**Applied fix:** Replaced the generic loop with two distinct checks: `"Primary must be an AI-sourced action item."` when the primary itself is non-AI, and `"Only AI-sourced items can be merged. Non-AI duplicates: [pk1, pk2]"` listing the offending IDs when the duplicates are non-AI. The frontend can now show a targeted toast. Both messages preserve the "AI-sourced" substring for any tests asserting on that token family.

### WR-06: `DuplicatePickerModal` allows cross-shop SHOP merges silently

**Files modified:** `frontend/src/widgets/action-items/DuplicatePickerModal.tsx`
**Commit:** `bd5ed15`
**Applied fix:** When `currentItem.scope === "SHOP"` and `currentItem.shop_id !== null`, the picker now passes `shop=currentItem.shop_id` to `listActionItems`, server-side filtering out candidates from other shops. Imported `ListParams` from `./types` to type the params object explicitly. The backend still permits cross-shop SHOP merges (D-05 only constrains scope), but the picker UI no longer surfaces them silently — cross-shop rollups belong at the BRAND scope per CONTEXT.md.

---

_Fixed: 2026-05-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
