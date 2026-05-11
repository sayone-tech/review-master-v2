# Recurring Review Targets — Design Spec

## Goal

Replace the current per-period `ReviewTarget` design with a recurring target model. Each shop can have up to two active recurring targets (one weekly, one monthly). A dedicated per-shop page replaces the existing modal/tab UI.

## Architecture

**Model change:** `ReviewTarget` becomes a recurring configuration record — one row per shop per period type, max two rows per shop. Progress for the current period is computed at query time from live review data, never stored.

**Backend:** Upsert-based service (set = create or update), enriched selector that annotates each target with current-period progress, two REST endpoints on the existing `ShopViewSet`.

**Frontend:** New Django template page at `/admin/org/shops/<id>/targets/` with a self-contained React widget. Reached via the shop `...` context menu. Old modal/tab files deleted.

## Data Model

`ReviewTarget` (table: `shops_reviewtarget`) — simplified:

| Field | Type | Notes |
|---|---|---|
| `shop` | FK → Shop | |
| `organisation` | FK → Organisation | |
| `period_type` | CharField | `"WEEK"` or `"MONTH"` |
| `target_count` | PositiveIntegerField | ≥ 1 |
| `created_by` | FK → User (nullable) | |

**Removed field:** `period_start` — no longer needed.

**Unique constraint:** `(shop, period_type)` — replaces the old three-field constraint.

**Migration steps:**
1. Delete all existing `ReviewTarget` rows (per-period records are incompatible).
2. Drop the `period_start` column.
3. Replace the unique constraint with `(shop, period_type)`.

**Progress computation:** At query time, count reviews where `created_at` falls in the current ISO week (Monday–Sunday) or current calendar month. Returned as `received_count` and `pct` in the selector output. Never stored.

## Backend

### Services (`apps/shops/services/targets.py`)

- **`set_target(*, shop_id, org_id, period_type, target_count, created_by)`** — upserts. Validates `target_count ≥ 1` and that the shop belongs to the org. Uses `update_or_create` on `(shop, period_type)`.
- **`delete_target(*, target_id, org_id)`** — unchanged from current.

### Selector (`apps/shops/selectors/targets.py`)

- **`list_targets_for_shop(*, shop_id, org_id)`** — returns both targets for the shop (if set), each annotated with:
  - `received_count`: review count in current period via a single `Count` aggregation
  - `pct`: integer percentage toward target (capped at 100)
  - `period_label`: human-readable label e.g. "Week of May 5–11" or "May 2026"
  - `period_type`: `"WEEK"` or `"MONTH"`
  - `target_count`, `id`

### Serializers (`apps/shops/serializers.py`)

- `ReviewTargetSerializer` — read serializer with computed fields (`received_count`, `pct`, `period_label`).
- `ReviewTargetWriteSerializer` — input: `{period_type, target_count}`.

### Views (`apps/shops/views.py`)

Two actions added to `ShopViewSet`:

| Method | URL | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/shops/<id>/targets/` | IsOrgAdmin or IsStaffAdmin (own shop) | List targets with progress |
| `POST` | `/api/v1/shops/<id>/targets/` | IsOrgAdmin | Set target (upsert) |
| `DELETE` | `/api/v1/shops/<id>/targets/<target_id>/` | IsOrgAdmin | Delete a target |

### Django Template Page

- **URL:** `/admin/org/shops/<shop_id>/targets/`
- **View:** `shop_targets_view` in `apps/shops/views.py` (template view)
- **Template:** `templates/org/shop_targets.html`
- Passes `shop_id`, `shop_name`, `is_org_admin` to the template as data attributes on the React root element.
- Accessible to Org Admin (read/write) and Staff (read-only, filtered to their assigned shops).

## Frontend

### New Files

| File | Purpose |
|---|---|
| `frontend/src/entrypoints/shop-targets.tsx` | Entrypoint — mounts `ShopTargetsWidget` |
| `frontend/src/widgets/shop-targets/ShopTargetsWidget.tsx` | Main widget |
| `frontend/src/widgets/shop-targets/api.ts` | API calls (list, set, delete) |
| `frontend/src/widgets/shop-targets/types.ts` | TypeScript types |
| `templates/org/shop_targets.html` | Django template shell |

### Deleted Files

| File | Reason |
|---|---|
| `frontend/src/widgets/shop-management/SetTargetModal.tsx` | Replaced by page |
| `frontend/src/widgets/shop-management/TargetsTab.tsx` | Replaced by page |
| `frontend/src/widgets/shop-management/targetsApi.ts` | Replaced by `shop-targets/api.ts` |
| `frontend/src/widgets/shop-management/useTargets.ts` | Replaced by widget-local state |
| `frontend/src/widgets/action-items/ShopTargetsModal.tsx` | No longer needed |

### Page Layout

**Header:** Shop name + "Review Targets" as breadcrumb/page title.

**Two cards** (side-by-side on desktop, stacked on mobile):
- **Weekly card** and **Monthly card** — identical structure:
  - Label: "Weekly" / "Monthly"
  - Current period: "Week of May 5–11" / "May 2026"
  - If target set:
    - Progress bar (green ≥ 70%, amber ≥ 40%, red < 40%)
    - `received / target` count + percentage
    - Days remaining in period
    - Edit button (inline number input, org admin only)
    - Delete button with confirm (org admin only)
  - If no target set:
    - "No target set" message
    - "+ Set Target" button (org admin only)

### Navigation Changes

- **Shop `...` menu:** "Review Targets" entry uses `window.location.href` to navigate to `/admin/org/shops/<id>/targets/` — full page navigation (not a modal trigger).
- `ShopDetailsModal` — `TargetsTab` removed; the "Targets" tab is removed from the modal entirely.
- `ShopModals` — remove `detailsInitialTab` state and `shop:open-targets` event listener added during the previous phase.

## Error Handling

- API errors shown inline in each card (non-blocking — other card still usable).
- Shop not found or access denied → Django returns 403/404, template view handles with standard redirect.
- `target_count < 1` validated server-side; frontend input enforces `min=1`.

## Testing

**Services:**
- `set_target` creates when no target exists.
- `set_target` updates when target exists (upsert).
- `set_target` rejects `target_count < 1`.
- `set_target` rejects shop from another org.
- `delete_target` removes the row.

**Selector:**
- `list_targets_for_shop` returns correct `received_count` for reviews in current week/month.
- `received_count` excludes reviews from previous periods.
- Returns empty list when no targets set.

**Views:**
- GET returns targets with progress for org admin and staff (own shop).
- POST upserts correctly; 400 on invalid input.
- DELETE removes target; 404 on wrong org.
- Staff cannot POST or DELETE (403).

**Frontend:**
- Cards render correct state for set/unset targets.
- Edit inline flow saves and refreshes.
- Delete with confirm removes card to "no target" state.
