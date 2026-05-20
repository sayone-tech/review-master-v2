# Phase 21: Audit Log Viewer - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a read-only **Audit Log** section to the Org Admin UI showing the activity history for replies and action items in the organisation. The `AuditLog` model already exists in `apps/common/models.py` and already has data written for every reply and action item event. This phase adds the API endpoint and frontend viewer — no new model or data pipeline needed.

**In scope:** View entries where `entity_type IN ("review", "action_item")` and actions match `reply_*` or `action_item.*`. Scoped to the Org Admin's organisation. Staff Admins see a shop-restricted subset.

**Out of scope:** Sync events (`shop_sync.*`), enrichment events, raw JSON diff editor, CSV export, Superadmin global audit log (Django admin already provides this), editing or deleting audit log entries.

</domain>

<decisions>
## Implementation Decisions

### Data scope
- **D-01:** Viewer shows only two entity categories:
  - `entity_type="review"` with `action IN ("reply_posted", "reply_deleted", "reply_failed")` — reply activity
  - `entity_type="action_item"` with `action LIKE "action_item.%"` — all action item lifecycle events (created, status_changed, assigned, note_added; plus `action_item.merged` once Phase 18 is shipped)
- **D-02:** Filter applied in the selector: `AuditLog.objects.filter(organisation=org, entity_type__in=["review", "action_item"]).exclude(entity_type="review").union(...)` — simpler: use `Q(entity_type="action_item") | Q(entity_type="review", action__in=["reply_posted", "reply_deleted", "reply_failed"])`.
- **D-03:** Staff Admin scope: additionally filter to only `entity_type="review"` entries where `entity_id` maps to a review whose shop is in the Staff's accessible shops. Action item entries for Staff are limited to `scope="SHOP"` items accessible to the Staff (matches existing Staff scoping pattern — CLAUDE.md §9). Use a two-step approach: fetch accessible entity IDs in the selector, apply as `.filter(entity_id__in=entity_ids)`.

### API
- **D-04:** New viewset `AuditLogViewSet(GenericViewSet, ListModelMixin)` in a new file `apps/common/views.py`. Read-only (list only — no retrieve, no create, no update).
- **D-05:** URL: `GET /api/v1/audit-logs/`. Registered in `config/urls.py` with `v1_router`.
- **D-06:** Permission: `IsAuthenticated & (IsOrgAdmin | IsStaffAdmin)`. Superadmin is excluded — they use Django admin for their audit needs.
- **D-07:** Filter parameters (via `django-filter`):
  - `entity_type` — `"review"` or `"action_item"` (optional; returns both if omitted)
  - `actor` — user ID (optional)
  - `date_from` / `date_to` — ISO date strings (optional)
  - `shop` — shop ID (optional; applies to review reply entries only — used by Staff to narrow their scope)
- **D-08:** Pagination: `CursorPagination` with `page_size=50`, ordered by `-created_at`. Cursor-based because the log can grow large and offset pagination degrades.
- **D-09:** Throttle: `"audit_log_list": "120/minute"` added to `DEFAULT_THROTTLE_RATES`. `AuditLogViewSet.throttle_scope = "audit_log_list"`.

### Serializer
- **D-10:** `AuditLogReadSerializer` returns:
  - `id`, `created_at`
  - `entity_type` — `"review"` or `"action_item"`
  - `entity_id` — raw string PK
  - `action` — e.g. `"reply_posted"`, `"action_item.status_changed"`
  - `actor_id`, `actor_name` — user display name (first + last), null if system action
  - `after_data` — JSON object (the snapshot stored at write time); omit `before_data` from the response to keep payloads small
- **D-11:** No `before_data` in the response payload — it would double response size and the UI shows a summary, not a diff editor. Internal ops can query `before_data` via Django admin if needed.

### Frontend — placement and layout
- **D-12:** New "Activity Log" nav item in the Org Admin sidebar, under a "Governance" group (or at the bottom of the existing nav after "Settings"). Icon: clock or list-check.
- **D-13:** Dedicated page (not a modal) rendered by a new Django template `templates/org-admin/audit-log.html` with a React widget at `#audit-log-root`.
- **D-14:** New entrypoint `frontend/src/entrypoints/audit-log.tsx` → new widget `frontend/src/widgets/audit-log/`.
- **D-15:** Table columns: **Date/Time** (relative + tooltip with absolute), **Actor** (name or "System"), **Type** (pill: "Reply" | "Action Item"), **Action** (human-readable label), **Details** (expandable caret — shows formatted `after_data` JSON on click).
- **D-16:** Filter bar above the table: Type (All / Replies / Action Items), Date Range (7d / 30d / 90d / custom), Actor (dropdown populated from distinct actors in the log for this org). Filters update URL params (bookmarkable).
- **D-17:** Empty state: "No activity logged yet." with a short description.
- **D-18:** Error state: inline retry (same pattern as dashboard widgets).
- **D-19:** No export button in this phase.

### Human-readable action labels
- **D-20:** Map raw `action` values to display strings in the frontend (not backend):

| action | display |
|--------|---------|
| `reply_posted` | Reply posted |
| `reply_deleted` | Reply deleted |
| `reply_failed` | Reply failed |
| `action_item.created` | Action item created |
| `action_item.status_changed` | Status changed |
| `action_item.assigned` | Assigned |
| `action_item.note_added` | Note added |
| `action_item.merged` | Merged as duplicate |

Unknown actions fall back to the raw string.

### Performance
- **D-21:** The existing composite index `audit_org_entity_date_idx` on `(organisation, entity_type, created_at)` covers the primary query shape. The filter `entity_type__in=["review", "action_item"]` will use the index. No new migration needed.
- **D-22:** The selector applies `.select_related("actor")` to avoid N+1 on actor name resolution.

### Phase 18 / 19 audit log writes
- **D-23:** Phase 18 (`merge_action_items`) must write an `AuditLog` entry with `action="action_item.merged"`, `entity_id=str(primary_id)`, `after_data={"merged_ids": [...], "count": N}`.
- **D-24:** Phase 19 (`generate_reply_draft`) does NOT write an `AuditLog` entry — draft generation is not a committed action. Only `submit_reply()` (Phase 11) writes the log.
- **D-25:** Phase 20 (`moderate_input` flagging) does NOT write an `AuditLog` entry — moderation events are observability data, not user activity. They are logged at WARNING level in the application log only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing code to extend
- `apps/common/models.py` — `AuditLog` model (read-only in this phase; already has all needed fields)
- `apps/common/views.py` — create this file with `AuditLogViewSet`
- `config/urls.py` — register `AuditLogViewSet` on `v1_router`
- `config/settings/base.py` — add `"audit_log_list": "120/minute"` to `DEFAULT_THROTTLE_RATES`
- `apps/accounts/permissions.py` — `IsOrgAdmin`, `IsStaffAdmin` (already exist, compose them)
- Templates: `templates/org-admin/` directory (check existing org admin templates for sidebar nav pattern)

### New files
- `apps/common/selectors/audit_logs.py` — `list_audit_logs_for_org()`, `list_audit_logs_for_staff()`
- `apps/common/serializers.py` — `AuditLogReadSerializer`
- `apps/common/filters.py` — `AuditLogFilterSet`
- `frontend/src/widgets/audit-log/` — React widget
- `frontend/src/entrypoints/audit-log.tsx`
- `templates/org-admin/audit-log.html`

### Architecture constraints
- `CLAUDE.md` §5 — `list_audit_logs_for_org()` is a selector (read-only query); viewset calls it
- `CLAUDE.md` §6 — use `select_related("actor")` on the audit log queryset to avoid N+1
- `CLAUDE.md` §8 — `CursorPagination` for large tables; cursor on `created_at`
- `CLAUDE.md` §9 — Staff scoping: restrict to accessible shops for review entries, scope=SHOP for action item entries
- `CLAUDE.md` §24 — order: selector → serializer → filter → view → URL → frontend

</canonical_refs>

<code_context>
## Existing Code Insights

### AuditLog entity_type and action values already in production
- `entity_type="review"` actions: `reply_posted`, `reply_deleted`, `reply_failed`
- `entity_type="action_item"` actions: `action_item.created`, `action_item.status_changed`, `action_item.assigned`, `action_item.note_added`
- `entity_type="shop_sync"` — excluded from viewer

### Existing index covering primary query
```python
# apps/common/models.py AuditLog.Meta
indexes = [
    models.Index(
        fields=["organisation", "entity_type", "created_at"],
        name="audit_org_entity_date_idx",
    ),
    ...
]
```

### Sidebar nav pattern
- Check `templates/org-admin/base.html` or `templates/base.html` for the existing nav item pattern used in Phase 11–14 (reviews, action items, dashboard).

### Staff scoping pattern reference
- `apps/action_items/selectors/items.py` — see how Staff scope is applied using `shop__in=accessible_shops`
- Mirror the same pattern in `list_audit_logs_for_staff()`

</code_context>

<deferred>
## Deferred Ideas

- **CSV / Excel export** — one-click download of filtered log — own task, requires streaming response or Celery export job
- **Diff viewer** — side-by-side `before_data` / `after_data` comparison — own feature, needs a JSON diff library
- **Notification on sensitive events** — email Org Admin when a reply is deleted — own feature
- **Superadmin cross-org audit viewer** — aggregate log across all orgs — Django admin covers this adequately for now
- **Retention policy** — auto-delete entries older than 2 years — own housekeeping task

</deferred>

---

*Phase: 21-audit-log-viewer*
*Context gathered: 2026-05-21*
