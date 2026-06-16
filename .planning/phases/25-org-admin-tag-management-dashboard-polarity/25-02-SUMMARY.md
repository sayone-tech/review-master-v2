---
phase: 25-org-admin-tag-management-dashboard-polarity
plan: "02"
subsystem: reviews/tag-management/api
tags: [canonical-tags, drf, viewsets, permissions, tdd, templates, sidebar]
dependency_graph:
  requires:
    - 25-01 (rename_canonical_tag, create_merge_job, list_canonical_tags_for_org, TagMergeJob model)
  provides:
    - OrgCanonicalTagViewSet (list + rename action + merge action)
    - TagMergeJobViewSet (active poll + dismiss action)
    - OrgCanonicalTagReadSerializer / RenameSerializer / TagMergeJobSerializer
    - tags_page_view (@org_admin_required, renders #tag-management-root)
    - /admin/org/tags/ template URL
    - /api/v1/reviews/canonical-tags/ and /api/v1/reviews/tag-merge-jobs/ routes
    - Staff-gated Tags nav item in sidebar_org.html
  affects:
    - apps/reviews/serializers.py (3 new serializers)
    - apps/reviews/views.py (OrgCanonicalTagViewSet, TagMergeJobViewSet, tags_page_view)
    - apps/reviews/urls.py (tags page URL)
    - config/urls.py (canonical-tags + tag-merge-jobs registered before ReviewViewSet)
    - templates/org-admin/tags.html (new template)
    - templates/partials/sidebar_org.html (Tags nav item)
    - apps/reviews/tests/test_views.py (7 new tests)
tech_stack:
  added: []
  patterns:
    - TDD RED-GREEN cycle (7 failing tests → 7 passing)
    - IsOrgAdmin permission (not IsOrgScoped) — Staff 403 (D-01)
    - @org_admin_required on template view — not @login_required (Staff redirect)
    - DefaultPageNumberPagination + OrderingFilter on list viewset (§8)
    - CaptureQueriesContext query-count ceiling ≤3 (§6.9)
    - mixins.ListModelMixin + viewsets.GenericViewSet (AuditLogViewSet analog)
    - Router order fix — canonical-tags before ReviewViewSet in config/urls.py
    - Staff-gated nav item pattern from sidebar_org.html ({% if user.role != "STAFF_ADMIN" %})
key_files:
  created:
    - templates/org-admin/tags.html
  modified:
    - apps/reviews/serializers.py (OrgCanonicalTagReadSerializer, RenameSerializer, TagMergeJobSerializer)
    - apps/reviews/views.py (OrgCanonicalTagViewSet, TagMergeJobViewSet, tags_page_view)
    - apps/reviews/urls.py (tags page URL, removed local DRF router)
    - config/urls.py (canonical-tags + tag-merge-jobs routes added before ReviewViewSet)
    - templates/partials/sidebar_org.html (Tags nav item under STAFF_ADMIN guard)
    - apps/reviews/tests/test_views.py (7 new tests + 2 additional imports)
decisions:
  - D-01: IsOrgAdmin (not IsOrgScoped) on both viewsets; @org_admin_required (not @login_required) on tags_page_view — Staff excluded at both API + template layer
  - Router order: canonical-tags/tag-merge-jobs registered before ReviewViewSet in config/urls.py to prevent PK-shadowing (/api/v1/reviews/<pk>/ matching /canonical-tags/)
  - active/ endpoint returns null (not 404) when no active job exists — simpler polling contract
  - org_admin_required decorator redirects Staff to /login/ (verified by test_tags_page_staff_redirected)
  - Template path uses existing org-admin/ (hyphen) convention, not org_admin/ (underscore)
metrics:
  duration: "~9 minutes"
  completed: "2026-06-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 6
---

# Phase 25 Plan 02: Tag Management API + Template Layer Summary

**One-liner:** OrgCanonicalTagViewSet (list/rename/merge) + TagMergeJobViewSet (active/dismiss) + @org_admin_required tags page + Staff-gated sidebar nav, all with IsOrgAdmin permission and ≤3-query list endpoint.

## What Was Built

### Task 1: Wave 0 view tests (RED) + serializers + viewsets + URLs (commit: f965e34)

**7 RED tests written first in `apps/reviews/tests/test_views.py`:**
1. `test_canonical_tags_list_query_count` — ≤3 queries, 20 tags (§6.9)
2. `test_canonical_tags_ordering` — `?ordering=label` + `?ordering=-review_count`
3. `test_merge_409_when_active_job` — POST merge with PENDING job → 409
4. `test_tag_merge_job_active_endpoint` — active/ cross-org isolation (T-25-AC1b)
5. `test_tag_merge_job_dismiss` — dismiss/ sets dismissed=True
6. `test_tags_page_staff_redirected` — Staff GET /admin/org/tags/ → redirect
7. `test_tags_page_org_admin_ok` — ORG_ADMIN GET /admin/org/tags/ → 200

**`apps/reviews/serializers.py`** — 3 new serializers:
- `OrgCanonicalTagReadSerializer`: id, label, polarity_type, review_count, first_seen (=created_at alias)
- `RenameSerializer`: label CharField(min_length=1, max_length=100) — input only
- `TagMergeJobSerializer`: id, status, processed, total, source_label, target_label, error_message, dismissed

**`apps/reviews/views.py`** — 3 new view classes:
- `OrgCanonicalTagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet)`: IsOrgAdmin, DefaultPageNumberPagination, OrderingFilter on [label, review_count, created_at], ordering=["-review_count"]; `rename` action (→400 on dup); `merge` action (→201/409 conflict/404 cross-org)
- `TagMergeJobViewSet(viewsets.GenericViewSet)`: IsOrgAdmin, org-scoped get_queryset(); `active` detail=False action returning most-recent non-dismissed PENDING/IN_PROGRESS job or null; `dismiss` action setting dismissed=True
- `tags_page_view`: @org_admin_required decorator, renders `org-admin/tags.html`

**`config/urls.py`** — Router order fix: `canonical-tags` and `tag-merge-jobs` registered BEFORE `reviews` to prevent the ReviewViewSet's `<pk>` pattern from swallowing these routes.

**`apps/reviews/urls.py`** — Simplified: tags page URL only (DRF routes in config/urls.py).

**`templates/org-admin/tags.html`** — New template extending base_org.html with `<div id="tag-management-root"></div>`.

All 7 tests turn GREEN.

### Task 2: ORG_ADMIN-only tags page view + tags.html + Staff redirect tests

Covered by Task 1 TDD (both page tests written and implemented in the same commit). Verification:
- `test_tags_page_staff_redirected` → Staff (StaffAdminFactory) → 302 redirect
- `test_tags_page_org_admin_ok` → ORG_ADMIN (OrgAdminFactory, django.test.Client.force_login) → 200
- `@org_admin_required` on the view (NOT `@login_required`)
- `/admin/org/tags/` resolves to `org_tags_page`

### Task 3: Staff-gated Tags sidebar nav item (commit: b1f55c3)

Added to `templates/partials/sidebar_org.html` after the Activity Log item:
```html
{% if user.role != "STAFF_ADMIN" %}
  {% include "partials/_nav_item.html" with href="/admin/org/tags/" icon="tags" label="Tags" %}
{% endif %}
```
Belt-and-braces UI layer (D-01). Authoritative defense is @org_admin_required + IsOrgAdmin.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Router URL ordering: canonical-tags shadowed by ReviewViewSet**
- **Found during:** Task 1 (GREEN phase — tests showed 404 on /api/v1/reviews/canonical-tags/)
- **Issue:** The SimpleRouter registered `api/v1/reviews` first in `config/urls.py`. DRF's router pattern for `ReviewViewSet` included `api/v1/reviews/(?P<pk>[^/.]+)/` which matched `/canonical-tags/` as pk="canonical-tags", returning a 404 (no review found)
- **Fix:** Moved `OrgCanonicalTagViewSet` and `TagMergeJobViewSet` registrations in `config/urls.py` to appear BEFORE `ReviewViewSet`. Also removed the local SimpleRouter from `apps/reviews/urls.py` (it was redundant and the ordering could not be enforced from there)
- **Files modified:** `config/urls.py`, `apps/reviews/urls.py`
- **Commit:** f965e34

**2. [Rule 1 - Bug] Template path convention: org_admin vs org-admin**
- **Found during:** Task 2 (implementation)
- **Issue:** Plan specified `templates/org_admin/tags.html` (underscore) but the existing project convention uses `templates/org-admin/` (hyphen, verified by `templates/org-admin/audit-log.html`)
- **Fix:** Created template at `templates/org-admin/tags.html` and updated `tags_page_view` to render `"org-admin/tags.html"`
- **Files modified:** `apps/reviews/views.py`, `templates/org-admin/tags.html`
- **Commit:** f965e34

## Known Stubs

None. All endpoints are fully implemented calling 25-01 services/selectors. No hardcoded empty values or placeholder text in API responses.

## Threat Surface Scan

New surfaces introduced:
- `GET /api/v1/reviews/canonical-tags/` — org-scoped (IsOrgAdmin), paginated, Staff 403
- `PATCH /api/v1/reviews/canonical-tags/{id}/rename/` — org-scoped via get_object() + IsOrgAdmin
- `POST /api/v1/reviews/canonical-tags/{id}/merge/` — org-scoped, 409 on active job, 404 on cross-org target
- `GET /api/v1/reviews/tag-merge-jobs/active/` — scoped via get_queryset(organisation_id=...), returns null for no job
- `PATCH /api/v1/reviews/tag-merge-jobs/{id}/dismiss/` — org-scoped via get_object() → 404 cross-org

All mitigations from the plan's threat model are implemented (T-25-AC1, T-25-AC1b, T-25-AC3, T-25-V1).

## Self-Check: PASSED

Files created/exist:
- `templates/org-admin/tags.html` FOUND
- `apps/reviews/serializers.py` FOUND (3 new serializers)
- `apps/reviews/views.py` FOUND (OrgCanonicalTagViewSet, TagMergeJobViewSet, tags_page_view)

Commits verified:
- f965e34: Task 1+2 — serializers, viewsets, URLs, template, 7 tests GREEN
- b1f55c3: Task 3 — Staff-gated sidebar nav item

Acceptance criteria verified:
- `grep -E "def test_(canonical_tags_list_query_count|...)" apps/reviews/tests/test_views.py` → 5 matches
- `grep -n "class OrgCanonicalTagViewSet" apps/reviews/views.py` → line 466
- `grep -n "class TagMergeJobViewSet" apps/reviews/views.py` → line 546
- `grep -n "IsOrgAdmin" apps/reviews/views.py` → matches (not IsOrgScoped for new viewsets)
- `/api/v1/reviews/tag-merge-jobs/active/` resolves → tag-merge-jobs-active
- `/admin/org/tags/` resolves → org_tags_page
- `pytest apps/reviews/tests/test_views.py -k "canonical_tags or tag_merge_job or merge_409 or tags_page"` → 7 PASSED
- `grep -n 'href="/admin/org/tags/"' templates/partials/sidebar_org.html` → match (inside STAFF_ADMIN guard)
- `python manage.py check` → no issues
