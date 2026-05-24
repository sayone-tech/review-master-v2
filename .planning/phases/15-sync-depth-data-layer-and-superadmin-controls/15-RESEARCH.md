# Phase 15: Sync Depth Data Layer and Superadmin Controls — Research

**Researched:** 2026-05-15
**Domain:** Django model extension, DRF serializer update, React toggle UI, Celery task date-filter logic
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Superadmin toggle UX (CreateOrgModal + EditOrgModal)**
- UI element: Toggle switch (not a checkbox)
- Placement: Bottom of form, before the submit button — below Number of Stores
- Label: "Allow configurable sync depth"
- Helper text: "When enabled, Org Admins can choose how far back to sync reviews when adding a new shop."
- Applies to both CreateOrgModal (default off) and EditOrgModal (reflects current value)

**Org detail display (ViewOrgModal)**
- Pattern: Simple dt/dd row — consistent with other org detail rows
- Label: "Configurable sync depth"
- Values: "Enabled" or "Disabled"
- No badge/color treatment — plain text value, same styling as other rows

**Shop depth display (ShopDetailsModal)**
- Visibility: Shown for ALL shops regardless of whether the org has custom sync depth enabled
- Row label: "Review history"
- Display values: "Last 1 year" / "Last 2 years" / "All time"
- The `sync_depth` serializer field must be included in the ShopRow type and the shops list/detail API response

**Backfill date cutoff**
- Approach: Fetch all pages from the GBP API, filter by `review_created_at >= start_date` at persist time — do NOT stop paginating early
- Date computation: Fixed `timedelta` — not calendar-month `relativedelta`
  - ONE_YEAR → `timezone.now() - timedelta(days=365)`
  - TWO_YEARS → `timezone.now() - timedelta(days=730)`
  - ALL_TIME → no `start_date` filter; pass no date to Google API
- The `run_initial_backfill` service function reads `shop.sync_depth` and computes `start_date` before beginning pagination; `start_date` is passed through to `_persist_page` or the filter applied there

### Claude's Discretion
- Exact toggle switch component implementation (can reuse or build a minimal Tailwind toggle)
- Where exactly in `_persist_page` the `start_date` filter is applied (pre-save check on `review_created_at`)
- Migration naming and reversibility details
- Index decision for `allow_custom_sync_depth` (boolean field, low cardinality — likely not needed)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNC-01 | Superadmin can enable "Allow configurable sync depth" when creating an organisation | `allow_custom_sync_depth` BooleanField on Organisation; `OrganisationCreateSerializer` must include field; `create_organisation` service must accept and persist it |
| SYNC-02 | Superadmin can enable/disable "Allow configurable sync depth" when editing an existing organisation | `update_organisation` service extension via `_UPDATABLE_FIELDS`; `OrganisationUpdateSerializer` must include field |
| SYNC-03 | The "Allow configurable sync depth" state is visible on the org detail page | `OrganisationListSerializer` / `OrganisationDetailSerializer` must expose `allow_custom_sync_depth`; `ViewOrgModal.tsx` adds dt/dd row |
| SDEP-02 | When parent org does not allow custom sync depth, shop is created with "Last 2 years" as default | `sync_depth` TextChoices on Shop; `default=Shop.SyncDepth.TWO_YEARS`; `create_shop` service sets default unconditionally for Phase 15 (Phase 16 handles the selector) |
| SDEP-03 | Selected review history depth shown on shop detail page | `sync_depth` in `ShopReadSerializer` and `ShopRow` TypeScript type; `ShopDetailsModal.tsx` adds "Review history" row |
| BKFL-01 | Initial backfill for "Last 1 year" fetches only last 12 months | `run_initial_backfill` computes `start_date = now() - timedelta(days=365)` and passes to `fetch_and_persist_reviews`; `_persist_page` skips rows where `review_create_time < start_date` |
| BKFL-02 | Initial backfill for "Last 2 years" fetches only last 24 months | Same mechanism; `timedelta(days=730)` |
| BKFL-03 | Initial backfill for "All time" fetches all — no date filter | `start_date=None`; `_persist_page` skips the date check when `start_date is None` |
</phase_requirements>

---

## Summary

Phase 15 is a purely additive data-layer phase — two model fields, two migrations, serializer extensions, service extensions, and frontend additions across two widgets. No existing rows change behavior: the new `allow_custom_sync_depth` field defaults to `False` (Organisation), and `sync_depth` defaults to `TWO_YEARS` (Shop), so all existing data is correctly defaulted without any data migration.

The most complex piece is the backfill date-filter threading: `run_initial_backfill` computes `start_date` from `shop.sync_depth`, then passes it down through `fetch_and_persist_reviews` into `_persist_page`. The GBP API does not support date-range query parameters directly, so filtering happens at persist time (after receiving each page). Per the locked decision, pagination continues to the end — do not short-circuit on page age, because GBP returns reviews sorted by `updateTime`, not `createTime`.

The frontend work involves adding a Tailwind toggle switch component to `CreateOrgModal` and `EditOrgModal`, a new dt/dd row to `ViewOrgModal`, and a "Review history" dt/dd row to `ShopDetailsModal`. No new shared component library is needed — the toggle can be built inline with existing Tailwind design tokens (`bg-yellow`, `bg-line`, etc.).

**Primary recommendation:** Implement in strict CLAUDE.md §24 order — model → migration → service → tests → serializer → view → frontend. All layers are straightforward extensions of established patterns already present in the codebase.

---

## Standard Stack

### Core (all already in project dependencies — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django `models.TextChoices` | Django 6.0.x | `Shop.SyncDepth` enum | Same pattern as `Organisation.Status`, `Shop.ConnectionStatus` already in codebase |
| Django `models.BooleanField` | Django 6.0.x | `Organisation.allow_custom_sync_depth` | Native Django field, no extras needed |
| `datetime.timedelta` | stdlib | Date offset computation in `run_initial_backfill` | Locked decision: fixed `timedelta`, not `relativedelta` |
| DRF `serializers.BooleanField` | DRF latest | Serialize `allow_custom_sync_depth` | Consistent with existing serializer patterns |
| DRF `serializers.ChoiceField` | DRF latest | Serialize `sync_depth` | Same as `connection_method`, `org_type` |
| React `useState` | 18.x | Toggle state management in modals | Already used in all modals |
| Tailwind CSS | 3.x | Toggle switch UI | All frontend uses Tailwind; peer-free approach (controlled component with `useState`) |

### No New Dependencies Required

This phase adds no new packages. Everything uses the existing stack.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
apps/
├── organisations/
│   ├── models.py              # + allow_custom_sync_depth BooleanField
│   ├── serializers.py         # + field in List/Detail/Create/Update serializers
│   ├── services/
│   │   └── organisations.py   # + allow_custom_sync_depth in _UPDATABLE_FIELDS + create_organisation sig
│   ├── migrations/
│   │   └── 0002_organisation_allow_custom_sync_depth.py  # new
│   └── tests/
│       ├── factories.py       # + allow_custom_sync_depth=False default (no change needed, Django default)
│       └── test_services.py   # + test allow_custom_sync_depth persisted on create and update
│
├── shops/
│   ├── models.py              # + SyncDepth TextChoices + sync_depth field
│   ├── serializers.py         # + sync_depth in ShopReadSerializer
│   ├── services/
│   │   └── shops.py           # create_shop: sync_depth defaults to TWO_YEARS
│   ├── migrations/
│   │   └── 0008_shop_sync_depth.py  # new
│   └── tests/
│       ├── factories.py       # + sync_depth=Shop.SyncDepth.TWO_YEARS (or leave implicit via model default)
│       └── test_services.py   # + test sync_depth default on create
│
├── reviews/
│   └── services/
│       └── sync.py            # run_initial_backfill computes start_date; _persist_page + fetch_and_persist_reviews accept start_date param
│   └── tests/
│       └── test_sync_service.py  # + 4 new test cases for date-filter behaviour
│
frontend/src/widgets/
├── org-management/
│   ├── types.ts               # + allow_custom_sync_depth in OrgRow, CreateOrgPayload, UpdateOrgPayload
│   ├── CreateOrgModal.tsx     # + ToggleSwitch at bottom of form
│   ├── EditOrgModal.tsx       # + ToggleSwitch reflecting current value
│   └── ViewOrgModal.tsx       # + "Configurable sync depth" dt/dd row
└── shop-management/
    ├── types.ts               # + sync_depth: SyncDepth in ShopRow
    └── ShopDetailsModal.tsx   # + "Review history" dt/dd row
```

### Pattern 1: TextChoices for SyncDepth (Django)

**What:** Inner class on `Shop` model following the exact established pattern.
**When to use:** All enumerated string fields in this codebase.

```python
# apps/shops/models.py — add to Shop class
class SyncDepth(models.TextChoices):
    ONE_YEAR  = "ONE_YEAR",  "Last 1 year"
    TWO_YEARS = "TWO_YEARS", "Last 2 years"
    ALL_TIME  = "ALL_TIME",  "All time"

sync_depth = models.CharField(
    max_length=10,
    choices=SyncDepth.choices,
    default=SyncDepth.TWO_YEARS,
)
```

No `db_index=True` — this field is not used in filtering or ordering (Claude's Discretion).

### Pattern 2: BooleanField with explicit default=False (Django)

```python
# apps/organisations/models.py — add to Organisation class
allow_custom_sync_depth = models.BooleanField(default=False)
```

No `db_index=True` — low cardinality boolean used only on create/edit, never in queryset filtering (Claude's Discretion confirms this).

### Pattern 3: Extending _UPDATABLE_FIELDS (organisations service)

**What:** The `update_organisation` service function filters updates through `_UPDATABLE_FIELDS` frozenset. Add `"allow_custom_sync_depth"` to that set.

```python
# apps/organisations/services/organisations.py
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {"name", "org_type", "address", "number_of_stores", "status", "allow_custom_sync_depth"}
)
```

`create_organisation` must also accept `allow_custom_sync_depth: bool = False` as a keyword arg and pass it to `Organisation.objects.create(...)`.

### Pattern 4: start_date threading through sync service

**What:** `run_initial_backfill` computes `start_date` from `shop.sync_depth` and passes it through the call chain. `fetch_and_persist_reviews` and `_persist_page` receive the optional `start_date` parameter.

**Key insight:** `fetch_and_persist_reviews` is also called by `run_incremental_sync`. The `start_date` parameter must default to `None` so incremental syncs are unaffected.

```python
# apps/reviews/services/sync.py

from datetime import timedelta
from django.utils import timezone as dj_timezone
from apps.shops.models import Shop

def run_initial_backfill(*, shop_id: int) -> dict[str, Any]:
    """Initial backfill — computes start_date from shop.sync_depth."""
    shop = Shop.objects.get(pk=shop_id)
    start_date: datetime | None
    if shop.sync_depth == Shop.SyncDepth.ONE_YEAR:
        start_date = dj_timezone.now() - timedelta(days=365)
    elif shop.sync_depth == Shop.SyncDepth.TWO_YEARS:
        start_date = dj_timezone.now() - timedelta(days=730)
    else:  # ALL_TIME
        start_date = None
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="initial", start_date=start_date)


def fetch_and_persist_reviews(
    *, shop_id: int, trigger: str = "incremental", start_date: datetime | None = None
) -> dict[str, Any]:
    # ... existing logic unchanged, except _persist_page receives start_date
    with transaction.atomic():
        persisted, ids, new_ids = _persist_page(
            shop=shop, api_reviews=page_reviews, start_date=start_date
        )
    # ...


def _persist_page(
    *,
    shop: Shop,
    api_reviews: list[dict[str, Any]],
    start_date: datetime | None = None,
) -> tuple[int, set[str], set[str]]:
    if not api_reviews:
        return 0, set(), set()
    rows: list[Review] = []
    rev_ids: set[str] = set()
    for api_rev in api_reviews:
        norm = _normalise_review(api_rev, shop=shop)
        if not norm["google_review_id"]:
            continue
        # Date filter: skip reviews older than start_date (initial backfill only)
        if start_date is not None and norm["review_create_time"] < start_date:
            continue
        rev_ids.add(norm["google_review_id"])
        rows.append(Review(**norm))
    # ... rest unchanged
```

**Important:** `run_initial_backfill` currently calls `Shop.objects.get(pk=shop_id)` — but `fetch_and_persist_reviews` also fetches the shop with `select_related`. To avoid a double-fetch, compute `start_date` inside `fetch_and_persist_reviews` when `trigger == "initial"`, using the `shop` object that is already fetched there. This is the cleaner implementation location. See "Common Pitfalls" below.

### Pattern 5: Tailwind Toggle Switch (React, no external library)

**What:** A controlled `<button role="switch">` pattern using existing Tailwind design tokens. No `peer` class trick (controlled component with `useState` is simpler and more explicit).

```tsx
// Inline in CreateOrgModal.tsx and EditOrgModal.tsx
// Uses bg-yellow (on) / bg-line (off) and the established text-subtle/text-ink styles.

function ToggleSwitch({
  id,
  checked,
  onChange,
  label,
  description,
}: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-black/10 ${
          checked ? "bg-yellow" : "bg-line"
        }`}
      >
        <span
          aria-hidden="true"
          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
      <div>
        <label
          htmlFor={id}
          className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] cursor-pointer"
        >
          {label}
        </label>
        {description && (
          <p className="mt-0.5 text-[12px] text-muted">{description}</p>
        )}
      </div>
    </div>
  );
}
```

`role="switch"` + `aria-checked` satisfies ARIA switch widget requirements. The `bg-yellow` (on) / `bg-line` (off) colors are established design tokens.

### Anti-Patterns to Avoid

- **Stopping pagination early on page age:** GBP reviews are sorted by `updateTime`. An old review updated recently will appear early in the list. Stopping when a page's first review is older than `start_date` would miss qualifying reviews. Always paginate fully; filter at persist time.
- **Using `relativedelta` for date offsets:** Locked decision uses `timedelta(days=365)` and `timedelta(days=730)`. Do not introduce `python-dateutil` or `relativedelta`.
- **Putting start_date computation in `run_initial_backfill` with a second Shop fetch:** The shop is already fetched in `fetch_and_persist_reviews`. Compute `start_date` inside `fetch_and_persist_reviews` when `trigger == "initial"` to avoid a redundant DB query.
- **Indexing `allow_custom_sync_depth`:** Boolean field with extremely low cardinality — an index would not be used by Postgres and adds write overhead. Claude's Discretion confirms: skip the index.
- **Passing `sync_depth` as a mutable field via `update_shop`:** `sync_depth` is set at creation and is conceptually read-only for existing shops (Phase 16 sets it only during creation via the selector). Do not add it to `_LOCKED_FIELDS` (that's for connection-related fields), but also do not expose it in `ShopUpdateSerializer` — simply omit it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toggle/switch UI | Custom toggle with complex CSS | Minimal Tailwind `<button role="switch">` | 5 lines of Tailwind classes; `role="switch"` + `aria-checked` is the ARIA standard |
| Date range offset | Calendar-month calculation | `timedelta(days=365)` / `timedelta(days=730)` | Locked decision; simpler, deterministic, no extra dependency |
| Enum field | `CharField` with manual validation | `models.TextChoices` | Django built-in, readable, self-documenting, generates proper migration |

**Key insight:** This phase is purely additive. The hardest part is threading `start_date` through `fetch_and_persist_reviews` and `_persist_page` without breaking incremental sync — both of which currently have no `start_date` parameter.

---

## Common Pitfalls

### Pitfall 1: Double Shop Fetch in Backfill
**What goes wrong:** `run_initial_backfill` fetches the shop to read `sync_depth`, then `fetch_and_persist_reviews` immediately fetches the shop again via `Shop.objects.select_related("organisation").get(pk=shop_id)`.
**Why it happens:** Straightforward implementation of "compute start_date before calling fetch".
**How to avoid:** Compute `start_date` inside `fetch_and_persist_reviews` by inspecting `trigger == "initial"` and reading `shop.sync_depth` from the shop object that is already fetched there. `run_initial_backfill` remains a one-liner calling `fetch_and_persist_reviews(shop_id=shop_id, trigger="initial")`.
**Warning signs:** Two `SELECT ... FROM shops_shop WHERE id=X` appearing in query logs for initial backfill.

### Pitfall 2: start_date Computed at Task Enqueue Time vs. Execution Time
**What goes wrong:** Computing `start_date` when the Celery task is enqueued, not when it executes. If the task sits in the queue for minutes/hours, the date would be slightly stale.
**Why it happens:** Passing `start_date` as a Celery task argument.
**How to avoid:** Never pass `start_date` as a Celery task argument. The task passes `shop_id` only (existing signature). `start_date` is computed inside the service at execution time from the live `shop.sync_depth` value.
**Warning signs:** Task signature `initial_backfill_task(shop_id, start_date)`.

### Pitfall 3: Forgetting start_date=None Default Breaks Incremental Sync
**What goes wrong:** If `_persist_page` or `fetch_and_persist_reviews` adds a required `start_date` parameter, incremental sync calls (which don't pass `start_date`) will break.
**Why it happens:** Missing `start_date: datetime | None = None` default.
**How to avoid:** Always default `start_date=None` in function signatures. When `start_date is None`, no date filtering is applied — this is the existing behavior for all syncs.
**Warning signs:** `TypeError: _persist_page() missing required argument: 'start_date'` in incremental sync tests.

### Pitfall 4: `review_create_time` Timezone Comparison
**What goes wrong:** Comparing a timezone-aware `start_date` (`timezone.now()` returns UTC-aware) against `review_create_time` values that were stored without timezone info.
**Why it happens:** `_normalise_review` uses `_parse_dt()` which sets `UTC` if `tzinfo is None`, and falls back to `dj_timezone.now()`. All `review_create_time` values should be timezone-aware. But the comparison `norm["review_create_time"] < start_date` must use the value in the `norm` dict (before the `Review` object is constructed), not a DB query.
**How to avoid:** The filter operates on `norm["review_create_time"]` which is already a timezone-aware datetime from `_parse_dt`. Verify `start_date = dj_timezone.now() - timedelta(...)` to confirm it is also timezone-aware (it is — `timezone.now()` returns UTC).
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` in tests.

### Pitfall 5: OrganisationCreateSerializer Not Including allow_custom_sync_depth in create_organisation Call
**What goes wrong:** `allow_custom_sync_depth` is added to `OrganisationCreateSerializer.Meta.fields` but `create_organisation()` service function does not accept the kwarg, causing a `TypeError` when `perform_create` calls `create_organisation(**serializer.validated_data)`.
**Why it happens:** Forgetting to update the service signature when updating the serializer.
**How to avoid:** Add `allow_custom_sync_depth: bool = False` to `create_organisation`'s signature and pass it to `Organisation.objects.create(...)` simultaneously with the serializer update.
**Warning signs:** `TypeError: create_organisation() got an unexpected keyword argument 'allow_custom_sync_depth'`.

### Pitfall 6: sync_depth Not in ShopReadSerializer Breaks ShopDetailsModal
**What goes wrong:** `sync_depth` is added to the `Shop` model and the TypeScript `ShopRow` type, but not to `ShopReadSerializer.Meta.fields`. The API response omits `sync_depth`, so `shop.sync_depth` is `undefined` in React and the "Review history" row shows nothing.
**Why it happens:** Model field added, serializer field list not updated.
**How to avoid:** Add `"sync_depth"` to `ShopReadSerializer.Meta.fields` in the same plan that adds the model field. The planner should make this a single atomic task.
**Warning signs:** `shop.sync_depth` is `undefined` in the browser; TypeScript may or may not catch this depending on whether `sync_depth` is declared as optional in `ShopRow`.

---

## Code Examples

Verified patterns from existing codebase:

### TextChoices Migration Pattern (existing: Organisation.Status)
```python
# apps/organisations/migrations/0002_organisation_allow_custom_sync_depth.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("organisations", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="organisation",
            name="allow_custom_sync_depth",
            field=models.BooleanField(default=False),
        ),
    ]
```

The migration is reversible by default (Django generates `RemoveField` for reversal of `AddField`).

### SyncDepth on Shop (following Shop.ConnectionStatus pattern)
```python
# apps/shops/migrations/0008_shop_sync_depth.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("shops", "0007_recurring_review_targets"),
    ]
    operations = [
        migrations.AddField(
            model_name="shop",
            name="sync_depth",
            field=models.CharField(
                choices=[
                    ("ONE_YEAR", "Last 1 year"),
                    ("TWO_YEARS", "Last 2 years"),
                    ("ALL_TIME", "All time"),
                ],
                default="TWO_YEARS",
                max_length=10,
            ),
        ),
    ]
```

### Serializer Extension (ShopReadSerializer)
```python
# apps/shops/serializers.py — ShopReadSerializer.Meta.fields addition
fields: ClassVar[list[str]] = [
    "id",
    "name",
    ...
    "sync_depth",   # new
    "created_at",
    "updated_at",
]
```

`sync_depth` is a `CharField` with choices — DRF serializes it as the raw string value (`"ONE_YEAR"`, etc.). The TypeScript frontend receives the raw value and maps it to display labels.

### TypeScript type additions
```typescript
// frontend/src/widgets/shop-management/types.ts
export type SyncDepth = "ONE_YEAR" | "TWO_YEARS" | "ALL_TIME";

export const SYNC_DEPTH_LABELS: Record<SyncDepth, string> = {
  ONE_YEAR:  "Last 1 year",
  TWO_YEARS: "Last 2 years",
  ALL_TIME:  "All time",
};

export interface ShopRow {
  // ... existing fields
  sync_depth: SyncDepth;
}
```

```typescript
// frontend/src/widgets/org-management/types.ts
export interface OrgRow {
  // ... existing fields
  allow_custom_sync_depth: boolean;
}

export interface CreateOrgPayload {
  // ... existing fields
  allow_custom_sync_depth: boolean;
}

export type UpdateOrgPayload = Partial<{
  // ... existing fields
  allow_custom_sync_depth: boolean;
}>;
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Sync all reviews regardless of age | Sync depth-gated by `shop.sync_depth` field | Phase 15 introduces this |
| Fixed "all reviews" behavior | Configurable per-shop depth, defaulting to TWO_YEARS | Org Admin selector deferred to Phase 16 |

**No deprecated patterns in this phase** — this is a clean additive change to existing, established patterns.

---

## Open Questions

1. **`_persist_page` row count semantics with date filter**
   - What we know: `_persist_page` currently returns `(len(new_google_review_ids), rev_ids, new_google_review_ids)`. With date filtering, some reviews are skipped and never added to `rev_ids`.
   - What's unclear: Should skipped reviews be added to `all_fetched_ids` (which drives `_soft_delete_absent`)? If not, a review that was previously synced (before the depth field was added) but is now outside the date window will be soft-deleted on the next initial backfill re-run.
   - Recommendation: For Phase 15, `_soft_delete_absent` is only called by `fetch_and_persist_reviews` at the end of all pages. Skipped (date-filtered) reviews should NOT be added to `all_fetched_ids` — they will be soft-deleted if they exist in the DB. This is correct behavior: an "All time → Last 1 year" depth change on re-sync should remove old reviews. The planner should make this behavior explicit in a test.

2. **Migration number for shops**
   - What we know: Last migration is `0007_recurring_review_targets.py`.
   - What's unclear: Confirmed — next migration is `0008_shop_sync_depth.py`.
   - Recommendation: Use this number.

3. **Migration number for organisations**
   - What we know: Only migration is `0001_initial.py`.
   - Recommendation: Next is `0002_organisation_allow_custom_sync_depth.py`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest apps/organisations/tests/ apps/shops/tests/ apps/reviews/tests/test_sync_service.py -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNC-01 | `allow_custom_sync_depth=True` persisted on org create | unit | `pytest apps/organisations/tests/test_services.py::test_create_organisation_allow_custom_sync_depth -x` | ❌ Wave 0 |
| SYNC-02 | `allow_custom_sync_depth` toggled via `update_organisation` | unit | `pytest apps/organisations/tests/test_services.py::test_update_organisation_allow_custom_sync_depth -x` | ❌ Wave 0 |
| SYNC-03 | `allow_custom_sync_depth` in list/detail API response | integration | `pytest apps/organisations/tests/test_views.py::test_org_list_includes_allow_custom_sync_depth -x` | ❌ Wave 0 |
| SDEP-02 | Shop created with `sync_depth=TWO_YEARS` by default | unit | `pytest apps/shops/tests/test_services.py::test_create_shop_default_sync_depth -x` | ❌ Wave 0 |
| SDEP-03 | `sync_depth` in shops list API response | integration | `pytest apps/shops/tests/test_views.py::test_shop_list_includes_sync_depth -x` | ❌ Wave 0 |
| BKFL-01 | `start_date=now-365d` filters reviews in `_persist_page` | unit | `pytest apps/reviews/tests/test_sync_service.py::test_initial_backfill_one_year_date_filter -x` | ❌ Wave 0 |
| BKFL-02 | `start_date=now-730d` filters reviews in `_persist_page` | unit | `pytest apps/reviews/tests/test_sync_service.py::test_initial_backfill_two_years_date_filter -x` | ❌ Wave 0 |
| BKFL-03 | No date filter for ALL_TIME; all reviews persisted | unit | `pytest apps/reviews/tests/test_sync_service.py::test_initial_backfill_all_time_no_filter -x` | ❌ Wave 0 |

**Additional required test:**
- Incremental sync (no `start_date`) is unaffected by the new parameter — `test_incremental_sync_start_date_default_none` in `test_sync_service.py` (regression guard).

### Sampling Rate
- **Per task commit:** `pytest apps/organisations/tests/ apps/shops/tests/ apps/reviews/tests/test_sync_service.py -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
All test cases for this phase are new — none exist yet. The existing `test_sync_service.py` file exists and should have new test functions added (do not create a new file).

- [ ] `apps/organisations/tests/test_services.py` — add `test_create_organisation_allow_custom_sync_depth`, `test_update_organisation_allow_custom_sync_depth`
- [ ] `apps/organisations/tests/test_views.py` — add `test_org_list_includes_allow_custom_sync_depth`
- [ ] `apps/shops/tests/test_services.py` — add `test_create_shop_default_sync_depth`
- [ ] `apps/shops/tests/test_views.py` — add `test_shop_list_includes_sync_depth`
- [ ] `apps/reviews/tests/test_sync_service.py` — add 4 date-filter test cases + 1 regression guard

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `apps/organisations/models.py`, `apps/shops/models.py`, `apps/reviews/services/sync.py`, `apps/organisations/serializers.py`, `apps/shops/serializers.py`, `apps/organisations/services/organisations.py`, `apps/shops/services/shops.py`
- Direct codebase inspection — `frontend/src/widgets/org-management/{CreateOrgModal,EditOrgModal,ViewOrgModal}.tsx`, `frontend/src/widgets/shop-management/{ShopDetailsModal,types}.tsx`
- `CLAUDE.md` §5, §6, §12.3, §24 — architecture constraints

### Secondary (MEDIUM confidence)
- CONTEXT.md locked decisions — all implementation decisions sourced from Phase 15 context session
- REQUIREMENTS.md — SYNC-01/02/03, SDEP-02/03, BKFL-01/02/03

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project; no new dependencies
- Architecture: HIGH — all patterns are established in existing codebase; direct inspection confirms structure
- Pitfalls: HIGH — all pitfalls identified from direct code reading of the exact functions being modified

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (stable codebase; no external API dependency changes expected)
