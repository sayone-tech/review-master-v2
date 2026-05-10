# Review Target Design

## Goal

Allow Org Admins to set review count targets for individual shops on a weekly or monthly basis. Staff Admins can view progress. No recurring targets — each period is set explicitly for the current or any future period.

## Architecture

A single `ReviewTarget` model in the `shops` app. Progress is always computed live (no stored counter), so it is never stale. Targets surface inside the existing Shop Details modal as a second tab — no new top-level navigation required.

## Tech Stack

- **Backend:** Django model + DRF ViewSet (nested under shops), services/selectors pattern
- **Frontend:** New React tab component + form modal inside the existing `ShopDetailsModal`

---

## Data Model

New model `ReviewTarget` added to `apps/shops/models.py`:

```python
class ReviewTarget(TimeStampedModel):
    class PeriodType(models.TextChoices):
        WEEK  = "WEEK",  "Weekly"
        MONTH = "MONTH", "Monthly"

    organisation = ForeignKey("organisations.Organisation", CASCADE, related_name="review_targets")
    shop         = ForeignKey("shops.Shop", CASCADE, related_name="targets")
    period_type  = CharField(max_length=5, choices=PeriodType.choices, db_index=True)
    period_start = DateField(db_index=True)   # Monday for WEEK, 1st of month for MONTH
    target_count = PositiveIntegerField()
    created_by   = ForeignKey("accounts.User", SET_NULL, null=True, blank=True, related_name="created_targets")

    class Meta:
        db_table = "shops_reviewtarget"
        constraints = [
            UniqueConstraint(fields=["shop", "period_type", "period_start"], name="target_unique_per_shop_period")
        ]
        indexes = [
            Index(fields=["organisation", "shop", "period_type", "period_start"], name="target_org_shop_period_idx")
        ]
```

### Period anchoring rules

- `MONTH` → `period_start` is always the 1st of the month (e.g., `2026-05-01`)
- `WEEK` → `period_start` is always the Monday of that ISO week (e.g., `2026-05-12`)
- The API normalises the supplied date to the correct anchor automatically — it does not reject non-anchored dates.
- `period_end` is computed: last day of month for MONTH; Sunday for WEEK.

### Past period restriction

Creating or updating a target whose `period_start` falls before the current period's start returns HTTP 400. Past targets that already exist are readable but not editable.

---

## API Endpoints

Base path: `/api/v1/shops/{shop_id}/targets/`

| Method   | URL                                  | Permission              | Description                        |
|----------|--------------------------------------|-------------------------|------------------------------------|
| `GET`    | `/api/v1/shops/{shop_id}/targets/`   | `IsOrgScoped`           | List targets with live progress    |
| `POST`   | `/api/v1/shops/{shop_id}/targets/`   | `IsOrgAdmin + IsOrgScoped` | Create a target                 |
| `PATCH`  | `/api/v1/shops/{shop_id}/targets/{id}/` | `IsOrgAdmin + IsOrgScoped` | Edit target count only        |
| `DELETE` | `/api/v1/shops/{shop_id}/targets/{id}/` | `IsOrgAdmin + IsOrgScoped` | Remove a target               |

Staff Admins hitting `GET` are scoped via `StaffAccessScope` — the view validates the requested `shop_id` is in their accessible shop IDs.

### GET response shape (per target)

```json
{
  "id": 1,
  "period_type": "MONTH",
  "period_start": "2026-05-01",
  "period_end": "2026-05-31",
  "target_count": 200,
  "received_count": 124,
  "pct": 62,
  "days_remaining": 21
}
```

- `received_count` — live `COUNT(*)` of `Review` rows for this shop where `review_create_time` falls within `[period_start, period_end]` and `deleted_at IS NULL`
- `pct` — `floor(received_count / target_count * 100)`, capped at 100
- `days_remaining` — calendar days from today to `period_end`, min 0

### POST / PATCH request shape

```json
{
  "period_type": "MONTH",
  "period_start": "2026-05-01",
  "target_count": 200
}
```

`PATCH` only accepts `target_count` — period type and start are immutable after creation.

### Validation errors

| Condition | HTTP | Message |
|-----------|------|---------|
| `period_start` in a past period | 400 | "Cannot set targets for past periods." |
| Duplicate `(shop, period_type, period_start)` | 400 | "A target for this period already exists." |
| `target_count < 1` | 400 | "Target must be at least 1 review." |

---

## Services & Selectors

### `apps/shops/selectors/targets.py`

```python
def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict]:
    """Return targets with live progress. Ordered: current first, future next, past last."""
```

The selector fetches all `ReviewTarget` rows for the shop, computes `period_end` per row, then runs a single aggregation query to get `received_count` for all periods in one DB round trip using `Count` with conditional filters or a subquery.

### `apps/shops/services/targets.py`

```python
def create_target(*, shop_id: int, org_id: int, period_type: str,
                  period_start: date, target_count: int, created_by: User) -> ReviewTarget: ...

def update_target(*, target_id: int, org_id: int, target_count: int) -> ReviewTarget: ...

def delete_target(*, target_id: int, org_id: int) -> None: ...
```

All service functions verify `organisation_id` matches before mutating.

---

## Frontend Components

### New files

| File | Responsibility |
|------|---------------|
| `frontend/src/widgets/shop-management/TargetsTab.tsx` | Tab body — lists targets with progress bars, edit/delete buttons, "+ Set Target" button |
| `frontend/src/widgets/shop-management/SetTargetModal.tsx` | Form modal — period type toggle (Monthly/Weekly), period dropdown (current + future only), target count input, info note showing existing progress for current period |
| `frontend/src/widgets/shop-management/useTargets.ts` | React Query hook — `GET /api/v1/shops/{id}/targets/`, mutations for create/update/delete |

### Modified files

| File | Change |
|------|--------|
| `ShopDetailsModal.tsx` | Add tab state (`"details" \| "targets"`), render `TargetsTab` when active |

### Targets tab UI behaviour

- Active targets (current period): show coloured progress bar (green ≥ 70%, amber 40–69%, red < 40%), count fraction, percentage, days remaining
- Future targets: shown with dashed border, no progress bar, "starts in N days" label
- Edit: inline — replaces the count display with an input, saves on blur or Enter
- Delete: confirmation prompt before removal
- Org Admin: sees edit + delete buttons. Staff: read-only, no buttons

### Set Target form behaviour

- Period type toggle: Monthly / Weekly (default Monthly)
- Period dropdown: populated from today's current period forward (up to 12 months / 52 weeks). Already-set periods are excluded from the dropdown.
- If the current period is selected and `received_count > 0`, show an info note: "This period already has N reviews — target will show X% progress immediately."
- On save: optimistic UI update, invalidate React Query cache for this shop's targets

---

## Permissions Summary

| Action | Org Admin | Staff Admin |
|--------|-----------|-------------|
| View targets tab | ✅ | ✅ (own shops only) |
| Create target | ✅ | ❌ |
| Edit target count | ✅ | ❌ |
| Delete target | ✅ | ❌ |

Staff Admins who attempt `POST/PATCH/DELETE` receive HTTP 403.

---

## Error States

- **No targets set yet:** Empty state with "No targets set for this shop. Set your first target →" and a CTA button (Org Admin only; staff sees "No targets set.")
- **Shop not connected to Google:** Targets can still be set and tracked (review count comes from our DB, not Google directly).
- **API error on load:** Show inline error with retry button inside the tab.

---

## Testing

### Backend

- `test_create_target_org_admin` — 201, correct `period_start` normalisation
- `test_create_target_staff_forbidden` — 403
- `test_create_target_past_period` — 400
- `test_create_target_duplicate` — 400
- `test_list_targets_includes_live_progress` — `received_count` matches actual review rows in DB
- `test_update_target_count` — 200, only `target_count` changes
- `test_update_target_period_immutable` — period fields ignored in PATCH
- `test_delete_target` — 204, row gone
- `test_staff_can_list_own_shop_targets` — 200
- `test_staff_cannot_list_other_shop_targets` — 403 or 404
- `test_org_scoping` — org A cannot read or mutate org B's targets

### Frontend

- `TargetsTab` renders progress bars with correct colour at 30%, 55%, 80%
- `TargetsTab` hides edit/delete for Staff role
- `SetTargetModal` excludes already-set periods from dropdown
- `SetTargetModal` shows info note when current period has existing reviews
- Empty state renders when no targets exist
