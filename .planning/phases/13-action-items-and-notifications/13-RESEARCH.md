# Phase 13: Action Items and Notifications — Research

**Researched:** 2026-05-03
**Domain:** Django services/selectors + DRF viewsets + React widget (DataTable, Modal) + HTTP-polling notification bell
**Confidence:** HIGH — based entirely on existing codebase inspection; no stale training-data guesses

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Status change UX**
- Three-dot row menu includes a full status submenu listing all 4 states (To Do, In Progress, Complete, Won't Do). Direct table-row transition without opening a modal.
- Modal status control is a `<select>` dropdown at the top of the Details tab — inline, single click, immediate transition.
- Status badge in the table row is decorative only (not a click target).

**Modal — Details tab and edit mode**
- Edit transforms in-place (same tab, no new modal). Save and Cancel appear at the bottom.
- Scope and Shop are NOT editable for AI-extracted items even in edit mode.
- For manually-created items, Scope and Shop are also NOT editable after creation.
- Modal always opens on the Details tab.

**Modal — Notes tab**
- Always-visible textarea at the bottom (no toggle).
- Notes are append-only.
- Oldest-first timeline sort (CONTEXT.md decision).

**Notification bell**
- Numeric badge on bell icon.
- Each notification row shows: title + shop name + relative time.
- Two separate icons — existing TopbarBell (sync) unchanged; new bell added to its right.
- 60-second HTTP poll (NOTF-04); counter refreshes immediately after any interaction.

**AI chip click on review card**
- Clicking navigates to `/admin/org/action-items/?review={review_id}`.
- Chips with no ActionItem rows are non-interactive.

### Claude's Discretion
- Notes timeline sort order: oldest-first (per CONTEXT.md)
- Exact chip disabled state when ActionItem rows don't exist yet
- Empty state illustrations and copy for the action items list
- Loading skeleton design for the action items table
- Popover positioning and animation for the notification bell
- How the action items page handles the `?review=` query parameter when no items exist for that review

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACTN-01 | ActionItem rows created from GPT's `action_items` JSON; SHOP scope has `shop_id` from source review; BRAND scope has `shop_id = NULL` | Promotion service reads `Review.extracted_action_items` JSONField; bulk_create with `update_conflicts=False` (first-write-wins); runs inside `enrich_review` post-success or as dedicated `promote_action_items_task` |
| ACTN-02 | Action Items list at `/admin/org/action-items/`; Staff see only SHOP-scoped items for their shops; brand-scoped blocked at API (403) | `list_action_items` selector applies SHOP-scope filter when `user.role == STAFF_ADMIN`; `IsOrgScoped` permission + `BrandScopeGuard` permission on detail/mutation endpoints; UI hides Scope filter from Staff |
| ACTN-03 | Filter bar: Store, Status, Scope toggle (Org Admin only), Assignee, From Date, To Date, Search | `ActionItemFilterSet` using `django-filter`; Scope filter excluded at view layer for Staff (not at filterset level — keeping filterset clean) |
| ACTN-04 | Table columns: Title, Status badge, Scope pill, Shop, Assignee, Due Date (red if overdue), Created, Source, three-dot menu | DataTable column accessors; overdue = `due_date < today` CSS red; source = AI (Sparkles) or Manual (User) icon |
| ACTN-05 | Pagination 10/25/50/100, default 25; sort: Newest, Oldest, Due Date asc, Status (To Do first), Priority (high first) | `DefaultPageNumberPagination` (already in `apps/common/pagination.py`); `OrderingFilter` with explicit `ordering_fields` |
| ACTN-06 | Action Item modal with three tabs: Details, Notes, Source Review (AI items only) | Reuse `Modal` at `size="lg"`; tab state is local React state; Source Review tab hidden when `source == "manual"` |
| ACTN-07 | Edit mode: Title, Priority, Due Date, Assignee editable; Scope and Shop NOT editable for AI-extracted or manual items after creation | PATCH serializer excludes `scope` and `shop` from writable fields; UI renders them as read-only text in edit mode |
| ACTN-08 | Status workflow: any-to-any; every transition writes to AuditLog | `transition_status` service function with `transaction.atomic()`; AuditLog writes `action_item.status_changed` with `before_data` and `after_data` |
| ACTN-09 | Manual creation: Title, Scope, Shop, Priority, Assignee, Due Date, Initial note | `create_action_item` service; Brand scope hidden from Staff at view layer (not serializer — keeps serializer reusable) |
| ACTN-10 | Notes append-only; 1–2000 chars; no edit/delete | `add_note` service; `ActionItemNote` model with `is_edited = False` enforced; no PATCH/DELETE endpoint for notes |
| ACTN-11 | Source Review tab renders read-only review card; "Open in Reviews" link | Review FK on ActionItem; serializer includes review fields when `source == "ai"`; link navigates to `/admin/org/reviews/?id={review_id}` |
| ACTN-12 | `GET /api/v1/action-items/` resolves in ≤5 SQL queries; verified by `CaptureQueriesContext` test | `select_related("shop", "assignee", "review")` on base queryset; `get_accessible_shop_ids` reused from reviews (1 query for Staff); total: 1 session auth + 1 scope lookup + 1 main query + prefetch |
| ACTN-13 | AuditLog entries for `action_item.created`, `action_item.status_changed`, `action_item.assigned`, `action_item.note_added` | Reuse `AuditLog` model from `apps/common/models.py`; `entity_type = "action_item"`, `entity_id = str(action_item.pk)` |
| NOTF-01 | Notification bell: unread count badge; popover with last 10 unread newest-first | `NotifBell` React component at `<div id="notif-bell-root">`; polls `/api/v1/notifications/unread-count/` every 60s |
| NOTF-02 | Three notification types: `new_review`, `new_action_item`, `action_item_assigned` | `Notification` model with `notification_type` choices; dispatch service called from enrichment success + action_item lifecycle |
| NOTF-03 | Clicking notification navigates to relevant page + marks it read | PATCH `/api/v1/notifications/{id}/read/`; navigation via `window.location.href` (same pattern as Phase 11) |
| NOTF-04 | Unread counter polled every 60s via HTTP; refreshes immediately after interaction | `setInterval(60000)` in `useNotifications` hook; also called in `markRead` / `markAllRead` success handler |
| NOTF-05 | Brand-scoped action item notifications NOT delivered to Staff | `dispatch_notification` service filters recipients by `user.role != STAFF_ADMIN` when `notification_type == "new_action_item"` and `scope == BRAND` |

</phase_requirements>

---

## Summary

Phase 13 builds two fully independent features on top of the existing Phase 11/12 stack: (1) the **ActionItem module** — a full CRUD entity with status workflow, notes, and a three-tab modal — and (2) the **notification bell** — an HTTP-polled popover for surfacing new reviews and action item assignments.

The architectural patterns are already established in this codebase. The ActionItem module follows the exact same services/selectors/views/tasks layering as the Reviews module. The notification bell follows the exact same React entrypoint-mount pattern as `TopbarBell` (sync indicator). No new libraries are needed; all required building blocks already exist.

The most complex parts are: (a) the three-layer Staff scoping for ActionItem (selector + permission + UI), which mirrors the existing Review scoping pattern exactly; (b) the `promote_action_items_task` that converts `Review.extracted_action_items` JSON to `ActionItem` rows idempotently; and (c) the `ACTN-12` query-count gate, which requires careful `select_related` design on the ActionItem queryset.

**Primary recommendation:** Build the ActionItem data layer (model, migration, services, selectors) first, then the API (serializers, viewset, URLs), then the React widget, and the notification bell last. This ordering maximizes parallelism between backend and frontend work.

---

## Standard Stack

### Core (all already in pyproject.toml — no new dependencies needed)

| Library | Version (pinned) | Purpose | Why Standard |
|---------|-----------------|---------|--------------|
| Django | 6.0.2 | ORM, models, migrations, template views | Project base |
| djangorestframework | 3.17.1 | ViewSets, serializers, permissions, pagination | Project API framework |
| django-filter | 24.3 | `FilterSet` for ActionItem list endpoint | Already used by ReviewFilterSet |
| celery | 5.6.3 | `promote_action_items_task` thin wrapper | Already used for enrich tasks |
| React 18 (via django-vite) | current via vite | ActionItemManagementWidget, NotifBell entrypoints | Project frontend standard |
| lucide-react | current project dep | Icons: Sparkles, Star, UserCheck, Check, User, Bell | Already project dep |

### Supporting (already in codebase)

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `apps/common/models.py` → `TimeStampedModel` | Base model with `created_at`/`updated_at` | ActionItem, ActionItemNote, Notification inherit from this |
| `apps/common/models.py` → `AuditLog` | Audit trail | Write `action_item.*` events — no new model needed |
| `apps/common/pagination.py` → `DefaultPageNumberPagination` | Page 25 default, 10/25/50/100 selector | ActionItem list uses this (unlike Reviews which uses CursorPagination) |
| `apps/common/viewsets.py` → `TenantScopedViewSet` | Auto-filters by `organisation_id` | All ActionItem and Notification viewsets inherit this |
| `apps/common/permissions.py` → `IsOrgScoped` | Base Org/Staff permission | Compose with scope guard for brand-item protection |
| `apps/reviews/selectors/reviews.py` → `get_accessible_shop_ids` | Staff shop list (1 query) | Reuse directly in `list_action_items` selector |
| `frontend/src/widgets/data-table/DataTable.tsx` | Table with renderRowActions, skeleton | ActionItemTable wraps this without modification |
| `frontend/src/widgets/modal/Modal.tsx` | Modal with `size="lg"` | ActionItemModal and ActionItemCreateModal |
| `frontend/src/lib/toast.ts` → `emitToast` | `{kind, title}` API | Status transition, note added, create success toasts |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `DefaultPageNumberPagination` for action items | `CursorPagination` (used for reviews) | ActionItem volumes are orders of magnitude smaller than reviews; PageNumber gives the 10/25/50/100 selector required by ACTN-05; cursor cannot do total-count cheaply |
| HTTP polling for unread count | WebSocket push | CLAUDE.md §13.2 explicitly prohibits new Channels consumers; polling is the mandated approach per NOTF-04 |
| GenericForeignKey for AuditLog entity | String FK (`entity_type` + `entity_id`) | Already decided in Phase 11 (STATE.md); AuditLog uses string entity_type/entity_id pattern |

**Installation:** No new packages required. All dependencies are already pinned in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

New files to create (skeleton files already exist for models):

```
apps/action_items/
├── models.py           # ActionItem + ActionItemNote (replace skeleton)
├── serializers.py      # ActionItemReadSerializer, ActionItemCreateSerializer, ActionItemUpdateSerializer, ActionItemNoteSerializer
├── views.py            # ActionItemViewSet + action_item_list template view
├── urls.py             # /admin/org/action-items/ + /api/v1/action-items/ router registration
├── filters.py          # ActionItemFilterSet (django-filter)
├── services/
│   ├── __init__.py
│   └── lifecycle.py    # create_action_item, transition_status, assign_action_item, add_note, promote_from_review
├── selectors/
│   ├── __init__.py
│   └── items.py        # list_action_items (with Staff scope), get_action_item
└── tests/
    ├── __init__.py
    ├── factories.py    # ActionItemFactory, ActionItemNoteFactory
    ├── test_models.py
    ├── test_services.py
    ├── test_selectors.py
    └── test_views.py   # includes ACTN-12 query count gate

apps/notifications/
├── models.py           # Notification (replace skeleton)
├── serializers.py      # NotificationReadSerializer
├── views.py            # NotificationViewSet (list, mark-read, mark-all-read, unread-count)
├── urls.py
├── services/
│   ├── __init__.py
│   └── dispatch.py     # dispatch_notification (creates Notification rows, filters by role)
└── tests/
    ├── __init__.py
    ├── factories.py
    └── test_dispatch.py

frontend/src/widgets/action-items/
├── ActionItemTable.tsx
├── ActionItemModal.tsx
├── ActionItemCreateModal.tsx
├── ActionItemFilters.tsx
├── ActionItemManagementWidget.tsx   # top-level composition
├── api.ts
├── types.ts
└── useActionItems.ts

frontend/src/widgets/notif-bell/
├── NotifBell.tsx
├── api.ts
└── useNotifications.ts

frontend/src/entrypoints/
├── action-items-management.tsx      # mounts ActionItemManagementWidget
└── notif-bell.tsx                   # mounts NotifBell
```

### Pattern 1: ActionItem Model Design

**What:** ActionItem is a full model (not JSON) with org-scoping, staff-scope field (`scope`), and optional FK to source review.

**When to use:** For any entity with status workflow, audit log, and multi-user visibility.

```python
# apps/action_items/models.py
from apps.common.models import TimeStampedModel

class ActionItem(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETE = "COMPLETE", "Complete"
        WONT_DO = "WONT_DO", "Won't Do"

    class Scope(models.TextChoices):
        SHOP = "SHOP", "Shop"
        BRAND = "BRAND", "Brand"

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Source(models.TextChoices):
        AI = "AI", "AI Extracted"
        MANUAL = "MANUAL", "Manual"

    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, db_index=True, related_name="action_items")
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.TODO, db_index=True)
    scope = models.CharField(max_length=10, choices=Scope.choices, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL, db_index=True)
    shop = models.ForeignKey("shops.Shop", null=True, blank=True, on_delete=models.SET_NULL, related_name="action_items")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_action_items")
    due_date = models.DateField(null=True, blank=True, db_index=True)
    source_review = models.ForeignKey("reviews.Review", null=True, blank=True, on_delete=models.SET_NULL, related_name="action_items")

    class Meta:
        db_table = "action_items_actionitem"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organisation", "status", "scope"], name="ai_org_status_scope_idx"),
            models.Index(fields=["organisation", "due_date"], name="ai_org_due_idx"),
            models.Index(fields=["organisation", "assignee"], name="ai_org_assignee_idx"),
        ]
```

**Key decisions:**
- `scope` is indexed because it's always in the Staff filter.
- `shop` is nullable (NULL for BRAND-scoped items, per ACTN-01).
- `source_review` uses `SET_NULL` so action items persist if the source review is soft-deleted.
- Integer PK — consistent with all other models in this project (STATE.md: "Integer PK kept on Review").

### Pattern 2: ActionItemNote Model (Append-Only)

```python
class ActionItemNote(TimeStampedModel):
    action_item = models.ForeignKey(ActionItem, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    body = models.TextField(max_length=2000)

    class Meta:
        db_table = "action_items_actionitemnote"
        ordering = ["created_at"]  # oldest-first per CONTEXT.md decision
```

No `updated_at` sentinel needed — notes are never edited. `ordering = ["created_at"]` enforces oldest-first at the ORM level.

### Pattern 3: Notification Model

```python
class Notification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        NEW_REVIEW = "new_review", "New Review"
        NEW_ACTION_ITEM = "new_action_item", "New Action Item"
        ACTION_ITEM_ASSIGNED = "action_item_assigned", "Action Item Assigned"

    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.CASCADE, db_index=True, related_name="notifications")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=True, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, db_index=True)
    title = models.CharField(max_length=200)
    shop = models.ForeignKey("shops.Shop", null=True, blank=True, on_delete=models.SET_NULL)
    action_item = models.ForeignKey("action_items.ActionItem", null=True, blank=True, on_delete=models.SET_NULL)
    review = models.ForeignKey("reviews.Review", null=True, blank=True, on_delete=models.SET_NULL)
    is_read = models.BooleanField(default=False, db_index=True)
    target_url = models.CharField(max_length=500)  # pre-computed navigation target

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"], name="notif_recipient_unread_idx"),
        ]
```

**Key decisions:**
- `target_url` is pre-computed at dispatch time so the frontend can navigate without resolving the FK inline.
- FKs to shop, action_item, review are all nullable (not all notifications are for all types).
- Composite index on `(recipient, is_read, created_at)` — covers the unread-count query and the popover list query with one index scan.

### Pattern 4: Staff Scoping (Three-Layer, CLAUDE.md §9)

This is the critical security pattern for this phase. Must be enforced at ALL three layers.

**Layer 1 — Selector:**
```python
# apps/action_items/selectors/items.py
from apps.reviews.selectors.reviews import get_accessible_shop_ids

def list_action_items(*, organisation_id: int, user: User) -> QuerySet[ActionItem]:
    qs = (
        ActionItem.objects
        .filter(organisation_id=organisation_id)
        .select_related("shop", "assignee", "source_review", "source_review__shop")
    )
    if user.role == User.Role.STAFF_ADMIN:
        accessible = get_accessible_shop_ids(user_id=user.pk)
        # CRITICAL: only SHOP-scoped items; brand items are NEVER visible to Staff
        qs = qs.filter(scope=ActionItem.Scope.SHOP, shop_id__in=accessible)
    return qs.order_by("-created_at")
```

**Layer 2 — Permission (object-level):**
```python
# apps/action_items/permissions.py  (new file)
class BrandScopeGuard(BasePermission):
    """Block Staff users from brand-scoped action items on detail/mutation endpoints."""
    message = "Brand-scoped action items are not accessible to Staff."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            if getattr(obj, "scope", None) == ActionItem.Scope.BRAND:
                return False
        return True
```

**Layer 3 — UI:**
- Scope filter `<select>` hidden from Staff via `userRole` prop.
- Brand scope option hidden in ActionItemCreateModal.
- These are rendering-only concerns; the API layers above are the authoritative defence.

### Pattern 5: ActionItem Promotion from JSON (ACTN-01)

The `enrich_review` service already writes `extracted_action_items` to `Review.extracted_action_items` (JSONField). Phase 13 must promote these to `ActionItem` rows. The cleanest approach is a **separate service function** called from within `enrich_review` post-success, NOT a separate Celery task, to avoid an extra queue hop.

```python
# apps/action_items/services/lifecycle.py

def promote_action_items_from_review(*, review: Review) -> int:
    """Convert extracted_action_items JSON to ActionItem rows.

    Idempotent: only creates rows where (organisation, source_review, title, scope)
    does not already exist. Returns count of rows created.

    Called from apps.reviews.services.enrichment._persist_success AFTER the
    transaction commits (same pattern as _emit_enrichment_progress).
    """
    if not review.extracted_action_items:
        return 0
    to_create = []
    for item in review.extracted_action_items:
        scope = ActionItem.Scope.BRAND if item["scope"] == "brand" else ActionItem.Scope.SHOP
        to_create.append(ActionItem(
            organisation_id=review.organisation_id,
            title=item["title"],
            scope=scope,
            priority=_map_priority(item["priority"]),
            source=ActionItem.Source.AI,
            shop_id=review.shop_id if scope == ActionItem.Scope.SHOP else None,
            source_review=review,
        ))
    # Use ignore_conflicts=True — safe because a second enrichment on the same review
    # would produce identical rows. Duplicate-safe without unique constraint complexity.
    created = ActionItem.objects.bulk_create(to_create, ignore_conflicts=True)
    return len([c for c in created if c.pk])
```

**Why `ignore_conflicts=True`:** Reviews can be re-enriched (text/rating change resets status to PENDING per SYNC-05). On re-enrichment, `extracted_action_items` is rewritten. Calling `promote_action_items_from_review` again must not duplicate rows. Using `ignore_conflicts=True` with a unique constraint on `(source_review, title, scope)` is the correct idempotency strategy — clean, no try/except, no pre-query.

Add to `ActionItem.Meta.constraints`:
```python
models.UniqueConstraint(
    fields=["source_review", "title", "scope"],
    name="ai_unique_per_review_title_scope",
    condition=models.Q(source=ActionItem.Source.AI),  # partial constraint
)
```

Note: Partial unique constraints require PostgreSQL. The project already uses PostgreSQL exclusively.

### Pattern 6: Status Transition Service

```python
# apps/action_items/services/lifecycle.py

@transaction.atomic
def transition_status(
    *, action_item: ActionItem, new_status: str, actor: User
) -> ActionItem:
    old_status = action_item.status
    action_item = (
        ActionItem.objects.select_for_update().get(pk=action_item.pk)
    )
    action_item.status = new_status
    action_item.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        organisation_id=action_item.organisation_id,
        actor=actor,
        entity_type="action_item",
        entity_id=str(action_item.pk),
        action="action_item.status_changed",
        before_data={"status": old_status},
        after_data={"status": new_status},
    )
    return action_item
```

Use `select_for_update()` inside `transaction.atomic()` — same pattern as `enrich_review` in Phase 12 (STATE.md pattern; prevents concurrent status race).

### Pattern 7: Notification Dispatch Service

```python
# apps/notifications/services/dispatch.py

def dispatch_notification(
    *,
    organisation_id: int,
    notification_type: str,
    title: str,
    shop: "Shop | None" = None,
    action_item: "ActionItem | None" = None,
    review: "Review | None" = None,
    target_url: str,
    recipient_ids: list[int] | None = None,
) -> None:
    """Create Notification rows for all eligible recipients.

    If recipient_ids is None, creates for all Org members (except Superadmin).
    Applies Staff brand-scope filtering (NOTF-05) when notification involves
    a brand-scoped action item.
    """
    from apps.accounts.models import User
    recipients = User.objects.filter(
        organisation_id=organisation_id,
        role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
        is_active=True,
    )
    if recipient_ids is not None:
        recipients = recipients.filter(pk__in=recipient_ids)
    # NOTF-05: Brand-scoped action item notifications not delivered to Staff
    if action_item and getattr(action_item, "scope", None) == "BRAND":
        recipients = recipients.exclude(role=User.Role.STAFF_ADMIN)
    Notification.objects.bulk_create([
        Notification(
            organisation_id=organisation_id,
            recipient=r,
            notification_type=notification_type,
            title=title,
            shop=shop,
            action_item=action_item,
            review=review,
            target_url=target_url,
        )
        for r in recipients
    ])
```

### Pattern 8: Notification API — Unread Count Endpoint

The unread count endpoint is the hot path (polled every 60s per user). Keep it to 1 query:

```python
# apps/notifications/views.py
@action(detail=False, methods=["get"], url_path="unread-count")
def unread_count(self, request):
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return Response({"count": count})
```

### Pattern 9: React Entrypoint Mount Pattern

Follow the established `topbar-sync-indicator.tsx` pattern exactly:

```tsx
// frontend/src/entrypoints/notif-bell.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { NotifBell } from "../widgets/notif-bell/NotifBell";

const root = document.getElementById("notif-bell-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <NotifBell />
    </StrictMode>,
  );
}
```

The `NotifBell` component manages its own state internally (no props needed from Django template). The unread count comes from the polled API, not from server-side rendering.

### Pattern 10: `useNotifications` Hook — 60s Poll

```tsx
// frontend/src/widgets/notif-bell/useNotifications.ts
export function useNotifications() {
  const [count, setCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationRow[]>([]);

  const fetchCount = useCallback(async () => {
    const data = await getUnreadCount();
    setCount(data.count);
  }, []);

  // 60-second poll (NOTF-04)
  useEffect(() => {
    void fetchCount();
    const id = setInterval(() => void fetchCount(), 60_000);
    return () => clearInterval(id);
  }, [fetchCount]);

  const markRead = async (notifId: number, targetUrl: string) => {
    await patchMarkRead(notifId);
    setCount((c) => Math.max(0, c - 1));  // optimistic
    void fetchCount();  // reconfirm from server
    window.location.href = targetUrl;
  };

  const markAllRead = async () => {
    await postMarkAllRead();
    setCount(0);  // optimistic
    setNotifications((ns) => ns.map((n) => ({ ...n, is_read: true })));
    void fetchCount();
  };

  return { count, notifications, setNotifications, markRead, markAllRead, fetchCount };
}
```

### Pattern 11: ActionItemManagementWidget — `?review=` Filter Pre-population

The ActionItem list page must handle `?review={review_id}` from chip clicks (CONTEXT.md decision). Read it on mount and pre-populate the filter:

```tsx
const reviewParam = useMemo(() => {
  const p = new URLSearchParams(window.location.search);
  return p.get("review") ?? undefined;
}, []);
```

Pass `reviewParam` as the initial `review` filter in `DEFAULT_PARAMS`. When no items match for that review, show the "No results" empty state (not the "No action items yet" state) with a "Clear filters" CTA.

### Anti-Patterns to Avoid

- **Do not put AuditLog writes inside the serializer.** Status transitions call `transition_status` service from the viewset `@action`; the serializer just validates input.
- **Do not make ActionItem Notes editable.** No PATCH or DELETE endpoint for `ActionItemNote`. Notes list is returned as nested array on the ActionItem detail endpoint — no separate notes list endpoint needed.
- **Do not call `promote_action_items_from_review` inside `transaction.atomic()`.** It must run AFTER the transaction commits, same as `_emit_enrichment_progress` in enrichment.py. Add it to `_persist_success` AFTER `_emit_enrichment_progress`.
- **Do not poll unread count inside the notification popover list.** The popover fetches the full list lazily (on open), not on the 60s cycle.
- **Do not use `count()` on a queryset after `paginate_queryset`.** Compute `total_count` via `qs.values("pk").count()` before pagination (Phase 11 pattern, STATE.md).
- **Do not filter ActionItems by scope at the serializer level.** The selector is the authoritative filter; the serializer should be role-agnostic.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination with 10/25/50/100 selector | Custom pagination | `DefaultPageNumberPagination` in `apps/common/pagination.py` | Already implemented; just override `page_size = 25` |
| Org-scoped queryset filtering | Per-viewset `filter(organisation_id=...)` | `TenantScopedViewSet` base class | Already built; every ActionItem and Notification viewset inherits it |
| Staff shop-id resolution | New shop-access query | `get_accessible_shop_ids` from `apps/reviews/selectors/reviews.py` | 1-query implementation already tested; reuse directly |
| CSRF token for fetch | Custom header logic | `getCsrfToken()` helper from existing `api.ts` pattern | Copy verbatim from `apps/reviews/widgets/review-management/api.ts` |
| Tab switching in modal | Custom tab library | Local React `useState` | DataTable and Modal don't use tabs; tabs are just conditional rendering on a `activeTab` state string |
| Relative date formatting | `date-fns` or custom | `formatRelativeDate` helper from `ReviewTable.tsx` | Already implemented; export and reuse |
| Overdue date detection | Custom date logic | `new Date(due_date) < new Date()` inline in column accessor | Trivial, no library needed |
| Focus trap in modal | Custom focus management | `FocusTrap` (already used in `Modal.tsx`) | Modal component already handles this |
| QuerySet total count before pagination | `len(paginate_queryset())` | `qs.values("pk").count()` before calling `paginate_queryset` | Phase 11 pattern; avoids double-evaluation |

---

## Common Pitfalls

### Pitfall 1: Brand-Scope Bypass via Direct URL

**What goes wrong:** Staff user manually calls `GET /api/v1/action-items/42/` where item 42 is BRAND-scoped. If only the list selector filters, the detail endpoint returns the item.

**Why it happens:** DRF's `get_queryset()` is used for list; `get_object()` also calls `get_queryset()` — but only if `get_queryset()` is correctly scoped. If the viewset's `get_queryset()` returns a differently-scoped QS for list vs. detail, or if `has_object_permission` is not implemented, the detail leaks.

**How to avoid:** Use `BrandScopeGuard.has_object_permission()` as a second permission class on the ActionItem viewset. This runs on every `get_object()` call. The selector filter is Layer 1; the permission is Layer 2. Both must be present.

**Warning signs:** Test that `GET /api/v1/action-items/{brand_item_id}/` returns 403 for Staff users even when the item belongs to their org.

### Pitfall 2: N+1 on ActionItem List (ACTN-12 gate)

**What goes wrong:** ActionItem serializer accesses `obj.shop.name`, `obj.assignee.full_name`, `obj.source_review.comment` without prefetch. 20 items = 60+ queries.

**Why it happens:** DRF serializer `SerializerMethodField` or `source="shop.name"` without `select_related` in the queryset.

**How to avoid:** `select_related("shop", "assignee", "source_review", "source_review__shop")` on the base queryset in `list_action_items`. The CaptureQueriesContext test (ACTN-12) gates this in CI. Budget allocation:
- Q1: Session/auth check
- Q2: `get_accessible_shop_ids` for Staff (skipped for Org Admin)
- Q3: Main ActionItem list query with select_related
- Q4: Pagination count (`.values("pk").count()`)
- Total: ≤4 for Org Admin, ≤5 for Staff. Well within the 5-query ceiling.

### Pitfall 3: promote_action_items_from_review Called Inside Transaction

**What goes wrong:** If `promote_action_items_from_review` is called inside `transaction.atomic()` in `_persist_success`, a DB error in `bulk_create` (e.g. duplicate key) rolls back the entire enrichment success — losing the sentiment/tags update.

**Why it happens:** Natural reflex to group related writes in one transaction.

**How to avoid:** Follow the exact pattern of `_emit_enrichment_progress`: call `promote_action_items_from_review` AFTER the `with transaction.atomic()` block in `_persist_success`. The `ignore_conflicts=True` on `bulk_create` also prevents raises from duplicates, but the transaction isolation is still important.

**Warning signs:** Test enrichment re-runs (ENRCH-02 idempotency test) to verify `ActionItem` rows are not duplicated and `Review.enrichment_status` stays SUCCESS on second run.

### Pitfall 4: Notification Dispatch Blocks Review/ActionItem Writes

**What goes wrong:** `dispatch_notification` runs inside the same `transaction.atomic()` as the main write (e.g., inside `create_action_item`). A notification dispatch failure rolls back the action item creation.

**Why it happens:** Grouping all side effects in one transaction.

**How to avoid:** Call `dispatch_notification` AFTER the transaction commits. In services that use `@transaction.atomic` decorator, use `transaction.on_commit()` or call notification dispatch after the `with transaction.atomic()` block.

**Warning signs:** Unit test for `create_action_item` should mock `dispatch_notification` and verify it is called after the action item is committed to DB.

### Pitfall 5: ActionItem Detail endpoint includes Notes inline — N+1

**What goes wrong:** `ActionItemDetailSerializer` includes `notes` as a nested serializer. Each note accesses `note.author.full_name` without prefetch.

**Why it happens:** Forgetting that the detail endpoint (for the modal) loads notes separately from the list endpoint.

**How to avoid:** The detail serializer uses `prefetch_related("notes__author")`. The detail serializer (used in `ActionItemModal`) is separate from the list serializer. List serializer: no notes. Detail serializer: `notes` nested with `prefetch_related`.

### Pitfall 6: Celery Beat `promote_action_items_task` — not actually needed

**What goes wrong:** Creating a new Celery Beat task just for promotion, when calling the service function inline from `_persist_success` is simpler and sufficient.

**Why it happens:** Over-engineering based on the Phase 11 pattern of separate tasks.

**How to avoid:** `promote_action_items_from_review` is called synchronously from `enrichment._persist_success` (after transaction commit), NOT as a separate Celery task. The function is fast (bulk_create of a small list) and idempotent. No retry logic needed because if it fails, the next re-enrichment will trigger it again.

### Pitfall 7: Notification Bell Initial Render Flash

**What goes wrong:** On page load, the bell renders with count=0 (no badge), then the first poll fires after 60 seconds (or immediately), causing a flash/pop when the badge appears.

**Why it happens:** Starting the poll interval before the initial fetch.

**How to avoid:** In `useNotifications`, call `fetchCount()` immediately on mount (before setting up the interval). The interval starts AFTER the initial fetch resolves. The component renders as loading until the first fetch, then shows the badge.

### Pitfall 8: Mypy strict mode with ActionItem nullable FK

**What goes wrong:** `action_item.shop.name` fails mypy strict because `shop` is `Shop | None`. Accessing `.name` directly triggers `Item "None" of "Shop | None" has no attribute "name"`.

**Why it happens:** Nullable FK typed as `Optional[Shop]` in django-stubs.

**How to avoid:** Use `action_item.shop.name if action_item.shop else "—"` pattern in serializers. See Phase 11 pattern for `shop.region` (STATE.md: "StaffAccessScope REGION check guards shop.region_id for None").

---

## Code Examples

### ActionItem Viewset — Status Transition Custom Action

```python
# apps/action_items/views.py
# Source: established Phase 11 review reply @action pattern
from rest_framework.decorators import action

class ActionItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgScoped, BrandScopeGuard]  # noqa: RUF012
    pagination_class = DefaultPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]  # noqa: RUF012
    filterset_class = ActionItemFilterSet
    ordering_fields = ["created_at", "due_date", "status", "priority"]  # noqa: RUF012
    queryset = ActionItem.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return ActionItemCreateSerializer
        if self.action in ("update", "partial_update"):
            return ActionItemUpdateSerializer
        return ActionItemReadSerializer

    def get_queryset(self):
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return ActionItem.objects.none()
        return list_action_items(organisation_id=org_id, user=user)

    @action(detail=True, methods=["post"], url_path="transition-status")
    def transition_status_action(self, request, pk=None):
        item = self.get_object()
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = transition_status(
            action_item=item,
            new_status=serializer.validated_data["status"],
            actor=request.user,
        )
        return Response(ActionItemReadSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="add-note")
    def add_note_action(self, request, pk=None):
        item = self.get_object()
        serializer = ActionItemNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = add_note(
            action_item=item,
            author=request.user,
            body=serializer.validated_data["body"],
        )
        return Response(ActionItemNoteSerializer(note).data, status=201)
```

### FilterSet — Scope Exclusion at View Layer, Not FilterSet Layer

```python
# apps/action_items/filters.py
class ActionItemFilterSet(django_filters.FilterSet):
    shop = django_filters.NumberFilter(field_name="shop_id")
    status = django_filters.ChoiceFilter(choices=ActionItem.Status.choices)
    scope = django_filters.ChoiceFilter(choices=ActionItem.Scope.choices)
    assignee = django_filters.CharFilter(method="filter_assignee")
    from_date = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")
    review = django_filters.NumberFilter(field_name="source_review_id")  # for chip navigation
    class Meta:
        model = ActionItem
        fields: ClassVar[list[str]] = []
```

In the viewset, Staff cannot pass `scope=BRAND` in query params because the selector already filters them to SHOP-only items. The filterset `scope` filter is still present for Org Admin use — it's not removed.

### Query Count Test Pattern (ACTN-12)

```python
# apps/action_items/tests/test_views.py — mirrors Phase 11 REVW-14 pattern
def test_list_action_items_query_count_org_admin(org_admin_client):
    client, _, org = org_admin_client
    shop = ShopFactory(organisation=org)
    ActionItemFactory.create_batch(20, organisation=org, shop=shop)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/action-items/")
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5

def test_list_action_items_query_count_staff(staff_client):
    client, _, org = staff_client
    shop = ShopFactory(organisation=org)
    ActionItemFactory.create_batch(20, organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/action-items/")
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5  # includes get_accessible_shop_ids query
```

### Template View — Action Items List Page

```python
# apps/action_items/views.py — template view follows Phase 11 review_list pattern
@login_required
def action_item_list(request: HttpRequest):
    user = request.user
    shops = list_shops(organisation_id=user.organisation_id)
    team_members = User.objects.filter(
        organisation_id=user.organisation_id,
        role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
    ).values("id", "full_name")
    context = {
        "user_role": user.role,
        "shops_json": json.dumps(list(shops.values("id", "name"))),
        "team_members_json": json.dumps(list(team_members)),
    }
    return render(request, "action_items/action_item_list.html", context)
```

### Notification Bell — Mark All Read Endpoint

```python
# apps/notifications/views.py
@action(detail=False, methods=["post"], url_path="mark-all-read")
def mark_all_read(self, request):
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True)
    return Response({"status": "ok"})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate Celery task for ActionItem promotion | Inline call from `_persist_success` after transaction commit | Phase 13 design decision | Simpler, no extra queue hop, same idempotency guarantee |
| ActionItemNote with `updated_at` | No `updated_at` (notes never edited) | Phase 13 model design | Signals append-only at schema level |
| WebSocket push for notification count | 60s HTTP poll | CLAUDE.md §13.2 mandate | Keeps Channels surface small; acceptable latency for notifications |

**No deprecated patterns introduced in this phase.**

---

## Open Questions

1. **Where does `promote_action_items_from_review` get called when existing reviews (enriched in Phase 12) need retroactive promotion?**
   - What we know: Phase 12 `ENRCH-13` ran a one-time post-deployment enrichment job for existing reviews. Those reviews now have `extracted_action_items` JSON but no `ActionItem` rows.
   - What's unclear: Does Phase 13 need a management command (similar to `enrich_existing_reviews.py`) to promote existing JSON to rows, or does the re-enrichment path handle it?
   - Recommendation: Add a one-time management command `promote_existing_action_items.py` that reads all Reviews with `enrichment_status=SUCCESS AND extracted_action_items != []` and calls `promote_action_items_from_review`. Run post-deploy. This is the same pattern as Phase 12's `enrich_existing_reviews`.

2. **ActionItem `has_action_items` boolean in ReviewReadSerializer (ActionItemChip clickability)**
   - What we know: UI-SPEC §6 says chip clickability depends on whether ActionItem rows exist. ReviewReadSerializer currently returns `extracted_action_items` (raw JSON from GPT), not a count of actual `ActionItem` rows.
   - What's unclear: Should `ReviewReadSerializer` add a `has_action_items` boolean (1 extra query per review = N+1 risk), or should the chip use `extracted_action_items.length > 0` as a proxy?
   - Recommendation: Add `has_action_items = serializers.SerializerMethodField()` to `ReviewReadSerializer` that does `bool(obj.extracted_action_items)`. This is `O(1)` (already loaded field, no extra query). The chip uses `has_action_items` for clickability. This is slightly imprecise (JSON exists but rows may not yet be promoted), but it's the safest approach that avoids N+1.

3. **REVW-08 — ActionItem chips on review cards need to navigate to the action items page**
   - What we know: Phase 13 must deliver REVW-08 (clickable chips). `ActionItemChip.tsx` is currently non-interactive.
   - What's unclear: The chip needs `review_id` to build the navigation URL. The chip currently receives `count` prop only.
   - Recommendation: Add `reviewId: number` prop to `ActionItemChip`. When `has_action_items` (from API) is true, render as a clickable anchor `<a href="/admin/org/action-items/?review={reviewId}">`. When false, render as non-interactive span. This is a breaking prop change on `ActionItemChip` but it's a new Phase 13 behaviour so no backward compat concern.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/action_items/ apps/notifications/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACTN-01 | Promotion creates correct ActionItem rows from JSON | unit | `pytest apps/action_items/tests/test_services.py::test_promote_from_review -x` | ❌ Wave 0 |
| ACTN-01 | Promotion is idempotent (second call = no duplicate rows) | unit | `pytest apps/action_items/tests/test_services.py::test_promote_idempotent -x` | ❌ Wave 0 |
| ACTN-02 | Staff sees only SHOP-scoped items for accessible shops | unit | `pytest apps/action_items/tests/test_selectors.py::test_staff_scope_filter -x` | ❌ Wave 0 |
| ACTN-02 | Direct GET /api/v1/action-items/{brand_id}/ returns 403 for Staff | integration | `pytest apps/action_items/tests/test_views.py::test_staff_cannot_access_brand_item -x` | ❌ Wave 0 |
| ACTN-08 | Status transition writes AuditLog entry | unit | `pytest apps/action_items/tests/test_services.py::test_status_transition_audit_log -x` | ❌ Wave 0 |
| ACTN-08 | Any-to-any transitions allowed | unit | `pytest apps/action_items/tests/test_services.py::test_all_status_transitions -x` | ❌ Wave 0 |
| ACTN-10 | Notes are append-only (no PATCH endpoint) | integration | `pytest apps/action_items/tests/test_views.py::test_note_no_patch_endpoint -x` | ❌ Wave 0 |
| ACTN-12 | GET /api/v1/action-items/ ≤5 SQL queries (Org Admin) | integration | `pytest apps/action_items/tests/test_views.py::test_list_query_count_org_admin -x` | ❌ Wave 0 |
| ACTN-12 | GET /api/v1/action-items/ ≤5 SQL queries (Staff) | integration | `pytest apps/action_items/tests/test_views.py::test_list_query_count_staff -x` | ❌ Wave 0 |
| ACTN-13 | AuditLog entries written for all 4 action_item.* events | unit | `pytest apps/action_items/tests/test_services.py::test_audit_log_events -x` | ❌ Wave 0 |
| NOTF-02 | dispatch_notification excludes Staff for brand-scope items | unit | `pytest apps/notifications/tests/test_dispatch.py::test_brand_scope_excludes_staff -x` | ❌ Wave 0 |
| NOTF-03 | Marking a notification read sets is_read=True | integration | `pytest apps/notifications/tests/test_views.py::test_mark_read -x` | ❌ Wave 0 |
| NOTF-05 | Brand-scoped action item notifications not delivered to Staff | unit | `pytest apps/notifications/tests/test_dispatch.py::test_notf05_brand_not_to_staff -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/action_items/ apps/notifications/ -x -q`
- **Per wave merge:** `pytest apps/action_items/ apps/notifications/ apps/reviews/ -x -q`
- **Phase gate:** `pytest --cov=apps --cov-fail-under=85` green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/action_items/tests/__init__.py` — empty init
- [ ] `apps/action_items/tests/factories.py` — ActionItemFactory, ActionItemNoteFactory
- [ ] `apps/action_items/tests/test_services.py` — covers ACTN-01, ACTN-08, ACTN-10, ACTN-13
- [ ] `apps/action_items/tests/test_selectors.py` — covers ACTN-02 selector layer
- [ ] `apps/action_items/tests/test_views.py` — covers ACTN-02 permission layer, ACTN-12
- [ ] `apps/notifications/tests/__init__.py` — empty init
- [ ] `apps/notifications/tests/factories.py` — NotificationFactory
- [ ] `apps/notifications/tests/test_dispatch.py` — covers NOTF-02, NOTF-05
- [ ] `apps/notifications/tests/test_views.py` — covers NOTF-03

---

## Sources

### Primary (HIGH confidence — codebase inspection)

- `/Users/renjith/Documents/Accounts/review-master/apps/reviews/selectors/reviews.py` — `get_accessible_shop_ids` pattern reused for ActionItem
- `/Users/renjith/Documents/Accounts/review-master/apps/reviews/services/enrichment.py` — post-transaction emit pattern; base for `promote_action_items_from_review` placement
- `/Users/renjith/Documents/Accounts/review-master/apps/common/models.py` — `AuditLog`, `TimeStampedModel` base
- `/Users/renjith/Documents/Accounts/review-master/apps/common/pagination.py` — `DefaultPageNumberPagination`
- `/Users/renjith/Documents/Accounts/review-master/apps/common/viewsets.py` — `TenantScopedViewSet`
- `/Users/renjith/Documents/Accounts/review-master/apps/common/permissions.py` — `IsOrgScoped` pattern
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/data-table/DataTable.tsx` — table component API
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/modal/Modal.tsx` — modal component API (`size`, `subtitle`, `footer`)
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/api.ts` — CSRF + fetch pattern
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/entrypoints/topbar-sync-indicator.tsx` — entrypoint mount pattern
- `/Users/renjith/Documents/Accounts/review-master/apps/reviews/tests/test_views.py` — `CaptureQueriesContext` query gate pattern
- `/Users/renjith/Documents/Accounts/review-master/apps/reviews/tasks.py` — thin Celery task pattern
- `/Users/renjith/Documents/Accounts/review-master/pyproject.toml` — exact pinned dependencies
- `.planning/phases/13-action-items-and-notifications/13-CONTEXT.md` — locked decisions
- `.planning/phases/13-action-items-and-notifications/13-UI-SPEC.md` — component contracts
- `.planning/STATE.md` — all prior project decisions
- `CLAUDE.md` — RBAC rules (§9), Celery conventions (§12), Channels scope (§13.2)

### Secondary (MEDIUM confidence)

- Django 6.0 partial unique constraints — `models.Q` conditions on `UniqueConstraint` verified as stable since Django 4.2
- `bulk_create(ignore_conflicts=True)` — standard Django ORM, PostgreSQL-specific; verified against project Postgres-only constraint

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already pinned and in use; no new dependencies
- Architecture: HIGH — patterns cloned from existing Phase 11/12 codebase with traceable precedent
- Pitfalls: HIGH — each pitfall is grounded in a specific existing code pattern or STATE.md decision
- Data model: HIGH — field choices and index strategy based on direct REQUIREMENTS.md analysis

**Research date:** 2026-05-03
**Valid until:** This is a pure codebase-derived research; no external APIs. Valid indefinitely until codebase changes.
