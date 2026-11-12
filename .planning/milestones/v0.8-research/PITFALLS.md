# Pitfalls Research — v0.4 Dashboard

**Domain:** Multi-tenant SaaS dashboard — Redis TTL caching, Django ORM aggregations, React parallel fetching
**Researched:** 2026-05-07
**Confidence:** HIGH (cache scoping, ORM aggregation, index design — verified against codebase and Django docs) | MEDIUM (React Query stale-data patterns, URL state pitfalls — verified against community sources) | HIGH (timezone handling — verified against Django docs and known production failure modes)

---

## Critical Pitfalls

### DASH-C1: Cache Key Missing `accessible_shop_ids` for Staff Users

**What goes wrong:**
The dashboard cache key is built from `(organisation_id, filter_region, filter_store, filter_date_range)`. A Staff Admin scoped to Shop A requests the KPI card. The response is cached. A Staff Admin scoped to Shop B (different user, same org, different scope) requests the same KPI card with the same region/store/date filters. They receive the first Staff Admin's data — including review counts and sentiment from shops outside their StaffAccessScope.

**Why it happens:**
Developers model the cache key on the filter bar parameters, which are the same for both users. The distinction that Staff users have row-level shop restrictions (via `StaffAccessScope`) is not visible at the filter bar level. The `get_accessible_shop_ids()` function already exists in `apps/reviews/selectors/reviews.py` and is used by the Reviews list, but is not yet called anywhere in the dashboard context.

**How to avoid:**
Cache key construction for all dashboard endpoints must include a `shop_ids_hash` component derived from the user's accessible shop ID list:

```python
import hashlib, json

def dashboard_cache_key(
    *,
    endpoint: str,
    organisation_id: int,
    user_id: int,
    accessible_shop_ids: list[int],  # sorted list; empty list = full org access (Org Admin)
    region_id: int | None,
    shop_id: int | None,
    date_from: str | None,
    date_to: str | None,
) -> str:
    # Org Admin: accessible_shop_ids=[] means "all shops" — this is a stable, distinct value
    scope_hash = hashlib.sha256(
        json.dumps(sorted(accessible_shop_ids)).encode()
    ).hexdigest()[:12]
    return (
        f"dashboard:{endpoint}:org:{organisation_id}:"
        f"scope:{scope_hash}:"
        f"r:{region_id}:s:{shop_id}:"
        f"from:{date_from}:to:{date_to}"
    )
```

For Org Admins, pass `accessible_shop_ids=[]` (meaning unrestricted). The hash of `[]` is stable and distinct from any Staff user's non-empty list.

**Warning signs:**
- Cache key builder takes `organisation_id` but not `user_id` or any scope identifier
- Staff user and Org Admin receive identical cache keys for the same filters
- No `get_accessible_shop_ids()` call in dashboard selector or view logic

**Phase to address:** Phase 14 — cache key builder must be the first utility written before any endpoint is cached.

---

### DASH-C2: Top-Performing Outlets Widget Incorrectly Applies Region/Store Filters

**What goes wrong:**
The Top Performing Outlets section (bar chart + Performance Highlights card) is specified to respond only to the Date Range filter, not Region or Store filters. The dashboard has a single unified filter bar with Region, Store, and Date Range controls. Developers wire all four dashboard API calls with the same filter parameters. Top Performing Outlets now excludes stores from the ranking when a specific Region or Store is selected — producing nonsensical results (a "top performers" list that only shows the selected store).

**Why it happens:**
The filter bar state object is passed as a single block to all React Query hooks. It is simpler and more consistent to use the same filter object everywhere. The specification that Top Performing Outlets ignores Region/Store is easy to miss or deprioritize in implementation.

**How to avoid:**
In the React dashboard component, construct two distinct filter objects before passing to hooks:

```typescript
// Full filters — used by KPI cards, Sentiment Distribution
const fullFilters = { regionId, shopId, dateFrom, dateTo };

// Date-only filters — used by Top Performing Outlets
const dateOnlyFilters = { dateFrom, dateTo };

const { data: topPerformers } = useTopPerformers(dateOnlyFilters);
const { data: kpis } = useKPIs(fullFilters);
```

On the backend, the Top Performing Outlets endpoint must ignore `region_id` and `shop_id` query parameters even if passed. Never trust that the frontend will omit them — enforce the filter scope in the selector.

**Warning signs:**
- Top Performing Outlets API endpoint accepts `region_id` and `shop_id` parameters and applies them
- A single `filters` object passed to all five React Query hooks
- Manual testing: select a specific store; Top Performers shows only that one store

**Phase to address:** Phase 14 — must be in the API contract specification for the Top Performing Outlets endpoint before any implementation begins.

---

### DASH-C3: Out-of-Scope URL Parameters Silently Ignored Instead of Returning 403

**What goes wrong:**
The filter bar stores region and store selection in the URL (`?region=5&shop=12`). When an Org Admin bookmarks a URL and shares it with a Staff Admin whose StaffAccessScope does not include Region 5 or Shop 12, the dashboard silently ignores the out-of-scope parameter and renders as if no filter is selected. No error is shown. This is a security failure, not a UX failure: the Staff user does not know their filter was silently dropped, and the dashboard data may partially reflect data from shops they are not entitled to see (depending on implementation order of filtering).

**Why it happens:**
The "silent fallback to unfiltered" pattern is intuitive for broken URL parameters in general web UIs. Developers apply the same pattern to tenant-scoped parameters without recognizing that `region_id` and `shop_id` from URL params are authorization-relevant, not just preference-relevant.

**How to avoid:**
The dashboard API endpoints must validate that `region_id` and `shop_id` filter parameters belong to the requesting user's organization AND are within their StaffAccessScope. Return `403 Forbidden` (not `400 Bad Request`) for out-of-scope parameters:

```python
# In the dashboard selector or view
def validate_filter_params(
    *,
    user: User,
    organisation_id: int,
    shop_id: int | None,
    region_id: int | None,
) -> None:
    if shop_id is not None:
        if not Shop.objects.filter(id=shop_id, organisation_id=organisation_id).exists():
            raise PermissionDenied("shop_id is not accessible")
        if user.role == User.Role.STAFF_ADMIN:
            accessible = get_accessible_shop_ids(user_id=user.pk)
            if shop_id not in accessible:
                raise PermissionDenied("shop_id is not in your access scope")
    if region_id is not None:
        if not Region.objects.filter(id=region_id, organisation_id=organisation_id).exists():
            raise PermissionDenied("region_id is not accessible")
```

The frontend must handle `403` on dashboard endpoints by showing an explicit "Access denied for the selected filter" message and clearing the filter from the URL, rather than silently retrying with no filters.

**Warning signs:**
- Dashboard filter validation returns `400` or silently falls back to unfiltered on invalid params
- No cross-org check on `shop_id`/`region_id` filter params in the selector
- No test asserting `403` when a Staff user passes a shop outside their scope as a URL param

**Phase to address:** Phase 14 — validate_filter_params must be implemented and tested before any endpoint accepts region/shop filter parameters.

---

### DASH-C4: Python-Side Aggregation Instead of DB-Level Avg/Count with HAVING

**What goes wrong:**
The KPI card "Average Rating" is computed by fetching all reviews into Python and calling `statistics.mean([r.star_rating for r in reviews])`. The Negative Reviews count is computed by filtering `[r for r in reviews if r.sentiment == 'negative']` in Python. The "minimum 3 reviews" threshold for Top Performing Outlets is enforced by a Python-side `if len(shop_reviews) >= 3` check after fetching per-shop review lists.

**Why it happens:**
The Reviews list already loads review rows for the list view. Developers reuse that queryset for aggregations rather than writing a separate aggregate query. The minimum review threshold feels like a business rule that belongs in application code.

**How to avoid:**
All aggregations must be computed at the database level using `annotate()`, `Avg()`, `Count()`, and `HAVING` (`filter()` on an annotation):

```python
from django.db.models import Avg, Count, Q

def get_kpi_metrics(
    *,
    organisation_id: int,
    shop_ids: list[int] | None,
    date_from: datetime,
    date_to: datetime,
) -> dict:
    qs = (
        Review.objects.active()
        .filter(
            organisation_id=organisation_id,
            review_create_time__gte=date_from,
            review_create_time__lt=date_to,
            **({"shop_id__in": shop_ids} if shop_ids else {}),
        )
    )
    return qs.aggregate(
        total_reviews=Count("id"),
        average_rating=Avg("star_rating"),
        negative_count=Count("id", filter=Q(
            sentiment="negative",
            enrichment_status="SUCCESS",
        )),
    )

# Top Performing Outlets — HAVING clause via annotation + filter
def get_top_performers(*, organisation_id, date_from, date_to, limit=10):
    return (
        Review.objects.active()
        .filter(
            organisation_id=organisation_id,
            review_create_time__gte=date_from,
            review_create_time__lt=date_to,
        )
        .values("shop_id", "shop__display_name")
        .annotate(
            review_count=Count("id"),
            avg_rating=Avg("star_rating"),
        )
        .filter(review_count__gte=3)  # HAVING clause — enforced at DB level
        .order_by("-avg_rating", "-review_count")[:limit]
    )
```

The `filter(review_count__gte=3)` after `annotate()` translates to a SQL `HAVING` clause, not a Python-side filter. This is critical for correctness: if done in Python after fetching results, a shop with 2 reviews might still appear in results if it was the only shop in the queryset.

**Warning signs:**
- `reviews = list(qs)` followed by `sum(r.star_rating for r in reviews)` in a service or selector
- `[r for r in reviews if r.sentiment == ...]` in dashboard code
- `len(shop_reviews) >= 3` rather than `.filter(review_count__gte=3)` after `.annotate()`
- `CaptureQueriesContext` test missing from the dashboard selectors

**Phase to address:** Phase 14 — write aggregate selectors with query-count tests before wiring to views.

---

### DASH-C5: Composite Index Field Order Mismatches Query Filter Order

**What goes wrong:**
The dashboard adds an index `(organisation_id, sentiment, review_create_time)` for the Sentiment Distribution query. The actual query filters on `(organisation_id, shop_id__in, review_create_time__range, enrichment_status)`. PostgreSQL cannot use the new index for this query because `shop_id` is the second filter predicate but is not in the index. The query falls back to a sequential scan. EXPLAIN ANALYZE shows `Seq Scan` on `reviews_review` with a large row estimate.

**Why it happens:**
Index design is often done once, based on a mental model of "what fields are filtered on." The composite index is created for the most commonly expected query shape, but the actual WHERE clause in the ORM query differs because of the `shop_id__in` restriction for Staff users and the `enrichment_status=SUCCESS` requirement for sentiment queries.

**How to avoid:**
Design indexes from the actual ORM queries, not from intuition. The three new indexes needed for the dashboard (as specified in the milestone requirements) must match the exact filter order:

```python
# In Review.Meta.indexes — add alongside existing indexes
indexes = [
    # Existing indexes...
    models.Index(
        fields=["organisation", "review_create_time", "deleted_at"],
        name="review_dash_date_idx",
        # Used by: KPI total count, Top Performers (date-only filter)
    ),
    models.Index(
        fields=["organisation", "shop", "review_create_time"],
        name="review_dash_shop_date_idx",
        # Used by: KPI with shop/region filter; shop_id IN (...) uses this
    ),
    models.Index(
        fields=["organisation", "enrichment_status", "sentiment", "review_create_time"],
        name="review_dash_sentiment_idx",
        # Used by: Sentiment Distribution (enrichment_status=SUCCESS + sentiment)
    ),
]
```

After adding indexes, run `EXPLAIN ANALYZE` against the actual dashboard queries in a test database with representative data volume. Confirm `Index Scan` is used, not `Seq Scan` or `Bitmap Heap Scan with large filter ratio`.

Note: the existing `review_org_date_idx` index covers `(organisation, review_create_time)` which helps the KPI total count query, but NOT the sentiment distribution query which also needs `enrichment_status` in the filter prefix.

**Warning signs:**
- Index defined on `(organisation, sentiment)` but query filters on `(organisation, shop, enrichment_status, sentiment)`
- No `EXPLAIN ANALYZE` check in the implementation plan
- Dashboard P95 latency >400ms in staging with >1000 reviews

**Phase to address:** Phase 14 — index migrations must be created and reviewed against actual query plans before the endpoint tests are written.

---

### DASH-C6: Enrichment Coverage Footer Showing Zero Instead of Partial State

**What goes wrong:**
The Sentiment Distribution card has a coverage footer: e.g., "Based on 847 of 1,200 reviews (71%)." The implementation calculates the denominator as `total_reviews_in_period` and the numerator as `enriched_reviews_in_period` (enrichment_status=SUCCESS). When some reviews in the period are unenriched (status=PENDING or FAILED), the footer correctly shows partial coverage. However, the implementation filters the entire Sentiment Distribution card to only show data when coverage is 100%, treating partial coverage as "no data." The result: if any reviews are unenriched, the entire Sentiment Distribution card is blank with a "No data" state, which is incorrect.

**Why it happens:**
The "only show AI data when enrichment is complete" heuristic is applied from the sync progress context (where showing partial data during an active sync is genuinely misleading). Developers apply the same heuristic to the dashboard analytics context, where it is incorrect: historical partial coverage is informative, not ambiguous.

**How to avoid:**
Always render the Sentiment Distribution card when at least one enriched review exists in the period. The coverage footer is the mechanism for communicating partial state:

```python
def get_sentiment_distribution(*, organisation_id, shop_ids, date_from, date_to):
    base_qs = Review.objects.active().filter(
        organisation_id=organisation_id,
        review_create_time__gte=date_from,
        review_create_time__lt=date_to,
        **({"shop_id__in": shop_ids} if shop_ids else {}),
    )
    total = base_qs.count()
    enriched_qs = base_qs.filter(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    enriched = enriched_qs.count()
    if enriched == 0:
        return None  # Genuine empty state — no enriched reviews at all

    distribution = enriched_qs.values("sentiment").annotate(count=Count("id"))
    return {
        "distribution": {row["sentiment"]: row["count"] for row in distribution},
        "enriched_count": enriched,
        "total_count": total,
        "coverage_pct": round(enriched / total * 100, 1) if total else 0,
    }
```

Return `None` only when `enriched == 0`. Return partial data with coverage metadata in all other cases.

**Warning signs:**
- Card renders "No data" when any reviews are PENDING or FAILED
- Coverage percentage is checked as a condition for rendering, rather than as metadata displayed alongside the chart
- No test case for "50% enriched — card should still render with coverage footer"

**Phase to address:** Phase 14 — Sentiment Distribution selector must include a test for partial enrichment state.

---

### DASH-C7: Timezone Mismatch on Date Window Boundaries

**What goes wrong:**
The filter bar's "Last 30 days" preset computes `date_from = datetime.utcnow() - timedelta(days=30)`. The dashboard stores reviews with `review_create_time` in UTC. The Org Admin is in UTC+8 (Singapore). When they select "Last 30 days" on May 7 at 10:00 AM local time, they expect reviews from April 7 local time onward. The UTC-based computation cuts off at April 7 00:00 UTC, which is April 7 08:00 local time — silently excluding 8 hours of reviews. For "Last 7 days," this produces a visibly wrong chart where "yesterday" is missing data.

**Why it happens:**
Django stores all `DateTimeField` values in UTC (when `USE_TZ = True`). Backend date arithmetic using `datetime.utcnow()` or `timezone.now()` is correct for UTC comparisons. The mistake is computing the date window in UTC rather than in the user's local timezone before converting to UTC for the DB query.

**How to avoid:**
Date window boundaries must be computed in the user's timezone, then converted to UTC for the database filter. The user's timezone must be stored on the `User` model or derived from their organisation's default timezone:

```python
import zoneinfo
from django.utils import timezone

def resolve_date_window(
    *,
    date_from_str: str | None,
    date_to_str: str | None,
    user_timezone: str,  # e.g. "Asia/Singapore"
) -> tuple[datetime, datetime]:
    tz = zoneinfo.ZoneInfo(user_timezone)
    if date_from_str and date_to_str:
        # Parse as date in user's timezone, then make timezone-aware
        from_local = datetime.fromisoformat(date_from_str).replace(tzinfo=tz)
        to_local = datetime.fromisoformat(date_to_str).replace(tzinfo=tz)
    else:
        # Default: last 30 days from midnight in user's timezone
        today_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        from_local = today_local - timedelta(days=30)
        to_local = today_local + timedelta(days=1)  # end of today
    # Convert to UTC for DB comparison
    return from_local.astimezone(timezone.utc), to_local.astimezone(timezone.utc)
```

Store `User.timezone` as a `CharField` defaulting to `"UTC"`. Validate against `zoneinfo.available_timezones()` on save.

If timezone storage on User is out of scope for Phase 14, use UTC boundaries and display a "Dates are shown in UTC" notice in the filter bar. This is an explicit, honest limitation rather than a silent correctness bug.

**Warning signs:**
- `datetime.utcnow()` or `timezone.now()` used directly as date window boundary without timezone conversion
- Date filter preset ("Last 30 days") computed server-side without consulting user timezone
- No test asserting that a UTC+N user's "last 7 days" window starts at the correct UTC timestamp

**Phase to address:** Phase 14 — date window resolution utility must be written and tested before any endpoint uses date filter params.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single cache key per endpoint ignoring scope differences | Simpler cache key builder | Cross-tenant data leak for Staff users — security incident | Never |
| Python-side aggregation from a pre-fetched queryset | Reuses existing list queryset | O(N) Python computation; breaks query-count CI ceiling; N+1 under filters | Never for dashboard KPIs |
| UTC-only date boundaries without user timezone | No User.timezone field needed | Silent data exclusion at day boundaries for non-UTC users | Acceptable only with explicit "UTC only" UI notice |
| Applying all filters to Top Performers widget | Single filter state object for all hooks | Nonsensical "top performers" list when a specific store is selected | Never |
| TTL-only cache invalidation (no event-based invalidation) | No invalidation code to write | Stale dashboard data for up to 5 minutes after a new sync completes | Acceptable for Phase 14 (5-min TTL is a stated requirement) |
| One React Query hook per widget with independent loading states | Simpler hook logic | Skeleton layout appears piecemeal; some cards finish while others still load — acceptable | Acceptable for Phase 14 |
| `history.pushState` for URL state instead of `replaceState` | Intuitive analogy to navigation | Every filter change creates a new browser history entry; Back button steps through individual filter states | Never |

---

## Integration Gotchas

Specific risks when adding `apps/dashboard/` to the existing v0.3 system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| DRF router registration | Adding `dashboard/` endpoints to the existing `config/urls.py` router without a dedicated namespace, causing URL conflicts with `reviews/` endpoints | Create a separate `apps/dashboard/urls.py` with a `dashboard/` prefix; include in `config/urls.py` as `path("api/v1/dashboard/", include("apps.dashboard.urls"))` |
| `get_accessible_shop_ids()` | Calling `get_accessible_shop_ids(user_id=user.pk)` for Org Admins (who have no StaffAccessScope rows), producing an empty list that filters out all shops | The function already returns `[]` for users with no scopes — callers must treat `[]` from Org Admin as "all shops" (no shop filter), not "no shops". Use `None` vs `[]` distinction explicitly. |
| Review model indexes | Adding dashboard indexes in a new migration that conflicts with an in-flight Celery sync migration on the same table | Dashboard indexes must be additive (not modifying existing indexes); coordinate migration numbering with the latest v0.3 migration; use `CONCURRENTLY` for large tables if review count exceeds 100K rows |
| Redis cache keys | Reusing `"organisations:list:*"` key namespace pattern from the existing organisations cache | Use a dedicated `"dashboard:"` key prefix; never share namespaces with other apps' cache keys |
| Celery worker processes | Dashboard cache invalidation triggered by a Celery task (e.g., after sync completes) using `cache.delete_pattern()` — this requires the `django-redis` backend with `delete_pattern` support | Confirm `django-redis` is installed (it is, per v0.3 stack) and the cache backend is `RedisCache`, not `LocMemCache` (which does not support `delete_pattern`) |
| React widget isolation | Mounting the dashboard React widget in a Django template that already has the TopbarBell and NotifBell widgets — three React roots competing for the same `DOMContentLoaded` event | Use separate `<div id="dashboard-root">` mount point; dashboard widget must not import from TopbarBell or NotifBell modules; no shared global state |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Aggregate query without date index | Dashboard KPI endpoint takes 2–3s with 50K reviews | Add composite index with `organisation_id + review_create_time` (already exists as `review_org_date_idx` — verify it is used by EXPLAIN) | >10K reviews per org |
| Top Performers fetching all reviews then grouping in Python | Server memory spike; P95 >1s | Use `.values("shop_id").annotate(avg_rating=Avg("star_rating"))` — one DB query, not N queries | >5 shops per org |
| Sentiment Distribution without `enrichment_status` in the index prefix | PostgreSQL falls back to filtering after index scan — slow for large orgs | Add `(organisation, enrichment_status, sentiment, review_create_time)` index | >20K enriched reviews |
| React Query with no `staleTime` on filter-driven dashboard | Every component mount triggers a refetch even when filters haven't changed; multiple widgets refetch simultaneously on page focus | Set `staleTime: 5 * 60 * 1000` (matching backend 5-min TTL); use `refetchOnWindowFocus: false` for dashboard queries | Any page with >3 parallel queries |
| Filter state stored in `useState` instead of URL params | Refreshing the page loses filter state; users cannot share filtered views | Store region/store/date in URL query params via `replaceState`; read from `URLSearchParams` on mount | Every page refresh |
| Cache invalidation via `delete_pattern` across many keys | `cache.delete_pattern("dashboard:*")` scans all Redis keys — slow on large Redis instances | Use specific key deletion with known key components; avoid wildcard scans in production hot paths | Redis with >100K keys |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Cache key does not include `accessible_shop_ids` for Staff users | Staff Admin A sees Staff Admin B's data if they share the same org+filters | Include scope hash in all dashboard cache keys (see DASH-C1) |
| `region_id` / `shop_id` filter params accepted without org membership check | Org Admin A passes `shop_id` belonging to Org B; receives Org B's review data | Validate every filter param is within `organisation_id` before applying; raise `PermissionDenied` not `ValidationError` |
| Out-of-scope filter params return 400 instead of 403 | Reveals whether the shop_id exists (400 = param invalid; 403 = param valid but forbidden) | Return 403 for cross-tenant or cross-scope params; same 403 response body regardless of whether the ID exists at all |
| Dashboard endpoint lacks `IsAuthenticated` + org-scoped permission | Anonymous access or cross-tenant API access | Every dashboard viewset must declare `permission_classes = [IsAuthenticated, IsOrgScoped]` explicitly; no default |
| React Query error handler silently swallows 403 and retries with no filters | Security 403 is treated as a "stale data" error; widget renders all-org data | Distinguish 403 from network errors; 403 must clear the relevant filter from state and URL and show an access-denied message |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| `history.pushState` for filter changes | Back button steps backward through every filter state (region, then store, then date); users lose their place | Use `history.replaceState` for filter changes; `pushState` only for intentional navigation (e.g., navigating to a review detail page) |
| All five dashboard widgets show skeleton loaders independently | Page feels fragmented; cards "pop in" at different times over 0.5–2s | Group widgets by data source; show a single skeleton per section until the group resolves |
| "No data" shown when zero enriched reviews exist but reviews do exist | User thinks the feature is broken | Show "Reviews are being analyzed — check back shortly" when `total > 0` and `enriched == 0`; reserve "No data" for `total == 0` |
| Filter "Clear" button reloads all five dashboard endpoints simultaneously | Network burst; brief loading flash | Debounce filter changes by 300ms; batch the clear action so all five queries are re-fetched in a single render cycle |
| "Your Store" single-shop variant (Staff with one accessible shop) shows the same bar chart as multi-shop | Meaningless chart with one bar | When `accessible_shop_ids.length === 1`, render the "Your Store" card variant (single shop KPIs + trend line) instead of the bar chart |

---

## "Looks Done But Isn't" Checklist

- [ ] **Cache key includes scope hash:** After implementation, log cache keys in dev and verify two Staff users with different scopes produce different keys even with identical filter params.
- [ ] **Top Performers ignores region/store filter:** Manually test: select a region in the filter bar; confirm the Top Performers bar chart still shows all shops in the org, not just that region's shops.
- [ ] **403 on out-of-scope params:** Write a test: Staff Admin with Shop A scope requests dashboard with `?shop=<Shop B ID>`; assert `403` returned.
- [ ] **HAVING clause at DB level:** Confirm with `EXPLAIN ANALYZE` that the minimum-3-reviews threshold produces a `HAVING count(id) >= 3` in the SQL, not a Python-side filter.
- [ ] **Sentiment Distribution shows partial state:** Test: org has 10 reviews, 5 enriched, 5 pending — Sentiment Distribution renders with `coverage_pct=50`, not a blank "No data" state.
- [ ] **Date window in user timezone:** Test: create reviews at 23:30 UTC on May 6; a UTC+8 user's "today" filter (May 7 local) should NOT include those reviews; a "yesterday" filter should include them.
- [ ] **`replaceState` not `pushState`:** Verify in browser devtools: changing the region dropdown 3 times results in 1 history entry, not 4.
- [ ] **`accessible_shop_ids` empty list correctly means "all shops" for Org Admin:** Test that an Org Admin with no StaffAccessScope rows sees all shops' data in the KPI cards.
- [ ] **React Query staleTime set:** Inspect network tab; confirm no refetch occurs when switching tabs and back within 5 minutes.
- [ ] **`enrichment_status=SUCCESS` filter on Negative Reviews count:** Confirm that reviews with `sentiment=negative` but `enrichment_status=FAILED` or `PENDING` are NOT counted in the Negative Reviews KPI.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cache key missing scope hash — data served to wrong Staff user | HIGH — security incident | Flush all `dashboard:*` cache keys immediately; add scope hash to key builder; audit access logs for affected Staff users; notify affected users if data was served incorrectly |
| Python-side aggregation causing P95 >400ms | MEDIUM | Rewrite selector to use `annotate()` + `Avg()` + `Count()` in the same sprint; existing tests should catch the query-count regression if CI gates are in place |
| Wrong index field order causing Seq Scan | MEDIUM | Add corrected index with `CONCURRENTLY` (no table lock); drop old index after new one is confirmed in EXPLAIN; no downtime required |
| UTC date boundary excluding user's local-time reviews | LOW-MEDIUM | Add `User.timezone` field (nullable, default UTC); update `resolve_date_window()` to use it; no data migration required (timezone is read-only at query time) |
| `pushState` instead of `replaceState` in filter bar | LOW | One-line JS fix; no backend changes; deploy immediately |
| Top Performers applying store/region filter | LOW-MEDIUM | Fix backend endpoint to strip region/shop params; fix React hook to pass `dateOnlyFilters`; cache keys change so old cached results expire naturally |

---

## Pitfall-to-Phase Mapping

Since this milestone is delivered as a single Phase 14, the mapping is to the specific **plan** within Phase 14 that must address each pitfall.

| Pitfall | Prevention Plan | Verification |
|---------|----------------|--------------|
| DASH-C1: Cache key missing scope hash | Plan: `apps/dashboard/` app skeleton + cache key builder | Test: two Staff users with different scopes produce different cache keys; verify in logs |
| DASH-C2: Top Performers applies wrong filters | Plan: Dashboard API endpoints (Top Performers endpoint contract) | Test: `GET /api/v1/dashboard/top-performers/?region=1` returns all shops; assert region param is ignored |
| DASH-C3: 403 on out-of-scope params | Plan: Dashboard API endpoints (filter param validation) | Test: Staff user with Shop A passes `?shop=<Shop B ID>`; assert `403` |
| DASH-C4: Python-side aggregation | Plan: Dashboard selectors with CaptureQueriesContext tests | Test: `CaptureQueriesContext` asserts ≤3 queries for KPI endpoint regardless of review count |
| DASH-C5: Wrong index field order | Plan: Review model — 3 new indexes migration | Verify: `EXPLAIN ANALYZE` shows `Index Scan` on all 5 dashboard queries after seeding 5K reviews |
| DASH-C6: Sentiment card blank on partial enrichment | Plan: Sentiment Distribution selector + enrichment coverage logic | Test: 50% enriched org — card renders with `coverage_pct=50`, not "No data" |
| DASH-C7: Timezone mismatch on date boundaries | Plan: Date window resolution utility | Test: UTC+8 user "last 7 days" window starts at correct UTC timestamp; verified against known review timestamps |

---

## Sources

- Django ORM `annotate()` + `HAVING` clause behavior: confirmed against Django 6.0 documentation for `.filter()` after `.annotate()` translating to SQL HAVING
- Composite index selectivity and field order: verified against PostgreSQL documentation on multicolumn indexes — leftmost field must match the leading filter predicate
- `history.replaceState` vs `pushState` for filter-driven UIs: React Router and TanStack Router documentation both recommend `replaceState` for filter/search state
- Django `USE_TZ = True` and `DateTimeField` UTC storage: Django 6.0 timezone documentation — all `DateTimeField` values stored in UTC; comparison requires timezone-aware datetimes
- React Query `staleTime` for TTL-aligned caching: TanStack Query v5 documentation — `staleTime` prevents background refetches within the window; should match backend TTL
- Multi-tenant cache key isolation: identified from analysis of existing `TenantScopedViewSet` and `get_accessible_shop_ids()` in this codebase
- `EXPLAIN ANALYZE` for index verification: PostgreSQL documentation — required after adding any new composite index to confirm the query planner selects it
- Partial enrichment coverage footer: derived from the "enriched count vs total" pattern already present in the sync progress consumer payload (`sync.enrichment.progress` event in CLAUDE.md §13.5)

---
*Pitfalls research for: v0.4 Dashboard — Redis caching, Django ORM aggregations, React parallel fetching, multi-tenant filter scoping*
*Researched: 2026-05-07*
