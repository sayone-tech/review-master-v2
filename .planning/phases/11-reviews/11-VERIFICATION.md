---
phase: 11-reviews
verified: 2026-05-02T08:00:00Z
status: human_needed
score: 34/34 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 29/34
  gaps_closed:
    - "review.fetched AuditLog entry written per persisted page (SYNC-10)"
    - "token_bucket_depleted() gates the pagination loop before list_reviews (SYNC-09)"
    - "Tag chips scaffolding: ReviewTag type, tags JSONField, SentimentBadge chip rendering (REVW-07)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Reviews page renders and filters work end-to-end"
    expected: "Navigate to /admin/org/reviews/, see paginated review table, apply Store/Rating/Sentiment/Reply filters additively, observe correct results"
    why_human: "Visual rendering and filter interaction cannot be verified programmatically"

  - test: "ProgressModal auto-opens after OAuth shop creation"
    expected: "Create a new shop with Google OAuth; page redirects to /admin/org/shops/?open_progress={id}; ProgressModal opens and shows live progress bars"
    why_human: "End-to-end OAuth flow and modal auto-open requires browser + real OAuth callback"

  - test: "TopbarSyncIndicator badge and dropdown"
    expected: "During active sync, badge shows spinner+count; click opens dropdown listing shops; badge disappears when all syncs complete; turns red on permanent failure"
    why_human: "Real-time WebSocket interaction and visual badge state changes require browser"

  - test: "ReplyComposer inline accordion expand/collapse"
    expected: "Click Reply on an unreplied row inserts an inline <tr> composer; submitting posts to Google synchronously; on success composer replaces with Replied view; Discard closes composer"
    why_human: "Inline DOM accordion manipulation and actual reply posting requires browser"
---

# Phase 11: Reviews Module Verification Report

**Phase Goal:** Deliver the full Reviews module — fetch GBP reviews (initial backfill + incremental sync), display them in a paginated filterable table, allow inline reply posting, and surface sync progress in real time via WebSocket.
**Verified:** 2026-05-02
**Status:** human_needed
**Re-verification:** Yes — after gap closure plans 11-14 (SYNC-09, SYNC-10) and 11-15 (REVW-07)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Review model stores all GBP API fields including starRating, comment, reviewer, reply, enrichment_status | VERIFIED | `apps/reviews/models.py`: full field set, UniqueConstraint on (shop, google_review_id), GinIndex on search_vector |
| 2 | Review row unique per (shop_id, google_review_id); re-fetch updates not duplicates | VERIFIED | `UniqueConstraint(fields=["shop","google_review_id"])` + `bulk_create(update_conflicts=True)` in sync.py |
| 3 | Review can be soft-deleted via deleted_at | VERIFIED | `deleted_at = models.DateTimeField(null=True)` in Review model; `_soft_delete_absent()` in sync.py |
| 4 | AuditLog model with tenant-scoped organisation FK | VERIFIED | `apps/common/models.py`: AuditLog with organisation FK, entity_type, action, before/after_data |
| 5 | Shop carries google_account_name and google_location_name | VERIFIED | `apps/shops/models.py`: both fields present |
| 6 | list_reviews returns dict with reviews + nextPageToken | VERIFIED | `apps/integrations/google/reviews_client.py`: returns resp.json() |
| 7 | post_reply PUTs to GBP and returns parsed response | VERIFIED | `reviews_client.py` |
| 8 | 401 invalid_grant raises GoogleAuthError(reason='invalid_grant') | VERIFIED | `reviews_client.py` |
| 9 | 403 quota_exceeded raises GoogleQuotaError | VERIFIED | `reviews_client.py` |
| 10 | 5xx raises GoogleUnreachableError | VERIFIED | `reviews_client.py` |
| 11 | fetch_and_persist_reviews writes one batch per page using bulk_create + update_conflicts | VERIFIED | `sync.py` |
| 12 | When a review's text or rating changes, enrichment_status is reset to PENDING | VERIFIED | `sync.py` |
| 13 | Reviews absent from sync fetched ID set are soft-deleted | VERIFIED | `sync.py`: `_soft_delete_absent(shop=shop, fetched_ids=all_fetched_ids)` |
| 14 | On 401 invalid_grant, shop connection_status set to EXPIRED | VERIFIED | `sync.py` |
| 15 | Per-shop Redis lock prevents concurrent sync | VERIFIED | `sync.py`: `distributed_lock(lock_key, timeout=300)` |
| 16 | Token bucket (rate:google:project) is incremented per fetch | VERIFIED | `sync.py` line 292: `increment_google_token_bucket()` called after depletion check, before `list_reviews` |
| 17 | Token bucket depletion HOLDS new fetches | VERIFIED | `sync.py` line 284: `if token_bucket_depleted(): logger.warning(...); break` — depletion check is first statement in while-True loop, before increment and before `list_reviews`. `test_pagination_halts_when_bucket_depleted` asserts `list_mock.call_count == 0` when depleted. |
| 18 | Progress snapshot written to Redis at sync:progress:{shop_id} with correct TTLs | VERIFIED | `progress.py`: TTL_ACTIVE_SECONDS=86400, TTL_SUCCESS_SECONDS=3600, TTL_FAILED_SECONDS=604800 |
| 19 | AuditLog entries written for sync.started, sync.completed, sync.failed | VERIFIED | `sync.py` lines 235, 371, 407 |
| 20 | AuditLog entry written for review.fetched | VERIFIED | `sync.py` lines 307-318: `AuditLog.objects.create(entity_type="review", action="review.fetched", after_data={"page": page_count, "count": persisted, "trigger": trigger})` after every `_persist_page` call. `test_review_fetched_audit_logged` confirms 2 rows for a 2-page sync with correct page/count values. |
| 21 | Search vector populated after each bulk_create page | VERIFIED | `sync.py`: `Review.objects.filter(search_vector__isnull=True).update(search_vector=SearchVector(...))` |
| 22 | initial_backfill_task + sync_shop_reviews_task + enqueue_incremental_syncs_task on google-sync queue | VERIFIED | `tasks.py`: three tasks, `CELERY_TASK_ROUTES` in settings/base.py |
| 23 | Beat schedule seeded by data migration | VERIFIED | `0002_periodic_tasks_seed.py`: hourly crontab PeriodicTask seeded |
| 24 | SyncProgressConsumer rejects Staff users not in their StaffAccessScope | VERIFIED | `consumers.py`: SHOP and REGION scope checks |
| 25 | On connect, consumer sends current Redis snapshot immediately | VERIFIED | `consumers.py`: `get_progress_snapshot` called on connect |
| 26 | GET /api/v1/reviews/ returns paginated reviews scoped to caller's org | VERIFIED | `views.py` ReviewViewSet.get_queryset() + TenantScopedViewSet |
| 27 | Staff users only see reviews for shops in their StaffAccessScope | VERIFIED | `views.py`: role check + `get_accessible_shop_ids()` |
| 28 | All filters (shop, rating, sentiment, is_replied, from_date, to_date, search) apply additively | VERIFIED | `filters.py`: ReviewFilterSet with all 7 filters |
| 29 | List endpoint resolves in <=5 SQL queries (CaptureQueriesContext test) | VERIFIED | `test_views.py`: two CaptureQueriesContext tests asserting <=5 queries |
| 30 | POST /api/v1/reviews/{id}/reply/ posts to Google synchronously | VERIFIED | `views.py`: @action reply + `submit_reply()` service |
| 31 | On Google API failure, no local row mutation; API returns 502 | VERIFIED | `replies.py`: mutation only in SUCCESS path inside transaction.atomic(); failures raise ReplyFailedError mapped to 502 |
| 32 | Per-review distributed lock (lock:reply:review:{review_id}, 30s) | VERIFIED | `replies.py` |
| 33 | Reply throttle: 30/minute per user (ScopedRateThrottle) | VERIFIED | `views.py`: `throttle_classes=[ScopedRateThrottle]`; `settings/base.py`: `"review_reply": "30/minute"` |
| 34 | Tag chips shown on enriched reviews per REVW-07 | VERIFIED | `apps/reviews/models.py` line 70: `tags = models.JSONField(default=list, blank=True)`. `apps/reviews/migrations/0003_review_tags.py`: AddField operation. `apps/reviews/serializers.py` line 38: `"tags"` in fields list. `frontend/src/widgets/review-management/types.ts`: `ReviewTag` interface, `tags: ReviewTag[]` on `ReviewRow`. `frontend/src/widgets/review-management/SentimentBadge.tsx`: `TAG_STYLES`, `MAX_TAGS=5`, `tags.slice(0, MAX_TAGS)` with chip rendering. `frontend/src/widgets/review-management/ReviewTable.tsx` line 91: `tags={r.tags}` passed to SentimentBadge. Phase 11 delivers rendering; Phase 12 ENRCH-14 populates data. With tags=[], SentimentBadge renders only the sentiment pill — no visual regression. |

**Score:** 34/34 truths verified

---

### Previously-Failed Gaps: Re-verification

#### Gap 1 (SYNC-10): review.fetched audit log — CLOSED

`apps/reviews/services/sync.py` lines 307-318: `AuditLog.objects.create` with `entity_type="review"`, `action="review.fetched"`, `entity_id=str(shop.pk)`, `after_data={"page": page_count, "count": persisted, "trigger": trigger}` is placed immediately after the `page_count += 1` increment in every iteration of the pagination loop. The test `test_review_fetched_audit_logged` in `apps/reviews/tests/test_sync_service.py` (lines 218-245) asserts exactly 2 rows for a 2-page backfill with pages=[1,2] and counts=[2,1].

#### Gap 2 (SYNC-09): token bucket depletion gating — CLOSED

`apps/reviews/services/sync.py` imports `token_bucket_depleted` at line 45 alongside `increment_google_token_bucket`. Inside `fetch_and_persist_reviews`, the while-True loop's first statement (line 284) is `if token_bucket_depleted(): logger.warning(...); break`. The increment (line 292) and `list_reviews` call (line 293) only execute when the bucket is not depleted. The test `test_pagination_halts_when_bucket_depleted` (lines 248-272) patches `token_bucket_depleted` to return True and asserts `list_mock.call_count == 0` and zero `review.fetched` rows, while `sync.started` is still recorded.

#### Gap 3 (REVW-07): tag chip rendering scaffolding — CLOSED

All six artifacts required by plan 11-15 are present and wired:
- `apps/reviews/models.py`: `tags = models.JSONField(default=list, blank=True)` (line 70)
- `apps/reviews/migrations/0003_review_tags.py`: valid `AddField` migration, dependency on `0002_periodic_tasks_seed`, cross-DB safe (JSONField not ArrayField)
- `apps/reviews/serializers.py`: `"tags"` in `ReviewReadSerializer.Meta.fields` list (line 38)
- `frontend/src/widgets/review-management/types.ts`: `TagPolarity`, `ReviewTag` interface, `tags: ReviewTag[]` on `ReviewRow`
- `frontend/src/widgets/review-management/SentimentBadge.tsx`: imports `ReviewTag, TagPolarity`, `TAG_STYLES` dict, `MAX_TAGS=5`, `tags?.ReviewTag[]` prop with default `[]`, `tags.slice(0, MAX_TAGS)` chip rendering when `enrichment_status === "SUCCESS"`
- `frontend/src/widgets/review-management/ReviewTable.tsx`: `tags={r.tags}` passed to SentimentBadge (line 91)
- `.planning/REQUIREMENTS.md`: REVW-07 note reads "rendering scaffolding delivered in Phase 11 plan 11-15; tag DATA arrives in Phase 12 ENRCH-14"; traceability row updated to "Phase 11 + Phase 12 | Complete (rendering); data via ENRCH-14"

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/reviews/models.py` | VERIFIED | Review model with all GBP fields, UniqueConstraint, SearchVectorField, GinIndex, plus `tags = models.JSONField(default=list, blank=True)` |
| `apps/reviews/managers.py` | VERIFIED | ReviewQuerySet with active(), for_organisation(), for_shops(), replied() |
| `apps/common/models.py` | VERIFIED | AuditLog model with organisation FK |
| `apps/shops/models.py` | VERIFIED | google_account_name, google_location_name present |
| `apps/reviews/tests/factories.py` | VERIFIED | ReviewFactory present |
| `apps/reviews/tests/test_models.py` | VERIFIED | UniqueConstraint test present |
| `apps/integrations/google/reviews_client.py` | VERIFIED | list_reviews + post_reply |
| `apps/integrations/google/exceptions.py` | VERIFIED | GoogleQuotaError + GoogleReplyError |
| `apps/integrations/google/tests/test_reviews_client.py` | VERIFIED | HTTP mock tests for both functions |
| `apps/reviews/services/sync.py` | VERIFIED | token_bucket_depleted gate + review.fetched AuditLog in pagination loop |
| `apps/reviews/services/progress.py` | VERIFIED | write_progress_snapshot, read_progress_snapshot, clear_progress_snapshot, token_bucket helpers |
| `apps/reviews/tasks.py` | VERIFIED | initial_backfill_task, sync_shop_reviews_task, enqueue_incremental_syncs_task |
| `apps/reviews/migrations/0002_periodic_tasks_seed.py` | VERIFIED | RunPython seeds PeriodicTask |
| `apps/reviews/migrations/0003_review_tags.py` | VERIFIED | AddField tags JSONField, default=list, dependency on 0002 |
| `apps/reviews/consumers.py` | VERIFIED | SyncProgressConsumer with _user_can_access_shop |
| `apps/reviews/selectors/sync_progress.py` | VERIFIED | get_progress_snapshot with sync_to_async |
| `apps/reviews/filters.py` | VERIFIED | ReviewFilterSet with 7 filters |
| `apps/reviews/serializers.py` | VERIFIED | ReviewReadSerializer with "tags" in fields; ReviewReplySerializer |
| `apps/reviews/selectors/reviews.py` | VERIFIED | list_reviews + get_accessible_shop_ids + base_reviews_queryset |
| `apps/reviews/views.py` | VERIFIED | ReviewViewSet (list + retrieve + reply action) + review_list template view |
| `apps/reviews/urls.py` | VERIFIED | path("admin/org/reviews/", review_list) |
| `config/urls.py` | VERIFIED | router.register("api/v1/reviews", ReviewViewSet) |
| `apps/reviews/services/replies.py` | VERIFIED | submit_reply |
| `apps/reviews/exceptions.py` | VERIFIED | ReplyConflictError + ReplyFailedError |
| `apps/shops/views.py` | VERIFIED | syncing @action, initial_backfill_task dispatch on create/reconnect, open_progress_shop_id |
| `apps/shops/services/shops.py` | VERIFIED | google_account_name + google_location_name populated |
| `frontend/src/widgets/shop-management/CreateShopModal.tsx` | VERIFIED | Redirects to /admin/org/shops/?open_progress={id} on create success |
| `templates/reviews/review_list.html` | VERIFIED | mounts review-management-root, shops_json island, has_connected_shops island |
| `frontend/src/widgets/review-management/types.ts` | VERIFIED | ReviewRow, ReviewTag, TagPolarity, ReviewFilterParams, ReviewListResponse, ShopOption |
| `frontend/src/widgets/review-management/api.ts` | VERIFIED | listReviews, submitReply, fetchSyncingShops |
| `frontend/src/widgets/review-management/useReviews.ts` | VERIFIED | useReviews hook with all filter/sort/pagination controls + 300ms search debounce |
| `frontend/src/entrypoints/review-management.tsx` | VERIFIED | createRoot mounting ReviewManagementWidget |
| `frontend/vite.config.ts` | VERIFIED | review-management and topbar-sync-indicator entrypoints registered |
| `frontend/src/widgets/review-management/StarRating.tsx` | VERIFIED | export function StarRating |
| `frontend/src/widgets/review-management/SentimentBadge.tsx` | VERIFIED | Sentiment badge + Analyzing + failed icon + TAG_STYLES + chip rendering when tags.length > 0 |
| `frontend/src/widgets/review-management/ReplyStatusBadge.tsx` | VERIFIED | export function ReplyStatusBadge |
| `frontend/src/widgets/review-management/ReviewFilters.tsx` | VERIFIED | export function ReviewFilters |
| `frontend/src/widgets/review-management/ReviewEmptyStates.tsx` | VERIFIED | EmptyStateA, EmptyStateB, EmptyStateC |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | VERIFIED | DataTable wired + renderExpanded prop + ReplyComposer + tags={r.tags} prop on SentimentBadge |
| `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` | VERIFIED | Full widget assembly, useReviews, showFullComment tracking |
| `frontend/src/widgets/data-table/DataTable.tsx` | VERIFIED | renderExpanded prop added |
| `frontend/src/widgets/review-management/ReplyComposer.tsx` | VERIFIED | inline accordion, submitReply, char counter, error banner, Discard/Submit |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | VERIFIED | WebSocket, two progress bars, ETA, error state, complete state, Run in background |
| `frontend/src/widgets/shop-management/ShopTable.tsx` | VERIFIED | mounts ProgressModal when open_progress URL param present |
| `frontend/src/entrypoints/shop-management.tsx` | VERIFIED | reads open_progress query param, passes to ShopTableWidget |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | VERIFIED | fetchSyncingShops, per-shop WS, badge, dropdown, failure state |
| `frontend/src/entrypoints/topbar-sync-indicator.tsx` | VERIFIED | createRoot mounting TopbarSyncIndicator |
| `templates/partials/topbar.html` | VERIFIED | sync-indicator-root mount point + vite_asset script |
| `apps/reviews/tests/test_sync_service.py` | VERIFIED | includes test_review_fetched_audit_logged and test_pagination_halts_when_bucket_depleted |

---

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `apps/reviews/models.py` | `apps/shops/models.py` | ForeignKey("shops.Shop") | VERIFIED |
| `apps/reviews/models.py` | `apps/organisations/models.py` | ForeignKey("organisations.Organisation") | VERIFIED |
| `apps/common/models.py` | `apps/organisations/models.py` | AuditLog.organisation FK | VERIFIED |
| `apps/reviews/services/sync.py` | `apps/integrations/google/reviews_client.py` | list_reviews() call | VERIFIED |
| `apps/reviews/services/sync.py` | `apps/common/locks.py` | distributed_lock() | VERIFIED |
| `apps/reviews/services/sync.py` | `apps/reviews/services/progress.py` | write_progress_snapshot() + token_bucket_depleted() | VERIFIED |
| `apps/reviews/services/sync.py` | `apps/common/models.AuditLog` | AuditLog.objects.create for sync.started/completed/failed/review.fetched | VERIFIED |
| `apps/reviews/services/sync.py` | `apps/reviews/models.Review.search_vector` | search_vector__isnull update | VERIFIED |
| `apps/reviews/services/sync.py` | token bucket depletion guard | token_bucket_depleted() is first statement in while-True loop before list_reviews | VERIFIED |
| `apps/reviews/tasks.py` | `apps/reviews/services/sync.py` | run_initial_backfill / run_incremental_sync | VERIFIED |
| `apps/reviews/tasks.py` | `django_celery_beat.models.PeriodicTask` | data migration | VERIFIED |
| `apps/reviews/consumers.py` | `apps/accounts.models.StaffAccessScope` | SHOP + REGION scope checks | VERIFIED |
| `apps/reviews/selectors/sync_progress.py` | `apps/reviews/services/progress.read_progress_snapshot` | sync_to_async wrapper | VERIFIED |
| `apps/reviews/views.py` | `apps/common/viewsets.TenantScopedViewSet` | class ReviewViewSet(...TenantScopedViewSet) | VERIFIED |
| `apps/reviews/views.py` | `apps/reviews/selectors/reviews.py` | list_reviews + get_accessible_shop_ids | VERIFIED |
| `apps/reviews/views.py` | `apps/reviews/filters.ReviewFilterSet` | filterset_class = ReviewFilterSet | VERIFIED |
| `config/urls.py` | `apps/reviews/views.ReviewViewSet` | router.register("api/v1/reviews", ...) | VERIFIED |
| `apps/reviews/services/replies.py` | `apps/integrations/google/reviews_client.post_reply` | post_reply() call | VERIFIED |
| `apps/reviews/services/replies.py` | `apps/common/locks.distributed_lock` | distributed_lock("lock:reply:review:{id}", 30) | VERIFIED |
| `apps/reviews/services/replies.py` | `apps/common/models.AuditLog` | reply_posted + reply_failed | VERIFIED |
| `apps/reviews/views.py` | `apps/reviews/services/replies.submit_reply` | submit_reply(review, comment, actor) | VERIFIED |
| `apps/shops/views.py` | `apps/reviews.tasks.initial_backfill_task` | initial_backfill_task.delay(shop_id=shop.pk) | VERIFIED |
| `apps/shops/views.py` | `apps/reviews.selectors.reviews.get_accessible_shop_ids` | Staff filter in syncing endpoint | VERIFIED |
| `apps/shops/views.py` | Redis sync:progress:{shop_id} keys | r.exists(f"sync:progress:{shop.pk}") | VERIFIED |
| `frontend/src/widgets/shop-management/CreateShopModal.tsx` | `/admin/org/shops/?open_progress={id}` | window.location.href redirect on create success | VERIFIED |
| `templates/reviews/review_list.html` | `frontend/src/entrypoints/review-management.tsx` | vite_asset 'src/entrypoints/review-management.tsx' | VERIFIED |
| `frontend/src/widgets/review-management/api.ts` | `/api/v1/reviews/` | fetch with credentials + CSRF | VERIFIED |
| `frontend/src/widgets/review-management/useReviews.ts` | `api.listReviews` | useEffect + refresh on filter change | VERIFIED |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | `frontend/src/widgets/data-table/DataTable.tsx` | DataTable import | VERIFIED |
| `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` | `useReviews.ts` | const {...} = useReviews() | VERIFIED |
| `frontend/src/widgets/review-management/ReplyComposer.tsx` | `api.submitReply` | submitReply(row.id, comment) | VERIFIED |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | renderExpanded prop | renderExpanded callback wired | VERIFIED |
| `frontend/src/widgets/review-management/ReviewTable.tsx` | `SentimentBadge` with `tags={r.tags}` | tags prop propagated from ReviewRow | VERIFIED |
| `frontend/src/widgets/review-management/ProgressModal.tsx` | WebSocket `/ws/sync-progress/{shop_id}/` | new WebSocket(buildWsUrl(shopId)) | VERIFIED |
| `frontend/src/widgets/shop-management/ShopTable.tsx` | `ProgressModal` | ProgressModal rendered when open_progress present | VERIFIED |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | `/api/v1/shops/syncing/` | fetchSyncingShops() | VERIFIED |
| `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` | WebSocket `/ws/sync-progress/{shop_id}/` | per-shop ws connection | VERIFIED |
| `templates/partials/topbar.html` | `topbar-sync-indicator.tsx` | vite_asset directive | VERIFIED |

---

### Requirements Coverage

| Requirement | Plan(s) | Description | Status | Notes |
|-------------|---------|-------------|--------|-------|
| SYNC-01 | 04, 08 | Initial backfill dispatched after OAuth | SATISFIED | initial_backfill_task.delay() in ShopViewSet.perform_create |
| SYNC-02 | 04 | Incremental sync every 6h with 30-min jitter | SATISFIED | enqueue_incremental_syncs_task with random jitter up to 1800s |
| SYNC-03 | 03 | Per-shop Redis lock, 5-min TTL | SATISFIED | distributed_lock("lock:google_sync:shop:{id}", timeout=300) |
| SYNC-04 | 01, 03 | Unique per (shop_id, google_review_id); upsert | SATISFIED | UniqueConstraint + bulk_create(update_conflicts=True) |
| SYNC-05 | 03 | Changed review text/rating resets enrichment_status | SATISFIED | changed_ids detection + `.update(enrichment_status=PENDING)` |
| SYNC-06 | 03 | Soft-delete absent reviews | SATISFIED | _soft_delete_absent() sets deleted_at |
| SYNC-07 | 02, 03 | 401 invalid_grant sets shop EXPIRED | SATISFIED | sync.py + reviews_client.py |
| SYNC-08 | 02, 04 | Retry with backoff, failure to AuditLog | SATISFIED | autoretry_for + AuditLog sync.failed |
| SYNC-09 | 03, 14 | Token bucket holds new fetches when near depletion | SATISFIED | token_bucket_depleted() is first statement in while-True before list_reviews; loop breaks with logger.warning on depletion; test_pagination_halts_when_bucket_depleted verifies list_reviews never called |
| SYNC-10 | 01, 03, 14 | AuditLog for sync.started, sync.completed, sync.failed, review.fetched | SATISFIED | All four actions present: sync.started (line 235), sync.completed (line 371), sync.failed (lines 265, 407), review.fetched (lines 307-318 in pagination loop); test_review_fetched_audit_logged verifies per-page audit rows |
| PROG-01 | 08, 12 | Progress Modal opens after OAuth | SATISFIED | open_progress_shop_id response → redirect → ShopTable opens ProgressModal |
| PROG-02 | 12 | ETA displayed once >= 2 pages fetched | SATISFIED | computeEtaMinutes() checks page_count >= 2 |
| PROG-03 | 12, 13 | "Run in background" closes modal; topbar indicator appears | SATISFIED | ProgressModal "Run in background" button + TopbarSyncIndicator |
| PROG-04 | 12 | "View shop details" disabled until complete/error | SATISFIED | disabled={!isComplete && !isError} |
| PROG-05 | 12 | Error state message with reconnect CTA | SATISFIED | error state in ProgressModal with "Reconnect Google" button |
| PROG-06 | 08, 13 | Topbar badge with count + "N shops syncing" tooltip | SATISFIED | TopbarSyncIndicator with aria-label + title |
| PROG-07 | 13 | Topbar turns red on permanent failure; "View error" link | SATISFIED | hasFailures branch: red bg, AlertTriangle, "View error" link |
| PROG-08 | 05, 12, 13 | WS client connects to /ws/sync-progress/?shop_id={id} | SATISFIED (with note) | URL uses path param /ws/sync-progress/{shop_id}/ not query param; implementation consistent with CLAUDE.md §13.3 |
| PROG-09 | 05 | On reconnect, consumer sends Redis snapshot immediately | SATISFIED | consumers.py: get_progress_snapshot called on connect |
| PROG-10 | 03 | sync:progress:{shop_id} with 24h/1h/7d TTLs | SATISFIED | progress.py TTL constants correct |
| REVW-01 | 06 | Reviews list at /admin/org/reviews/ | SATISFIED | review_list view + url |
| REVW-02 | 06, 10 | Filter bar with 7 filters; FTS on search_vector | SATISFIED | ReviewFilterSet + SearchQuery |
| REVW-03 | 06, 10 | "Showing X of Y reviews" live count; search debounced 300ms | SATISFIED | total_count in API response; 300ms setTimeout in useReviews |
| REVW-04 | 06, 10 | Sort selector: newest/oldest/highest/lowest | SATISFIED | ordering_fields + SortKey type |
| REVW-05 | 06, 10 | Pagination 10/25/50/100; prev/next | SATISFIED | CursorPagination + page_size_query_param + goNext/goPrev in widget |
| REVW-06 | 10, 11 | "Show more" toggle for comments > 1000 chars | SATISFIED | showFullComment Map in ReviewManagementWidget + ReplyComposer |
| REVW-07 | 10, 15 | Sentiment badge + tag chips + Analyzing pill + failed icon | SATISFIED | Rendering scaffolding complete: Review.tags JSONField, migration 0003, serializer field, ReviewTag type, ReviewRow.tags, SentimentBadge chip rendering, ReviewTable tags={r.tags} prop. With tags=[] (Phase 11 state) only sentiment pill renders — no visual regression. Tag data arrives in Phase 12 ENRCH-14. REQUIREMENTS.md traceability updated. |
| REVW-08 | — | Action item chips | PENDING | Explicitly deferred to Phase 13 in REQUIREMENTS.md |
| REVW-09 | 07, 11 | Reply section: replied view / inline composer with 4000-char counter | SATISFIED | ReplyComposer with char counter |
| REVW-10 | 07, 11 | Reply posts to Google sync; success replaces composer; failure shows error | SATISFIED | submit_reply + ReplyComposer error handling |
| REVW-11 | 10 | Three empty states | SATISFIED | EmptyStateA/B/C in ReviewEmptyStates |
| REVW-12 | 07 | Reply throttle 30/minute | SATISFIED | ScopedRateThrottle + "review_reply": "30/minute" |
| REVW-13 | 07 | AuditLog for review.replied and review.reply_failed | SATISFIED | replies.py: reply_posted + reply_failed |
| REVW-14 | 06 | <=5 SQL queries for list endpoint | SATISFIED | CaptureQueriesContext tests assert <=5 queries |

**Orphaned Phase 11 Requirements:**
- REVW-08: Explicitly marked Pending in REQUIREMENTS.md. Deferred to Phase 13 (ActionItems). Expected.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/widgets/review-management/ProgressModal.tsx` | 282 | "Will be processed after sync completes" | Info | Expected placeholder — AI enrichment progress is Phase 12. Not a blocker. |

No new anti-patterns introduced by 11-14 or 11-15. No TODO/FIXME/HACK comments in the changed files.

---

### Human Verification Required

#### 1. Reviews page renders and filters work end-to-end

**Test:** Navigate to `/admin/org/reviews/`, observe paginated review table, apply Store/Rating/Sentiment/Reply filters additively, observe correct filtered results.
**Expected:** Table renders with all filter controls; each filter narrows results correctly; "Showing X of Y reviews" updates.
**Why human:** Visual rendering and interactive filter behavior cannot be verified programmatically.

#### 2. ProgressModal auto-opens after OAuth shop creation

**Test:** Create a new shop with Google OAuth; confirm page redirects to `/admin/org/shops/?open_progress={id}`; confirm ProgressModal opens and shows live fetch progress bars.
**Expected:** Modal auto-opens with two progress bars (Fetching/Enriching); ETA appears after first two pages.
**Why human:** End-to-end OAuth flow and modal auto-open requires a browser and a real OAuth callback.

#### 3. TopbarSyncIndicator badge and dropdown

**Test:** During an active sync, confirm badge shows spinner + shop count; click opens dropdown listing syncing shops; badge disappears when all syncs complete; badge turns red on permanent failure with "View error" link.
**Expected:** Real-time badge updates as WebSocket events arrive; dropdown state is correct.
**Why human:** Real-time WebSocket interaction and visual state changes require a browser.

#### 4. ReplyComposer inline accordion expand/collapse

**Test:** On an unreplied review row, click Reply; confirm an inline `<tr>` composer appears; type a reply; submit; confirm Google accept results in "Replied" status replacing the composer; confirm Discard closes the composer.
**Expected:** Inline DOM accordion works; reply posts to Google synchronously; success/failure states render correctly.
**Why human:** Inline DOM manipulation and actual reply posting require a browser and a connected Google account.

---

### Summary

All 34 observable truths are now verified. The three gaps identified in initial verification are confirmed closed:

1. **SYNC-10 closed:** `review.fetched` AuditLog rows written per-page inside the pagination loop with `{page, count, trigger}` payload. Two new tests verify the behavior and cover regressions.

2. **SYNC-09 closed:** `token_bucket_depleted()` is the first statement in the while-True pagination loop, before both `increment_google_token_bucket()` and `list_reviews()`. When depleted, the loop breaks with a `logger.warning` so the next Beat tick retries cleanly without over-counting the token bucket. Test verifies zero `list_reviews` calls when depleted.

3. **REVW-07 closed:** Full rendering scaffolding delivered — `tags` JSONField on Review model (migration 0003), serializer field, TypeScript `ReviewTag` interface, `tags: ReviewTag[]` on `ReviewRow`, `SentimentBadge` chip rendering with polarity-aware `TAG_STYLES` and `MAX_TAGS=5`. Backwards-compatible: empty `tags=[]` renders only the sentiment pill. Phase 12 ENRCH-14 will populate the tag data. `REQUIREMENTS.md` traceability updated to reflect the Phase 11/12 split.

Automated checks are complete. Four human verification items remain covering visual rendering, OAuth flow, real-time WebSocket behavior, and reply posting — none of these are regressions introduced by the gap-closure plans.

---

_Verified: 2026-05-02_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — gaps closed by plans 11-14 and 11-15_
