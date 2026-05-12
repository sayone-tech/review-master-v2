# Store Review Report — Design Spec

## Goal

Add a Reports page for Org Admins that shows a per-store summary of reviews for a selected period, filterable by reply status and sentiment.

## Access

- **Org Admin only.** Staff Admin does not have access.
- Enforced via `IsOrgAdmin` permission on the API endpoint and template-level role check on the page.

## Architecture

New Django app `apps/reports/` following the existing services/selectors/views pattern.

```
apps/reports/
├── __init__.py
├── apps.py
├── urls.py
├── views.py
├── selectors/
│   ├── __init__.py
│   └── store_report.py
└── tests/
    ├── __init__.py
    ├── factories.py
    └── test_selectors.py
    └── test_views.py
```

New frontend widget:

```
frontend/src/widgets/reports/
├── ReportsWidget.tsx
├── FilterBar.tsx
├── ReportsTable.tsx
├── api.ts
├── types.ts
├── useReportData.ts
└── index.ts
```

New Django template: `templates/org/reports.html`
New Vite entrypoint: `frontend/src/entrypoints/reports.ts`

## API

**Endpoint:** `GET /api/v1/reports/stores/`

**Permission:** `IsOrgAdmin`

**Query parameters:**

| Param | Values | Default |
|---|---|---|
| `range` | `7d`, `30d`, `90d`, `custom` | all time |
| `from` | ISO date (`YYYY-MM-DD`) | — |
| `to` | ISO date (`YYYY-MM-DD`) | — |
| `reply_status` | `replied`, `not_replied` | all |
| `sentiment` | `positive`, `neutral`, `negative` | all |

`range`, `from`, `to` use the same parsing logic as `apps/dashboard/filters.py` (`_resolve_date_window`). Max custom range: 365 days.

**Response:** JSON array of `StoreReportRow` objects, ordered by `total_reviews` descending.

```json
[
  {
    "shop_id": 1,
    "shop_name": "Sayone HQ",
    "total_reviews": 42,
    "avg_rating": 4.6,
    "replied_count": 38,
    "not_replied_count": 4,
    "positive_count": 35,
    "neutral_count": 3,
    "negative_count": 4
  }
]
```

**Filter semantics:**

- `sentiment=negative` — only negative-sentiment reviews (enrichment_status=SUCCESS, ai_sentiment='negative') are counted in all metrics including `total_reviews`, `avg_rating`, `replied_count`, `not_replied_count`.
- `reply_status=not_replied` — only reviews with no reply posted are counted.
- Both filters are additive (AND logic).
- Stores with zero matching reviews are **excluded** from the response (so `avg_rating` is always a number, never null).

**Caching:** No caching on this endpoint — reports are expected to be run infrequently and must reflect current data.

## Selector

`apps/reports/selectors/store_report.py` — `list_store_report(*, org_id, params) -> list[StoreReportRow]`

Single DB query using `values("shop_id", "shop__name").annotate(...)` on the Review queryset. No N+1. Uses `select_related` not needed — annotation covers all needed fields.

```python
from typing import TypedDict

class StoreReportRow(TypedDict):
    shop_id: int
    shop_name: str
    total_reviews: int
    avg_rating: float | None
    replied_count: int
    not_replied_count: int
    positive_count: int
    neutral_count: int
    negative_count: int
```

Filter params are a dataclass `ReportFilterParams` (same shape as `DashboardFilterParams` minus `region_id` and `shop_id`, which are not applicable to a cross-store report):

```python
@dataclass(frozen=True)
class ReportFilterParams:
    date_from: date | None
    date_to: date | None
    reply_status: str | None   # 'replied' | 'not_replied' | None
    sentiment: str | None      # 'positive' | 'neutral' | 'negative' | None
```

## Frontend

**FilterBar** — three dropdowns in a row (same visual style as the dashboard FilterBar):
- Period: All time / Last 7 days / Last 30 days / Last 90 days / Custom
- Reply status: All / Replied / Not replied
- Sentiment: All / Positive / Neutral / Negative

**ReportsTable** — HTML table with columns:

| Store | ★ Avg Rating | Reviews | Replied | Not Replied | 😊 Positive | 😐 Neutral | 😞 Negative |

- All numeric columns sortable client-side (no round trips).
- Default sort: Reviews descending.
- Empty state: "No reviews match the selected filters."
- Loading state: skeleton rows while fetching.

**useReportData** — fetches on mount and on filter change. Debounced by 300ms on custom date input only.

## Navigation

`templates/partials/sidebar.html` — add Reports nav item under the `ORG_ADMIN` section:

```html
{% include "partials/_nav_item.html" with href="/admin/org/reports/" icon="bar-chart-2" label="Reports" %}
```

## URL wiring

`config/urls.py` — include `apps/reports/urls.py` under the `/admin/org/` prefix.
`apps/reports/urls.py` — `path("reports/", ReportsPageView.as_view(), name="reports")`.
`config/urls.py` API block — include reports API under `/api/v1/reports/`.
`apps/reports/urls.py` (API) — `path("stores/", StoreReportApiView.as_view(), name="store-report")`.

## Testing

- `test_selectors.py`: single-query assertion (CaptureQueriesContext ≤ 2), filter combinations (all, replied only, negative only, combined), stores with zero matches are excluded.
- `test_views.py`: 200 for org admin, 403 for staff admin, 400 for invalid params.
