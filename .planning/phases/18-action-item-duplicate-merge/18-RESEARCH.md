# Phase 18: Action Item Duplicate Merge — Research

**Researched:** 2026-05-22
**Domain:** Django self-referential ForeignKey, DRF ViewSet custom action, React multi-select UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Data model**
- D-01: `canonical = ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='duplicates', db_index=True)` added to `ActionItem`
- D-02: `on_delete=SET_NULL` — if canonical deleted, duplicates revert to standalone
- D-03: Duplicates are read-only: `transition_status`, `assign_action_item`, `add_note` raise `ValidationError` if `action_item.canonical_id is not None`
- D-04: New migration `0003_actionitem_canonical` with DB index; no data migration

**Merge rules**
- D-05: Only same-scope items can be merged (SHOP+SHOP or BRAND+BRAND)
- D-06: Only `source='AI'` items can be merged (manual excluded for now)
- D-07: Merge is permanent; confirmation dialog: "Merge {N} items into '{canonical title}'? This cannot be undone."
- D-08: A canonical item that already has a `canonical_id` cannot be used as primary (no chaining)
- D-09: Sub-duplicates of a selected duplicate are re-parented to the new primary (no orphaning)

**List view**
- D-10: `list_action_items()` adds `.filter(canonical__isnull=True)` (merged duplicates hidden)
- D-11: Annotates `duplicate_count=Count('duplicates')`; serializer exposes `duplicate_count: int`; frontend shows `+{N}` badge when `> 0`

**Detail view**
- D-12: `get_action_item()` prefetches `duplicates` with `select_related('shop', 'source_review')`; detail serializer includes nested `duplicates` list `[{id, title, shop_name, source_review_date, source_review_rating}]`
- D-13: Detail UI shows "Also reported in" section when `duplicates.length > 0`

**Merge service**
- D-14: New function `merge_action_items(*, primary_id, duplicate_ids, actor) -> ActionItem` in `apps/action_items/services/lifecycle.py`
- D-15: Wrapped in `transaction.atomic()`; no notifications; no status changes on primary

**API**
- D-16: `POST /api/v1/action-items/merge/` — `@action(detail=False, methods=['post'])`; body `{primary_id: int, duplicate_ids: [int]}`; Org Admin only; returns updated primary
- D-17: `PATCH /api/v1/action-items/{id}/` and `POST /api/v1/action-items/{id}/status/` return `400` if target has `canonical_id` set

**UX — two entry points**
- D-18: List view multi-select checkboxes (Org Admin only); "Merge duplicates" toolbar button when ≥2 checked; modal with radio to pick primary; confirm → POST `/merge/`
- D-19: Detail view "Mark as duplicate of…" button (Org Admin only); search-as-you-type picker; selected item becomes primary; confirm → POST `/merge/` with current as duplicate
- D-20: Same confirmation text for both flows

### Claude's Discretion
- Exact serializer field names for `duplicate_count` and the nested `duplicates` list
- Whether checkbox multi-select re-uses an existing pattern or needs a new one
- Whether `duplicate_count` is annotated in the selector or computed as a `SerializerMethodField`

### Deferred Ideas (OUT OF SCOPE)
- Automatic AI deduplication (embedding similarity / GPT comparison)
- Manual items merging (currently AI-only)
- Bulk-resolve across duplicates
- Unmerge
</user_constraints>

---

## Summary

Phase 18 adds a self-referential FK to `ActionItem` (`canonical` pointing to itself) that marks merged duplicates. The migration is straightforward — one column plus a DB index, no data migration needed. The service layer gains a new `merge_action_items()` function and three existing mutators get a read-only guard at their top. The selector gains a `canonical__isnull=True` filter plus a `Count('duplicates')` annotation. The API gains a single new `@action` endpoint restricted to Org Admin. The frontend gains two UX entry points: row checkboxes on the list table and a "Mark as duplicate of…" button in the detail modal.

The codebase is consistent and well-structured. No external packages are needed for this phase — it is pure extension of existing patterns. The existing `DataTable` component does NOT support checkboxes natively; that prop will need to be added (or worked around with a custom first column). The `ConfirmModal` component exists and is reusable as-is. The `IsOrgAdmin` permission class already exists in `apps/accounts/permissions.py`.

The primary technical risk is the annotation ordering in `list_action_items()`: the `Count('duplicates')` annotation must be applied AFTER the `canonical__isnull=True` filter to avoid counting rows that are themselves duplicates. Django ORM evaluates annotations on the filtered queryset, so the order in Python is filter-then-annotate to be explicit and correct.

**Primary recommendation:** Implement in four plans — (1) model + migration, (2) service + selector + serializer + backend view, (3) frontend list multi-select + merge modal, (4) frontend detail "Mark as duplicate of…" + "Also reported in" section.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Merge validation (scope, source, ownership) | API / Backend (service) | — | Business rules; must not be client-enforced |
| Duplicate hiding from list | API / Backend (selector) | — | DB-level filter; cannot trust client |
| Duplicate count annotation | API / Backend (selector) | — | Avoids N+1; single annotated queryset |
| Read-only guard on merged duplicates | API / Backend (service) | — | Security invariant; must be enforced server-side |
| Sub-duplicate re-parenting | API / Backend (service) | — | Atomicity requirement |
| `+N` badge display | Frontend / Client | — | Presentation only |
| Multi-select checkboxes | Frontend / Client | — | Interaction pattern |
| Search-as-you-type primary picker | Frontend / Client | — | Client-side filter over existing org items |
| Confirmation dialog | Frontend / Client | — | UX gate; server validates regardless |

---

## Standard Stack

No new packages. All work extends existing project dependencies. [VERIFIED: codebase grep]

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django 6.0.x | 6.0.x | ORM self-referential FK, `Count`, `F`, `transaction.atomic` | Project standard |
| Django REST Framework | latest | `@action(detail=False)`, `ValidationError` response | Project standard |
| django-filter | latest | `ActionItemFilterSet` (no changes needed) | Project standard |
| React + TypeScript | project version | Multi-select checkboxes, modals, search picker | Project standard |

### Installation

No new packages to install.

---

## Package Legitimacy Audit

No external packages are introduced in this phase.

**Packages removed due to slopcheck:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (Org Admin)
    │
    ├─ List view: checkbox per row → toolbar "Merge" button
    │       │
    │       └─ MergeModal (radio pick primary, confirm)
    │               │
    │               └─ POST /api/v1/action-items/merge/
    │
    └─ Detail view: "Mark as duplicate of…" button
            │
            └─ DuplicatePickerModal (search-as-you-type)
                    │
                    └─ POST /api/v1/action-items/merge/

POST /api/v1/action-items/merge/
    │ ActionItemViewSet.merge_action @action(detail=False)
    │ Permission: IsOrgAdmin + IsOrgScoped
    │
    └─ merge_action_items(primary_id, duplicate_ids, actor)
            ├─ Fetch primary + duplicates with select_for_update
            ├─ Validate: same org, same scope, source=AI, primary has no canonical
            ├─ Re-parent sub-duplicates of selected duplicates → primary
            ├─ bulk update(canonical_id=primary_id) on duplicate_ids
            ├─ AuditLog.objects.create(action="action_item.merged")
            └─ return primary (refreshed, prefetch duplicates)

GET /api/v1/action-items/              (list)
    └─ list_action_items()
            ├─ .filter(canonical__isnull=True)   ← merged duplicates hidden
            └─ .annotate(duplicate_count=Count('duplicates'))

GET /api/v1/action-items/{id}/         (detail)
    └─ get_action_item()
            └─ prefetch_related(
                   Prefetch('duplicates',
                       queryset=ActionItem.objects.select_related(
                           'shop', 'source_review')))
```

### Recommended Project Structure

No new directories. All changes are additive to existing files.

```
apps/action_items/
├── migrations/
│   └── 0003_actionitem_canonical.py        # NEW — self-ref FK + db_index
├── models.py                               # MODIFIED — add canonical FK
├── selectors/items.py                      # MODIFIED — filter + annotate
├── services/lifecycle.py                   # MODIFIED — merge fn + guards
├── serializers.py                          # MODIFIED — list + detail serializers
└── views.py                               # MODIFIED — merge @action

frontend/src/widgets/action-items/
├── types.ts                                # MODIFIED — duplicate_count, duplicates list
├── api.ts                                  # MODIFIED — mergeActionItems()
├── ActionItemTable.tsx                     # MODIFIED — checkbox column, toolbar
├── ActionItemManagementWidget.tsx          # MODIFIED — selected set state, merge flow
├── ActionItemModal.tsx                     # MODIFIED — "Mark as duplicate of…" + "Also reported in"
└── MergeModal.tsx                          # NEW — primary picker + confirm
    DuplicatePickerModal.tsx                # NEW — search-as-you-type picker
```

### Pattern 1: Self-Referential ForeignKey in Django

**What:** A FK that points to the same model — the standard Django pattern for hierarchical/tree-like relationships.
**When to use:** Parent–child relationships where the parent is the same type as the child.

```python
# Source: Django docs (ASSUMED — standard Django pattern, stable across versions)
# apps/action_items/models.py
canonical = models.ForeignKey(
    'self',
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name='duplicates',
    db_index=True,
)
```

Key points: [ASSUMED: standard Django ORM behavior]
- `related_name='duplicates'` makes `item.duplicates.all()` available
- `on_delete=SET_NULL` means deleting a canonical sets `canonical=None` on its duplicates (they become standalone again)
- `db_index=True` is required — the selector filters `canonical__isnull=True` on every list query

### Pattern 2: Count Annotation After Filter (Critical Order)

**What:** Annotating a reverse FK count on a filtered queryset.
**When to use:** Whenever you need a per-row aggregate that must not include excluded rows.

```python
# Source: [VERIFIED: codebase — existing selector pattern at apps/action_items/selectors/items.py]
# CORRECT order: filter first, then annotate
from django.db.models import Count

def list_action_items(*, organisation_id: int, user: User) -> QuerySet[ActionItem]:
    # ... role-based base filter ...
    qs = qs.filter(canonical__isnull=True)          # hide merged duplicates
    qs = qs.annotate(duplicate_count=Count('duplicates'))  # count only canonical items' duplicates
    return qs.order_by("-created_at")
```

**Critical:** If you annotate before filtering, Django may still produce correct results, but the intent is unclear and future developers may reorder. Keep filter-then-annotate for readability and correctness.

**N+1 avoidance:** `Count('duplicates')` is a single aggregate JOIN — not an extra query per row. The existing query budget test must be updated to accommodate the added JOIN (expect +0 queries, just a more complex SQL).

### Pattern 3: `@action(detail=False)` Custom ViewSet Endpoint

**What:** Adding a non-CRUD endpoint to an existing ViewSet.
**When to use:** When the operation is a collection-level mutation (not tied to a specific object PK).

```python
# Source: [VERIFIED: codebase — transition_status_action already uses this pattern]
# apps/action_items/views.py
from rest_framework.decorators import action

@action(detail=False, methods=["post"], url_path="merge",
        permission_classes=[IsOrgAdmin, IsOrgScoped])
def merge_action(self, request: Request) -> Response:
    s = MergeSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    primary = merge_action_items(
        primary_id=s.validated_data["primary_id"],
        duplicate_ids=s.validated_data["duplicate_ids"],
        actor=request.user,
        organisation_id=request.user.organisation_id,
    )
    return Response(ActionItemReadSerializer(primary).data)
```

**Permission scoping:** The merge endpoint overrides the ViewSet's default `[IsOrgScoped, BrandScopeGuard]` permission with `[IsOrgAdmin, IsOrgScoped]`. This is consistent with the existing pattern in `apps/shops/views.py` and `apps/regions/views.py` where `get_permissions()` returns role-specific permission lists per action. Use the same `get_permissions()` override approach.

### Pattern 4: Nested Prefetch for Duplicates on Detail

**What:** Prefetching a related reverse-FK queryset with `select_related` on the inner queryset.
**When to use:** Detail endpoint needing a nested list without N+1.

```python
# Source: [VERIFIED: codebase — existing prefetch in ActionItemViewSet.get_queryset()]
from django.db.models import Prefetch

if self.action == "retrieve":
    qs = qs.prefetch_related(
        "notes__author",
        Prefetch(
            "duplicates",
            queryset=ActionItem.objects.select_related("shop", "source_review"),
        ),
    )
```

**The nested serializer field names per D-12:**
`[{id, title, shop_name, source_review_date, source_review_rating}]`
- `shop_name`: `obj.shop.name if obj.shop else ""`
- `source_review_date`: `obj.source_review.review_create_time if obj.source_review else None`
- `source_review_rating`: `obj.source_review.star_rating if obj.source_review else None`

The `Review` model has `review_create_time` (DateTimeField) and `star_rating` (SmallIntegerField). [VERIFIED: codebase — apps/reviews/models.py lines 49, 54]

### Pattern 5: Service-Layer Merge Implementation

**What:** Atomic multi-step merge with validation, re-parenting, bulk update, audit log.
**When to use:** Any multi-row mutation with business rules.

```python
# Source: [VERIFIED: codebase — lifecycle.py existing @transaction.atomic pattern]
@transaction.atomic
def merge_action_items(
    *,
    primary_id: int,
    duplicate_ids: list[int],
    actor: User,
    organisation_id: int,
) -> ActionItem:
    if not duplicate_ids:
        raise ValidationError("At least one duplicate must be provided.")
    if primary_id in duplicate_ids:
        raise ValidationError("Primary cannot be in the duplicate list.")

    # Lock rows in consistent order to avoid deadlock
    all_ids = sorted({primary_id} | set(duplicate_ids))
    locked = {
        item.pk: item
        for item in ActionItem.objects.select_for_update().filter(
            pk__in=all_ids, organisation_id=organisation_id
        )
    }
    if len(locked) != len(all_ids):
        raise ValidationError("One or more items not found or not in this organisation.")

    primary = locked.get(primary_id)
    if primary is None:
        raise ValidationError("Primary item not found.")

    # D-06: only AI-sourced
    for item in locked.values():
        if item.source != ActionItem.Source.AI:
            raise ValidationError("Only AI-extracted items can be merged.")

    # D-05: same scope
    scopes = {item.scope for item in locked.values()}
    if len(scopes) > 1:
        raise ValidationError("All items must have the same scope to merge.")

    # D-08: primary must not already be a duplicate
    if primary.canonical_id is not None:
        raise ValidationError("Cannot use a merged item as primary.")

    # D-09: re-parent sub-duplicates of selected duplicates
    ActionItem.objects.filter(canonical_id__in=duplicate_ids).update(canonical_id=primary_id)

    # Set canonical on the selected duplicates
    ActionItem.objects.filter(pk__in=duplicate_ids).update(canonical_id=primary_id)

    AuditLog.objects.create(
        organisation_id=organisation_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        entity_type="action_item",
        entity_id=str(primary_id),
        action="action_item.merged",
        before_data={},
        after_data={"merged_ids": duplicate_ids},
    )

    # Return primary refreshed with duplicates prefetched
    return (
        ActionItem.objects.prefetch_related(
            Prefetch(
                "duplicates",
                queryset=ActionItem.objects.select_related("shop", "source_review"),
            )
        )
        .get(pk=primary_id)
    )
```

**Deadlock prevention:** Always lock rows in sorted PK order when using `select_for_update` on multiple rows in one query. [ASSUMED: standard DB locking best practice]

### Pattern 6: Read-Only Guard on Mutators

**What:** Guard at the top of each mutating service function.
**When to use:** Whenever a resource has a read-only mode.

```python
# Source: [VERIFIED: codebase — lifecycle.py functions take action_item: ActionItem as first arg]
# Add to transition_status, assign_action_item, add_note:
def transition_status(*, action_item: ActionItem, new_status: str, actor: User) -> ActionItem:
    if action_item.canonical_id is not None:
        raise ValidationError("Cannot modify a merged duplicate.")
    # ... existing implementation unchanged ...
```

The ViewSet's `update()` method also needs a guard — the serializer's `validate()` or the view's `perform_update()` should check `instance.canonical_id`.

### Pattern 7: Frontend Multi-Select Checkboxes

**What:** Row-level checkbox state tracked in parent widget; toolbar appears when ≥2 selected.
**When to use:** Bulk operations on list rows.

The existing `DataTable` component (at `frontend/src/widgets/data-table/DataTable.tsx`) does NOT have a checkbox prop. [VERIFIED: codebase — DataTable.tsx, no checkbox logic]

**Approach (Claude's discretion):** Add a `selectedIds` prop and `onToggle` callback to `DataTable`, plus an optional leading checkbox column. The `ActionItemTable` passes these down from the widget. This is additive — existing consumers of `DataTable` are unaffected since the props are optional.

```typescript
// Minimal interface additions — Source: [VERIFIED: codebase pattern]
interface DataTableProps<T> {
  // ... existing props ...
  selectedIds?: Set<string>;
  onToggleRow?: (key: string) => void;
  onToggleAll?: (allKeys: string[]) => void;
}
```

Track selection state in `ActionItemManagementWidget`:

```typescript
const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

// Clear selection on page change / filter reset
useEffect(() => { setSelectedIds(new Set()); }, [params.page, params.shop, params.status]);
```

Only `source === 'AI'` rows should be selectable (checkbox disabled for MANUAL). Show the merge toolbar only when `selectedIds.size >= 2` AND `userRole === 'ORG_ADMIN'`.

### Anti-Patterns to Avoid

- **Annotating before filtering:** Annotate `duplicate_count` after `canonical__isnull=True` filter — otherwise the annotation runs on the unfiltered queryset and becomes semantically confusing (though Django may still produce the right result via the WHERE clause applied to the outer query).
- **SerializerMethodField for duplicate_count:** Do NOT use `SerializerMethodField` — it causes N+1 (one extra query per row to count duplicates). Use the `Count('duplicates')` annotation in the selector. [VERIFIED: CONTEXT.md §Architecture constraints + CLAUDE.md §6]
- **Chained canonical FKs:** The service MUST prevent `canonical_id` from being set on an item that is itself already a canonical (D-08). Without this guard, you get chains: A→B→C, and B's `duplicates.all()` returns C but C appears in B's detail — confusing and inconsistent.
- **Selecting Staff-inaccessible items in merge:** The merge endpoint fetches items by PK and validates `organisation_id`. Staff cannot reach this endpoint (permission is `IsOrgAdmin`), so no extra staff-scope check is needed in the service. However, the service must still validate all items belong to `organisation_id` to prevent IDOR.
- **Updating the list query to drop `canonical__isnull=True` after filtering:** `list_action_items` already applies the Staff-scope filter before returning. The `canonical__isnull=True` filter must be chained ON TOP of the existing Staff filter, not replace it. [VERIFIED: CONTEXT.md §Architecture constraints]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic multi-row update | Custom SQL | `ActionItem.objects.filter(...).update(canonical_id=...)` + `transaction.atomic` | Handles rollback, works with Django ORM constraints |
| Row locking | `time.sleep` retry | `select_for_update()` inside `transaction.atomic` | Correct DB-level locking |
| Confirm dialog | Custom modal from scratch | `ConfirmModal` at `frontend/src/widgets/modal/ConfirmModal.tsx` | Already matches design system; supports `variant="amber"` for destructive actions |
| Search-as-you-type picker | External library | `useState` + `useMemo` filter over pre-loaded org items | All action items in the same org fit in memory; no extra API call needed |

**Key insight:** The entire merge flow works on data already available in the frontend (the paginated list rows) plus a focused API call. No new endpoints are needed beyond `POST /merge/`.

---

## Common Pitfalls

### Pitfall 1: `duplicate_count` is undefined on the list serializer

**What goes wrong:** After adding the `Count('duplicates')` annotation, the `ActionItemListSerializer` does not expose it. The frontend receives rows without `duplicate_count`.
**Why it happens:** The base `_ActionItemBaseRead` and `ActionItemListSerializer` have explicit `Meta.fields` lists. Adding a new field to the annotation requires adding it to `fields` as a `serializers.IntegerField(read_only=True)`.
**How to avoid:** Add `duplicate_count = serializers.IntegerField(read_only=True)` to `ActionItemListSerializer` explicitly.
**Warning signs:** `AttributeError: 'ActionItem' object has no attribute 'duplicate_count'` if the annotation is missing; or missing key on the response JSON if the field is not in the serializer.

### Pitfall 2: `get_action_item()` delegates to `list_action_items()` — the prefetch must be added there

**What goes wrong:** `get_action_item()` calls `list_action_items(...).filter(pk=pk).first()`. The prefetch for `duplicates` must be added on the `list_action_items` queryset (when called from the detail context), or the ViewSet's `get_queryset()` must add the prefetch when `self.action == "retrieve"`.
**Why it happens:** [VERIFIED: codebase — `selectors/items.py` line 50]: `get_action_item` reuses `list_action_items` — it does NOT independently construct a queryset.
**How to avoid:** Extend the ViewSet's `get_queryset()` where `self.action == "retrieve"` to add the `Prefetch('duplicates', ...)` (this is exactly how `notes__author` is currently added — line 81 of `views.py`). The selector itself stays simple; the prefetch is applied at the view layer.

### Pitfall 3: `update()` endpoint does not check canonical guard

**What goes wrong:** D-17 says `PATCH /api/v1/action-items/{id}/` returns `400` if the target is a merged duplicate. But `perform_update()` calls `assign_action_item()` which will now raise `ValidationError` — but the `serializer.save()` call before it does NOT raise.
**Why it happens:** The serializer's `save()` writes `title`, `priority`, `due_date` — fields not guarded by the service. The guard in `assign_action_item` only fires if `new_assignee` changes.
**How to avoid:** Add a check in `perform_update()` (or `update()`) at the view level: `if instance.canonical_id: raise ValidationError(...)`. Alternatively add it to `ActionItemUpdateSerializer.validate()` by passing the instance in context.

### Pitfall 4: The `merge` @action needs its own permission, not ViewSet default

**What goes wrong:** The ViewSet uses `[IsOrgScoped, BrandScopeGuard]`. The merge endpoint should be Org Admin only (D-16). Without override, Staff could call it.
**Why it happens:** DRF `@action` inherits `permission_classes` from the ViewSet unless explicitly overridden.
**How to avoid:** Either pass `permission_classes=[IsOrgAdmin, IsOrgScoped]` directly in the `@action` decorator, or override `get_permissions()` in the ViewSet to return the right list based on `self.action`. The `get_permissions()` approach is already used in `apps/shops/views.py` — use the same pattern.

### Pitfall 5: Staff user sees 500 instead of 403 on merge endpoint

**What goes wrong:** Staff user POSTs to `/merge/`. `IsOrgAdmin.has_permission` returns `False`. DRF returns `403` — correct. But if `BrandScopeGuard` runs and `obj` is None (no object for detail=False), it returns `True` by default. This is fine — but confirm `BrandScopeGuard.has_object_permission` is never called on `detail=False` actions (it isn't, DRF only calls `has_object_permission` for `get_object()` calls).
**How to avoid:** Use `permission_classes=[IsOrgAdmin, IsOrgScoped]` on the merge action — `BrandScopeGuard` is irrelevant here and can be omitted from this specific action's permission list.

### Pitfall 6: Sub-duplicate re-parenting uses the wrong query

**What goes wrong:** When duplicate D1 is selected for merging, and D1 itself has sub-duplicates S1, S2 — these sub-duplicates need to be re-parented to the new primary P. If the re-parenting update is `filter(canonical_id__in=duplicate_ids)`, it correctly catches S1 and S2. But if the update is done AFTER setting D1's canonical to P, Django may miss S1/S2 depending on transaction isolation.
**How to avoid:** Perform the re-parenting update BEFORE the bulk update that sets `canonical_id` on the selected duplicates. The order in D-14 is correct: re-parent first, then set canonical on selected duplicates.

### Pitfall 7: Frontend selects all rows including MANUAL items

**What goes wrong:** If the "select all" checkbox in the table header selects MANUAL items, the user sees them in the merge modal but the API rejects with `400`. Confusing UX.
**How to avoid:** Disable the checkbox for `source === 'MANUAL'` rows. The "select all" header checkbox should only select `source === 'AI'` rows. Log a clear error message if somehow a MANUAL item ID appears in `duplicate_ids`.

---

## Key Files to Read / Modify

### Backend (in implementation order)

| File | Action | Key Lines / Notes |
|------|--------|-------------------|
| `apps/action_items/models.py` | MODIFY | Lines 94–113 (Meta, constraints). Add `canonical` FK after `source_review` FK (~line 93). Next migration: `0003_actionitem_canonical.py` |
| `apps/action_items/migrations/0003_actionitem_canonical.py` | CREATE | Standard `AddField` + `AddIndex` for `canonical` + `db_index=True` |
| `apps/action_items/services/lifecycle.py` | MODIFY | Lines 129, 177, 223 — add guard to `transition_status`, `assign_action_item`, `add_note`. Add new `merge_action_items()` function at end of file |
| `apps/action_items/selectors/items.py` | MODIFY | Lines 35–44 — add `.filter(canonical__isnull=True).annotate(duplicate_count=Count('duplicates'))` in `list_action_items()`; update `get_action_item()` (no change needed — prefetch added in view) |
| `apps/action_items/serializers.py` | MODIFY | `ActionItemListSerializer` — add `duplicate_count`; `ActionItemReadSerializer` — add nested `duplicates` list; new `ActionItemDuplicateSerializer`; new `MergeSerializer` |
| `apps/action_items/views.py` | MODIFY | `get_queryset()` — add `Prefetch('duplicates',...)` when `action == "retrieve"`; `get_permissions()` — return `[IsOrgAdmin, IsOrgScoped]` for `merge_action`; add `merge_action` `@action`; `update()` / `perform_update()` — add canonical guard |
| `apps/action_items/tests/test_services.py` | MODIFY | Add `test_merge_*` tests |
| `apps/action_items/tests/test_selectors.py` | MODIFY | Add `test_list_hides_merged_duplicates`, `test_list_annotates_duplicate_count` |
| `apps/action_items/tests/test_views.py` | MODIFY | Add merge endpoint tests, guard tests |
| `apps/action_items/tests/factories.py` | MODIFY | `ActionItemFactory` — no change needed yet (canonical defaults to None by model) |

### Frontend (in implementation order)

| File | Action | Key Notes |
|------|--------|-----------|
| `frontend/src/widgets/action-items/types.ts` | MODIFY | Add `duplicate_count: number` to `ActionItemListRow`; add `ActionItemDuplicate` interface; add `duplicates: ActionItemDuplicate[]` to `ActionItemDetail`; add `MergePayload` type |
| `frontend/src/widgets/action-items/api.ts` | MODIFY | Add `mergeActionItems(payload: MergePayload): Promise<ActionItemDetail>` |
| `frontend/src/widgets/data-table/DataTable.tsx` | MODIFY | Add optional `selectedIds?: Set<string>`, `onToggleRow?`, `onToggleAll?` props; add leading checkbox column when these props are provided |
| `frontend/src/widgets/action-items/ActionItemTable.tsx` | MODIFY | Pass `selectedIds`, `onToggleRow`, `onToggleAll`; disable checkbox for `source === 'MANUAL'`; add `+N` badge to title cell |
| `frontend/src/widgets/action-items/MergeModal.tsx` | CREATE | Shows selected items; radio to pick primary; confirmation text per D-20; "Merge" button calls `mergeActionItems` |
| `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` | MODIFY | Add `selectedIds: Set<number>` state; show merge toolbar when `selectedIds.size >= 2 && isOrgAdmin`; handle merge flow |
| `frontend/src/widgets/action-items/ActionItemModal.tsx` | MODIFY | Add "Mark as duplicate of…" button (Org Admin only, source=AI only); "Also reported in" section with duplicates list; `DuplicatePickerModal` integration |
| `frontend/src/widgets/action-items/DuplicatePickerModal.tsx` | CREATE | Search-as-you-type picker over existing org items; scoped to same scope; filters out already-merged items (canonical_id set) |

---

## Code Examples

### Self-Referential FK Migration

```python
# apps/action_items/migrations/0003_actionitem_canonical.py
# Source: [VERIFIED: codebase — 0002_actionitem_category.py as template]
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('action_items', '0002_actionitem_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionitem',
            name='canonical',
            field=models.ForeignKey(
                'self',
                null=True,
                blank=True,
                on_delete=models.deletion.SET_NULL,
                related_name='duplicates',
                db_index=True,
                to='action_items.actionitem',
            ),
        ),
    ]
```

Note: `db_index=True` on the FK column creates the index automatically; no separate `AddIndex` operation is needed. [ASSUMED: standard Django migration behavior — db_index=True on ForeignKey adds an index]

### List Serializer with `duplicate_count`

```python
# Source: [VERIFIED: codebase — existing serializer pattern]
class ActionItemListSerializer(_ActionItemBaseRead):
    duplicate_count = serializers.IntegerField(read_only=True)

    class Meta(_ActionItemBaseRead.Meta):
        fields: ClassVar[list[str]] = [
            *_ActionItemBaseRead.Meta.fields,
            "duplicate_count",
        ]
        read_only_fields: ClassVar[list[str]] = fields
```

### Nested Duplicates Serializer

```python
# Source: [VERIFIED: codebase — ActionItemNoteSerializer as pattern]
class ActionItemDuplicateSerializer(serializers.ModelSerializer):
    shop_name = serializers.SerializerMethodField()
    source_review_date = serializers.SerializerMethodField()
    source_review_rating = serializers.SerializerMethodField()

    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = [
            "id", "title", "shop_name", "source_review_date", "source_review_rating",
        ]
        read_only_fields: ClassVar[list[str]] = fields

    def get_shop_name(self, obj: ActionItem) -> str:
        return str(obj.shop.name) if obj.shop else ""

    def get_source_review_date(self, obj: ActionItem) -> str | None:
        if obj.source_review is None:
            return None
        return obj.source_review.review_create_time.isoformat()

    def get_source_review_rating(self, obj: ActionItem) -> int | None:
        if obj.source_review is None:
            return None
        return obj.source_review.star_rating
```

### Merge Serializer

```python
# Source: [VERIFIED: codebase — StatusTransitionSerializer as pattern]
class MergeSerializer(serializers.Serializer):
    primary_id = serializers.IntegerField()
    duplicate_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )

    def validate(self, attrs: dict) -> dict:
        primary_id = attrs["primary_id"]
        duplicate_ids = attrs["duplicate_ids"]
        if primary_id in duplicate_ids:
            raise serializers.ValidationError(
                {"duplicate_ids": "Primary ID cannot appear in duplicate_ids."}
            )
        if len(set(duplicate_ids)) != len(duplicate_ids):
            raise serializers.ValidationError(
                {"duplicate_ids": "Duplicate IDs must be unique."}
            )
        return attrs
```

### `get_permissions()` Override Pattern

```python
# Source: [VERIFIED: codebase — apps/shops/views.py line 158]
def get_permissions(self):  # type: ignore[no-untyped-def]
    if self.action == "merge_action":
        return [IsOrgAdmin(), IsOrgScoped()]
    return [IsOrgScoped(), BrandScopeGuard()]
```

### Frontend `+N` Badge Pattern

```typescript
// Source: [ASSUMED — consistent with existing badge components]
// In ActionItemTable.tsx — title column accessor:
accessor: (r) => (
  <div className="flex items-center gap-1.5">
    <button
      type="button"
      onClick={() => onOpenModal(r.id)}
      className="text-[14px] text-ink font-semibold cursor-pointer hover:underline text-left"
    >
      {r.title}
    </button>
    {r.duplicate_count > 0 && (
      <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full bg-amber-tint text-amber text-[11px] font-semibold">
        +{r.duplicate_count}
      </span>
    )}
  </div>
),
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSONField `tags` for AI output | Relational `ReviewTag` model | Phase 17 | Pattern: AI pipeline writes relational rows, not JSON blobs |
| Global `permission_classes` on ViewSet | `get_permissions()` override per action | Phase 8+ | Pattern for mixed-permission endpoints |

**Not applicable / nothing deprecated in this domain.**

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `db_index=True` on ForeignKey automatically creates a DB index in the migration without a separate `AddIndex` operation | Code Examples | Migration missing index → slower `canonical__isnull=True` filter; easily fixed by adding explicit `AddIndex` |
| A2 | Django's `Count('duplicates')` with `filter(canonical__isnull=True)` applied first produces the correct per-canonical duplicate count without a double-counting issue | Architecture Patterns | Wrong badge counts; would require adding `filter=Q(...)` to the `Count()` call or moving to a subquery annotation |
| A3 | Sorted-PK locking order in `select_for_update` is sufficient deadlock prevention for the merge operation | Common Pitfalls — Pitfall 6 | Deadlocks under concurrent merge of overlapping sets; mitigated by the fact that the `canonical__isnull=True` filter on the list prevents already-merged items from appearing |
| A4 | Adding optional `selectedIds`/`onToggleRow`/`onToggleAll` props to `DataTable` will not break any existing consumer since they are optional | Key Files | TypeScript type errors if DataTable.tsx has strict required-props enforcement; low risk given existing `renderExpanded?` optional prop pattern |
| A5 | The "Mark as duplicate of…" picker can use client-side filtering of items already loaded in the list (no new endpoint needed) | Don't Hand-Roll | If the org has thousands of action items, the picker would need a debounced search API; current data volume doesn't warrant it |

---

## Open Questions (RESOLVED)

1. **Should `duplicate_count` exclude items where the duplicate itself has a non-null `canonical`?**
   - What we know: D-09 re-parents orphans. After a merge, all items in the duplicate chain point directly to the primary (no second-level canonicals).
   - What's unclear: If re-parenting works correctly, `Count('duplicates')` will always count direct children only. This is correct.
   - Recommendation: No extra filter needed on the annotation. Confirm this in the service test.

2. **Should the `+N` badge appear for BRAND-scope items visible to Org Admin?**
   - What we know: Org Admin sees BRAND items; duplicates can be BRAND-scoped (D-05).
   - What's unclear: Badge is always shown when `duplicate_count > 0` — no scope restriction. This seems correct.
   - Recommendation: Show badge for both scopes.

3. **What does the detail modal show when the item itself is a duplicate (has `canonical_id` set)?**
   - What we know: Merged duplicates are hidden from the list (D-10). The detail endpoint can still be called directly.
   - What's unclear: Should the detail show a "This item has been merged into [primary title]" banner?
   - Recommendation: Add a `canonical_id` and `canonical_title` field to `ActionItemReadSerializer`. The modal can show a read-only banner. This is a planner-level decision — flag as open.

4. **DuplicatePickerModal: should it call a new search endpoint or filter client-side?**
   - What we know: The "Mark as duplicate of…" flow (D-19) opens a search-as-you-type picker. All action items for the org are NOT pre-loaded — only the current page is.
   - What's unclear: Do we need a `/api/v1/action-items/?scope=SHOP&source=AI&canonical__isnull=1&search=...` call, or do we load all items?
   - Recommendation: Make a focused fetch with a debounced search query to the existing list endpoint (it already supports `search` and `source` isn't a filter yet — add `source` to `ActionItemFilterSet`, or fetch without source filter and filter client-side after response). Planner should decide.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — this phase introduces no new CLI tools, services, or runtimes).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest apps/action_items/ -x -q` |
| Full suite command | `uv run pytest apps/action_items/ --cov=apps/action_items --cov-report=term-missing` |

[VERIFIED: codebase — pyproject.toml `[tool.pytest.ini_options]`]

### Phase Requirements → Test Map

No formal requirement IDs are mapped to Phase 18 in ROADMAP.md (it is described as a success-criteria phase). Mapping from CONTEXT.md decisions:

| Behavior | Test Type | Automated Command | File |
|----------|-----------|-------------------|------|
| D-01: `canonical` FK field on ActionItem model | unit | `pytest apps/action_items/tests/test_models.py -x -q` | ❌ Wave 0 |
| D-02: Deleting canonical sets duplicates' canonical to None | unit | `pytest apps/action_items/tests/test_models.py::test_canonical_set_null_on_delete` | ❌ Wave 0 |
| D-03: `transition_status` raises on duplicate | unit | `pytest apps/action_items/tests/test_services.py::test_transition_status_raises_on_duplicate` | ❌ Wave 0 |
| D-03: `assign_action_item` raises on duplicate | unit | `pytest apps/action_items/tests/test_services.py::test_assign_raises_on_duplicate` | ❌ Wave 0 |
| D-03: `add_note` raises on duplicate | unit | `pytest apps/action_items/tests/test_services.py::test_add_note_raises_on_duplicate` | ❌ Wave 0 |
| D-05: Merge rejects cross-scope | unit | `pytest apps/action_items/tests/test_services.py::test_merge_rejects_cross_scope` | ❌ Wave 0 |
| D-06: Merge rejects MANUAL source | unit | `pytest apps/action_items/tests/test_services.py::test_merge_rejects_manual_source` | ❌ Wave 0 |
| D-08: Merge rejects already-merged primary | unit | `pytest apps/action_items/tests/test_services.py::test_merge_rejects_already_merged_primary` | ❌ Wave 0 |
| D-09: Sub-duplicates re-parented | unit | `pytest apps/action_items/tests/test_services.py::test_merge_reparents_sub_duplicates` | ❌ Wave 0 |
| D-10: List hides merged duplicates | unit | `pytest apps/action_items/tests/test_selectors.py::test_list_hides_merged_duplicates` | ❌ Wave 0 |
| D-11: List annotates duplicate_count | unit | `pytest apps/action_items/tests/test_selectors.py::test_list_annotates_duplicate_count` | ❌ Wave 0 |
| D-12: Detail prefetches duplicates | unit | `pytest apps/action_items/tests/test_selectors.py::test_detail_prefetches_duplicates` | ❌ Wave 0 |
| D-16: POST /merge/ succeeds for Org Admin | integration | `pytest apps/action_items/tests/test_views.py::test_merge_endpoint_org_admin` | ❌ Wave 0 |
| D-16: POST /merge/ returns 403 for Staff | integration | `pytest apps/action_items/tests/test_views.py::test_merge_endpoint_staff_forbidden` | ❌ Wave 0 |
| D-17: PATCH on merged duplicate returns 400 | integration | `pytest apps/action_items/tests/test_views.py::test_patch_merged_duplicate_returns_400` | ❌ Wave 0 |
| D-17: Status transition on merged duplicate returns 400 | integration | `pytest apps/action_items/tests/test_views.py::test_status_transition_merged_duplicate_returns_400` | ❌ Wave 0 |
| List query-count gate (no N+1 with duplicates annotated) | performance | `pytest apps/action_items/tests/test_selectors.py::test_list_query_count_with_duplicates` | ❌ Wave 0 |
| D-18/19 UI flows | manual | — | manual-only |
| D-20 Confirmation dialog | manual | — | manual-only |

### Sampling Rate

- **Per task commit:** `uv run pytest apps/action_items/ -x -q`
- **Per wave merge:** `uv run pytest apps/action_items/ --cov=apps/action_items --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

All test cases above are new (❌). The test files exist but need new test functions. No new test files need to be created — extend existing ones:

- `apps/action_items/tests/test_models.py` — add D-01 and D-02 tests
- `apps/action_items/tests/test_services.py` — add D-03, D-05, D-06, D-07, D-08, D-09 tests + `merge_action_items` happy path + audit log test
- `apps/action_items/tests/test_selectors.py` — add D-10, D-11, D-12 tests + query-count gate
- `apps/action_items/tests/test_views.py` — add D-16, D-17 endpoint tests

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | `IsOrgAdmin` on merge endpoint; `organisation_id` validation in service; `IsOrgScoped.has_object_permission` prevents IDOR |
| V5 Input Validation | yes | `MergeSerializer` validates `primary_id`, `duplicate_ids` list; service validates org membership |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Staff merging items they shouldn't access | Elevation of Privilege | `IsOrgAdmin` on merge endpoint — Staff cannot reach it |
| Org Admin merging items from other orgs (IDOR) | Tampering | `service validates organisation_id` for all fetched items; `select_for_update().filter(organisation_id=...)` |
| Merging across scopes to expose BRAND items to Staff indirectly | Information Disclosure | D-05 scope validation in service; `canonical__isnull=True` filter still applies Staff scope |
| Chained canonical chains causing circular reference | Tampering | D-08 check: primary must have `canonical_id=None`; enforced before any updates |

---

## Sources

### Primary (HIGH confidence)

- [VERIFIED: codebase] `apps/action_items/models.py` — ActionItem model, existing FK patterns, Meta, constraints
- [VERIFIED: codebase] `apps/action_items/selectors/items.py` — `list_action_items`, `get_action_item` implementation
- [VERIFIED: codebase] `apps/action_items/services/lifecycle.py` — service pattern, `@transaction.atomic`, `AuditLog.objects.create`
- [VERIFIED: codebase] `apps/action_items/serializers.py` — serializer hierarchy, `_ActionItemBaseRead`, field lists
- [VERIFIED: codebase] `apps/action_items/views.py` — `ActionItemViewSet`, `get_queryset`, existing `@action` handlers
- [VERIFIED: codebase] `apps/accounts/permissions.py` — `IsOrgAdmin`, `IsOrgScoped` implementations
- [VERIFIED: codebase] `apps/common/models.py` — `AuditLog` model and fields
- [VERIFIED: codebase] `apps/reviews/models.py` — `Review.star_rating` (SmallIntegerField), `Review.review_create_time`
- [VERIFIED: codebase] `frontend/src/widgets/data-table/DataTable.tsx` — no checkbox support today
- [VERIFIED: codebase] `frontend/src/widgets/modal/ConfirmModal.tsx` — reusable confirm modal
- [VERIFIED: codebase] `frontend/src/widgets/action-items/types.ts` — existing type shapes
- [VERIFIED: codebase] `pyproject.toml` — pytest 8.3.3 + pytest-django 4.9.0

### Secondary (MEDIUM confidence)

- CLAUDE.md §5 (services/selectors pattern), §6 (N+1 prevention), §9 (Staff scope enforcement), §24 (implementation order)
- 18-CONTEXT.md — all decisions D-01 through D-20

### Tertiary (LOW confidence)

- None — all claims are codebase-verified or from authoritative project docs.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing
- Architecture: HIGH — all patterns verified in codebase
- Pitfalls: HIGH — derived from actual code paths read
- Frontend patterns: MEDIUM — DataTable extension is additive; ConfirmModal verified; new components (MergeModal, DuplicatePickerModal) follow existing modal patterns

**Research date:** 2026-05-22
**Valid until:** 2026-06-22 (stable domain — Django ORM self-refs have not changed in years)
