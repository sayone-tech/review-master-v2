---
phase: 03-organisation-management
verified: 2026-04-23T00:00:00Z
status: passed
score: 25/25 must-haves verified
re_verification: false
---

# Phase 3: Organisation Management Verification Report

**Phase Goal:** Full CRUD control plane: list, create, view, edit, enable/disable, delete, store allocation
**Verified:** 2026-04-23
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | IsSuperadmin permission class exists and rejects non-SUPERADMIN users | VERIFIED | `apps/accounts/permissions.py` has `class IsSuperadmin(BasePermission)` with `role == User.Role.SUPERADMIN` check; 5 unit tests pass |
| 2 | send_transactional_email() exists and sends multipart HTML+text email | VERIFIED | `apps/common/services/email.py` has full implementation with `EmailMultiAlternatives`, `attach_alternative`, SES header support; 6 unit tests pass |
| 3 | list_organisations() returns non-deleted orgs filtered/prefetched in ≤ 3 queries | VERIFIED | Selector uses `not_deleted().select_related().annotate_store_counts().prefetch_related(Prefetch(...to_attr="prefetched_tokens"))` |
| 4 | GET /admin/organisations/ renders 200 for superadmin; 302 for anonymous | VERIFIED | `@login_required` on `organisation_list` view; tested in `test_views.py` |
| 5 | OrganisationListSerializer exposes 12 fields including activation_status and last_invited_at | VERIFIED | `apps/organisations/serializers.py` lists all 12 fields exactly |
| 6 | POST /api/v1/organisations/ creates org + InvitationToken + invitation email atomically | VERIFIED | `create_organisation` is `@transaction.atomic`; calls `send_transactional_email`; InvitationToken created; rollback test passes |
| 7 | GET /api/v1/organisations/ lists non-deleted orgs with filters using pagination | VERIFIED | `OrganisationViewSet.get_queryset()` calls `list_organisations_selector`; `pagination_class = PageNumberPagination` |
| 8 | PATCH /api/v1/organisations/{id}/ updates allowed fields; email silently ignored | VERIFIED | `OrganisationUpdateSerializer` excludes email; `update_organisation` calls `data.pop("email", None)` |
| 9 | PATCH with status=DISABLED/ACTIVE toggles status | VERIFIED | `OrganisationUpdateSerializer` has status ChoiceField; `update_organisation` handles status in `_UPDATABLE_FIELDS` |
| 10 | DELETE /api/v1/organisations/{id}/ soft-deletes (status=DELETED, row remains) | VERIFIED | `perform_destroy` calls `delete_organisation(organisation=instance)` which calls `organisation.soft_delete()` |
| 11 | Unauthenticated returns 401/403; non-Superadmin returns 403 | VERIFIED | `permission_classes = [IsAuthenticated, IsSuperadmin]` on `OrganisationViewSet`; tests confirm |
| 12 | Invitation email renders org name, accept URL, 48h expiry in HTML and text | VERIFIED | `templates/emails/invitation.html` and `.txt` contain `{{ organisation.name }}`, `{{ accept_url }}`, `{{ expires_in_hours }}`, "Accept Invitation" |
| 13 | React widget mounts in #org-table-root; reads initial data from #org-data JSON blob | VERIFIED | `org-management.tsx` uses `createRoot(document.getElementById("org-table-root"))`; `useOrgs` reads `getElementById("org-data")` |
| 14 | DataTable renders 6 data columns + auto-emitted Actions column (ORGL-02) | VERIFIED | `OrgTable.tsx` `buildColumns()` returns 6 columns; `renderRowActions` prop triggers auto-emitted `<th aria-label="Actions">` in DataTable |
| 15 | Create modal validates 5 fields, calls POST, dispatches exact toast | VERIFIED | `CreateOrgModal.tsx` validates all fields; exact toast: "Organisation created. Invitation email sent to {email}." |
| 16 | Edit modal pre-fills fields; email disabled with helper text; dispatches "Organisation updated." toast | VERIFIED | `EditOrgModal.tsx` has `disabled` on email input; "Email cannot be changed after creation." helper; exact toast confirmed |
| 17 | View modal shows activation_status and last_invited_at; Resend button conditional | VERIFIED | `ViewOrgModal.tsx` renders activation status labels, `last_invited_at`; `{org.activation_status !== "active" && <button>Resend Invitation</button>}` |
| 18 | Disable modal (amber) calls PATCH {status: DISABLED}; toast "{name} has been disabled." | VERIFIED | `DisableConfirmModal.tsx` uses `variant="amber"`, calls `updateOrg(org.id, { status: "DISABLED" })` |
| 19 | Enable modal (blue) calls PATCH {status: ACTIVE}; toast "{name} has been enabled." | VERIFIED | `EnableConfirmModal.tsx` uses `variant="blue"`, calls `updateOrg(org.id, { status: "ACTIVE" })` |
| 20 | Delete modal (red) requires typing org name; calls DELETE; toast "{name} has been deleted." | VERIFIED | `DeleteConfirmModal.tsx` uses `variant="red"`, `requireTypeToConfirm={org.name}`, calls `deleteOrg(org.id)` |
| 21 | Store allocation modal: pre-filled input; amber warning below active_stores; 2-step confirm; toast "Store allocation updated to {n}." | VERIFIED | `StoreAllocationModal.tsx` has `tooLow` check with `role="alert"` warning; `ConfirmModal variant="blue"` confirm step; exact toast |
| 22 | After every successful mutation, table re-fetches via GET preserving filters, stripping page | VERIFIED | `useOrgs.ts` `refreshQueryString()` does `current.delete("page")`; `await refresh()` called in all 6 mutation handlers in entrypoint |
| 23 | All four notImplemented stubs in org-management.tsx replaced with real modal handlers | VERIFIED | No `notImplemented` calls remain; `setDisableRow`, `setEnableRow`, `setDeleteRow`, `setStoreRow` all wired |
| 24 | Vite config registers org-management entrypoint | VERIFIED | `vite.config.ts` has `"org-management": resolve(__dirname, "src/entrypoints/org-management.tsx")` |
| 25 | DRF router registered at /api/v1/organisations/ before app URL includes | VERIFIED | `config/urls.py` uses `SimpleRouter`; `path("", include(router.urls))` before `apps.organisations.urls` |

**Score:** 25/25 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/accounts/permissions.py` | IsSuperadmin DRF permission class | VERIFIED | Contains `class IsSuperadmin(BasePermission)` with exact role check |
| `apps/common/services/email.py` | send_transactional_email() per CLAUDE.md §12.4 | VERIFIED | Full implementation with SES header support |
| `apps/organisations/selectors/organisations.py` | list_organisations + get_organisation_detail + activation_status_for | VERIFIED | All 4 functions present with correct prefetch pattern |
| `apps/organisations/services/organisations.py` | create/update/enable/disable/delete/adjust_store_allocation | VERIFIED | All 6 service functions with `@transaction.atomic` on create |
| `apps/organisations/serializers.py` | OrganisationListSerializer + OrganisationCreateSerializer + OrganisationUpdateSerializer | VERIFIED | All 4 serializers present |
| `apps/organisations/views.py` | organisation_list (template) + OrganisationViewSet (DRF) | VERIFIED | Both present; ViewSet has `[IsAuthenticated, IsSuperadmin]` |
| `apps/organisations/urls.py` | Template view URL at /admin/organisations/ | VERIFIED | `path("admin/organisations/", organisation_list, name="organisation_list")` |
| `config/urls.py` | DRF router with OrganisationViewSet at api/v1/organisations | VERIFIED | SimpleRouter (acceptable deviation from DefaultRouter) |
| `templates/organisations/list.html` | Full list page with filter bar, table mount, empty state, pagination, JSON blob | VERIFIED | All required elements present |
| `templates/emails/invitation.html` | HTML invitation email with org name, accept URL, 48h expiry | VERIFIED | All template variables present; "Accept Invitation" CTA |
| `templates/emails/invitation.txt` | Plain-text invitation email | VERIFIED | All template variables present |
| `frontend/src/entrypoints/org-management.tsx` | Vite entrypoint mounting OrgManagement with all imports at top | VERIFIED | `createRoot` used; all imports at top; all modal handlers wired |
| `frontend/src/widgets/org-management/types.ts` | OrgRow interface and related types | VERIFIED | `export interface OrgRow` with all required fields |
| `frontend/src/widgets/org-management/api.ts` | createOrg, listOrgs, updateOrg, deleteOrg, getCsrfToken | VERIFIED | All 5 functions with `X-CSRFToken` header and `credentials: "same-origin"` |
| `frontend/src/widgets/org-management/useOrgs.ts` | useOrgs hook reading blob, managing refresh | VERIFIED | `getElementById("org-data")`, `window.location.search`, `current.delete("page")` |
| `frontend/src/widgets/org-management/OrgTable.tsx` | 6 data columns + row actions | VERIFIED | `buildColumns` returns 6 columns; `renderRowActions` wires RowActionsMenu |
| `frontend/src/widgets/org-management/CreateOrgModal.tsx` | Create modal with validation and exact toast | VERIFIED | Validates all 5 fields; exact success toast; exact duplicate email error text |
| `frontend/src/widgets/org-management/ViewOrgModal.tsx` | View modal with activation status and conditional Resend | VERIFIED | Shows pending/active/expired; Resend only when `activation_status !== "active"` |
| `frontend/src/widgets/org-management/EditOrgModal.tsx` | Edit modal with email disabled and exact toast | VERIFIED | Email input `disabled`; "Email cannot be changed after creation."; "Organisation updated." toast |
| `frontend/src/widgets/org-management/DisableConfirmModal.tsx` | Amber confirm modal calling updateOrg with status DISABLED | VERIFIED | `variant="amber"`, `updateOrg(org.id, { status: "DISABLED" })` |
| `frontend/src/widgets/org-management/EnableConfirmModal.tsx` | Blue confirm modal calling updateOrg with status ACTIVE | VERIFIED | `variant="blue"`, `updateOrg(org.id, { status: "ACTIVE" })` |
| `frontend/src/widgets/org-management/DeleteConfirmModal.tsx` | Red confirm modal with requireTypeToConfirm calling deleteOrg | VERIFIED | `variant="red"`, `requireTypeToConfirm={org.name}`, `deleteOrg(org.id)` |
| `frontend/src/widgets/org-management/StoreAllocationModal.tsx` | Two-step store allocation: input + blue confirm | VERIFIED | `tooLow` warning disables Update; `ConfirmModal variant="blue"` step 2 |
| `frontend/vite.config.ts` | org-management entrypoint registered | VERIFIED | `"org-management": resolve(__dirname, "src/entrypoints/org-management.tsx")` |
| `apps/organisations/tests/conftest.py` | Shared fixtures for all tests | VERIFIED | `superadmin`, `org_admin`, `client_logged_in`, `api_client_superadmin`, `api_client_orgadmin`, `anon_api_client`, `three_orgs` |
| `apps/organisations/tests/test_selectors.py` | 11 selector tests (8 original + 3 activation_status) | VERIFIED | 11 test functions; no xfail markers remaining |
| `apps/organisations/tests/test_services.py` | 12 service tests | VERIFIED | 12 test functions; no xfail markers remaining |
| `apps/organisations/tests/test_views.py` | 21 view tests (template + API) | VERIFIED | 21 test functions; no xfail markers remaining |
| `frontend/src/widgets/org-management/OrgTable.test.tsx` | 5 vitest tests | VERIFIED | 5 `it()` blocks |
| `frontend/src/widgets/org-management/CreateOrgModal.test.tsx` | 3 vitest tests | VERIFIED | 3 `it()` blocks |
| `frontend/src/widgets/org-management/DeleteConfirmModal.test.tsx` | 4 vitest tests | VERIFIED | 4 `it()` blocks |
| `frontend/src/widgets/org-management/StoreAllocationModal.test.tsx` | 4 vitest tests | VERIFIED | 4 `it()` blocks |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/common/services/email.py::send_transactional_email` | `django.core.mail.EmailMultiAlternatives` | `msg.attach_alternative + msg.send` | WIRED | `attach_alternative(html_body, "text/html")` present |
| `apps/accounts/permissions.py::IsSuperadmin.has_permission` | `User.Role.SUPERADMIN` | `getattr(user, "role", None) == User.Role.SUPERADMIN` | WIRED | Exact pattern present |
| `apps/organisations/services/organisations.py::create_organisation` | `apps/common/services/email.py::send_transactional_email` | `send_transactional_email(` inside `@transaction.atomic` | WIRED | Line 56 in services file |
| `apps/organisations/services/organisations.py::create_organisation` | `apps.accounts.models.InvitationToken` | `InvitationToken.objects.create(token_hash=InvitationToken.hash_token(raw_token))` | WIRED | Lines 52-55 |
| `apps/organisations/views.py::OrganisationViewSet.perform_create` | `apps/organisations/services/organisations.py::create_organisation` | `create_organisation(created_by=self.request.user, **serializer.validated_data)` | WIRED | Line 126 |
| `apps/organisations/views.py::OrganisationViewSet.perform_destroy` | `apps/organisations/services/organisations.py::delete_organisation` | `delete_organisation(organisation=instance)` | WIRED | Line 141 |
| `config/urls.py` | `apps.organisations.views.OrganisationViewSet` | `SimpleRouter.register(r"api/v1/organisations", OrganisationViewSet, ...)` | WIRED | Line 11 |
| `frontend/src/entrypoints/org-management.tsx` | `document.getElementById("org-data")` | `JSON.parse(el.textContent)` in `readInitialRows()` (useOrgs.ts) | WIRED | `useOrgs.ts` line 6 |
| `frontend/src/widgets/org-management/api.ts` | `/api/v1/organisations/` | `fetch()` with `credentials: "same-origin"` and `X-CSRFToken` header | WIRED | `const BASE = "/api/v1/organisations/"` |
| `frontend/src/widgets/org-management/CreateOrgModal.tsx` | `emitToast` | `"Organisation created. Invitation email sent to {email}."` | WIRED | Line 70 exact match |
| `frontend/src/widgets/org-management/useOrgs.ts` | `window.location.search` | `new URLSearchParams(window.location.search)` + `current.delete("page")` | WIRED | Lines 17-18 |
| `DisableConfirmModal.tsx` | `api.ts::updateOrg` | `updateOrg(org.id, { status: "DISABLED" })` | WIRED | Line 20 |
| `EnableConfirmModal.tsx` | `api.ts::updateOrg` | `updateOrg(org.id, { status: "ACTIVE" })` | WIRED | Line 20 |
| `DeleteConfirmModal.tsx` | `api.ts::deleteOrg` | `deleteOrg(org.id)` | WIRED | Line 20 |
| `StoreAllocationModal.tsx` | `api.ts::updateOrg` | `updateOrg(currentOrg.id, { number_of_stores: parsed })` | WIRED | Line 54 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ORGL-01 | 03-01, 03-02 | Superadmin sees org list at /admin/organisations | SATISFIED | `@login_required` view at that path; 200 for superadmin, 302 for anon |
| ORGL-02 | 03-02, 03-04 | Columns: Name (clickable), Type, Email, Stores, Status, Created, Actions | SATISFIED | 6 data columns in `buildColumns()`; Actions auto-emitted by DataTable via `renderRowActions` |
| ORGL-03 | 03-02 | Search by name or email (real-time, debounced) | SATISFIED | `list_organisations(search=...)` does `Q(name__icontains)\|Q(email__icontains)`; server-side via GET form (locked hybrid decision in 03-CONTEXT.md) |
| ORGL-04 | 03-02 | Filter by status | SATISFIED | `list_organisations(status=...)` filters by `Organisation.Status.values`; filter_bar with status_options |
| ORGL-05 | 03-02 | Filter by type | SATISFIED | `list_organisations(org_type=...)` filters by `Organisation.OrgType.values`; filter_bar with type_options |
| ORGL-06 | 03-02 | Paginated with rows-per-page selector 10/25/50/100 | SATISFIED | `PER_PAGE_OPTIONS = (10, 25, 50, 100)`; pagination.html has `name="per_page"` select |
| ORGL-07 | 03-02, 03-04 | Skeleton loading + empty state with CTA | SATISFIED | DataTable has `loading` prop with skeleton rows; `empty_state.html` with "No organisations yet" |
| ORGL-08 | 03-02 | Fixed query count regardless of result size | SATISFIED | ≤ 3 queries for list selector; ≤ 7 for API endpoint; `test_list_organisations_fixed_query_count_ceiling` asserts this |
| CORG-01 | 03-03, 03-04 | Open Create Organisation modal from list page header | SATISFIED | `CreateButtonBridge` listens to `#open-create-org` click; `CreateOrgModal` component |
| CORG-02 | 03-03, 03-04 | Create form accepts 5 fields with validation | SATISFIED | `OrganisationCreateSerializer` validates all fields; `CreateOrgModal` client-side validation |
| CORG-03 | 03-03, 03-04 | On create: modal closes, toast with email, list refreshes | SATISFIED | `onCreated` callback closes modal and calls `refresh()`; exact toast confirmed |
| CORG-04 | 03-03 | Invitation token + email sent atomically on create | SATISFIED | `create_organisation` is `@transaction.atomic`; creates `InvitationToken`; sends invitation email |
| VORG-01 | 03-04 | Open View Details modal by clicking org name or "View Details" in row menu | SATISFIED | Name column button calls `handlers.onOpenView`; RowActionsMenu "View Details" item calls same |
| VORG-02 | 03-02, 03-04 | Details modal shows all org fields + activation status + last invite timestamp | SATISFIED | `ViewOrgModal` renders all fields; `activation_status_for()` and `last_invited_at_for()` used |
| VORG-03 | 03-04 | "Resend Invitation" button only when not yet activated | SATISFIED | `{org.activation_status !== "active" && <button>Resend Invitation</button>}` in ViewOrgModal |
| EORG-01 | 03-04 | Open Edit modal with all fields pre-filled | SATISFIED | `EditOrgModal` uses `useEffect` to pre-fill from `org` prop |
| EORG-02 | 03-03, 03-04 | Email field disabled in edit; cannot be changed | SATISFIED | `OrganisationUpdateSerializer` excludes email; `update_organisation` pops email; EditOrgModal has `disabled` on email input |
| EORG-03 | 03-04 | On save: modal closes, "Organisation updated." toast, view refreshes | SATISFIED | `onUpdated` closes modal, calls `refresh()`; toast "Organisation updated." confirmed |
| ENBL-01 | 03-03, 03-05 | Disable via row actions with amber confirm popup; success toast | SATISFIED | `DisableConfirmModal` with `variant="amber"`, `updateOrg(org.id, { status: "DISABLED" })`, toast `"{name} has been disabled."` |
| ENBL-02 | 03-03, 03-05 | Enable via row actions with blue confirm popup; success toast | SATISFIED | `EnableConfirmModal` with `variant="blue"`, `updateOrg(org.id, { status: "ACTIVE" })`, toast `"{name} has been enabled."` |
| DORG-01 | 03-03, 03-05 | Delete via row actions; confirm by typing org name; success toast | SATISFIED | `DeleteConfirmModal` with `variant="red"`, `requireTypeToConfirm={org.name}`, `deleteOrg(org.id)`, toast `"{name} has been deleted."` |
| DORG-02 | 03-03 | Delete is soft-delete only | SATISFIED | `delete_organisation` calls `organisation.soft_delete()`; `perform_destroy` calls `delete_organisation`, NOT `instance.delete()` |
| STOR-01 | 03-03, 03-05 | Adjust Store Count via row actions; input shows current usage | SATISFIED | `StoreAllocationModal` shows "Currently using X of Y stores."; pre-filled input |
| STOR-02 | 03-05 | Amber warning + Update blocked when value below active_stores | SATISFIED | `tooLow = isInt && parsed < currentOrg.active_stores`; `data-testid="store-alloc-warning"` with `role="alert"`; `updateDisabled` blocks button |
| STOR-03 | 03-05 | Step 2 confirmation shows old and new count; blue ConfirmModal; success toast | SATISFIED | `ConfirmModal variant="blue"` with message showing old/new stores; toast `"Store allocation updated to {n}."` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `templates/organisations/list.html` | 29 | `#org-table-root` div is OUTSIDE the `{% if/else %}` block — React mounts even when Django shows the empty state | Info | Both empty states (Django template + React widget) render simultaneously initially; React would eventually show an empty table or skeleton. In practice the Django empty state shows for SSR and React re-renders after mount. Not a functional blocker. |
| `apps/organisations/views.py` | 64-67 | `orgs_json` passes a Python list (not JSON string) to template context; template uses `\|json_script` tag which handles serialization | Info | This is actually correct usage of Django's `json_script` template filter; no bug. |

### Human Verification Required

1. **Create Organisation end-to-end flow**
   - **Test:** Navigate to /admin/organisations/ as superadmin, click "Create Organisation", fill the form, submit
   - **Expected:** Modal closes, toast "Organisation created. Invitation email sent to {email}." appears, new row visible in table, invitation email arrives in MailHog
   - **Why human:** Cannot verify email delivery or toast UI behaviour programmatically without E2E browser testing

2. **Edit Organisation email disabled**
   - **Test:** Open Edit modal for an org; attempt to click the email field
   - **Expected:** Email field is visually greyed out and cannot be focused/typed in
   - **Why human:** Requires visual inspection and interaction testing

3. **Delete confirmation requires typing org name**
   - **Test:** Click Delete in row actions; verify Delete button stays disabled until exact org name is typed
   - **Expected:** Button becomes enabled only when typed name matches exactly
   - **Why human:** Interactive behaviour — button enable/disable state on keypress

4. **Store Allocation two-step flow**
   - **Test:** Click "Adjust Store Count", enter a value below `active_stores`, verify amber warning appears; enter valid value > current, click Update, verify Step 2 confirm modal shows old/new count
   - **Expected:** Amber warning visible; Step 2 shows "Change store allocation for {name} from {old} to {new}?"
   - **Why human:** Multi-step interactive flow requires browser testing

5. **Skeleton loading state on mutations**
   - **Test:** Submit a create/update and observe the table during the API call in-flight
   - **Expected:** Table shows skeleton rows while loading=true
   - **Why human:** Timing-dependent UI state

---

## Summary

Phase 3 goal is **fully achieved**. All 25 required capabilities are implemented and verifiably present in the codebase:

**Backend (Django):**
- `IsSuperadmin` permission class correctly gates all org API endpoints
- `send_transactional_email` service delivers multipart emails via Django backend
- All 6 service functions implement correct business rules (atomic create, soft delete, email stripping)
- DRF `OrganisationViewSet` registered at `/api/v1/organisations/` with full CRUD; query count ceiling tested
- Invitation email templates in both HTML and plain text with all required template variables
- 44 backend tests: 11 selector, 12 service, 21 view

**Frontend (React):**
- Vite entrypoint mounts widget into `#org-table-root`; reads initial rows from `#org-data` JSON blob
- DataTable renders 6 data columns; Actions column auto-emitted by DataTable widget
- All 5 modals (Create, View, Edit, and Plan 05's Disable/Enable/Delete/StoreAllocation) fully wired
- Zero `notImplemented` stubs remain in `org-management.tsx`
- All destructive modals call correct API functions (`updateOrg`/`deleteOrg`) and dispatch exact spec-required toast messages
- Post-mutation refresh uses `window.location.search` with page stripped
- 16 vitest tests across 4 test files

**Notable Deviation:** `config/urls.py` uses `SimpleRouter` instead of `DefaultRouter` as specified in the PLAN. This is an intentional and correct deviation — `SimpleRouter` avoids generating a browsable API root at `/` that would conflict with the existing home view. All API URL paths function identically.

---

_Verified: 2026-04-23_
_Verifier: Claude (gsd-verifier)_
