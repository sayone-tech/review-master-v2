---
phase: 11
phase_name: Reviews Fetching, Display, Reply
status: context_complete
created_at: "2026-05-01"
---

# Phase 11 Context — Reviews Fetching, Display, Reply

## Gray Areas Discussed

### 1. Progress Modal Placement

**Decision:** The Progress Modal opens on the **Shops page** immediately after Google OAuth completes.

Details:
- OAuth callback re-renders the Shops page; the Progress Modal opens there automatically (PROG-01)
- Always open on OAuth completion regardless of whether a sync is already running — read the current Redis snapshot and display whatever progress exists
- When the Org Admin clicks "Run in background", the modal closes and the **top-bar badge takes over exclusively** (no toast)
- The Org Admin can re-open the Progress Modal for a specific shop via the top-bar badge dropdown → "View progress" link, which navigates to the Shops page and re-opens the modal for that shop

**Wiring:**
- The OAuth callback (`/oauth/google/callback/`) must set a flag (e.g. session variable or query param) so the Shops page knows to trigger the modal on load
- The Shops page frontend reads this flag and mounts the ProgressModal for the connected shop's `shop_id`

---

### 2. Review List Layout

**Decision:** Dense table rows using the shared **DataTable React component**, consistent with Shops and Team tables.

Column layout:
- Stars (1–5 rating rendered as star icons)
- Shop name
- Reviewer name
- Date
- Sentiment badge (Positive / Neutral / Negative) — shown only after enrichment
- Reply status badge (Pending / Replied)
- "Reply" inline CTA (shown only for unreplied reviews — primary action in this column)
- Row actions menu (••• for additional actions)

**Reply composer:** Expands inline below the selected row (accordion pattern) or opens as a slide-out drawer from the right. The full review text and metadata are visible above the composer while typing.

**Filters:** Inline filter bar above the DataTable — compact controls for Store, Rating, Sentiment, Reply Status, Date range, and Search. Active filters displayed as dismissible chips. All filters apply additively (AND logic). Staff users see only their accessible shops in the Store filter dropdown.

**Reply CTA placement:** Visible inline on the row for all unreplied reviews (zero-click access to the primary action). No extra click needed to expand first.

---

### 3. Audit Log Model

**Decision:** Create a **generic shared `AuditLog` model** in `apps/common` (or `apps/reviews` if common feels too broad). Used by Phases 12–13 without new migrations.

**Model fields:**
- `entity_type` (CharField) — e.g. `"review"`, `"shop_sync"`, `"action_item"`
- `entity_id` (CharField/UUIDField) — PK of the entity
- `actor` (FK to User, nullable for system events)
- `action` (CharField) — e.g. `"reply_posted"`, `"sync_triggered"`, `"sync_completed"`
- `before_data` (JSONField, nullable)
- `after_data` (JSONField, nullable)
- `organisation` (FK to Organisation — for tenant scoping)
- `created_at` (auto DateTimeField)

**Phase 11 events to log:**
1. **Reply posted to Google** — `entity_type="review"`, `action="reply_posted"`, `after_data={reply_text, google_response_status}`
2. **Sync triggered (manual)** — `entity_type="shop_sync"`, `action="sync_triggered"`, `after_data={trigger_type="manual", shop_id}`
3. **Sync completed** — `entity_type="shop_sync"`, `action="sync_completed"`, `after_data={total_fetched, duration_seconds, trigger_type}`

**Not logged in Phase 11:** Review soft-delete events (soft-delete still happens per REVW-13 but is not audited yet).

**Access:** Org Admins only. No UI surface in Phase 11 — data is queryable via Django admin. Future phases add the audit trail UI.

---

### 4. Top-Bar Sync Indicator

**Decision:** A **React widget** embedded in the topbar div, using WebSocket events for real-time badge dismissal.

**Implementation:**
- Small React entrypoint (`frontend/src/entrypoints/topbar-sync-indicator.tsx`) mounted into a `<div id="sync-indicator-root">` in `templates/partials/topbar.html`
- On mount: calls `GET /api/v1/shops/syncing/` → `{count: N, shops: [{shop_id, shop_name}, ...]}`
- Shows badge with count when `count > 0`
- For each syncing shop, opens a WebSocket connection to `/ws/sync-progress/{shop_id}/`; on `sync.complete` event, removes that shop from the active list and decrements count
- Badge disappears immediately when count reaches 0 (WebSocket-driven, not poll-driven)

**API endpoint:** `GET /api/v1/shops/syncing/`
- Returns: `{count: int, shops: [{shop_id: int, shop_name: str}]}`
- Staff users see only their accessible shops' syncing status
- Lives on the ShopViewSet as a custom `@action` or a dedicated view

**Badge click:** Opens an Alpine.js-compatible dropdown listing each syncing shop name with a "View progress" link. The link navigates to `/admin/org/shops/` and passes `?open_progress={shop_id}` so the Shops page re-opens the modal for that shop.

**Constraint:** No new Channels consumers are created. The topbar widget reuses the existing `SyncProgressConsumer` at `/ws/sync-progress/<int:shop_id>/`. Connecting to N per-shop endpoints is acceptable because the typical concurrent sync count is small (1–3 shops at a time).

---

## Code Context

### Reusable assets

| Asset | Path | Reuse |
|-------|------|-------|
| DataTable | `frontend/src/widgets/data-table/DataTable.tsx` | Use directly for Reviews list |
| Modal | `frontend/src/widgets/modal/Modal.tsx` | Use for Progress Modal |
| toast.ts | `frontend/src/utils/toast.ts` | Use for reply success/error toasts |
| SyncProgressConsumer | `apps/reviews/consumers.py` | Existing — extend for progress events |
| Shop.ConnectionStatus | `apps/shops/models.py` | Check `IN_PROGRESS` before triggering sync |
| Google OAuth client | `apps/integrations/google/oauth.py` | Existing — call after shop connects |
| distributed_lock | `apps/common/locks.py` | Per-shop sync lock |
| with_retry | `apps/common/retry.py` | Wrap Google API calls |

### Existing review app skeleton (Phase 10 stub)

`apps/reviews/models.py` — empty stub, needs full Review model
`apps/reviews/consumers.py` — SyncProgressConsumer implemented in Phase 10
`apps/reviews/tasks.py` — task stubs, routing already in settings

### Pattern to follow for the Reviews list

The Shops list pattern (`ShopTable.tsx`, `apps/shops/views.py`, `apps/shops/selectors/`) is the closest precedent. Follow the same:
- `TenantScopedViewSet` base class
- Two serializers (read/write)
- `CaptureQueriesContext` test asserting ≤5 queries regardless of page size
- FilterSet with explicit declared filters (no `__` lookups)
- Cursor pagination for large tables (reviews can be in the thousands)

### Channels scope constraint

Per CLAUDE.md §13.2 — only `SyncProgressConsumer` in Phase 3. No new consumers without architecture review. The topbar React widget connects to the existing consumer endpoint; no new consumer file needed.

---

## Deferred Ideas (out of scope for Phase 11)

- Live new-review toast notifications (Phase 13 Notifications)
- Bulk reply or bulk action on multiple reviews
- Review export to CSV
- Audit log UI surface (future phase)
- Staff notification of new reviews assigned to their shops (Phase 13)
