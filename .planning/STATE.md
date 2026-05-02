---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: — Superadmin Module
status: unknown
stopped_at: Completed 11-10-PLAN.md (Reviews list UI)
last_updated: "2026-05-02T05:39:27.575Z"
progress:
  total_phases: 11
  completed_phases: 8
  total_plans: 59
  completed_plans: 55
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-01)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** Phase 11 — reviews

## Current Position

Phase: 11 (reviews) — EXECUTING
Plan: 9 of 13

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: 9.5 minutes
- Total execution time: 0.96 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 6. Org Admin Shell | 4/5 | 35m | 8.75m |
| 7. Regions | 0/3 | - | - |
| 8. Shops | 1/5 | 12m | 12m |
| 9. Team | 0/5 | - | - |

**Recent Trend:**

- Last 5 plans: 06-01 (9m), 06-02 (6m), 06-03 (15m), 06-04 (5m)
- Trend: stable

*Updated after each plan completion*
| Phase 10 P01 | 7 | 3 tasks | 11 files |
| Phase 10 P03 | 35 | 3 tasks | 20 files |
| Phase 11 P01 | 15 | 2 tasks | 14 files |
| Phase 11 P02 | 10 | 2 tasks | 3 files |
| Phase 11 P03 | 8 | 2 tasks | 5 files |
| Phase 11 P06 | 8 | 2 tasks | 8 files |
| Phase 11 P04 | 12 | 2 tasks | 3 files |
| Phase 11 P05 | 10 | 2 tasks | 3 files |
| Phase 11 P07 | 7 | 2 tasks | 5 files |
| Phase 11 P09 | 2 | 2 tasks | 7 files |
| Phase 11 P08 | 6 | 2 tasks | 10 files |
| Phase 11 P13 | 95 | 2 tasks | 4 files |
| Phase 11 P12 | 2 | 2 tasks | 3 files |
| Phase 11 P10 | 30 | 2 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v0.3 roadmap: Celery tasks are thin wrappers over service functions; three-layer idempotency for all background work
- v0.3 roadmap: Channels surface kept narrow — only SyncProgressConsumer in Phase 11
- v0.3 roadmap: Cost calculation locked at log time using time-versioned AiPricing; historical costs never retroactively changed
- v0.3 roadmap: OpenAI idempotency — enrich_review exits if enrichment_status is already SUCCESS or IN_PROGRESS
- v0.3 roadmap: LangSmith is best-effort; if unreachable, OpenAI call still proceeds
- v0.3 roadmap: Single Celery Beat instance; Flower never in production
- [Phase 09-05]: ConfirmModal uses open= prop (not isOpen=)
- [Phase 09-05]: Enable flow is inline in TeamModals; no confirmation modal
- [Phase 10]: @shared_task(bind=True) uses type: ignore[misc] + Any for self — mypy strict mode has no stubs for celery decorators
- [Phase 10]: celery + django-celery-beat added to pre-commit mypy additional_dependencies so isolated hook env can load Django settings
- [Phase 10]: Shop uses integer PK — WebSocket routing uses <int:shop_id>, not <uuid:shop_id> as plan specified
- [Phase 10]: channels stubs typed as Any — AsyncJsonWebsocketConsumer subclass and database_sync_to_async get type: ignore[misc] consistent with celery decorator pattern
- [Phase 11-01]: Integer PK kept on Review — consistent with Shop/Organisation models (no UUID needed)
- [Phase 11-01]: AuditLog uses string entity_type/entity_id (not GenericForeignKey) — avoids content-type overhead, works for external IDs
- [Phase 11-01]: SearchVectorField added in migration but populated in Plan 11-07 — GIN index exists, data is null until sync runs
- [Phase 11-01]: django.contrib.postgres + psycopg[binary] added to pre-commit mypy additional_dependencies for SearchVectorField import
- [Phase 11-01]: pyproject.toml dependencies sorted alphabetically to prevent duplicate entries
- [Phase 11-02]: httpx.MockTransport used for reviews_client tests — avoids respx dependency, MockTransport built into httpx
- [Phase 11-02]: list_reviews maps other 4xx (not 401/403) to GoogleUnreachableError so Celery autoretry_for covers transient failures
- [Phase 11-03]: SearchVector update guarded by connection.vendor check to prevent SQLite test failures; test verifies code path via QuerySet.update interception
- [Phase 11-06]: CursorPagination chosen over PageNumberPagination — reviews table grows large with incremental sync, cursor provides O(1) performance
- [Phase 11-06]: total_count computed via qs.values("pk").count() before paginate_queryset — includes filter effects in count
- [Phase 11-06]: get_accessible_shop_ids returns Python list (not subquery) — predictable 1 query, keeps main queryset independent
- [Phase 11-04]: enqueue_incremental_syncs_task uses random.uniform (# noqa: S311) — scheduling jitter, not cryptographic randomness
- [Phase 11-04]: Beat seed migration depends on django_celery_beat 0019_alter_periodictasks_options as the latest migration at time of writing
- [Phase 11-05]: StaffAccessScope REGION check guards shop.region_id for None to avoid unnecessary queries when shop has no region
- [Phase 11-05]: get_progress_snapshot catches NotImplementedError (locmem cache in tests) to keep existing Phase 10 tests green without requiring Redis in CI
- [Phase 11-05]: test_no_snapshot_sent_when_redis_empty avoids disconnect() after timeout to prevent CancelledError — uses boolean flag pattern instead
- [Phase 11-07]: Lock TTL = 30s for reply submission — fast synchronous call; prevents double-post without holding lock longer than needed
- [Phase 11-07]: HTTP status: ReplyConflictError -> 409, ReplyFailedError -> 502 — 409 signals concurrent request conflict; 502 signals upstream Google failure
- [Phase 11-09]: Template uses base_org.html + extra_js block pattern (matching shop_list.html) — not base.html with shell includes
- [Phase 11-09]: ReviewManagementWidget stub added so Plan 09 builds independently; Plan 10 replaces it
- [Phase 11-09]: useReviews always fetches on mount with DEFAULT_PARAMS (no SSR seeding) — reviews table too dynamic for server-side pre-population
- [Phase 11-08]: syncing endpoint uses IsOrgScoped — Staff Admins need sync progress visibility for their shops
- [Phase 11-08]: Task dispatch wrapped in try/except in perform_create — failure logs warning but does not block shop creation
- [Phase 11-08]: Frontend redirect uses window.location.href — Plan 12 mounts fresh and reads ?open_progress= from URL on init
- [Phase 11]: Alpine.js dropdown replaced by React open= state in TopbarSyncIndicator — simpler, avoids mixing two reactive systems in one React root
- [Phase 11-12]: ProgressModal mounts inside ShopTableWidget — consistent with how ShopModals manages other modals in the same widget tree
- [Phase 11-12]: URL param ?open_progress= cleared via history.replaceState immediately after modal opens — prevents re-open on refresh
- [Phase 11-12]: ETA calculation guards page_count >= 2 — first page has no elapsed time ratio to extrapolate from
- [Phase 11-10]: ReviewEmptyStates exports individual named functions + namespace object — supports both import { EmptyStateA } and ReviewEmptyStates.EmptyStateA usage patterns
- [Phase 11-10]: shops_data typed as list[Any] in view to avoid strict mypy conflict with QuerySet.values() TypedDict return type
- [Phase 11-10]: user.pk None guard replaces type: ignore[assignment] — pre-commit mypy strict mode rejects unused ignore comments
- [Phase 11-10]: review:open-composer CustomEvent dispatched from ReviewManagementWidget — Plan 11 reply composer listens via window event

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8: GBP API production approval from Google is a non-code prerequisite for production launch (code can be built and tested against sandbox first).

## Session Continuity

Last session: 2026-05-02T05:39:27.573Z
Stopped at: Completed 11-10-PLAN.md (Reviews list UI)
Resume file: None
