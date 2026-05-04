---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: — Superadmin Module
status: unknown
stopped_at: Completed 13-05-PLAN.md
last_updated: "2026-05-04T05:18:26.002Z"
progress:
  total_phases: 13
  completed_phases: 10
  total_plans: 78
  completed_plans: 72
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-02)

**Core value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.
**Current focus:** Phase 13 — action-items-and-notifications

## Current Position

Phase: 13 (action-items-and-notifications) — EXECUTING
Plan: 6 of 8

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
| Phase 11 P11 | 2 | 2 tasks | 4 files |
| Phase 11-reviews P14 | 3 | 2 tasks | 2 files |
| Phase 11 P15 | 149 | 2 tasks | 7 files |
| Phase 12 P01 | 5 | 2 tasks | 9 files |
| Phase 12 P07 | 2 | 2 tasks | 2 files |
| Phase 12 P08 | 2 | 2 tasks | 2 files |
| Phase 12 P03 | 4 | 2 tasks | 5 files |
| Phase 12 P04 | 5 | 2 tasks | 4 files |
| Phase 12 P05 | 2 | 1 tasks | 4 files |
| Phase 12 P06 | 7 | 3 tasks | 6 files |
| Phase 12-ai-enrichment-pipeline P09 | 2 | 3 tasks | 2 files |
| Phase 13 P01 | 8 | 2 tasks | 8 files |
| Phase 13 P02 | 8 | 1 tasks | 7 files |
| Phase 13 P03 | 4 min | 2 tasks | 7 files |
| Phase 13-action-items-and-notifications P04 | 8min | 2 tasks | 7 files |
| Phase 13-action-items-and-notifications P05 | 12min | 2 tasks | 11 files |

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
- [Phase 11-11]: DataTable extended with optional renderExpanded prop (backward-compatible) — ShopTable and TeamTable unaffected
- [Phase 11-11]: ReplyComposer uses emitToast {kind, title} API matching lib/toast.ts — plan snippet had wrong {type, message} shape (auto-fixed)
- [Phase 11-reviews]: [Phase 11-14]: token_bucket_depleted() checked BEFORE increment_google_token_bucket() in pagination loop — prevents silent over-counting when halting on depletion
- [Phase 11-reviews]: [Phase 11-14]: Depletion does NOT raise exception — loop breaks cleanly so Celery marks task SUCCESS; next Beat tick is natural retry mechanism
- [Phase 11-reviews]: [Phase 11-14]: review.fetched uses entity_type='review' to distinguish per-page fetch events from entity_type='shop_sync' lifecycle events
- [Phase 11-15]: JSONField chosen over ArrayField(JSONField()) — cross-DB safe for SQLite test runner; stores list-of-dicts natively in jsonb on Postgres
- [Phase 11-15]: MAX_TAGS=5 enforced at render time in SentimentBadge (UI cap); Phase 12 prompt enforces <=5 at write time independently
- [Phase 11-15]: REVW-07 now jointly owned: Phase 11 owns rendering scaffolding, Phase 12 ENRCH-14 owns tag data population
- [Phase 12]: Exact version pins for openai==2.33.0/langsmith==0.8.0/pydantic==2.13.3 — CLAUDE.md §14.9 was stale; RESEARCH.md verified live PyPI 2026-05-02
- [Phase 12]: LangSmith disabled in test settings via os.environ before from .base import * — ruff isort moves import to top which is actually safer
- [Phase 12]: ClassVar[list] annotation on ReviewFactory tags/extracted_action_items — required by ruff RUF012 for mutable class attributes
- [Phase 12]: Local optimistic flip to status='success' in ProgressModal sync.enrichment.progress handler — UX safety net for slow networks; backend sync.complete re-confirms duration_seconds
- [Phase 12]: TopbarBell guards stage regression: sync.fetch.progress only sets stage='fetching' if not already enriching — defensive against stale events; stage transitions strictly one-directional
- [Phase 12]: get_current_run_tree() used for trace_id capture instead of run_tree parameter injection — portable across langsmith versions
- [Phase 12]: usage_data uses Chat-Completions key names (prompt_tokens/completion_tokens) not Responses API names — keeps pricing.calculate_cost and Plan 04 stable across SDK API changes
- [Phase 12]: Lazy _get_client() singleton in client.py — defers OpenAI() construction to first call so module import succeeds when OPENAI_API_KEY is empty in tests
- [Phase 12]: enrichment_version incremented on BOTH success and failure — doubles as attempt counter for retry_failed_enrichments_task cap
- [Phase 12]: OpenAI call OUTSIDE transaction.atomic() — holding row lock during slow HTTP call is anti-pattern per RESEARCH.md
- [Phase 12]: OpenAIPermanentError NOT in autoretry_for AND not re-raised — Beat retry_failed_enrichments_task is sole re-attempt mechanism for permanent failures
- [Phase 12]: Patch path in management command tests targets the bound import in the command module namespace (enrich_existing_reviews.enrich_review_task.delay), not the source module (apps.reviews.tasks.*) — per RESEARCH.md Pitfall 5
- [Phase 12]: Function-local import of enrich_review_task in sync.py avoids circular dependency with tasks.py
- [Phase 12]: sync.complete moved from sync.py to enrichment.py per CONTEXT.md; enrichment service is sole emitter, gated by enriched >= fetched
- [Phase 12]: Test patching for lazy imports targets source modules (progress.py, sync.py) not the enrichment namespace
- [Phase 12-ai-enrichment-pipeline]: [Phase 12-09]: Skip OpenAI for comment-less reviews — branch placed AFTER PENDING->IN_PROGRESS so Layer 3 status guard protects skip path identically to OpenAI path
- [Phase 12-ai-enrichment-pipeline]: [Phase 12-09]: Skip path writes NO AiUsageLog row — zero billable cost; skip path is invisible to billing aggregations
- [Phase 12-ai-enrichment-pipeline]: [Phase 12-09]: Forward-only — historical comment-less reviews already SUCCESS are not re-processed (out of scope per gap brief)
- [Phase 13]: [Phase 13-01]: Partial unique constraint on (source_review,title,scope) WHERE source=AI enables idempotent AI promotion via bulk_create(ignore_conflicts=True)
- [Phase 13]: [Phase 13-01]: ActionItemNote ordering=['created_at'] enforces oldest-first at ORM level per CONTEXT.md
- [Phase 13]: [Phase 13-01]: Pre-commit hooks ran admin.py imports during stash — committed pre-existing notifications model+admin+migration to unblock (Rule 3)
- [Phase 13]: [Phase 13-02]: Notification.target_url stored at dispatch time (not derived) — popover navigates without resolving FKs inline
- [Phase 13]: [Phase 13-02]: Composite index (recipient,is_read,created_at) covers both unread-count poll and popover list with single index scan
- [Phase 13]: [Phase 13-03]: promote_action_items_from_review NOT @transaction.atomic — caller controls txn boundary so it runs AFTER enrichment _persist_success commits (RESEARCH.md Pitfall 3)
- [Phase 13]: [Phase 13-03]: BrandScopeGuard uses 'return not (...)' form to satisfy ruff SIM102+SIM103; semantics unchanged from plan-suggested nested-if
- [Phase 13]: [Phase 13-03]: Lowercase scope/priority from GPT JSON mapped to uppercase TextChoices via _SCOPE_MAP/_PRIORITY_MAP module constants
- [Phase 13-action-items-and-notifications]: [Phase 13-04]: ActionItemUpdateSerializer omits scope/shop fields entirely (not declared as read_only) — DRF silently ignores undeclared input, achieving ACTN-07 semantics
- [Phase 13-action-items-and-notifications]: [Phase 13-04]: List vs Read serializer split — list omits notes/source_review to keep ACTN-12 <=5 query budget; retrieve adds prefetch_related('notes__author')
- [Phase 13-action-items-and-notifications]: [Phase 13-04]: notifications URL include left to plan 13-05 — Django include('module.path') resolves eagerly so the planned 'lazy include' would have broken manage.py check before 13-05 commits
- [Phase 13-action-items-and-notifications]: [Phase 13-04]: perform_update intercepts assignee changes and routes them through assign_action_item service so AuditLog row is written; title/priority/due_date go straight via serializer.save (no audit per ACTN-13)
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: NOTF-05 enforced inside dispatch_notification (not at call sites) — Staff excluded from User queryset whenever action_item.scope == BRAND
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: All dispatch hooks use transaction.on_commit (not signals) so notifications never fire on rollback; signals fire pre-commit which would create phantom rows
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: Closure variable rebinding (assignee_pk: int = assignee_id) used to satisfy mypy narrowing across nested closure boundary in lifecycle.py — cleaner than scattered type: ignore
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: promote_action_items_from_review returns int count, not list[int] — enrichment._schedule_action_item_promotion bridges by snapshotting pre-promotion ActionItem PKs and diff-ing afterwards
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: Sync per-shop dispatch batches new_review notifications across pages and dispatches once at end of fetch_and_persist_reviews — per-page dispatch would scale dispatch passes proportional to page count
- [Phase 13-action-items-and-notifications]: [Phase 13-05]: Bell endpoint queryset filters only by recipient — dispatch_notification only writes for users in the same org so the recipient filter is the tenant boundary

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8: GBP API production approval from Google is a non-code prerequisite for production launch (code can be built and tested against sandbox first).

## Session Continuity

Last session: 2026-05-04T05:18:25.999Z
Stopped at: Completed 13-05-PLAN.md
Resume file: None
