# Phase 11: Reviews Fetching, Display, Reply — Research

**Researched:** 2026-05-01
**Domain:** Google Business Profile Reviews API, Celery-to-Channels progress events, DRF cursor pagination, React DataTable extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Progress Modal placement:** Opens on the Shops page immediately after OAuth; always reads current Redis snapshot on open. OAuth callback sets a flag (session variable or query param).
2. **Review list layout:** Dense DataTable rows using the shared DataTable React component; inline reply composer (accordion / slide-out drawer below row); filter bar above table (Store, Rating, Sentiment, Reply Status, Date range, Search); all filters apply additively (AND); "Reply" CTA visible inline on row for unreplied reviews.
3. **Audit log model:** Generic shared `AuditLog` in `apps/common` (or `apps/reviews`). Fields: `entity_type`, `entity_id`, `actor`, `action`, `before_data`, `after_data`, `organisation`, `created_at`. Phase 11 events: `reply_posted`, `sync_triggered`, `sync_completed`. No UI surface — Django admin only.
4. **Top-bar sync indicator:** React widget in `frontend/src/entrypoints/topbar-sync-indicator.tsx`, mounted into `<div id="sync-indicator-root">` in `templates/partials/topbar.html`. On mount: GET `/api/v1/shops/syncing/`. Reuses existing `SyncProgressConsumer` at `/ws/sync-progress/{shop_id}/`. Badge click: Alpine.js dropdown with "View progress" links passing `?open_progress={shop_id}`.
5. **No new Channels consumers:** Per CLAUDE.md §13.2, topbar widget reuses `SyncProgressConsumer`. No new consumer file needed.

### Claude's Discretion

- Whether the reply composer expands accordion-style in the same row or opens as a slide-out drawer
- OAuth → modal trigger mechanism: session variable vs. query param on the redirect URL

### Deferred Ideas (OUT OF SCOPE)

- Live new-review toast notifications (Phase 13)
- Bulk reply or bulk action on multiple reviews
- Review export to CSV
- Audit log UI surface (future phase)
- Staff notification of new reviews assigned to their shops (Phase 13)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SYNC-01 | Initial backfill dispatched after OAuth; fetches paginated historical reviews | GBP `list` endpoint: max 50/page, `nextPageToken` for continuation; task calls service function |
| SYNC-02 | Incremental sync every 6 hours with 30-min jitter via Beat fan-out | Beat `enqueue_incremental_syncs_task` fans out per-shop tasks; `random.uniform(0, 1800)` countdown |
| SYNC-03 | Per-shop Redis lock (`lock:google_sync:shop:{shop_id}`, 5-min TTL) | `distributed_lock` helper in `apps/common/locks.py` already implemented |
| SYNC-04 | `(shop_id, google_review_id)` uniqueness; re-fetch updates row | `update_or_create` with `google_review_id` as lookup; `UniqueConstraint` on model |
| SYNC-05 | Changed text/rating resets `enrichment_status = PENDING` | Compare fetched `comment`+`starRating` to stored; update + reset in same atomic write |
| SYNC-06 | Removed reviews soft-deleted (`deleted_at` set) | Fetch page of known `google_review_id`s; set `deleted_at = now()` for those absent |
| SYNC-07 | `401 invalid_grant` sets `connection_status = EXPIRED` | Catch `GoogleAuthError(reason="invalid_grant")`; call service to update shop status |
| SYNC-08 | `403`/5xx retries with backoff; persistent failure → AuditLog + Sentry | Celery `autoretry_for`, max 3; on exhaustion write AuditLog entry |
| SYNC-09 | Redis token bucket for Google API calls per project | Increment `rate:google:project` counter in Redis; check before each API call |
| SYNC-10 | AuditLog: `sync.started`, `sync.completed`, `sync.failed`, `review.fetched` | `AuditLog` generic model; write in service functions, not task bodies |
| PROG-01 | Progress Modal opens after OAuth; two progress bars (Fetched/AI) | Read Redis `sync:progress:{shop_id}` snapshot on connect; WebSocket events for live update |
| PROG-02 | ETA computed after ≥2 pages | Track page fetch timestamps in Redis progress state; compute rate → ETA |
| PROG-03 | "Run in background" closes modal; top-bar badge takes over | Modal `onDismiss` handler removes modal state; topbar React widget already polling WS |
| PROG-04 | "View shop details" enabled only on complete/error | Driven by `sync:progress:{shop_id}.status` field |
| PROG-05 | Error state with reconnect CTA | WebSocket `sync.error` event triggers error UI; error_code checked for `invalid_grant` |
| PROG-06 | Top-bar badge count with tooltip | React widget aggregates count from `GET /api/v1/shops/syncing/` |
| PROG-07 | Red warning icon on permanent failure | `sync.error` event with `error_code = "permanent_failure"` sets red badge |
| PROG-08 | WebSocket to `/ws/sync-progress/?shop_id={id}` — receives 4 event types | Existing `SyncProgressConsumer`; consumer group name `sync-progress-{shop_id}` |
| PROG-09 | On reconnect, snapshot sent immediately | `get_progress_snapshot` in Phase 10 stub → Phase 11 reads Redis |
| PROG-10 | `sync:progress:{shop_id}` Redis key; 24h TTL during, 1h after success, 7d after failure | `SETEX` / `EXPIRE` calls in sync service |
| REVW-01 | Reviews page at `/admin/org/reviews/`; Staff filtered to assigned shops | Template view + React entrypoint; `TenantScopedViewSet` base; Staff subquery on `StaffAccessScope` |
| REVW-02 | Filter bar: Store, Rating, Sentiment, Reply Status, Date, Search | `django-filter` `FilterSet`; FTS on `review_search_vector`; all additive |
| REVW-03 | "Showing X of Y" live count; search debounced 300ms | `count` field in API response; debounce in React hook (pattern from `useShops`) |
| REVW-04 | Sort selector: Newest/Oldest/Rating | CursorPagination with stable ordering; sort param maps to `ordering` field |
| REVW-05 | 10/25/50/100 page size; first/prev/next/last controls | Note: cursor pagination lacks offset-based "jump to page"; use next/prev cursor; show "Showing X-Y of Z" requires total count annotation |
| REVW-06 | Review card: reviewer name, star rating, shop badge, date, text with "Show more" | Serializer fields; `reviewer_display_name`, `star_rating`, `comment`; frontend truncates >1000 chars |
| REVW-07 | Sentiment badge, tags, "Analyzing…" pill, failure indicator | `enrichment_status` enum on Review model; Phase 12 fills sentiment/tags; Phase 11 shows pending/failed states |
| REVW-08 | Action item chips — clickable (Phase 12 populates) | Placeholder in Phase 11; M2M or FK relationship defined in model |
| REVW-09 | Reply section: replied view vs. inline composer | `review_reply` field serialized; composer state managed in React |
| REVW-10 | Reply submit → Google synchronously; success replaces composer | POST `/api/v1/reviews/{id}/reply/`; service calls GBP `updateReply`; on 200 return reply data |
| REVW-11 | Three empty states | Driven by `has_connected_shops` flag in API response; filters empty |
| REVW-12 | 30 replies/minute throttle | DRF `ScopedRateThrottle` with `throttle_scope = "review_reply"` |
| REVW-13 | AuditLog: `review.replied`, `review.reply_failed` | Write in reply service function |
| REVW-14 | `GET /api/v1/reviews/` ≤5 SQL queries; CI test | `select_related("shop__organisation", "shop__region")` + `prefetch_related` for reply; `CaptureQueriesContext` |
</phase_requirements>

---

## Summary

Phase 11 has three distinct technical sub-domains that must be planned and built in wave order:

**Wave 1 (model + sync backend):** The `Review` model, `AuditLog` model, Google review fetch client, Celery sync tasks (`initial_backfill_task`, `sync_shop_reviews_task`, `enqueue_incremental_syncs_task`), Redis progress key management, and the `SyncProgressConsumer` upgrade (staff-scope tightening + live snapshot reads).

**Wave 2 (API + reply):** The `ReviewViewSet` with cursor pagination, `django-filter` FilterSet (including full-text search via `SearchVectorField` + `GinIndex`), `TenantScopedViewSet` inheritance, Staff access scope filtering, reply endpoint that posts to Google synchronously, throttle, and AuditLog writes.

**Wave 3 (frontend):** Reviews page template + entrypoint, `useReviews` hook (mirrors `useShops`), `ReviewTable` component (extends `DataTable`), inline reply composer, `ProgressModal` component, OAuth → modal trigger wiring, topbar sync indicator entrypoint, and the `GET /api/v1/shops/syncing/` endpoint.

**Key architectural findings:**
- The GBP Reviews API (v4) uses `GET /v4/{parent}/reviews` with `pageSize` max 50 and `nextPageToken` pagination. Reply posting uses `PUT /v4/{parent}/reviews/{reviewId}/reply`.
- Emitting WebSocket events from Celery tasks uses `async_to_sync(channel_layer.group_send)(...)` from `asgiref.sync`. This is the canonical pattern and is safe with Celery's default `prefork` pool.
- DRF `CursorPagination` cannot support arbitrary sort + offset "jump to page" simultaneously. Use cursor pagination for the primary flow; total count is returned via a separate annotation.
- Full-text search on review text: use `SearchVectorField` with `GinIndex`; update via `update()` call in the sync service after each page persist.
- Staff access scope filtering requires a subquery on `StaffAccessScope` to derive the accessible `shop_id` set — one extra query that must be accounted for in the ≤5 query budget.

**Primary recommendation:** Build Wave 1 (models + sync) first — it unblocks Wave 2 (API) and Wave 3 (frontend) which can then proceed in parallel.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.2 | ORM, migrations, views | Already in project |
| DRF | 3.17.1 | ViewSets, serializers, throttling | Already in project |
| Celery | 5.6.3 | Background tasks, Beat schedule | Already in project; task routes pre-configured |
| channels | 4.3.2 | WebSocket consumer | Already in project; `SyncProgressConsumer` implemented |
| asgiref | (bundled with channels) | `async_to_sync` for Celery → Channels bridge | Part of channels; no extra install |
| django-filter | Not yet installed — **must add** | FilterSet for reviews endpoint | Standard DRF filtering; declared filters only |
| psycopg[binary] | 3.2.3 | Postgres FTS (`django.contrib.postgres`) | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | HTTP calls to GBP API (replies) | Already used for OAuth; extend for review endpoints |
| tenacity | 9.1.4 | Retry in `with_retry` decorator | Already in project; wrap GBP API calls |
| django-redis | 5.4.0 | Progress key storage, rate:google counter | Already in project |
| pytest-asyncio | 1.1.0 | Async consumer tests | Already in dev deps |

### New Dependencies
| Package | Install Command | Why |
|---------|----------------|-----|
| django-filter | `uv add django-filter` | DRF FilterSet for reviews; not yet in pyproject.toml |

**Installation:**
```bash
uv add django-filter
```

**Add to INSTALLED_APPS:**
```python
"django_filters",  # after rest_framework
```

**Add to REST_FRAMEWORK settings:**
```python
"DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
```

**Version verification:** `django-filter` latest stable is 24.x (HIGH confidence — maintained project).

---

## Architecture Patterns

### Recommended Project Structure (new files for Phase 11)

```
apps/reviews/
├── models.py                    # Review, AuditLog (or AuditLog in apps/common)
├── managers.py                  # ReviewQuerySet — annotate_reply_status, etc.
├── migrations/
├── consumers.py                 # Extend SyncProgressConsumer (staff scope)
├── serializers.py               # ReviewReadSerializer, ReviewReplySerializer
├── views.py                     # ReviewViewSet, template view
├── urls.py                      # /admin/org/reviews/ + router
├── filters.py                   # ReviewFilterSet (django-filter)
├── tasks.py                     # initial_backfill_task, sync_shop_reviews_task,
│                                #   enqueue_incremental_syncs_task
├── selectors/
│   ├── sync_progress.py         # get_progress_snapshot (upgrade from stub)
│   └── reviews.py               # list_reviews, get_accessible_shop_ids
├── services/
│   ├── sync.py                  # fetch_and_persist_reviews, emit_progress_event
│   ├── replies.py               # submit_reply (sync call to Google)
│   └── progress.py              # write_progress_snapshot, expire_progress_key
└── tests/
    ├── factories.py
    ├── test_models.py
    ├── test_sync_service.py
    ├── test_reply_service.py
    ├── test_selectors.py
    ├── test_views.py
    ├── test_tasks.py
    └── test_consumers.py        # extend existing with staff scope tests

apps/common/
└── models.py                   # Add AuditLog model here (generic, cross-phase)

frontend/src/
├── entrypoints/
│   ├── review-management.tsx    # Reviews page entrypoint
│   └── topbar-sync-indicator.tsx  # Topbar React widget entrypoint
└── widgets/
    └── review-management/
        ├── types.ts
        ├── api.ts
        ├── useReviews.ts
        ├── ReviewTable.tsx
        ├── ReviewCard.tsx          # Row renderer
        ├── ReplyComposer.tsx       # Inline expand/drawer
        ├── ProgressModal.tsx       # Sync progress modal
        ├── TopbarSyncIndicator.tsx
        └── ReviewFilters.tsx

templates/reviews/
└── review_list.html            # Template mounting review-management entrypoint
```

---

### Pattern 1: Review Model Design

The `Review` model uses integer PK (consistent with `Shop`), unique constraint on `(shop, google_review_id)`, soft-delete via `deleted_at`, `enrichment_status` enum, and a `SearchVectorField` for full-text search.

```python
# apps/reviews/models.py
from __future__ import annotations
from typing import ClassVar
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from apps.common.models import TimeStampedModel

class Review(TimeStampedModel):
    class StarRating(models.IntegerChoices):
        ONE = 1, "One"
        TWO = 2, "Two"
        THREE = 3, "Three"
        FOUR = 4, "Four"
        FIVE = 5, "Five"

    class EnrichmentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    # Tenant scope
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
    )
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    # Google identity
    google_review_id = models.CharField(max_length=200, db_index=True)
    google_account_id = models.CharField(max_length=200, blank=True)
    google_location_id = models.CharField(max_length=200, blank=True)

    # Review content (from GBP API)
    star_rating = models.SmallIntegerField(choices=StarRating.choices, db_index=True)
    reviewer_display_name = models.CharField(max_length=300, blank=True)
    reviewer_photo_url = models.URLField(blank=True)
    reviewer_is_anonymous = models.BooleanField(default=False)
    comment = models.TextField(blank=True)          # can be empty for rating-only reviews
    review_create_time = models.DateTimeField(db_index=True)
    review_update_time = models.DateTimeField()

    # Reply (from GBP API or just posted)
    reply_comment = models.TextField(blank=True)
    reply_update_time = models.DateTimeField(null=True, blank=True)
    is_replied = models.BooleanField(default=False, db_index=True)

    # Enrichment pipeline (Phase 12 populates)
    enrichment_status = models.CharField(
        max_length=15,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
        db_index=True,
    )
    enrichment_version = models.PositiveSmallIntegerField(default=0)
    enrichment_attempted_at = models.DateTimeField(null=True, blank=True)
    sentiment = models.CharField(max_length=10, blank=True)   # positive/neutral/negative

    # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Full-text search vector (updated by sync service after persist)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        db_table = "reviews_review"
        ordering: ClassVar[list[str]] = ["-review_create_time"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "google_review_id"],
                name="review_unique_per_shop",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "shop", "is_replied", "star_rating"],
                name="review_org_shop_filter_idx",
            ),
            models.Index(
                fields=["organisation", "review_create_time"],
                name="review_org_date_idx",
            ),
            GinIndex(fields=["search_vector"], name="review_search_vec_idx"),
        ]
```

---

### Pattern 2: AuditLog Model (generic, shared across phases 11–13)

```python
# apps/common/models.py (addition)
class AuditLog(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_entries",
    )
    entity_type = models.CharField(max_length=50, db_index=True)   # "review", "shop_sync", ...
    entity_id = models.CharField(max_length=200, db_index=True)    # PK of entity (str)
    action = models.CharField(max_length=100, db_index=True)       # "reply_posted", ...
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "common_audit_log"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "entity_type", "created_at"],
                name="audit_org_entity_date_idx",
            ),
        ]
```

---

### Pattern 3: Google Reviews API Client Extension

The project already uses `apps/integrations/google/oauth.py` with `httpx` and `tenacity`. The Phase 11 reviews client lives at `apps/integrations/google/reviews_client.py` and follows the same pattern.

```python
# apps/integrations/google/reviews_client.py
REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"

def list_reviews(
    *,
    access_token: str,
    account_id: str,
    location_id: str,
    page_token: str = "",
    page_size: int = 50,
) -> dict[str, Any]:
    """
    GET /v4/accounts/{account_id}/locations/{location_id}/reviews
    Returns: {"reviews": [...], "totalReviewCount": N, "nextPageToken": "..."}
    Max pageSize = 50. Paginate by passing nextPageToken as pageToken.
    """
    url = f"{REVIEWS_BASE}/accounts/{account_id}/locations/{location_id}/reviews"
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    resp = _bearer_get(url, access_token, params=params)
    if resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if resp.status_code == 403:
        raise GoogleQuotaError()
    if resp.status_code >= 500:
        raise GoogleUnreachableError()
    return resp.json()

def post_reply(
    *,
    access_token: str,
    account_id: str,
    location_id: str,
    review_id: str,
    comment: str,
) -> dict[str, Any]:
    """
    PUT /v4/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply
    Body: {"comment": "..."}
    Returns reply object with updateTime.
    """
    url = f"{REVIEWS_BASE}/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply"
    resp = httpx.put(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"comment": comment},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if resp.status_code >= 400:
        raise GoogleReplyError(status=resp.status_code, body=resp.text)
    return resp.json()
```

**GBP Review object fields (HIGH confidence — verified from official docs):**
```
name            → "accounts/{acct}/locations/{loc}/reviews/{reviewId}"
reviewId        → encrypted unique identifier (use as google_review_id)
starRating      → ONE | TWO | THREE | FOUR | FIVE
comment         → review text (may be absent for rating-only)
createTime      → RFC 3339 timestamp
updateTime      → RFC 3339 timestamp
reviewer.displayName    → reviewer name (absent if anonymous)
reviewer.profilePhotoUrl → photo URL
reviewer.isAnonymous    → bool
reviewReply.comment     → reply text (absent if no reply)
reviewReply.updateTime  → when reply was last modified
```

**Detecting deleted reviews:** The GBP API does NOT return deleted reviews. The sync service must compare fetched `google_review_id` sets against the local DB per shop and soft-delete those absent. Pattern:
```python
fetched_ids = {r["reviewId"] for r in page_reviews}
Review.objects.filter(shop=shop, deleted_at__isnull=True).exclude(
    google_review_id__in=fetched_ids
).update(deleted_at=timezone.now())
```
This runs once after the final page is persisted.

---

### Pattern 4: Celery → WebSocket Progress Events (async_to_sync)

**This is the canonical pattern (HIGH confidence — verified from Channels docs and multiple sources):**

```python
# apps/reviews/services/sync.py  (called from Celery task body, sync context)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def emit_progress_event(*, shop_id: int, payload: dict[str, Any]) -> None:
    """Send a progress event to the SyncProgressConsumer group.

    Safe to call from Celery prefork workers — async_to_sync creates a new
    event loop for each call in the worker process.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"sync-progress-{shop_id}",
        {"type": "progress.event", "payload": payload},
    )
```

**Caution:** Do NOT use this pattern with Celery's `gevent` or `eventlet` pools — those share an event loop across tasks and cause `RuntimeError: You cannot use AsyncToSync in the same thread as an async event loop`. The project uses default `prefork` (concurrency=8), so this is safe.

---

### Pattern 5: Redis Progress Snapshot

```python
# apps/reviews/services/progress.py
import json
from django_redis import get_redis_connection

PROGRESS_KEY = "sync:progress:{shop_id}"
TTL_ACTIVE = 86400      # 24h while running
TTL_SUCCESS = 3600      # 1h after success
TTL_FAILURE = 604800    # 7d after permanent failure

def write_progress_snapshot(*, shop_id: int, data: dict[str, Any], ttl: int = TTL_ACTIVE) -> None:
    r = get_redis_connection("default")
    r.setex(PROGRESS_KEY.format(shop_id=shop_id), ttl, json.dumps(data))

# In selectors/sync_progress.py (upgrade from Phase 10 stub):
async def get_progress_snapshot(*, shop_id: Any) -> dict[str, Any] | None:
    from channels.db import database_sync_to_async
    # Use redis-py async or wrap with database_sync_to_async for sync redis call
    import json
    from django_redis import get_redis_connection
    conn = get_redis_connection("default")
    data = conn.get(f"sync:progress:{shop_id}")
    return json.loads(data) if data else None
```

**IMPORTANT:** `get_progress_snapshot` is called from the async consumer. Use `sync_to_async` wrapper or use the async redis client. Simplest pattern: wrap the sync `get_redis_connection` call.

---

### Pattern 6: ReviewViewSet with Cursor Pagination

```python
# apps/reviews/views.py
from rest_framework.pagination import CursorPagination

class ReviewCursorPagination(CursorPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-review_create_time"   # stable, indexed field

class ReviewViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    permission_classes = [IsOrgScoped]  # ORG_ADMIN or STAFF_ADMIN
    serializer_class = ReviewReadSerializer
    pagination_class = ReviewCursorPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ReviewFilterSet
    ordering_fields = ["review_create_time", "star_rating"]
    ordering = ["-review_create_time"]

    def get_queryset(self) -> QuerySet[Review]:
        qs = super().get_queryset()  # applies organisation_id filter via TenantScopedViewSet
        qs = qs.filter(deleted_at__isnull=True)
        user = self.request.user
        if user.role == User.Role.STAFF_ADMIN:
            # Staff can only see reviews for their accessible shops
            accessible_shop_ids = get_accessible_shop_ids(user_id=user.pk)
            qs = qs.filter(shop_id__in=accessible_shop_ids)
        return qs.select_related("shop", "shop__region")
```

**Critical:** `CursorPagination` does NOT return a `count` field in the response. For "Showing X of Y", add a separate `count` endpoint or include a `total_count` annotation. The simplest approach is to include `total_count` as a custom field in the list response using a `@action` or by overriding `list()`.

---

### Pattern 7: ReviewFilterSet

```python
# apps/reviews/filters.py
import django_filters
from apps.reviews.models import Review

class ReviewFilterSet(django_filters.FilterSet):
    shop = django_filters.NumberFilter(field_name="shop_id")
    rating = django_filters.NumberFilter(field_name="star_rating")
    sentiment = django_filters.CharFilter(field_name="sentiment")
    is_replied = django_filters.BooleanFilter(field_name="is_replied")
    from_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="gte")
    to_date = django_filters.DateFilter(field_name="review_create_time", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Review
        fields: list[str] = []

    def filter_search(self, queryset, name, value):
        # Full-text search on search_vector; fallback to icontains on comment+reviewer_display_name
        from django.contrib.postgres.search import SearchQuery
        if not value:
            return queryset
        sq = SearchQuery(value, config="english")
        return queryset.filter(search_vector=sq)
```

---

### Pattern 8: Selector — get_accessible_shop_ids for Staff

```python
# apps/reviews/selectors/reviews.py
from django.db.models import Q
from apps.accounts.models import StaffAccessScope, User

def get_accessible_shop_ids(*, user_id: int) -> list[int]:
    """Return shop IDs accessible to a Staff user via StaffAccessScope.

    Handles both SHOP-scoped and REGION-scoped entries.
    Used in ReviewViewSet.get_queryset() for Staff users.
    This is one extra query counted against the ≤5 budget.
    """
    scopes = StaffAccessScope.objects.filter(user_id=user_id).select_related("region")
    shop_ids: set[int] = set()
    region_ids: set[int] = set()
    for s in scopes:
        if s.scope_type == StaffAccessScope.ScopeType.SHOP and s.shop_id:
            shop_ids.add(s.shop_id)
        elif s.scope_type == StaffAccessScope.ScopeType.REGION and s.region_id:
            region_ids.add(s.region_id)
    if region_ids:
        from apps.shops.models import Shop
        shop_ids.update(
            Shop.objects.filter(region_id__in=region_ids).values_list("id", flat=True)
        )
    return list(shop_ids)
```

---

### Pattern 9: Topbar React Entrypoint — OAuth Trigger Wiring

The OAuth callback (`GoogleOAuthCallbackView`) currently stores tokens in session and writes to Redis. After the shop creation POST (in `ShopViewSet.perform_create`), the Phase 11 implementation must:
1. Dispatch `initial_backfill_task.delay(shop_id=shop.pk)` immediately.
2. Set a session flag `pending_sync_shop_id = shop.pk` so the Shops page frontend knows to open the ProgressModal.

The Shops page frontend reads `?open_progress={shop_id}` (query param approach) or reads `window.__pending_sync_shop__` from a Django template context variable. **Recommended:** Use a query param on the redirect after shop creation (`/admin/org/shops/?open_progress={shop_id}`) — avoids session state complexity and is bookmarkable.

---

### Anti-Patterns to Avoid

- **Calling `emit_progress_event` from within a `transaction.atomic()` block:** The channel layer message is sent immediately; if the transaction rolls back, the progress event has already been sent. Write progress events AFTER committing.
- **Using `CursorPagination` with an ordering field that is NOT indexed:** Will cause full table scan. `review_create_time` must have a DB index.
- **Storing the full review list in session:** Session storage has a 4KB cookie limit. Use Redis for all progress state.
- **Calling `review.save()` from the sync service for each review:** Use `bulk_create` with `update_conflicts=True` for batch upsert.
- **`icontains` on `Review.comment` at scale:** Use `SearchVectorField` + `GinIndex`. The `filter_search` method already handles this.
- **Triggering `initial_backfill_task` synchronously (ALWAYS_EAGER=True in tests):** In tests, `CELERY_TASK_ALWAYS_EAGER=True` means the task runs synchronously — ensure the test DB is in a known state before dispatching.
- **Running multiple Beat instances:** Exactly one Beat instance. Duplicate `enqueue_incremental_syncs_task` runs would double-dispatch per-shop tasks.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DB-level upsert for reviews | Custom SQL | `Review.objects.update_or_create()` with `defaults=` | Handles MVCC correctly; simpler |
| Batch upsert for multiple reviews | Row-by-row loop | `Review.objects.bulk_create(objs, update_conflicts=True, update_fields=[...])` | psycopg3 supports this; far fewer queries |
| FTS indexing | Elasticsearch | `SearchVectorField` + `GinIndex` | Sufficient for review text at this scale; zero extra infra |
| Rate limiting reply endpoint | Redis counter | DRF `ScopedRateThrottle` with `"review_reply"` scope | Already in throttle settings pattern |
| Progress key TTL management | Cron job | Redis `SETEX`/`EXPIRE` at transition points | Self-healing; no extra process |
| Celery → WebSocket bridge | Polling / separate queue | `async_to_sync(channel_layer.group_send)` | Canonical Channels pattern |
| Token bucket for Google API | Rolling window counter | Redis `INCR` + `EXPIRE` on `rate:google:project` | Already defined in CLAUDE.md §7.7 |

**Key insight:** The psycopg3 driver (already installed) supports `bulk_create(..., update_conflicts=True)` natively. This replaces per-review `update_or_create` calls and reduces the sync service to 1–2 queries per page rather than N queries.

---

## Common Pitfalls

### Pitfall 1: CursorPagination + Total Count Conflict

**What goes wrong:** `CursorPagination` does not return a `count` field. The "Showing X of Y" requirement (REVW-03) needs total count. Developers add `count` to `CursorPagination.get_paginated_response()` by running `queryset.count()` — this adds an extra query and may bust the ≤5 query budget.

**Why it happens:** `CursorPagination` is designed for infinite scroll (no total count). Adding count is technically possible but costs a query.

**How to avoid:** Budget the count query explicitly. With `select_related("shop", "shop__region")` + the Staff subquery + the main queryset + next/prev cursor evaluation + count, that is exactly 5 queries for Staff users and 4 for Org Admins. The count query uses the same filtered queryset without ordering (Postgres optimizes this).

**Warning signs:** CI test `assert len(ctx.captured_queries) <= 5` fails.

---

### Pitfall 2: async_to_sync in Gevent/Eventlet Celery Pool

**What goes wrong:** `RuntimeError: You cannot use AsyncToSync in the same thread as an async event loop` if Celery workers use gevent/eventlet pool.

**Why it happens:** Gevent patches the event loop globally; `async_to_sync` creates a new event loop but finds one already running.

**How to avoid:** Confirm `CELERY_WORKER_POOL = "prefork"` (the default). The project's Docker CMD already uses the default. No action needed unless the pool is changed.

**Warning signs:** Error appears in Celery worker logs when `emit_progress_event` is called.

---

### Pitfall 3: SearchVectorField Stale After Bulk Insert

**What goes wrong:** `search_vector` is NOT auto-updated. After `bulk_create(..., update_conflicts=True)`, the field remains `NULL` for new rows and stale for updated rows.

**Why it happens:** Django's `SearchVectorField` requires explicit update; no automatic trigger exists unless configured via a PostgreSQL trigger.

**How to avoid:** After each page of reviews is persisted, run:
```python
from django.contrib.postgres.search import SearchVector
Review.objects.filter(shop=shop, search_vector__isnull=True).update(
    search_vector=SearchVector("comment", "reviewer_display_name", config="english")
)
```
This is one additional query per page but keeps the FTS index current. Add it to the sync service after each `bulk_create`.

**Warning signs:** Search returns no results for newly fetched reviews.

---

### Pitfall 4: Staff Scope Subquery Miscount

**What goes wrong:** The `get_accessible_shop_ids` subquery fires even for ORG_ADMIN requests, adding an extra query and busting the ≤5 budget.

**How to avoid:** Gate the subquery behind a role check in `get_queryset()`:
```python
if user.role == User.Role.STAFF_ADMIN:
    qs = qs.filter(shop_id__in=get_accessible_shop_ids(user_id=user.pk))
```
ORG_ADMIN requests skip this entirely.

---

### Pitfall 5: SyncProgressConsumer Staff Scope Not Tightened

**What goes wrong:** Phase 10 only checks org-level tenant scope. A Staff user could connect to a shop they don't have access to and receive progress events.

**How to avoid:** Phase 11 must tighten `_user_can_access_shop` to also check `StaffAccessScope` for `STAFF_ADMIN` role. The consumer docstring already notes this (`"Phase 11 will tighten to staff-scope"`).

---

### Pitfall 6: Reply Submitted Twice (Double-Post to Google)

**What goes wrong:** User clicks "Submit" twice quickly; two POST requests hit the reply endpoint; both succeed (Google allows overwriting an existing reply with the same text silently).

**How to avoid:** Use the Redis distributed lock `lock:reply:review:{review_id}` (30-second TTL, per CLAUDE.md §7.6) in the reply service. The second request exits immediately with a 429.

---

### Pitfall 7: `bulk_create` with `update_conflicts=True` and Missing `update_fields`

**What goes wrong:** Calling `bulk_create(..., update_conflicts=True)` without specifying `update_fields` defaults to updating ALL non-PK fields — this resets `enrichment_status` and `sentiment` even for reviews whose text/rating has not changed.

**How to avoid:** Only include fields that should change on conflict: `update_fields=["star_rating", "comment", "review_update_time", "reviewer_display_name", "reply_comment", "reply_update_time", "is_replied"]`. Handle `enrichment_status` reset separately (only when `star_rating` or `comment` actually changed — compare before/after in the service).

---

## Code Examples

### Celery Initial Backfill Task

```python
# apps/reviews/tasks.py
from celery import shared_task
from apps.reviews.services.sync import run_initial_backfill

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def initial_backfill_task(self, shop_id: int) -> None:  # type: ignore[misc]
    run_initial_backfill(shop_id=shop_id)

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def sync_shop_reviews_task(self, shop_id: int) -> None:  # type: ignore[misc]
    from apps.reviews.services.sync import run_incremental_sync
    run_incremental_sync(shop_id=shop_id)

@shared_task
def enqueue_incremental_syncs_task() -> None:
    """Fan-out: dispatches sync_shop_reviews_task for every connected shop with jitter."""
    import random
    from apps.shops.models import Shop
    connected = Shop.objects.filter(
        connection_status=Shop.ConnectionStatus.CONNECTED,
        is_active=True,
    ).values_list("id", flat=True)
    for shop_id in connected:
        jitter = random.uniform(0, 1800)  # up to 30 minutes
        sync_shop_reviews_task.apply_async(args=[shop_id], countdown=jitter)
```

### Reply Service (Synchronous Google Call)

```python
# apps/reviews/services/replies.py
from django.db import transaction
from django.utils import timezone
from apps.integrations.google.oauth import _refresh_access_token
from apps.integrations.google.reviews_client import post_reply
from apps.common.locks import distributed_lock
from apps.common.models import AuditLog
from apps.reviews.models import Review

@transaction.atomic
def submit_reply(*, review: Review, comment: str, actor) -> Review:
    """Post a reply to Google synchronously. Raises on failure (no local row created)."""
    lock_key = f"lock:reply:review:{review.pk}"
    with distributed_lock(lock_key, timeout=30) as acquired:
        if not acquired:
            raise ReplyConflictError("Another reply submission is in progress.")
        shop = review.shop
        access_token = _refresh_access_token(shop.google_refresh_token)
        reply_data = post_reply(
            access_token=access_token,
            account_id=shop.google_account_id,
            location_id=shop.google_location_id,
            review_id=review.google_review_id,
            comment=comment,
        )
        review.reply_comment = comment
        review.reply_update_time = timezone.now()
        review.is_replied = True
        review.save(update_fields=["reply_comment", "reply_update_time", "is_replied", "updated_at"])

        AuditLog.objects.create(
            organisation=shop.organisation,
            actor=actor,
            entity_type="review",
            entity_id=str(review.pk),
            action="reply_posted",
            after_data={"reply_text": comment, "google_response_status": 200},
        )
    return review
```

### Sincing Endpoint on ShopViewSet

```python
# apps/shops/views.py — new @action
@action(detail=False, methods=["get"], url_path="syncing")
def syncing(self, request: Request) -> Response:
    """Return shops currently in-progress sync (for topbar indicator)."""
    from django_redis import get_redis_connection
    user = request.user
    qs = list_shops(organisation_id=user.organisation_id, active_only=True)
    if user.role == User.Role.STAFF_ADMIN:
        from apps.reviews.selectors.reviews import get_accessible_shop_ids
        qs = qs.filter(id__in=get_accessible_shop_ids(user_id=user.pk))
    qs = qs.filter(connection_status=Shop.ConnectionStatus.CONNECTED)
    r = get_redis_connection("default")
    syncing_shops = []
    for shop in qs:
        if r.exists(f"sync:progress:{shop.pk}"):
            syncing_shops.append({"shop_id": shop.pk, "shop_name": shop.name})
    return Response({"count": len(syncing_shops), "shops": syncing_shops})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `update_or_create` per review | `bulk_create(..., update_conflicts=True)` | psycopg3 3.1+ | 10x fewer queries in sync |
| Separate FTS service (Elasticsearch) | `SearchVectorField` + `GinIndex` | Django 1.10+ | Zero extra infra for moderate scale |
| WebSocket from view (thread unsafe) | `async_to_sync(group_send)` from Celery | Channels 2+ / asgiref 3.2+ | Standard Channels bridge pattern |
| Offset pagination for large tables | `CursorPagination` on `review_create_time` | DRF 3.x | No slow-page N problem at scale |
| Per-field token refresh calls in service | Refresh once, pass token to all API calls in page | Always | Fewer 401s during long syncs |

**Deprecated/outdated:**
- `accounts.locations.reviews.list` in GBP API v3: Replaced by v4. Use v4 base URL `https://mybusiness.googleapis.com/v4/`.
- `django.contrib.postgres.search.SearchVector` on every query (on-the-fly): Replaced by `SearchVectorField` (persisted) for production-scale queries.

---

## Open Questions

1. **`google_account_id` and `google_location_id` on Shop model**
   - What we know: The GBP Reviews API requires the account and location IDs in the URL path. The current `Shop` model has `place_id` but not the GBP account/location resource names.
   - What's unclear: Phase 8 stored `place_id` (Google Maps Place ID). The GBP API v4 uses `accounts/{acct}/locations/{loc}` — these are different identifiers. The `list_business_locations` call in `oauth.py` returns location objects; the `name` field contains the full resource name `accounts/{acct}/locations/{loc}`.
   - Recommendation: During Phase 11, add `google_account_name` and `google_location_name` fields to the `Shop` model (storing the full resource name strings, e.g., `accounts/123/locations/456`). Populate them from the OAuth listing response during shop creation. The `review_id` extracted from the full review `name` field gives `google_review_id`.

2. **`SearchVectorField` update strategy at scale**
   - What we know: Updating `search_vector` per page in the sync service adds one extra query per 50 reviews.
   - What's unclear: At large scale (thousands of reviews in initial backfill), this adds significant wall time. A PostgreSQL trigger is faster but requires a custom migration with raw SQL.
   - Recommendation: Start with the per-page `update()` call in Phase 11 (simpler, testable). Document the trigger upgrade path in the migration for Phase 12 if performance degrades.

3. **`ScopedRateThrottle` configuration for `"review_reply"`**
   - What we know: CLAUDE.md §7.5 defines `"review_reply": "30/minute"` in `DEFAULT_THROTTLE_RATES`.
   - What's unclear: This rate key is not yet in `config/settings/base.py` (only `"user"` and `"anon"` and `"login"` are there).
   - Recommendation: Add `"review_reply": "30/minute"` to `DEFAULT_THROTTLE_RATES` in settings as part of this phase.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/reviews/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| SYNC-01 | Initial backfill dispatched after OAuth | unit | `pytest apps/reviews/tests/test_tasks.py::test_initial_backfill_dispatched -x` | Wave 0 |
| SYNC-02 | Incremental sync jitter fan-out | unit | `pytest apps/reviews/tests/test_tasks.py::test_enqueue_incremental_syncs_jitter -x` | Wave 0 |
| SYNC-03 | Per-shop Redis lock prevents concurrent sync | unit | `pytest apps/reviews/tests/test_sync_service.py::test_lock_prevents_concurrent_sync -x` | Wave 0 |
| SYNC-04 | Upsert: re-fetch updates, not duplicates | unit | `pytest apps/reviews/tests/test_sync_service.py::test_upsert_no_duplicates -x` | Wave 0 |
| SYNC-05 | Changed text/rating resets enrichment_status | unit | `pytest apps/reviews/tests/test_sync_service.py::test_changed_review_resets_enrichment -x` | Wave 0 |
| SYNC-06 | Deleted reviews soft-deleted | unit | `pytest apps/reviews/tests/test_sync_service.py::test_soft_delete_missing_reviews -x` | Wave 0 |
| SYNC-07 | 401 sets shop EXPIRED | unit | `pytest apps/reviews/tests/test_sync_service.py::test_401_sets_shop_expired -x` | Wave 0 |
| SYNC-08 | Retries on 403/5xx; AuditLog on failure | unit | `pytest apps/reviews/tests/test_sync_service.py::test_retry_and_audit_on_failure -x` | Wave 0 |
| SYNC-09 | Token bucket prevents burst | unit | `pytest apps/reviews/tests/test_sync_service.py::test_rate_bucket -x` | Wave 0 |
| SYNC-10 | AuditLog entries written | unit | `pytest apps/reviews/tests/test_sync_service.py::test_audit_log_entries -x` | Wave 0 |
| PROG-01 | Progress Modal shows on OAuth | integration (manual) | manual — Playwright test deferred | manual-only |
| PROG-08 | WebSocket receives 4 event types | integration | `pytest apps/reviews/tests/test_consumers.py::test_progress_event_types -x` | Wave 0 |
| PROG-09 | Reconnect sends Redis snapshot | integration | `pytest apps/reviews/tests/test_consumers.py::test_reconnect_sends_snapshot -x` | Wave 0 |
| PROG-10 | Redis TTLs set correctly | unit | `pytest apps/reviews/tests/test_sync_service.py::test_progress_ttls -x` | Wave 0 |
| REVW-01 | Reviews list accessible to ORG_ADMIN + STAFF_ADMIN | integration | `pytest apps/reviews/tests/test_views.py::test_reviews_list_accessible -x` | Wave 0 |
| REVW-02 | Filters apply additively | integration | `pytest apps/reviews/tests/test_views.py::test_filter_additive -x` | Wave 0 |
| REVW-10 | Reply POST → Google sync + local update | unit | `pytest apps/reviews/tests/test_reply_service.py::test_submit_reply_success -x` | Wave 0 |
| REVW-12 | Reply throttle 30/min | unit | `pytest apps/reviews/tests/test_views.py::test_reply_throttle -x` | Wave 0 |
| REVW-13 | AuditLog for reply events | unit | `pytest apps/reviews/tests/test_reply_service.py::test_audit_log_on_reply -x` | Wave 0 |
| REVW-14 | ≤5 SQL queries on list endpoint | query-count | `pytest apps/reviews/tests/test_views.py::test_reviews_list_query_count -x` | Wave 0 |
| SYNC-* consumer | Staff user cannot connect to non-scoped shop | WebSocket | `pytest apps/reviews/tests/test_consumers.py::test_staff_scope_rejection -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/reviews/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (files to create before implementation)
- [ ] `apps/reviews/tests/factories.py` — `ReviewFactory`, `AuditLogFactory`
- [ ] `apps/reviews/tests/test_models.py` — constraint tests
- [ ] `apps/reviews/tests/test_sync_service.py` — all SYNC-* tests
- [ ] `apps/reviews/tests/test_reply_service.py` — REVW-10, REVW-13
- [ ] `apps/reviews/tests/test_selectors.py` — selector tests
- [ ] `apps/reviews/tests/test_views.py` — REVW-* API tests including query count
- [ ] `apps/reviews/tests/test_tasks.py` — task dispatch tests
- [ ] Add `"review_reply": "30/minute"` to `DEFAULT_THROTTLE_RATES` in settings (needed for REVW-12 test)

---

## Sources

### Primary (HIGH confidence)
- Google Developers docs — `accounts.locations.reviews.list` and `accounts.locations.reviews` resource schema (fetched directly: endpoint URL, field names, `nextPageToken` pagination, max pageSize=50, `starRating` enum, `reviewer.*`, `reviewReply.*`)
- Google Developers docs — `review-data` guide (reply endpoint: PUT `.../reviews/{reviewId}/reply`, body: `{"comment": "..."}`)
- Django Channels docs — `channel_layers` topic (fetched: `async_to_sync(channel_layer.group_send)` as canonical sync-to-async pattern)
- DRF docs — `CursorPagination` (fetched: `ordering`, `page_size`, `cursor_query_param` attributes; limitation: requires stable unchanging field; no count in response)
- Django docs — `contrib.postgres.search` (fetched: `SearchVectorField`, `GinIndex`, `SearchQuery` usage)
- Codebase — `apps/reviews/consumers.py`, `apps/common/locks.py`, `apps/common/retry.py`, `apps/shops/views.py`, `apps/shops/selectors/shops.py`, `config/settings/base.py`, `config/routing.py`, `pyproject.toml`, `frontend/src/widgets/data-table/DataTable.tsx`, `frontend/src/widgets/modal/Modal.tsx`, `frontend/src/widgets/shop-management/ShopTable.tsx`, `frontend/vite.config.ts`

### Secondary (MEDIUM confidence)
- GitHub django/channels issues #1799, #1876, #1154 — confirm `async_to_sync` is safe with prefork; gevent/eventlet pools are the problematic case
- Multiple community sources confirming `bulk_create(update_conflicts=True)` is the psycopg3 upsert pattern

### Tertiary (LOW confidence)
- GBP API rate limits: Not documented in the official reference. Google provides per-location quotas via API Console; no hard number found. Use the Redis token bucket as defensive practice per CLAUDE.md §7.7.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; only `django-filter` is new
- Architecture: HIGH — GBP API schema verified from official docs; Channels pattern verified from official docs and codebase
- Pitfalls: HIGH — based on verified code patterns and documented Channels integration issues
- Google API rate limits: LOW — no official per-method quota documented; defensive bucket is the right mitigation

**Research date:** 2026-05-01
**Valid until:** 2026-07-01 (GBP API stable; DRF/Channels stable)
