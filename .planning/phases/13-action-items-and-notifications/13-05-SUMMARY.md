---
phase: 13-action-items-and-notifications
plan: 05
subsystem: notifications
tags: [django, drf, notifications, dispatch-service, transaction-on-commit, NOTF-05, query-count-gate]

requires:
  - phase: 13-01
    provides: Notification model + composite (recipient, is_read, created_at) index
  - phase: 13-02
    provides: NotificationFactory + Notification model tests
  - phase: 13-03
    provides: ActionItem lifecycle (create_action_item, assign_action_item, promote_action_items_from_review)
  - phase: 13-04
    provides: ActionItemViewSet (uses transition + assign services that 13-05 hooks into)
  - phase: 12
    provides: enrich_review _persist_success — extended with post-commit promotion + dispatch
  - phase: 11-reviews
    provides: fetch_and_persist_reviews _persist_page — extended to surface new google_review_ids

provides:
  - apps.notifications.services.dispatch.dispatch_notification (NOTF-05 enforced at this layer)
  - apps.notifications.serializers.NotificationReadSerializer
  - apps.notifications.views.NotificationViewSet (bell, mark-read, mark-all-read)
  - apps.notifications.urls (router under api/v1/notifications/)
  - URL include in config/urls.py for api/v1/notifications/
  - Side-effect hooks: action item create + assign, enrichment success, review sync new-row
    -> dispatch_notification via transaction.on_commit (no notification on rollback)

affects: [13-06, 13-07, 13-08]

tech-stack:
  added: []
  patterns:
    - "NOTF-05 enforced inside dispatch_notification (not at call sites) so a future caller cannot bypass"
    - "transaction.on_commit pattern for every dispatch hook — notifications never fire on rollback"
    - "Per-shop sync batches new_review notifications (collected across pages, dispatched once) to avoid spam"
    - "Function-local imports in lifecycle/enrichment/sync to avoid notifications<->callers app cycle"
    - "Bell endpoint hot-path budget enforced by CaptureQueriesContext gate (<=3 queries)"
    - "Closure variable rebinding (item_assignee_id / assignee_pk) to satisfy mypy narrowing across the closure boundary"

key-files:
  created:
    - apps/notifications/services/__init__.py
    - apps/notifications/services/dispatch.py
    - apps/notifications/serializers.py
    - apps/notifications/views.py
    - apps/notifications/urls.py
    - apps/notifications/tests/test_dispatch.py
    - apps/notifications/tests/test_views.py
  modified:
    - apps/action_items/services/lifecycle.py  # create + assign hooks
    - apps/reviews/services/enrichment.py      # post-commit promote + new_action_item dispatch
    - apps/reviews/services/sync.py            # _persist_page returns new google_review_ids; _schedule_new_review_dispatch
    - config/urls.py                           # include notifications api urls

key-decisions:
  - "NOTF-05 enforced at dispatch_notification, not at call sites. Centralising the rule means a future caller (Plan 13-08, future ad-hoc admin scripts) cannot accidentally leak brand-scope notifications to Staff. Test test_dispatch_brand_action_item_excludes_staff is the gate."
  - "transaction.on_commit chosen over signals for every dispatch hook. Signals fire pre-commit, which would create phantom notifications on rollback. on_commit defers callbacks to the outermost commit; if no transaction is active, runs synchronously — same semantics."
  - "Closure variable rebinding for assignee IDs (assignee_pk: int = assignee_id) because mypy strict mode cannot narrow `int | None` across a nested function boundary. Cleaner than a scattered `# type: ignore`."
  - "promote_action_items_from_review (plan 13-03) returns int count, not list[int] as plan body assumed. Bridged in enrichment._schedule_action_item_promotion by snapshotting pre-promotion ActionItem PKs and diff-ing afterwards — same outcome, no API change to 13-03."
  - "Per-shop sync collects new google_review_ids across all pages and dispatches once at the end of fetch_and_persist_reviews (R4 / NOTF-02). Per-page dispatch would multiply DB writes proportional to page count; per-shop batching is O(1) on dispatch passes per sync."
  - "Bell endpoint queryset filters only by recipient. Since dispatch_notification only writes Notification rows for users in the requesting user's org (cross-org rows cannot exist for this user as recipient), the recipient filter alone is the tenant boundary — no separate organisation_id filter needed."
  - "config/urls.py now imports from apps.notifications.urls. The 13-04 deferral is now resolved — module exists, eager include is safe."

requirements-completed: [ACTN-01, NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05]

duration: 12min
completed: 2026-05-04
---

# Phase 13 Plan 05: Notification Dispatch Service + Bell API Summary

**Notification dispatch service enforcing NOTF-05 at the dispatch layer (not at call sites), wired via transaction.on_commit into action item create/assign, enrichment promotion, and review sync new-row paths; plus the NotificationViewSet exposing GET /bell/, POST /{pk}/read/, POST /mark-all-read/ that Plan 13-08's NotifBell will poll.**

## Performance

- **Duration:** ~12 min (incl. recovering a stalled mid-Task-1 mypy narrowing error from the prior agent attempt)
- **Tasks:** 2 (per plan; Task 2 includes the view tests)
- **Files created:** 7
- **Files modified:** 4

## Accomplishments

- `dispatch_notification(*, organisation_id, notification_type, ...)` — single fan-out function. Filters User.objects to active ORG_ADMIN/STAFF_ADMIN in the org; honours `recipient_ids` and `exclude_recipient_ids` post-filters; **excludes Staff when `action_item.scope == "BRAND"`** (NOTF-05).
- Action item `create_action_item` and `assign_action_item` queue `action_item_assigned` notifications via `transaction.on_commit` — never on rollback, never to the actor themselves.
- Review enrichment `_persist_success` queues `_schedule_action_item_promotion` via `on_commit`. Closure: re-fetch Review (in-memory copy is stale after `Review.objects.filter().update()`), snapshot existing ActionItem PKs, call `promote_action_items_from_review`, dispatch `new_action_item` for each newly-created PK.
- Review sync `_persist_page` now returns `(count, all_ids, new_google_review_ids)`. `fetch_and_persist_reviews` accumulates `all_new_google_ids` across pages and dispatches one `new_review` Notification per genuinely-new review per eligible recipient via `on_commit` after the page loop completes.
- `NotificationViewSet` with three actions: `bell` (NOTF-01/04 — `{unread_count, items: <=10 newest-first}`), `mark_read` (NOTF-03 idempotent, 404 on cross-user pk), `mark_all_read` (NOTF-03 bulk update).
- `apps/notifications/urls.py` created from scratch; `config/urls.py` now includes it under `api/v1/`.
- 12 dispatch tests (eligibility, NOTF-05, recipient filters, assignment hooks, enrichment promotion flow, sync new-row flow) + 8 view tests including the `<=3 SQL` query budget gate on `/bell/`.

## Task Commits

1. **Task 1: dispatch_notification + on_commit hooks across lifecycle/enrichment/sync** — `cb5f35f` (feat)
2. **Task 2: NotificationViewSet + serializers + urls + config wiring + view tests** — `5501993` (feat)

## Files Created/Modified

**Created:**
- `apps/notifications/services/__init__.py`
- `apps/notifications/services/dispatch.py` — `dispatch_notification` with NOTF-05 enforcement
- `apps/notifications/serializers.py` — `NotificationReadSerializer`
- `apps/notifications/views.py` — `NotificationViewSet`
- `apps/notifications/urls.py` — router
- `apps/notifications/tests/test_dispatch.py` — 12 tests
- `apps/notifications/tests/test_views.py` — 8 tests

**Modified:**
- `apps/action_items/services/lifecycle.py` — create + assign hooks (closure variable rebinding for mypy)
- `apps/reviews/services/enrichment.py` — `_schedule_action_item_promotion` via on_commit
- `apps/reviews/services/sync.py` — `_persist_page` returns new ids; `_schedule_new_review_dispatch`; accumulator in `fetch_and_persist_reviews`
- `config/urls.py` — `include(notifications_api_urls)` (resolves the 13-04 coordination deferral)

## Decisions Made

- **NOTF-05 lives at the dispatch layer.** A future caller cannot leak brand-scope notifications to Staff because the rule is enforced inside `dispatch_notification` itself — Staff are excluded from the User queryset whenever `action_item is not None and action_item.scope == "BRAND"`. The test `test_dispatch_brand_action_item_excludes_staff` is the gate.
- **`transaction.on_commit` everywhere.** Every dispatch hook (create, assign, enrichment success, sync new-row) defers via `on_commit`. Signals fire pre-commit and would have created phantom notifications on rollback.
- **Sync per-shop dispatch batching.** New `google_review_id`s are accumulated across pages and dispatched once at the end of `fetch_and_persist_reviews`. Per-page dispatch would have multiplied dispatch passes proportional to page count.
- **Closure variable rebinding for mypy narrowing.** The `assignee_id: int | None` parameter cannot be narrowed across a nested closure boundary — rebinding to `assignee_pk: int = assignee_id` (after a `is not None` guard) is the cleanest fix. Reused in both `create_action_item` and `assign_action_item`.
- **`promote_action_items_from_review` returns `int`, not `list[int]`** as the plan body assumed. Adapter logic in `_schedule_action_item_promotion` snapshots pre-promotion ActionItem PKs for `source_review_id=review_pk`, calls promote, then `exclude(pk__in=pre_pks)` to identify new rows. Same outcome, zero change to the 13-03 API.
- **Bell queryset uses only `filter(recipient=request.user)`** — the recipient filter is the tenant boundary because `dispatch_notification` only writes rows for users in the same org as the source event.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mypy narrowing error on `recipient_ids=[assignee_id]` in lifecycle.py**

- **Found during:** Task 1 (resumed from prior agent's stall point)
- **Issue:** Both `create_action_item` and `assign_action_item` had `recipient_ids=[assignee_id]` inside a nested `_notify_*` closure. `assignee_id` is typed `int | None`; the surrounding `if assignee_id and ...` guard narrows in the if-block but mypy strict mode does not propagate the narrowing across the closure boundary, producing `error: List item 0 has incompatible type "int | None"; expected "int"`.
- **Fix:** Added a guard `if x is not None and x != actor_pk:` and rebound to a typed local `assignee_pk: int = x` immediately before the closure. The closure captures `assignee_pk: int`, satisfying mypy without `# type: ignore`.
- **Files modified:** `apps/action_items/services/lifecycle.py`
- **Committed in:** `cb5f35f`

**2. [Rule 1 - Lint/types] Mypy strict-mode adjustments to NotificationViewSet + serializer**

- **Found during:** Task 2 mypy run after writing views
- **Issue:** Five strict-mypy errors mirroring the same DRF/AnonymousUser typing pattern noted in the 13-04 SUMMARY: `Missing type parameters for ModelSerializer/GenericViewSet`; `cannot override APIView instance variable with class variable`; `request.user` typed `User | AnonymousUser`; `pk: str | None` in lookup.
- **Fix:** Same pattern as `apps/action_items/views.py`: parameterised generics (`ModelSerializer[Notification]`, `GenericViewSet[Notification]`), switched class attr to plain assignment with `# noqa: RUF012`, added `# type: ignore[misc]` on the `recipient=self.request.user` lookup, and added an early `if pk is None` guard in `mark_read`.
- **Files modified:** `apps/notifications/serializers.py`, `apps/notifications/views.py`
- **Committed in:** `5501993`

**3. [Rule 1 - Lint] Ruff RUF059 unused unpacked variable in test fixture**

- **Found during:** Task 2 commit (pre-commit ruff-check)
- **Issue:** `client, user, org = setup` — `user` was unused in `test_bell_excludes_other_users`.
- **Fix:** Renamed to `_user`.
- **Files modified:** `apps/notifications/tests/test_views.py`
- **Committed in:** `5501993` (in same commit after re-stage; pre-commit failed first attempt and was fixed before retry)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bug/lint). No Rule 4 architectural escalations.

## Issues Encountered

- Recovered from a prior agent stall on the mypy narrowing error (Task 1 was already ~80% done in the working tree). Re-verified the existing untracked dispatch.py + on_commit hooks against the plan; only the narrowing fix and re-running pre-commit were needed before Task 1 could ship.
- Pre-commit ruff-check caught one unused variable on first commit attempt of Task 2; standard hook-fix loop.

## User Setup Required

None — all changes are server-side Django code, no env vars or external services touched.

## Next Phase Readiness

- **Plan 13-06 / 13-07 (UI work)** can now: render the bell counter polling `/api/v1/notifications/bell/` every 60s; render the action items page knowing notifications fire on every state change.
- **Plan 13-08 (NotifBell front-end)** has its full backend contract finalised:
  - `GET /api/v1/notifications/bell/` -> `{unread_count: int, items: NotificationReadSerializer[]}` (<=10, newest-first)
  - `POST /api/v1/notifications/{pk}/read/` -> `{id, is_read: true}` (404 on cross-user pk; idempotent)
  - `POST /api/v1/notifications/mark-all-read/` -> `{status: "ok"}`
- **CI gate (NOTF bell <=3 queries) is now active** — `test_bell_query_count_le_3` will fail any future regression that bloats the bell endpoint past the auth + count + select budget.
- **NOTF-05 invariant test** (`test_dispatch_brand_action_item_excludes_staff`) is the bulwark against future regressions on the most security-sensitive notification rule.

## Self-Check

Verifying claimed artifacts:
- `apps/notifications/services/dispatch.py` — FOUND
- `apps/notifications/serializers.py` — FOUND
- `apps/notifications/views.py` — FOUND
- `apps/notifications/urls.py` — FOUND
- `apps/notifications/tests/test_dispatch.py` — FOUND (12 tests, all passing)
- `apps/notifications/tests/test_views.py` — FOUND (8 tests, all passing)
- `apps/action_items/services/lifecycle.py` — MODIFIED (create + assign hooks via on_commit)
- `apps/reviews/services/enrichment.py` — MODIFIED (`_schedule_action_item_promotion`)
- `apps/reviews/services/sync.py` — MODIFIED (new ids accumulator + `_schedule_new_review_dispatch`)
- `config/urls.py` — MODIFIED (include notifications api urls)
- Commit `cb5f35f` — FOUND
- Commit `5501993` — FOUND
- `pytest apps/notifications/` — 24 passed
- `pytest apps/action_items/tests/test_services.py` — 24 passed (no regression from on_commit hooks)
- `python manage.py check` — exits 0
- `mypy apps/notifications/ apps/action_items/services/lifecycle.py apps/reviews/services/sync.py apps/reviews/services/enrichment.py` — Success: no issues

## Self-Check: PASSED

---
*Phase: 13-action-items-and-notifications*
*Completed: 2026-05-04*
