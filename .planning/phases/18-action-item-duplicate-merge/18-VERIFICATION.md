---
phase: 18-action-item-duplicate-merge
verified: 2026-05-22T00:00:00Z
status: passed
score: 26/26 must-haves verified
overrides_applied: 0
---

# Phase 18: Action Item Duplicate Merge — Verification Report

**Phase Goal:** Allow users to mark multiple ActionItems as duplicates of a single canonical item, from both list (multi-select + Merge toolbar) and detail (Mark as duplicate of…) views, with backend self-FK + service + endpoint, and read-only guards on merged duplicates.

**Verified:** 2026-05-22
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Org Admin can select 2+ AI items and merge via two-step modal (pick primary → confirm) | VERIFIED | `ActionItemManagementWidget.tsx:236` toolbar gates on `isOrgAdmin && selectedIds.size >= 2`; `MergeModal.tsx:67,162` renders "Pick primary" step then confirmation "Merge {N} items into '{title}'? This cannot be undone." |
| SC-2 | Merged duplicates hidden from list; canonical shows +N badge | VERIFIED | `selectors/items.py:48` adds `.filter(canonical__isnull=True)`; line 49 annotates `duplicate_count=Count('duplicates')`. `ActionItemTable.tsx:211-216` renders `+{r.duplicate_count}` badge when `duplicate_count > 0`. |
| SC-3 | Canonical detail shows "Also reported in" with shop/date/rating | VERIFIED | `views.py:93-99` prefetches `duplicates` with `select_related('shop','source_review')`. `serializers.py:126` exposes nested `duplicates`. `ActionItemModal.tsx:185-191` renders "Also reported in" section. |
| SC-4 | "Mark as duplicate of…" from detail with search-as-you-type picker | VERIFIED | `ActionItemModal.tsx:225-232` renders button gated on `isOrgAdmin && source==='AI' && canonical_id===null`. `DuplicatePickerModal.tsx:43-50` debounced search; `ActionItemModal.tsx:518-529` shows confirmation. |
| SC-5 | Merged duplicates read-only — status/assign/notes return 400 | VERIFIED | `services/lifecycle.py:132,184,230` — `transition_status`, `assign_action_item`, `add_note` raise `ValidationError("Cannot modify a merged duplicate.")` when `canonical_id` set. `views.py:125-126` PATCH guard. |
| SC-6 | POST /merge/ Org Admin only; validates same org/scope/AI/non-chained | VERIFIED | `views.py:71-75` `get_permissions` returns `[IsOrgAdmin, IsOrgScoped]` for `merge_action`. `services/lifecycle.py:339-350` validates non-chained primary (D-08), AI source (D-06), same scope (D-05); `:329` filters by `organisation_id`. |

**Score:** 6/6 success criteria verified.

### Required Artifacts (Three-Level Check)

| Artifact | Expected | Exists | Substantive | Wired | Data Flows | Status |
|---|---|---|---|---|---|---|
| `apps/action_items/models.py` | canonical self-FK SET_NULL related_name='duplicates' db_index | Y | Y (lines 94-101) | Y | Y | VERIFIED |
| `apps/action_items/migrations/0003_actionitem_canonical.py` | AddField canonical | Y | Y (AddField w/ SET_NULL, db_index, related_name) | Y | Y | VERIFIED |
| `apps/action_items/services/lifecycle.py` | merge_action_items + guards | Y | Y (`merge_action_items` lines 300-373; guards 132/184/230) | Y (called from views.py:191) | Y | VERIFIED |
| `apps/action_items/selectors/items.py` | hide duplicates + annotate count | Y | Y (lines 48-49) | Y | Y | VERIFIED |
| `apps/action_items/serializers.py` | duplicate_count + nested duplicates + MergeSerializer | Y | Y (lines 76, 111, 126, 224-237) | Y | Y | VERIFIED |
| `apps/action_items/views.py` | merge endpoint + permission split + D-17 guard | Y | Y (lines 71-75, 125-126, 178-199) | Y | Y | VERIFIED |
| `frontend/src/widgets/data-table/DataTable.tsx` | checkbox column | Y | Y (lines 33-103, selectable keys, header select-all) | Y (consumed by ActionItemTable) | Y | VERIFIED |
| `frontend/src/widgets/action-items/types.ts` | duplicate types | Y | Y (lines 29-30, 43, 69) | Y | Y | VERIFIED |
| `frontend/src/widgets/action-items/api.ts` | mergeActionItems fetch | Y | Y (lines 148-153) | Y (called from MergeModal/ActionItemModal) | Y | VERIFIED |
| `frontend/src/widgets/action-items/MergeModal.tsx` | two-step modal | Y | Y (pick primary + confirm w/ "cannot be undone") | Y (rendered from widget) | Y | VERIFIED |
| `frontend/src/widgets/action-items/DuplicatePickerModal.tsx` | search picker | Y | Y (debounced search, results list, picked callback) | Y (rendered from ActionItemModal:507) | Y | VERIFIED |
| `frontend/src/widgets/action-items/ActionItemModal.tsx` | Also reported in + Mark as duplicate of… | Y | Y (lines 185-191, 225-232, 518-529) | Y | Y | VERIFIED |
| `frontend/src/widgets/action-items/ActionItemTable.tsx` | +N badge + selection plumbing | Y | Y (lines 177-191 select plumbing, 211-216 badge) | Y | Y | VERIFIED |
| `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` | merge toolbar + isOrgAdmin gating | Y | Y (lines 117, 119, 152, 236-258, 413-419) | Y | Y | VERIFIED |

### Requirements Coverage D-01..D-20

| ID | Description | Status | Evidence |
|----|-------------|--------|----------|
| D-01 | canonical self-FK | SATISFIED | `models.py:94-101` |
| D-02 | on_delete=SET_NULL | SATISFIED | `models.py:98` |
| D-03 | Read-only guards on duplicates | SATISFIED | `lifecycle.py:132,184,230` raise ValidationError |
| D-04 | Migration adds canonical FK + index | SATISFIED | `0003_actionitem_canonical.py` |
| D-05 | Same-scope only | SATISFIED | `lifecycle.py:348-350` |
| D-06 | source=AI only | SATISFIED | `lifecycle.py:343-345` |
| D-07 | Confirmation dialog before commit | SATISFIED | `MergeModal.tsx:158-164` confirm step |
| D-08 | Cannot chain (primary can't already be duplicate) | SATISFIED | `lifecycle.py:339-340` |
| D-09 | Sub-duplicates re-parented to new canonical | SATISFIED | `lifecycle.py:353` `filter(canonical_id__in=duplicate_ids).update(canonical_id=primary_id)` |
| D-10 | Selector filters merged duplicates | SATISFIED | `selectors/items.py:48` |
| D-11 | duplicate_count annotation + +N badge | SATISFIED | `selectors/items.py:49`; `serializers.py:111`; `ActionItemTable.tsx:211-216` |
| D-12 | get_action_item prefetches duplicates w/ select_related | SATISFIED | `views.py:93-99` (prefetch happens on retrieve action in viewset) |
| D-13 | "Also reported in" section | SATISFIED | `ActionItemModal.tsx:185-191` |
| D-14 | merge_action_items service | SATISFIED | `lifecycle.py:300-373` |
| D-15 | transaction.atomic + no side-effects | SATISFIED | `lifecycle.py:300` `@transaction.atomic`; no status/notification mutation |
| D-16 | POST /merge/ Org Admin only | SATISFIED | `views.py:71-75, 178-199` |
| D-17 | PATCH + status endpoint return 400 on canonical_id | SATISFIED | `views.py:125-126` (PATCH); `views.py:158-160` maps DjangoValidationError → DRF 400 |
| D-18 | List multi-select + Merge toolbar | SATISFIED | `ActionItemManagementWidget.tsx:236-258`; `DataTable.tsx` checkbox column |
| D-19 | Detail "Mark as duplicate of…" picker | SATISFIED | `ActionItemModal.tsx:225-232`; `DuplicatePickerModal.tsx` |
| D-20 | Confirmation: "Merge {N} items into '{title}'? This cannot be undone." | SATISFIED | `MergeModal.tsx:162-163`; `ActionItemModal.tsx:528` |

**All 20 requirement IDs satisfied. No orphaned IDs.**

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `views.py:merge_action` | `services/lifecycle.py:merge_action_items` | direct import line 40 + call line 191 | WIRED |
| `services/lifecycle.py` write guards | model.canonical_id | `if action_item.canonical_id is not None: raise` | WIRED |
| `selectors/items.py:list_action_items` | `views.py:get_queryset` | called line 91 | WIRED |
| `serializers.ActionItemReadSerializer.duplicates` | `views.py` retrieve prefetch | `Prefetch('duplicates', queryset=...)` line 95-98 | WIRED |
| `MergeModal` | `api.mergeActionItems` | imported & called on confirm | WIRED |
| `DuplicatePickerModal` → `ActionItemModal` → `ConfirmModal` → `mergeActionItems` | detail flow | `ActionItemModal.tsx:507, 518-529` | WIRED |
| `ActionItemTable` selection | `ActionItemManagementWidget` selectedIds state | props lines 177, 191; widget 152, 236 | WIRED |
| `DataTable` checkbox column | `ActionItemTable` consumers | `selectedIds`/`onToggleRow`/`onToggleAll` props | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Backend tests pass | `.venv/bin/pytest apps/action_items/` | 80 passed, 1 skipped | PASS |
| TypeScript clean | `npx tsc --noEmit` (frontend) | exit 0, no output | PASS |
| Migration exists & well-formed | Read `0003_actionitem_canonical.py` | AddField w/ SET_NULL + db_index + related_name='duplicates' | PASS |

### Anti-Patterns Found

None. Scanned `services/lifecycle.py`, `views.py`, `serializers.py`, `selectors/items.py`, and frontend widgets for TODO/FIXME/XXX/placeholder/return-null/stub patterns — no debt markers or hollow implementations in phase-modified code.

### Plan Deviations Reviewed

- **18-03 worktree recovery** — executor initially wrote to main repo before recovering to worktree; recovery confirmed clean before merge. Codebase state matches plan intent — VERIFIED.
- **18-04 isOrgAdmin plumbing** — `isOrgAdmin` prop added to `ActionItemManagementWidget`. Confirmed at `ActionItemManagementWidget.tsx:119` (`userRole === "ORG_ADMIN"`) gating toolbar (line 236) and propagated to child modals (lines 276, 399). This is a clean Rule-2 extension — VERIFIED.

### Gaps Summary

None. All 6 ROADMAP success criteria verified, all 20 D-XX requirements satisfied, all artifacts pass three-level (exists, substantive, wired) plus data-flow trace, all key links wired, tests green (80 pass / 1 skip), TypeScript clean.

---

*Verified: 2026-05-22*
*Verifier: Claude (gsd-verifier)*
