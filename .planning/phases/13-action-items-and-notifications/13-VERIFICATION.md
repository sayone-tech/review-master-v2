---
phase: 13-action-items-and-notifications
verified: 2026-05-04T00:00:00Z
status: human_needed
score: 38/38 must-have truths verified (1 requirement-interpretation flag)
gaps: []
human_verification:
  - test: "End-to-end bell flow with multiple roles"
    expected: "Org Admin sees badge updates within 60s; Staff does not see brand-scoped action_item notifications"
    why_human: "Cross-tenant + cross-role timing not exercised in unit tests"
  - test: "ActionItemModal 3-tab visual + interaction"
    expected: "Source Review tab hidden for MANUAL items; Notes ordered oldest-first; Edit Details preserves Scope/Shop as read-only"
    why_human: "UI rendering and tab toggling can only be confirmed visually"
  - test: "ActionItemChip click navigation on review cards"
    expected: "Chip is clickable when has_action_items=true and routes to /admin/org/action-items/?review={id}"
    why_human: "Visual chip state and routing observable only at runtime"
  - test: "NOTF-02 Staff scope interpretation"
    expected: "Per REQUIREMENTS.md wording, Staff should receive new_review notifications ONLY for shops in their StaffAccessScope (and same for shop-scoped new_action_item)."
    why_human: "Implementation dispatches new_review/new_action_item to ALL Staff in the org regardless of accessible shops. Plan 13-05 explicitly interprets NOTF-02 loosely (\"this delivers it\"). Confirm with PO whether the strict accessible-shops filter is required, or whether this looser delivery is acceptable for Phase 13 scope."
---

# Phase 13: Action Items and Notifications — Verification Report

**Phase Goal:** Deliver the Action Items workflow (manual + AI-promoted) plus the Notification dispatch system and bell. Three-layer Staff scope on action items (selector + permission + UI). Hooks wired into review enrichment, review sync, and action item creation/assignment. Bell counter via 60s HTTP polling (not WebSocket).

**Verified:** 2026-05-04
**Status:** human_needed (all artifacts/wiring verified; one requirement-interpretation flag for NOTF-02 needs PO sign-off)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (aggregated across 8 plans)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ActionItem rows can be created with org/scope/status/priority/source/optional shop/assignee/due_date/source_review | VERIFIED | `apps/action_items/models.py:24-99` — full field set with TextChoices |
| 2 | ActionItemNote append-only oldest-first | VERIFIED | `apps/action_items/models.py:105-115` — `ordering = ["created_at"]`; only `add_note` service writes; no edit/delete endpoints |
| 3 | Partial unique constraint prevents duplicate AI extraction on (source_review, title, scope) | VERIFIED | `apps/action_items/models.py:93-99` `ai_unique_per_review_title_scope` with `condition=Q(source="AI")`; reproduced in migration 0001 line 71 |
| 4 | Notification rows created with recipient, organisation, type, target_url | VERIFIED | `apps/notifications/models.py:22-77` |
| 5 | Composite index (recipient, is_read, created_at) for unread bell | VERIFIED | `apps/notifications/models.py:68-73` and migration 0001 line 40 |
| 6 | create_action_item creates row + AuditLog atomically | VERIFIED | `apps/action_items/services/lifecycle.py:39-116` (`@transaction.atomic`) |
| 7 | transition_status uses select_for_update + writes status_changed AuditLog (any-to-any) | VERIFIED | `lifecycle.py:122-139` |
| 8 | assign_action_item updates assignee + AuditLog | VERIFIED | `lifecycle.py:142-185` |
| 9 | add_note creates ActionItemNote + AuditLog | VERIFIED | `lifecycle.py:188-207` |
| 10 | promote_action_items_from_review idempotent | VERIFIED | `lifecycle.py:210-251`, uses bulk_create(ignore_conflicts=True) and partial unique constraint |
| 11 | list_action_items applies STAFF SHOP-only + accessible_shop_ids (Layer 1) | VERIFIED | `apps/action_items/selectors/items.py:25-45` |
| 12 | BrandScopeGuard returns False when Staff accesses BRAND item (Layer 2) | VERIFIED | `apps/action_items/permissions.py:19-32` |
| 13 | GET /api/v1/action-items/ returns paginated list ≤5 SQL queries | VERIFIED | `views.py:41-82`; query budget tests `apps/action_items/tests/test_views.py:202,206,222,225` |
| 14 | Staff GET on BRAND-scoped detail returns 403 | VERIFIED | BrandScopeGuard in `permission_classes`; selector layer also returns none for STAFF on BRAND |
| 15 | POST creates manual ActionItem; PATCH updates editable fields only; Scope/Shop read-only | VERIFIED | `views.py:84-124`; `serializers.py` UpdateSerializer excludes scope/shop |
| 16 | POST /transition-status/ writes AuditLog and returns updated item | VERIFIED | `views.py:126-136` |
| 17 | POST /add-note/ creates note (1-2000 chars) | VERIFIED | `views.py:138-148`; bounds enforced in service `lifecycle.py:191-192` |
| 18 | Detail GET nested notes oldest-first prefetched | VERIFIED | `views.py:81` `prefetch_related("notes__author")` |
| 19 | Template view at /admin/org/action-items/ | VERIFIED | `apps/action_items/urls.py:16`; `views.py:151-191` |
| 20 | dispatch_notification creates rows for eligible Org users | VERIFIED | `apps/notifications/services/dispatch.py:25-84` |
| 21 | Brand-scoped action_item notifications EXCLUDE Staff (NOTF-05) — enforced in dispatch, not call site | VERIFIED | `dispatch.py:64-66` (`if action_item.scope == "BRAND": qs.exclude(role=STAFF_ADMIN)`) |
| 22 | GET /notifications/bell/ returns {unread_count, items[≤10]} | VERIFIED | `apps/notifications/views.py:41-55` |
| 23 | POST /{pk}/read/ marks notification read | VERIFIED | `views.py:57-68` |
| 24 | POST /mark-all-read/ marks all unread for current user | VERIFIED | `views.py:70-74` |
| 25 | Bell endpoint ≤3 SQL queries | VERIFIED | `apps/notifications/tests/test_views.py:128-131` `<= 3` assertion |
| 26 | Enrichment _persist_success → promote → dispatch new_action_item per row | VERIFIED | `apps/reviews/services/enrichment.py:115-166` (`transaction.on_commit` → promote → dispatch loop) |
| 27 | create_action_item with assignee → dispatch action_item_assigned (skipped if assignee==actor) | VERIFIED | `lifecycle.py:92-115` (`if item_assignee_id != actor_pk`) |
| 28 | assign_action_item → dispatch action_item_assigned | VERIFIED | `lifecycle.py:162-184` |
| 29 | sync.fetch_and_persist_reviews → dispatch new_review per genuinely new google_review_id | VERIFIED | `apps/reviews/services/sync.py:189-227, 418-424` (only new_google_review_ids dispatched, via on_commit at end of fetch_and_persist_reviews) |
| 30 | has_action_items via Exists() annotation, REVW-14 budget intact | VERIFIED | `apps/reviews/views.py:67-75` Exists annotation; `apps/reviews/serializers.py:20,45`; existing REVW-14 tests `apps/reviews/tests/test_views.py:114,121,125,136` still ≤5 |
| 31 | Action Items list page React widget mounted | VERIFIED | `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx`, `entrypoints/action-items-management.tsx`, template at `apps/action_items/templates/action_items/action_item_list.html` |
| 32 | Filters with debounced refetch; Scope hidden from Staff (Layer 3) | VERIFIED | `useActionItems.ts`, `ActionItemFilters.tsx` (Layer 3 via user_role prop) |
| 33 | Three-dot row menu status submenu | VERIFIED | `ActionItemTable.tsx` includes status submenu wired to transition-status API |
| 34 | 3-tab modal (Details / Notes / Source Review); Source hidden for MANUAL | VERIFIED | `ActionItemModal.tsx:365-368` `showSourceTab` conditional; tab labels confirmed |
| 35 | Manual create modal with cross-field scope/shop validation; Brand hidden from Staff | VERIFIED | `ActionItemCreateModal.tsx` (263 lines, substantive) |
| 36 | Clickable ActionItemChip when has_action_items=true | VERIFIED | `frontend/src/widgets/review-management/ActionItemChip.tsx:18-26`; href `/admin/org/action-items/?review=${reviewId}` |
| 37 | NotifBell renders badge, popover (last 10), mark-all-read | VERIFIED | `frontend/src/widgets/notif-bell/NotifBell.tsx` (155 lines) |
| 38 | Bell polls every 60s via HTTP — NO WebSocket | VERIFIED | `useNotifications.ts:25-27` `setInterval(..., 60_000)`; initial fetch BEFORE interval (line 24); zero WebSocket/Channels references in `apps/notifications/` or `frontend/src/widgets/notif-bell/` |

**Score:** 38/38 truths verified

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `apps/action_items/models.py` | `apps/common/models.TimeStampedModel` | inheritance | WIRED (`class ActionItem(TimeStampedModel)`) |
| `apps/action_items/models.py` | `apps/reviews/models.Review` | FK source_review | WIRED |
| `apps/notifications/models.py` | `apps/action_items.ActionItem` | nullable FK action_item | WIRED |
| `apps/action_items/services/lifecycle.py` | `apps/common/models.AuditLog` | AuditLog.objects.create on every state change | WIRED (4 call sites: created/status_changed/assigned/note_added) |
| `apps/action_items/selectors/items.py` | `apps/reviews/selectors/reviews.get_accessible_shop_ids` | reuse for Staff scoping | WIRED (line 19 import; line 42 call) |
| `apps/action_items/views.py` | `apps/action_items/services/lifecycle` | viewset @action calls services | WIRED (transition_status, add_note, create_action_item, assign_action_item) |
| `apps/action_items/views.py` | `BrandScopeGuard` | permission_classes | WIRED (line 57) |
| `config/urls.py` | `apps/action_items/urls` | path include | WIRED (lines 6, 23, 31) |
| `apps/reviews/services/enrichment.py` | `promote_action_items_from_review` | called AFTER transaction.atomic | WIRED via `transaction.on_commit` (line 166) |
| `apps/action_items/services/lifecycle.py` | `dispatch_notification` | from create/assign AFTER commit | WIRED via `transaction.on_commit` |
| `apps/reviews/services/sync.py` | `dispatch_notification` | on_commit at end of fetch_and_persist_reviews; one new_review per genuinely-new google_review_id | WIRED |
| `frontend/src/widgets/notif-bell/api.ts` | `/api/v1/notifications/bell/` | GET, polled every 60s | WIRED |
| `frontend/src/widgets/review-management/ActionItemChip.tsx` | `/admin/org/action-items/?review=` | anchor href when has_action_items=true | WIRED |
| `templates/partials/topbar.html` | `notif-bell-root` mount | mount #notif-bell-root | WIRED (line 33) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description (abbrev.) | Status | Evidence |
|-------------|----------------|----------------------|--------|----------|
| ACTN-01 | 13-01, 13-03, 13-05 | AI promotion creates ActionItem rows; SHOP→shop_id, BRAND→null | SATISFIED | `lifecycle.py:210-251` |
| ACTN-02 | 13-03, 13-04, 13-06 | List page; Staff queryset SHOP+accessible; 403 on direct brand access | SATISFIED | Selector + BrandScopeGuard + UI Layer |
| ACTN-03 | 13-04, 13-06 | Filter bar | SATISFIED | `ActionItemFilters.tsx` + `ActionItemFilterSet` |
| ACTN-04 | 13-01, 13-04, 13-06 | Table columns + 3-dot menu | SATISFIED | `ActionItemTable.tsx` |
| ACTN-05 | 13-04, 13-06 | Pagination 10/25/50/100 + sort options | SATISFIED | `DefaultPageNumberPagination` + `ordering_fields` |
| ACTN-06 | 13-04, 13-07 | 3-tab modal; Source tab AI-only | SATISFIED | `ActionItemModal.tsx` `showSourceTab` |
| ACTN-07 | 13-04, 13-07 | Edit mode field permissions; Scope/Shop read-only | SATISFIED | `ActionItemUpdateSerializer` + UI |
| ACTN-08 | 13-01, 13-03, 13-04, 13-06 | Any-to-any status transitions + audit log | SATISFIED | `transition_status` (no state machine) + AuditLog |
| ACTN-09 | 13-03, 13-04, 13-07 | Manual create form; Brand hidden from Staff | SATISFIED | `ActionItemCreateModal.tsx` + Layer 3 |
| ACTN-10 | 13-04, 13-07 | Notes append-only 1-2000 chars | SATISFIED | `add_note` validation + UI no edit/delete |
| ACTN-11 | 13-04, 13-07 | Source Review tab + "Open in Reviews" link | SATISFIED | `SourceReviewTab.tsx` |
| ACTN-12 | 13-04 | GET ≤5 SQL queries | SATISFIED | `test_views.py:206,225` `<= 5` |
| ACTN-13 | 13-01, 13-03, 13-07 | Audit log on created/status_changed/assigned/note_added | SATISFIED | 4 AuditLog.create call sites in `lifecycle.py` |
| NOTF-01 | 13-02, 13-05, 13-08 | Bell shows unread count + last 10 unread popover | SATISFIED | `views.py` bell + `NotifBell.tsx` |
| NOTF-02 | 13-02, 13-05, 13-08 | Three notification types; **Staff only for accessible shops/items** | SATISFIED-WITH-CAVEAT | Three types dispatched correctly. **CAVEAT:** Staff are NOT filtered by accessible shops for `new_review`/`new_action_item` (only NOTF-05 BRAND filter applies). Plan 13-05 explicitly interprets this loosely. Flagged for human verification. |
| NOTF-03 | 13-05, 13-08 | Click → mark-read + navigate; mark-all-read | SATISFIED | `mark_read`/`mark_all_read` views + `useNotifications.ts` |
| NOTF-04 | 13-05, 13-08 | 60s HTTP polling (no WebSocket) | SATISFIED | `setInterval(..., 60_000)`; zero WebSocket refs |
| NOTF-05 | 13-05 | Brand-scoped action_item notifications NEVER reach Staff — enforced in dispatch | SATISFIED | `dispatch.py:64-66` excludes Staff inside dispatch |

**No orphaned requirements** — every ACTN-* and NOTF-* ID in REQUIREMENTS.md mapped to one or more plans, and all are covered in code.

### Anti-Patterns Found

None of severity blocker. Implementation follows CLAUDE.md conventions: services/selectors split, services thin in tasks, AuditLog rows on every state change, no WebSocket for the bell (CLAUDE.md §13.2 prohibition honoured), no business logic in serializers/views, atomic transactions used.

### Human Verification Required

1. **NOTF-02 wording vs. implementation** — REQUIREMENTS.md states Staff receive new_review/new_action_item only for accessible shops/shop-scoped accessible items. Implementation dispatches to ALL Staff in the org (only NOTF-05 BRAND filter is enforced). Plan 13-05 acknowledges and accepts this loose interpretation. Need PO sign-off that this is acceptable for Phase 13 scope, or this becomes a follow-up gap.
2. **End-to-end bell behaviour** — visual confirmation of badge updates, popover rendering, mark-all-read interaction across roles.
3. **ActionItemModal 3-tab UX** — Source Review tab visibility, Edit Details preserving Scope/Shop as read-only, Notes oldest-first ordering.
4. **ActionItemChip click behaviour** — chip clickability and routing on review cards.

### Gaps Summary

No structural gaps. All 38 must-have truths verify against actual code. The single open item is a **requirements interpretation question** for NOTF-02 (Staff scope on `new_review` / `new_action_item` notifications), which Plan 13-05 explicitly addressed by interpreting NOTF-02 loosely. This is flagged for human/PO confirmation rather than re-planning, since it is a contract-clarification question, not a missing implementation.

---

_Verified: 2026-05-04_
_Verifier: Claude (gsd-verifier)_
