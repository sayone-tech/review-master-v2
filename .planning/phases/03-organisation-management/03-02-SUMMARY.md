---
phase: 03-organisation-management
plan: "02"
subsystem: organisations
tags: [selectors, serializers, template-view, pagination, read-path]
dependency_graph:
  requires: [03-01]
  provides: [list-organisations-selector, organisation-list-view, organisation-list-serializer, pagination-component]
  affects: [03-03, 03-04]
tech_stack:
  added: []
  patterns:
    - selectors-pattern (list_organisations, get_organisation_detail, activation_status_for, last_invited_at_for)
    - Prefetch(to_attr=prefetched_tokens) for N+1-safe invitation token access
    - json_script template filter for safe JSON embedding (list passed, not string)
    - per_page selector via DRF RetainQuerySet paginator
key_files:
  created:
    - apps/organisations/selectors/organisations.py
    - apps/organisations/serializers.py
    - apps/organisations/services/organisations.py
    - templates/organisations/list.html
    - templates/emails/invitation.html
    - templates/emails/invitation.txt
  modified:
    - apps/organisations/views.py
    - apps/organisations/tests/test_selectors.py
    - apps/organisations/tests/test_views.py
    - apps/organisations/tests/test_services.py
    - templates/components/pagination.html
    - config/urls.py
decisions:
  - json_script receives a Python list (not a JSON string) to avoid double-encoding
  - pagination.html uses has_previous/has_next guards instead of |default filter to prevent EmptyPage exceptions
  - org-table-root div placed outside the empty/non-empty conditional so React mount point is always present
  - per_page URL param preserved via _page_url_params() helper that strips page from GET copy
  - WAVE_0_API xfail markers removed from test_views.py because services/organisations.py and config/urls.py were pre-scaffolded (full implementation available)
metrics:
  duration_seconds: 515
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_modified: 12
---

# Phase 3 Plan 2: Organisation List — Read Path Summary

Replaced the placeholder `organisation_list` view with the full read-path: a selector with ≤ 3 DB queries, read-side serializers exposing 12 fields, a template view with filter/pagination, and an updated pagination component with per_page selector and URL parameter preservation.

## What Was Built

### Selector Contract (apps/organisations/selectors/organisations.py)

```python
def list_organisations(*, search="", status="", org_type="") -> QuerySet[Organisation]
def get_organisation_detail(*, organisation_id: int) -> Organisation
def activation_status_for(organisation: Organisation) -> str  # 'active'|'pending'|'expired'
def last_invited_at_for(organisation: Organisation) -> datetime | None
```

- `_base_queryset()` chains `.not_deleted()`, `.select_related("created_by")`, `.annotate_store_counts()`, and `Prefetch("invitation_tokens", to_attr="prefetched_tokens")` — always ≤ 2 queries (org + prefetch)
- `activation_status_for` reads `prefetched_tokens` attribute first (avoids extra query), falls back to live queryset if attribute not set

### Serializer Contract (apps/organisations/serializers.py)

`OrganisationListSerializer` exposes 12 fields: `id`, `name`, `org_type`, `email`, `address`, `number_of_stores`, `status`, `created_at`, `total_stores`, `active_stores`, `activation_status`, `last_invited_at`. `total_stores` and `active_stores` come from annotated queryset. `activation_status` and `last_invited_at` are `SerializerMethodField`.

Also includes `OrganisationCreateSerializer` and `OrganisationUpdateSerializer` (Plan 03 prep).

### Template View (apps/organisations/views.py)

`organisation_list` handles:
- `per_page` whitelist: `(10, 25, 50, 100)` — invalid values fall back to `10`
- `_page_url_params()` helper: copies GET params, sets `per_page`, strips `page`
- Passes Python list to template (not JSON string) so `json_script` avoids double-encoding
- Context: `page_obj`, `orgs_json`, `per_page`, `per_page_options`, `status_options`, `type_options`, `page_url_params`, `total_count`, `search`, `current_status`, `current_type`

Also adds `OrganisationViewSet` (Plan 03 scaffold) registered at `/api/v1/organisations/`.

### Template Structure (templates/organisations/list.html)

```
{% extends "base.html" %}
- H1 + Create Organisation button
- {% include "components/filter_bar.html" %}
- if count==0: {% include "components/empty_state.html" with title="No organisations yet" %}
- else: {% include "components/pagination.html" %}
- (always) <div id="org-table-root"> — React mount point
- {{ orgs_json|json_script:"org-data" }} — safe JSON embedding
- {% vite_asset 'src/entrypoints/org-management.tsx' %}
```

Key decision: `org-table-root` div moved outside the empty/non-empty conditional so the React component mount point is always present (React component handles its own empty state display if needed).

### Pagination Component (templates/components/pagination.html)

Changes from previous version:
- Wrapped entire nav in `{% if page_obj.paginator.count > 0 %}` — hides when empty
- Added per_page `<form>` with hidden inputs preserving `search`, `status`, `type`
- `<select name="per_page">` with `onchange="this.form.submit()"`
- Page links: `?{{ page_url_params }}&page=N` instead of `?page=N`
- Prev/next links guarded with `{% if page_obj.has_previous %}` (avoids `EmptyPage` exception that `|default` filter cannot catch)

## Tests

### Selector Tests (apps/organisations/tests/test_selectors.py)
- Removed `@WAVE_0` xfail markers from 8 existing tests
- Added 3 new tests: `test_activation_status_returns_pending_when_no_tokens`, `test_activation_status_returns_active_when_a_token_is_used`, `test_activation_status_returns_expired_when_latest_unused_token_is_past_expiry`
- **11 selector tests pass** including fixed query count ceiling (≤ 3 queries for 20 rows)

### View Tests (apps/organisations/tests/test_views.py)
- Removed `@WAVE_0_TPL` markers from 7 existing template tests
- Added 2 new tests: `test_org_list_filter_by_status_returns_filtered_orgs`, `test_org_list_pagination_preserves_filter_params`
- WAVE_0_API markers removed because OrganisationViewSet + services were pre-scaffolded and fully operational
- **21 view tests pass** (9 template + 12 API)

### Total: 53 organisation tests pass (9 model + 11 selector + 12 service + 21 view)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pagination.html uses has_previous/has_next guards instead of |default filter**
- **Found during:** Task 2 initial test run
- **Issue:** `{{ page_obj.previous_page_number|default:1 }}` raises `EmptyPage` exception before `|default` can intercept it
- **Fix:** Changed to `{% if page_obj.has_previous %}{{ page_obj.previous_page_number }}{% else %}1{% endif %}` pattern
- **Files modified:** templates/components/pagination.html

**2. [Rule 1 - Bug] json_script double-encoding issue**
- **Found during:** Task 2 test for embedded JSON
- **Issue:** Passing pre-serialized JSON string to `json_script` filter double-encodes it (string becomes JSON-encoded string)
- **Fix:** Pass Python list to template context; `json_script` handles serialization
- **Files modified:** apps/organisations/views.py

**3. [Rule 2 - Missing functionality] org-table-root outside conditional**
- **Found during:** Task 2 test `test_org_list_template_renders_200_for_superadmin`
- **Issue:** `id="org-table-root"` was only in the non-empty branch; test expected it present without creating orgs
- **Fix:** Moved div outside the conditional; React component handles its own empty/non-empty rendering
- **Files modified:** templates/organisations/list.html

**4. [Rule 1 - Bug] pagination test assertion substring issue**
- **Found during:** Task 2 test run
- **Issue:** `assert "page=" not in params` was failing because "per_page=" contains "page=" as substring
- **Fix:** Used `urllib.parse.parse_qs` to check `"page" not in parsed` (key-based check)
- **Files modified:** apps/organisations/tests/test_views.py

### Scaffolded Plan 03 Code Included

The pre-commit hook and pre-existing scaffolding created/modified several Plan 03 files that were already prepared. These were included in the Task 2 commit as they're required for `views.py` imports to resolve and the API tests to pass:
- `apps/organisations/services/organisations.py` — full create/update/delete services
- `config/urls.py` — OrganisationViewSet registered at `/api/v1/organisations/`
- `apps/organisations/tests/test_services.py` — WAVE_0 markers removed (services implemented)
- `apps/organisations/tests/test_views.py` — WAVE_0_API markers removed (API tests pass)
- `templates/emails/invitation.html` and `invitation.txt` — email templates for invitations

## Self-Check: PASSED
