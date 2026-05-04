---
phase: 13-action-items-and-notifications
plan: 02
subsystem: notifications
tags:
  - notifications
  - data-layer
  - migration
dependency_graph:
  requires:
    - apps.common.models.TimeStampedModel
    - apps.action_items.ActionItem (plan 13-01)
    - apps.organisations.Organisation
    - apps.shops.Shop
    - apps.reviews.Review
  provides:
    - apps.notifications.models.Notification
    - apps.notifications.tests.factories.NotificationFactory
  affects:
    - apps/notifications/migrations/0001_initial.py
tech_stack:
  added: []
  patterns:
    - composite-index for hot-path poll query
    - pre-computed target_url stored on the row
    - role-fanout-via-recipient-rows (one Notification per recipient per event)
key_files:
  created:
    - apps/notifications/models.py
    - apps/notifications/admin.py
    - apps/notifications/migrations/__init__.py
    - apps/notifications/migrations/0001_initial.py
    - apps/notifications/tests/__init__.py
    - apps/notifications/tests/factories.py
    - apps/notifications/tests/test_models.py
  modified: []
decisions:
  - target_url is stored on Notification at dispatch time (not derived) so the
    bell popover can navigate without resolving FKs inline; trades a small
    storage cost for predictable single-query reads
  - Composite index (recipient, is_read, created_at) covers BOTH the
    unread-count count query and the popover ordered-list query with one index
    scan; matched to NOTF-04 60-second poll cadence and NOTF-01 last-10
    requirement
  - All three event-context FKs (shop, action_item, review) nullable because
    notification types share one table but populate different subsets
  - admin.ModelAdmin uses `# type: ignore[type-arg]` and untyped tuples,
    matching the established pattern from apps/action_items/admin.py
metrics:
  duration_minutes: 8
  completed: "2026-05-04"
  tasks_completed: 1
  files_changed: 7
requirements:
  - NOTF-01
  - NOTF-02
---

# Phase 13 Plan 02: Notification Data Layer — Summary

Notification model with three event types, composite unread-poll index, three nullable event-context FKs, initial migration, factory, and four passing model tests — schema ready for plan 13-05's dispatch service.

## What Shipped

- **`Notification` model** with `NotificationType` choices (`NEW_REVIEW`, `NEW_ACTION_ITEM`, `ACTION_ITEM_ASSIGNED`), org + recipient FKs (CASCADE), nullable shop/action_item/review FKs (SET_NULL), `is_read` boolean, `target_url` for pre-computed navigation
- **Composite index** `notif_recipient_unread_idx` on `(recipient, is_read, created_at)` — single-index scan for both unread count and popover list queries
- **Initial migration** `apps/notifications/migrations/0001_initial.py` with proper FK dependencies on action_items, organisations, reviews, shops, accounts
- **Admin registration** with raw_id_fields on all FKs to keep admin pages fast even with millions of notifications
- **NotificationFactory** with sensible defaults (NEW_REVIEW type, sequence-based title)
- **Four model tests**: defaults, str representation, default ordering newest-first, nullable FKs all save correctly

## Verification

- `python manage.py makemigrations --check --dry-run` → exits 0 (no pending changes)
- `pytest apps/notifications/tests/ -q` → **4 passed**
- All acceptance grep checks pass (Notification class, three NotificationType members, composite index name in both model + migration, NotificationFactory class)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocker] Generated `apps/action_items/migrations/0001_initial.py` to satisfy notifications migration FK dependency**
- **Found during:** Task 1 (makemigrations notifications)
- **Issue:** Notifications migration declares `dependencies = [('action_items', '0001_initial'), ...]` but plan 13-01 (running in parallel) had committed the model without generating its migration. `makemigrations --check` reported missing migration and pre-commit hooks blocked the commit.
- **Fix:** Ran `makemigrations notifications` which auto-generated the action_items migration as a side-effect, then included both in the commit.
- **Files added:** `apps/action_items/migrations/__init__.py`, `apps/action_items/migrations/0001_initial.py`
- **Note:** Plan 13-01's parallel agent ultimately took ownership of these files and packaged them with its own scaffolding-unblock commit (HEAD a10673a). Net result is identical: both apps now have proper initial migrations.

**2. [Rule 1 — Bug] Replaced `ClassVar` typed admin attributes with untyped tuples**
- **Found during:** Pre-commit mypy run
- **Issue:** Initial admin.py used `list_display: ClassVar[tuple[str, ...]]` patterns; mypy strict mode rejects this against `admin.ModelAdmin` because the base class declares them as instance variables and django-stubs doesn't parameterise `ModelAdmin`.
- **Fix:** Replaced ClassVar annotations with bare tuple assignments and added `# type: ignore[type-arg]` to the class declaration — matches the pattern in `apps/action_items/admin.py`.
- **Files modified:** `apps/notifications/admin.py`

## Race Condition Note

This plan executed in parallel with plan 13-01 (both Wave 1, no `depends_on`). The two agents touched overlapping files (action_items migration FK target). The git history shows commit `a10673a` (created by 13-01's agent) which actually contains all of plan 13-02's notification deliverables — the agents' commits cross-pollinated through `git add` race conditions. All planned files are present and tests pass; the work is correctly delivered, just with the commit attribution shifted.

## Self-Check: PASSED

- [x] `apps/notifications/models.py` exists and contains `class Notification(TimeStampedModel)`
- [x] `apps/notifications/migrations/0001_initial.py` exists and references action_items dependency
- [x] `apps/notifications/tests/factories.py` contains `class NotificationFactory`
- [x] `apps/notifications/tests/test_models.py` exists with 4 tests
- [x] `apps/notifications/admin.py` exists with `NotificationAdmin`
- [x] `apps/notifications/migrations/__init__.py` exists
- [x] Commit `a10673a` exists in git history containing all notifications files
- [x] `pytest apps/notifications/tests/` → 4 passed
- [x] `makemigrations --check --dry-run` → exits 0
