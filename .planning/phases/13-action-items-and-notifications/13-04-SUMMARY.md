---
phase: 13-action-items-and-notifications
plan: 04
subsystem: action-items
tags: [django, drf, viewset, serializers, filterset, query-count-gate, rbac, action-items]

requires:
  - phase: 13-01
    provides: ActionItem + ActionItemNote models
  - phase: 13-03
    provides: lifecycle services (create_action_item, transition_status, assign_action_item, add_note), list_action_items selector, BrandScopeGuard permission
  - phase: 11-reviews
    provides: TenantScopedViewSet, IsOrgScoped, get_accessible_shop_ids, DefaultPageNumberPagination

provides:
  - apps.action_items.serializers (Read/List/Create/Update/Note + StatusTransition + NoteCreate)
  - apps.action_items.filters.ActionItemFilterSet
  - apps.action_items.views.ActionItemViewSet
  - apps.action_items.views.action_item_list_view
  - apps.action_items.urls (router + template view)
  - URL wiring in config/urls.py for action-items API + page

affects: [13-05, 13-06, 13-07]

tech-stack:
  added: []
  patterns:
    - "ViewSet routes mutations through service functions (no business logic in viewset bodies)"
    - "ACTN-07 enforced by Update serializer omitting scope/shop fields entirely (DRF silently ignores unknown input fields)"
    - "Two-serializer split list vs detail: ActionItemListSerializer omits notes/source_review for tight query budget"
    - "Custom @action endpoints transition-status + add-note keep state changes auditable while staying RESTful"
    - "Three-layer Staff scope wired end-to-end: selector (L1) + permission (L2). UI (L3) deferred to 13-06/07"

key-files:
  created:
    - apps/action_items/serializers.py
    - apps/action_items/filters.py
    - apps/action_items/views.py
    - apps/action_items/urls.py
    - apps/action_items/templates/action_items/action_item_list.html
    - apps/action_items/tests/test_views.py
  modified:
    - config/urls.py

key-decisions:
  - "ActionItemUpdateSerializer omits scope/shop entirely (not declared as read-only fields). DRF silently ignores undeclared input fields, which is exactly the ACTN-07 semantics — PATCH succeeds and the read-only fields are unchanged."
  - "Two read serializers: List (lean) and Read (with nested notes/source_review prefetched). Keeps list endpoint inside the <=5 query budget while detail still returns rich data."
  - "perform_update intercepts assignee changes and routes them through assign_action_item service so they get an AuditLog row. Title/priority/due_date go straight through serializer.save() since they don't get audit rows per ACTN-13."
  - "viewset.create() overridden (not just perform_create) so the response uses ActionItemReadSerializer instead of the input shape. Matches the create_action_item service contract and gives clients a consistent payload."
  - "config/urls.py does NOT include apps.notifications.urls. The plan asked for a 'lazy string include' but Django's include('module.path') resolves eagerly at import time and breaks manage.py check before plan 13-05 has created the module. 13-05 will wire the include itself when it creates apps/notifications/urls.py."
  - "Layer 1 (selector) hides BRAND items from Staff entirely, so Staff GET on /action-items/{brand_id}/ returns 404 (not 403). The Layer 2 BrandScopeGuard remains the belt-and-braces in case the item ever resolves through a different code path. Test accepts either status code."
  - "filter_search uses .distinct() because the OR across notes__body can produce duplicates when an item has multiple matching notes."

requirements-completed: [ACTN-02, ACTN-03, ACTN-04, ACTN-05, ACTN-06, ACTN-07, ACTN-08, ACTN-09, ACTN-10, ACTN-11, ACTN-12]

duration: 8min
completed: 2026-05-04
---

# Phase 13 Plan 04: ActionItem REST API + Page View Summary

**ActionItem REST API (list / retrieve / create / update + transition-status / add-note custom actions) with three-layer Staff scope (selector + BrandScopeGuard) and ACTN-12 <=5-query CI gate, plus the template page view at /admin/org/action-items/.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-04T04:45:56Z
- **Completed:** 2026-05-04T04:54:10Z
- **Tasks:** 2
- **Files created:** 6 + 1 modified

## Accomplishments

- Five DRF serializers: List (lean), Read (with nested notes + source_review), Create, Update, Note + 2 input serializers (StatusTransition, NoteCreate)
- ActionItemFilterSet with shop / status / scope / assignee (special "me" and "unassigned" tokens) / created_at range / fulltext-ish search / source-review filter
- ActionItemViewSet (List/Retrieve/Create/Update mixins on GenericViewSet) with [IsOrgScoped, BrandScopeGuard] permissions
- Two custom actions: `POST /api/v1/action-items/{pk}/transition-status/` and `POST /api/v1/action-items/{pk}/add-note/`
- assignee-change interception in perform_update so audit log is written even when assignee changes via PATCH
- Template view `/admin/org/action-items/` rendering React mount root with shops + team JSON for the filter dropdowns
- 12 view tests including the two ACTN-12 query-count gate tests (Org Admin and Staff both <=5 SQL queries on a 20-item list)
- ACTN-10 enforced by URL-resolution test confirming `/notes/{id}/` does not exist as a route

## Task Commits

1. **Task 1: serializers + filters + viewset + urls + template + config wiring** — `5b3e63a` (feat)
2. **Task 2: 12 view tests including ACTN-12 query-count gate** — `18bf636` (test)

## Files Created/Modified

- `apps/action_items/serializers.py` — 5 read/write serializers
- `apps/action_items/filters.py` — ActionItemFilterSet
- `apps/action_items/views.py` — ActionItemViewSet + action_item_list_view template view
- `apps/action_items/urls.py` — router + template URL
- `apps/action_items/templates/action_items/action_item_list.html` — SPA mount template
- `apps/action_items/tests/test_views.py` — 12 view tests
- `config/urls.py` — wires action-items api + template URL

## Decisions Made

- **ACTN-07 via field omission, not via read_only_fields.** ActionItemUpdateSerializer's Meta.fields contains only [title, priority, due_date, assignee]. Posting scope/shop is silently ignored — DRF only validates and writes declared fields. Test `test_partial_update_cannot_change_scope_or_shop` asserts the behaviour.
- **List vs Read split.** ListSerializer omits notes/source_review nested data so the list endpoint stays inside the <=5-query budget. RetrieveSerializer adds them, and `get_queryset()` adds `prefetch_related("notes__author")` only on the retrieve action.
- **Notifications URL include left out (deviation from plan).** See deviations section below.
- **Layer 1 takes precedence over Layer 2.** With list_action_items already filtering Staff to SHOP-scope items, Staff GET on a BRAND item id returns 404 (object not in queryset) instead of 403. Both are valid blocks; the test accepts either.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed lazy notifications URL include from config/urls.py**

- **Found during:** Task 1 (verification step `python manage.py check`)
- **Issue:** The plan asked for `path("api/v1/", include("apps.notifications.urls"))` in `config/urls.py` as a "lazy string include — resolved on first request, NOT at import time" so the change could land before plan 13-05 creates the module. In practice Django's `include("module.path")` calls `import_module()` at the moment URL configs are loaded (during the boot-time URL resolver build), which fires on `python manage.py check`. The check failed with `ModuleNotFoundError: No module named 'apps.notifications.urls'`, blocking the verify step.
- **Fix:** Removed the include from this commit and added a comment block explaining that plan 13-05 will add it when it creates `apps/notifications/urls.py`. The action-items API include is unaffected and works today.
- **Files modified:** `config/urls.py`
- **Verification:** `python manage.py check` exits 0; the action-items router resolves correctly (`['^action-items/$', '^action-items/(?P<pk>[^/.]+)/$', ...]`).
- **Committed in:** `5b3e63a` (Task 1 commit)
- **Impact on 13-05:** 13-05 already owns `apps/notifications/urls.py` outright per the coordination note, so it is the natural place for the URL include too. No change to 13-05's scope.

**2. [Rule 1 - Bug] Fixed self-referential `source="author_id"` on serializer field**

- **Found during:** Task 1 (post-write proof-read)
- **Issue:** Initial draft of `ActionItemNoteSerializer` declared `author_id = serializers.IntegerField(source="author_id", read_only=True)`. DRF treats a `source=` equal to the field name as illegal (raises `AssertionError` at serializer build time when first accessed).
- **Fix:** Removed the `source=` argument; DRF infers the source from the field name.
- **Files modified:** `apps/action_items/serializers.py`
- **Committed in:** `5b3e63a`

**3. [Rule 1 - Lint/types] Mypy strict-mode adjustments to satisfy pre-commit**

- **Found during:** Task 1 commit (pre-commit mypy hook)
- **Issue:** Several strict-mypy errors:
  1. `ClassVar[list[Any]]` on viewset attributes was rejected as "Cannot override instance variable with class variable" (DRF declares them as instance vars on `APIView`/`GenericAPIView`).
  2. `request.user` is typed `User | AnonymousUser` while service functions take `User` only.
  3. `getattr(obj.author, "full_name", "")` triggered "Argument 3 incompatible with bool" because mypy infers the field type from getattr's third arg.
  4. `user.pk` is `int | None`, incompatible with `get_accessible_shop_ids(user_id: int)`.
- **Fix:** Switched viewset class attrs to plain assignments with `# noqa: RUF012` (matches the existing pattern in `apps/reviews/views.py`). Added narrow `# type: ignore[arg-type]` / `[union-attr]` comments only where DRF/auth typing forces our hand. Reworked the `getattr` calls into explicit `is None` guards. Added a `user.pk is not None` guard before the `get_accessible_shop_ids` call.
- **Files modified:** `apps/action_items/views.py`, `apps/action_items/serializers.py`
- **Verification:** Pre-commit mypy passes on the staged files; only a pre-existing error in someone else's uncommitted `apps/action_items/services/lifecycle.py` work remained, which is out of scope for this plan.
- **Committed in:** `5b3e63a`

---

**Total deviations:** 3 auto-fixed (1 Rule 3 - blocking; 2 Rule 1 - bug/lint)
**Impact on plan:** One change to a sibling plan's seam (13-05 now owns the notifications URL include) — coordinated by the existing coordination note. Other deviations are local correctness fixes.

## Issues Encountered

- Pre-commit ruff-format reformatted my files between attempts (cosmetic only). Standard hook-fix loop, expected.
- Three mypy iterations to satisfy strict-mode without disabling typing wholesale. Final form matches the established `apps/reviews/views.py` pattern.

## User Setup Required

None — all changes are server-side Django code, no env vars or external services touched.

## Next Phase Readiness

- **Plan 13-05** can now: create `apps/notifications/urls.py`, register its router, and add `path("api/v1/", include("apps.notifications.urls"))` to `config/urls.py`. The action-items include is already in place and unaffected.
- **Plan 13-06/07 (UI)** can implement Layer 3 (hide brand-scope filter and "Create brand action item" controls for Staff). The API surface is final:
  - `GET /api/v1/action-items/?status=&scope=&shop=&assignee=&from_date=&to_date=&search=&review=&page=&page_size=&ordering=`
  - `GET /api/v1/action-items/{pk}/`
  - `POST /api/v1/action-items/`
  - `PATCH /api/v1/action-items/{pk}/`
  - `POST /api/v1/action-items/{pk}/transition-status/`
  - `POST /api/v1/action-items/{pk}/add-note/`
  - Page renders at `/admin/org/action-items/` with mount root `#action-items-management-root` and `data-shops` / `data-team` JSON attributes pre-populated.
- **CI gate (ACTN-12) is now active** — any future selector change that breaks the <=5 query budget will fail `test_list_query_count_org_admin_le_5` and `test_list_query_count_staff_le_5`.

## Self-Check

Verifying claimed artifacts:
- `apps/action_items/serializers.py` — FOUND (5 + 2 input serializers)
- `apps/action_items/filters.py` — FOUND (ActionItemFilterSet)
- `apps/action_items/views.py` — FOUND (ActionItemViewSet + action_item_list_view)
- `apps/action_items/urls.py` — FOUND (router + template URL)
- `apps/action_items/templates/action_items/action_item_list.html` — FOUND (SPA mount root with `id="action-items-management-root"`)
- `apps/action_items/tests/test_views.py` — FOUND (12 tests)
- `config/urls.py` — MODIFIED (action-items api + template wired)
- Commit `5b3e63a` — FOUND
- Commit `18bf636` — FOUND
- `pytest apps/action_items/tests/test_views.py` — 12 passed
- `python manage.py check` — exits 0
- Router introspection — `['^action-items/$', '^action-items/(?P<pk>[^/.]+)/$', '^action-items/(?P<pk>[^/.]+)/add-note/$', '^action-items/(?P<pk>[^/.]+)/transition-status/$', ...]`

## Self-Check: PASSED

---
*Phase: 13-action-items-and-notifications*
*Completed: 2026-05-04*
