---
phase: 25-org-admin-tag-management-dashboard-polarity
plan: "01"
subsystem: reviews/tag-management
tags: [canonical-tags, celery, services, selectors, tdd, migrations]
dependency_graph:
  requires:
    - 24-02 (OrgCanonicalTag model + _refresh_review_counts from finalise.py)
    - 23-01 (distributed_lock, tag-merge queue, finalize_canonical_tags_task pattern)
    - 13 (Notification model + dispatch_notification)
  provides:
    - TagMergeJob model (durable merge progress record)
    - rename_canonical_tag service (O(1) FK-only, D-03/D-04)
    - create_merge_job service (validates, enqueues, returns job)
    - merge_canonical_tags service (atomic, locked, aggregate refresh)
    - merge_canonical_tags_task (tag-merge queue thin wrapper)
    - list_canonical_tags_for_org selector
    - TAG_MERGE_COMPLETE notification type
  affects:
    - apps/reviews/models.py (TagMergeJob added)
    - apps/reviews/tasks.py (merge_canonical_tags_task added)
    - apps/notifications/models.py (NotificationType extended)
    - config/settings/base.py (Celery route added)
tech_stack:
  added: []
  patterns:
    - TDD RED-GREEN cycle (7 failing tests → 7 passing tests)
    - transaction.atomic + distributed_lock per-org (§7.6, §12.4)
    - Single bulk UPDATE FK re-point before source.delete() (§6.10)
    - _refresh_review_counts aggregate — never naive sum (§29.2)
    - dispatch_notification called after atomic block (Pitfall 4)
    - Thin Celery task wrapper importing service inside body (§12.3)
key_files:
  created:
    - apps/reviews/services/tag_management.py
    - apps/reviews/migrations/0014_tagmergejob.py
    - apps/notifications/migrations/0002_notification_type_tag_merge_complete.py
    - apps/reviews/tests/test_services.py
  modified:
    - apps/reviews/models.py (TagMergeJob class added after OrgCanonicalTag)
    - apps/notifications/models.py (TAG_MERGE_COMPLETE notification type)
    - apps/reviews/tests/factories.py (TagMergeJobFactory)
    - apps/reviews/tasks.py (merge_canonical_tags_task)
    - config/settings/base.py (Celery route for tag-merge queue)
    - apps/reviews/selectors/canonical_tags.py (list_canonical_tags_for_org)
decisions:
  - D-03: rename_canonical_tag touches only OrgCanonicalTag.label (O(1)); ReviewTag.label rows unchanged
  - D-04: case-insensitive duplicate guard via label__iexact before save; never silently merges
  - D-06: user-chosen target wins (do NOT call _merge_group which picks by review_count)
  - D-07: merge_canonical_tags_task on tag-merge queue; per-org distributed_lock (non-blocking); transaction.atomic all-or-nothing
  - D-08: TagMergeJob durable DB record with PENDING/IN_PROGRESS/SUCCESS/FAILED status + denormalized labels
metrics:
  duration: "~22 minutes"
  completed: "2026-06-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 6
---

# Phase 25 Plan 01: Tag Management Backend Services Summary

**One-liner:** TagMergeJob model + rename/merge services + Celery task on tag-merge queue + list selector, all with TDD RED-GREEN cycle enforcing O(1) FK-only rename and atomic aggregate-refresh merge.

## What Was Built

### Task 1: TagMergeJob model + migrations + TAG_MERGE_COMPLETE + TagMergeJobFactory (commit: 855ba41)

Added `TagMergeJob(TimeStampedModel)` to `apps/reviews/models.py` immediately after `OrgCanonicalTag`. The model tracks durable merge progress (D-08):
- `Status` TextChoices: PENDING / IN_PROGRESS / SUCCESS / FAILED
- `source_tag` and `target_tag` FKs to `OrgCanonicalTag` with `on_delete=SET_NULL` (source FK becomes null after `source.delete()`)
- `source_label` / `target_label` — denormalized at job creation time (Pitfall 6: source.label inaccessible after deletion)
- `dismissed` BooleanField for UI dismissal
- Composite indexes: `tagmergejob_org_status_idx` (organisation, status) for active-job poll; `tagmergejob_org_date_idx` (organisation, -created_at) for history ordering

Generated `apps/reviews/migrations/0014_tagmergejob.py` (clean, reversible).

Added `TAG_MERGE_COMPLETE = "tag_merge_complete"` to `Notification.NotificationType` and generated `apps/notifications/migrations/0002_notification_type_tag_merge_complete.py` (separate from TagMergeJob migration for clean reversibility per §18).

Added `TagMergeJobFactory` to test factories.

### Task 2: Wave 0 RED service tests (commit: e0823dd)

Created `apps/reviews/tests/test_services.py` with 7 tests — all initially RED (ModuleNotFoundError):
1. `test_rename_updates_canonical_tag_label` — FK-only invariant (D-03)
2. `test_rename_rejects_iexact_duplicate` — case-insensitive guard (D-04, Pitfall 5)
3. `test_rename_title_case` — Title-Case normalization (D-04)
4. `test_merge_bulk_update_no_n_plus_one` — single bulk UPDATE assertion via CaptureQueriesContext (§6.10)
5. `test_merge_rollback_on_error` — transaction.atomic rollback verification (D-07)
6. `test_merge_cross_org_blocked` — org-scoped DoesNotExist check (T-25-AC1)
7. `test_merge_dispatches_notification` — dispatch_notification called once on SUCCESS (D-07)

### Task 3: tag_management service + task + route + selector (commit: 30db813)

**`apps/reviews/services/tag_management.py`** (new):
- `rename_canonical_tag(*, tag, new_label, organisation_id)`: strip + title(), 1-100 char validation, case-insensitive `label__iexact` duplicate guard (raises ValidationError — never silently merges), `tag.save(update_fields=["label", "updated_at"])` — no ReviewTag fan-out
- `create_merge_job(*, source_tag, target_id, organisation_id)`: fetches target org-scoped (DoesNotExist → 404), rejects source==target, rejects when active job exists (→ ValidationError for HTTP 409), creates `TagMergeJob` with denormalized labels, enqueues `merge_canonical_tags_task.delay(job.pk)`, returns job
- `merge_canonical_tags(*, job_id)`: acquires `distributed_lock("lock:tag_merge:org:{org_id}", blocking=False)`, calls `_execute_merge()` under the lock
- `_execute_merge(*, job_id, org_id)`: `select_for_update()` on job; idempotent guard for terminal states; org-scoped source/target fetch (T-25-AC1); sets status IN_PROGRESS + total; single `ReviewTag.objects.filter(canonical_tag=source).update(canonical_tag=target)` bulk UPDATE (§6.10 — NOT a per-row loop); `source.delete()`; `_refresh_review_counts(organisation_id=org_id)` (aggregate, never naive sum — D-03/Pitfall 2); sets status SUCCESS + processed; exception handler saves FAILED status outside atomic block (survives rollback); `dispatch_notification(notification_type="tag_merge_complete", org_admins_only=True)` called AFTER atomic block (Pitfall 4)

**`apps/reviews/tasks.py`**: Added `merge_canonical_tags_task` thin wrapper (bind=True, max_retries=3, retry_backoff=60, retry_backoff_max=600, retry_jitter=True; imports service inside body per §12.3).

**`config/settings/base.py`**: Added `"apps.reviews.tasks.merge_canonical_tags_task": {"queue": "tag-merge"}` to CELERY_TASK_ROUTES.

**`apps/reviews/selectors/canonical_tags.py`**: Added `list_canonical_tags_for_org(*, organisation_id)` returning `OrgCanonicalTag.objects.filter(organisation_id=...).order_by("-review_count", "label")` (1 query, no prefetch needed).

All 7 service tests turned GREEN.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ReviewTag UniqueConstraint violation in test_merge_bulk_update_no_n_plus_one**
- **Found during:** Task 3 (GREEN phase)
- **Issue:** Test created 5 ReviewTag rows with identical (review, label, polarity) values, hitting `uniq_reviewtag_review_label_polarity` DB constraint
- **Fix:** Changed loop to create one distinct `ReviewFactory()` per iteration so each ReviewTag belongs to a different review
- **Files modified:** `apps/reviews/tests/test_services.py`

**2. [Rule 1 - Bug] Test assertion too strict — cascade SET_NULL generates second UPDATE**
- **Found during:** Task 3 (GREEN phase)
- **Issue:** Test asserted `len(reviewtag_updates) == 1` but Django's `on_delete=SET_NULL` cascade during `source.delete()` generates a second SET NULL UPDATE on `reviews_reviewtag` (even though 0 rows are affected after the re-point). This is Django ORM behavior, not an N+1.
- **Fix:** Changed assertion to `len(reviewtag_updates) <= 2` and added separate check for exactly 1 non-NULL re-point statement (to confirm no per-row N+1)
- **Files modified:** `apps/reviews/tests/test_services.py`

**3. [Rule 2 - Missing critical functionality] Bandit flagged `assert` in service code**
- **Found during:** Task 3 (pre-commit hook)
- **Issue:** Used `assert job.source_tag_id is not None` in service code; bandit B101 flags asserts (removed by Python -O optimization flag)
- **Fix:** Replaced with explicit `if ... raise ValueError(...)` guard
- **Files modified:** `apps/reviews/services/tag_management.py`

**4. [Rule 2 - Missing critical functionality] RUF001 en-dash in error message string**
- **Found during:** Task 3 (pre-commit ruff check)
- **Issue:** Error message contained en-dash character (–) which triggers RUF001 (ambiguous Unicode)
- **Fix:** Replaced with hyphen-minus (-) in `"Label must be 1-100 characters."`
- **Files modified:** `apps/reviews/services/tag_management.py`

## Known Stubs

None. All services are fully implemented with real logic. No hardcoded empty values or placeholder text.

## Threat Surface Scan

No new network endpoints or trust boundary surfaces introduced in this plan. This plan adds service/model/task layer only — API endpoints are added in plan 25-02.

## Self-Check: PASSED

Files created/exist:
- `apps/reviews/services/tag_management.py` FOUND
- `apps/reviews/migrations/0014_tagmergejob.py` FOUND
- `apps/notifications/migrations/0002_notification_type_tag_merge_complete.py` FOUND
- `apps/reviews/tests/test_services.py` FOUND

Commits verified:
- 855ba41: Task 1 — TagMergeJob model + migrations + factory
- e0823dd: Task 2 — 7 RED service tests
- 30db813: Task 3 — tag_management service (all 7 tests GREEN)

Acceptance criteria verified:
- `grep -n "class TagMergeJob" apps/reviews/models.py` → match at line 179
- `apps/reviews/migrations/0014_tagmergejob.py` exists
- `apps/notifications/migrations/0002_notification_type_tag_merge_complete.py` exists
- `makemigrations --check --dry-run` → "No changes detected"
- `grep -n "TAG_MERGE_COMPLETE" apps/notifications/models.py` → match at line 27
- `grep -n "tagmergejob_org_status_idx" apps/reviews/migrations/0014_tagmergejob.py` → match at line 33
- `grep -n "TagMergeJobFactory" apps/reviews/tests/factories.py` → match at line 58
- `pytest apps/reviews/tests/test_services.py -k "rename or merge"` → 7 PASSED
- `grep -n "merge_canonical_tags_task" config/settings/base.py` → tag-merge route at line 130
- `grep -n "def list_canonical_tags_for_org" apps/reviews/selectors/canonical_tags.py` → match at line 50
- `grep -n "_refresh_review_counts" apps/reviews/services/tag_management.py` → match at line 25 (import) + line 213 (call)
- `grep -n "label__iexact" apps/reviews/services/tag_management.py` → match at line 57
- `grep -c "review_count +=" apps/reviews/services/tag_management.py` → 0 (no naive sum)
