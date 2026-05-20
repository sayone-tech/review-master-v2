# Phase 18: Action Item Duplicate Merge - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The AI enrichment pipeline extracts action items independently per review — so the same issue reported across multiple stores (e.g. "parking facilities" vs "enhance parking space") creates separate rows that clutter the list. This phase adds a **user-driven merge** flow: Org Admins can select action items and merge them under a single canonical item. Merged duplicates disappear from the list but appear as read-only context in the canonical's detail view (with date, store, source review). The canonical item is the only one that can be actioned (status changes, assignment, notes).

**Out of scope:** Automatic AI-driven deduplication, unmerge, cross-scope merging, bulk-resolve across duplicates.

</domain>

<decisions>
## Implementation Decisions

### Data model
- **D-01:** Add `canonical = ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='duplicates', db_index=True)` to `ActionItem`. When `canonical` is set, the item is a merged duplicate; when `canonical` is `None`, the item is primary (standalone or canonical).
- **D-02:** `on_delete=SET_NULL` — if the canonical item is deleted, its duplicates become standalone (canonical resets to None). This is safer than CASCADE (avoids silent bulk-delete) and avoids PROTECT blocking deletion of canonicals.
- **D-03:** Duplicates become **read-only context** once merged: no status changes, no assignment, no notes allowed on them. Enforcement in the service layer — `transition_status`, `assign_action_item`, `add_note` raise `ValidationError` if `action_item.canonical_id` is not None.
- **D-04:** New migration adds the `canonical` FK column and a DB index. No data migration needed — all existing items start with `canonical=None`.

### Merge rules
- **D-05:** Only **same-scope** items can be merged — SHOP with SHOP, BRAND with BRAND. The service validates this and raises `ValidationError` if scopes differ.
- **D-06:** Only `source='AI'` items can be merged initially (manual items excluded) — the problem domain is AI-extracted duplicates. Can be relaxed in a future phase.
- **D-07:** Merge is **permanent** — no unmerge UI. User is shown a confirmation dialog before the operation is committed. Confirmation text: "Merge {N} items into '{canonical title}'? This cannot be undone."
- **D-08:** A canonical item cannot itself be merged into another item (cannot chain). The service validates: if the selected primary already has a `canonical_id`, raise `ValidationError("Cannot use a merged item as primary.")`.
- **D-09:** If one of the selected duplicates already has its own duplicates (it was previously a canonical), those sub-duplicates are **re-parented** to the new canonical — no orphaning.

### List view changes
- **D-10:** `list_action_items()` selector adds `.filter(canonical__isnull=True)` so merged duplicates are hidden from the list.
- **D-11:** List query annotates `duplicate_count=Count('duplicates')` for every item. The serializer exposes this as `duplicate_count: int`. Frontend shows `+{N}` badge when `duplicate_count > 0`.

### Detail view changes
- **D-12:** `get_action_item()` prefetches `duplicates` with `select_related('shop', 'source_review')`. Detail serializer includes a `duplicates` nested list: `[{id, title, shop_name, source_review_date, source_review_rating}]` — read-only context, no status/assignee.
- **D-13:** The detail UI renders a "Also reported in" section when `duplicates.length > 0`, showing each duplicate as a collapsed row: shop name, date, star rating of the source review.

### Merge service
- **D-14:** New function `merge_action_items(*, primary_id: int, duplicate_ids: list[int], actor: User) -> ActionItem` in `apps/action_items/services/lifecycle.py`:
  1. Fetch primary + duplicates, validate all belong to same org, same scope, primary has no `canonical`.
  2. Re-parent any existing sub-duplicates of the selected duplicates to primary.
  3. `ActionItem.objects.filter(pk__in=duplicate_ids).update(canonical_id=primary_id)`.
  4. Return the primary item (refreshed from DB with prefetch).
- **D-15:** Wrap in `transaction.atomic()`. No side-effects (no notification, no status change on primary).

### API
- **D-16:** New endpoint: `POST /api/v1/action-items/merge/` on `ActionItemViewSet` (`@action(detail=False, methods=['post'])`). Body: `{primary_id: int, duplicate_ids: [int]}`. Permission: Org Admin only (no Staff). Returns the updated primary item.
- **D-17:** Existing `PATCH /api/v1/action-items/{id}/` and `POST /api/v1/action-items/{id}/status/` return `400` if the target item has `canonical_id` set (it's a merged duplicate — not actionable).

### Merge UX — two entry points
- **D-18 — List view multi-select:** Checkboxes appear on action item rows (Org Admin only). When 2+ are checked, a "Merge duplicates" button appears in the toolbar. Clicking opens a modal: "Pick the primary item" (radio buttons on the selected items). Confirm → POST `/merge/`.
- **D-19 — Detail view:** "Mark as duplicate of…" button on an action item's detail panel (Org Admin only). Opens a search-as-you-type picker scoped to same-scope items in the same org. Selecting and confirming → POST `/merge/` with current item as duplicate, selected as primary.
- **D-20:** Both flows show the same confirmation: "Merge {N} items into '{primary title}'? This cannot be undone." User must click "Merge" to confirm.

### Claude's Discretion
- Exact serializer field names for `duplicate_count` and the nested `duplicates` list
- Whether the checkbox multi-select re-uses an existing selection pattern in the frontend or needs a new one
- Whether `duplicate_count` is annotated in the selector or computed as a `SerializerMethodField`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend
- `apps/action_items/models.py` — `ActionItem` model (add `canonical` FK + migration)
- `apps/action_items/selectors/items.py` — `list_action_items()` (add `canonical__isnull=True` filter + `duplicate_count` annotation)
- `apps/action_items/services/lifecycle.py` — add `merge_action_items()`, guard existing functions against acting on duplicates
- `apps/action_items/views.py` — `ActionItemViewSet` (add `merge` action endpoint)
- `apps/action_items/serializers.py` — list serializer (add `duplicate_count`), detail serializer (add nested `duplicates`)
- `apps/action_items/filters.py` — `ActionItemFilterSet` (no change needed — `canonical__isnull=True` is in selector)
- Frontend: action items list widget (add checkboxes, toolbar, "+N" badge) and detail panel ("Also reported in" section + "Mark as duplicate of" button)

### Architecture constraints
- `CLAUDE.md` §5 — `merge_action_items()` is a service function; ViewSet calls it, not inline logic
- `CLAUDE.md` §6 — prefetch `duplicates` on detail fetch; annotate `duplicate_count` in selector (not N+1 via SerializerMethodField)
- `CLAUDE.md` §9 — Staff Admins must NEVER see brand-scope items; the `canonical__isnull=True` filter must apply AFTER the existing scope filter, not replace it
- `CLAUDE.md` §24 — Order: model + migration → service → selector → serializer → view → frontend

</canonical_refs>

<code_context>
## Existing Code Insights

### Selector to extend
```python
# apps/action_items/selectors/items.py — current
qs = ActionItem.objects.filter(organisation_id=organisation_id).select_related(...)
# After Phase 18: add
qs = qs.filter(canonical__isnull=True).annotate(duplicate_count=Count('duplicates'))
```

### Service guard pattern
- `transition_status`, `assign_action_item`, `add_note` all take `action_item: ActionItem` as first arg
- Add at top of each: `if action_item.canonical_id: raise ValidationError("Cannot modify a merged duplicate.")`

### Existing list UI
- Action items list is in the frontend under `frontend/src/widgets/action-items/`
- Check for existing checkbox/multi-select patterns in the review management widget — reuse if present

</code_context>

<deferred>
## Deferred Ideas

- **Automatic AI deduplication** — before creating an action item, check if a similar one (fuzzy title match) already exists for the org — own phase, requires embedding similarity or GPT comparison
- **Manual items merging** — currently only AI-sourced items can be merged; extend to manual in a future phase
- **Bulk-resolve across duplicates** — resolving a canonical auto-resolves all duplicates — deferred per user decision (statuses are independent)
- **Unmerge** — detach a duplicate back to standalone — deferred per user decision (merge is permanent)

</deferred>

---

*Phase: 18-action-item-duplicate-merge*
*Context gathered: 2026-05-18*
