---
phase: 03-organisation-management
plan: "01"
subsystem: permissions, email, test-infrastructure
tags: [permissions, email, testing, wave-0, scaffolding]
dependency_graph:
  requires:
    - apps/accounts/models.py (User.Role enum)
    - apps/organisations/models.py (Organisation, Status, OrgType)
    - apps/accounts/tests/factories.py (UserFactory, InvitationTokenFactory)
    - apps/organisations/tests/factories.py (OrganisationFactory)
  provides:
    - apps/accounts/permissions.py (IsSuperadmin DRF permission class)
    - apps/common/services/email.py (send_transactional_email helper)
    - apps/organisations/tests/conftest.py (shared Phase 3 fixtures)
    - apps/organisations/tests/test_selectors.py (xfail scaffolds)
    - apps/organisations/tests/test_services.py (xfail scaffolds)
    - apps/organisations/tests/test_views.py (xfail scaffolds)
  affects:
    - Plan 02 (implements selector scaffolds, turns xfail green)
    - Plan 03 (implements service scaffolds, turns xfail green)
    - Plan 04 (implements viewset scaffolds, turns xfail green)
tech_stack:
  added:
    - apps/common/services/ package (new)
    - apps/organisations/services/ package (new)
    - apps/organisations/selectors/ package (new)
  patterns:
    - IsSuperadmin extends DRF BasePermission, checks user.role == User.Role.SUPERADMIN
    - send_transactional_email renders .txt + .html templates, uses EmailMultiAlternatives
    - xfail(strict=False) for Wave 0 scaffolds — CI stays green, plans 02-05 remove markers
key_files:
  created:
    - apps/accounts/permissions.py
    - apps/accounts/tests/test_permissions.py
    - apps/common/services/__init__.py
    - apps/common/services/email.py
    - apps/common/tests/__init__.py
    - apps/common/tests/test_email_service.py
    - templates/emails/_test.html
    - templates/emails/_test.txt
    - apps/organisations/services/__init__.py
    - apps/organisations/selectors/__init__.py
    - apps/organisations/tests/conftest.py
    - apps/organisations/tests/test_selectors.py
    - apps/organisations/tests/test_services.py
    - apps/organisations/tests/test_views.py
  modified: []
decisions:
  - "dict[str, object] used for email context parameter type annotation to satisfy mypy strict mode"
  - "xfail(strict=False) chosen over strict=True so CI stays green while downstream plans implement features"
  - "Test fixture templates _test.html/_test.txt use underscore prefix to indicate test-only fixtures"
  - "Compound assertions (PT018) split into separate assert statements per ruff lint rules"
metrics:
  duration: "4 min"
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_created: 14
---

# Phase 3 Plan 1: Wave 0 Infrastructure Summary

One-liner: IsSuperadmin DRF permission class + send_transactional_email service + 33 xfail test scaffolds encoding Phase 3 behaviour contract.

## What Was Built

### IsSuperadmin Permission Class

**Location:** `apps/accounts/permissions.py`

**Signature:**
```python
class IsSuperadmin(BasePermission):
    message = "Superadmin role required."
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, "role", None) == User.Role.SUPERADMIN)
```

Importable as `from apps.accounts.permissions import IsSuperadmin`. Used by all Phase 3 viewsets via `permission_classes = [IsAuthenticated, IsSuperadmin]`.

### send_transactional_email Service

**Location:** `apps/common/services/email.py`

**Signature:**
```python
def send_transactional_email(
    *,
    to: list[str],
    subject: str,
    template_base: str,      # e.g. "emails/invitation" → renders .txt + .html
    context: dict[str, object],
    reply_to: list[str] | None = None,   # defaults to [settings.DEFAULT_REPLY_TO]
    tags: list[str] | None = None,       # emits X-SES-* headers when AWS_SES_CONFIGURATION_SET set
) -> None:
```

**Template resolution:** `{template_base}.txt` and `{template_base}.html` rendered via `render_to_string`. Both are attached — plain text as the body, HTML as an alternative.

**SES headers:** Only emitted when `tags` is provided AND `settings.AWS_SES_CONFIGURATION_SET` is set. Otherwise no SES-specific headers are added.

### Conftest Fixture Inventory (`apps/organisations/tests/conftest.py`)

| Fixture | Purpose |
|---------|---------|
| `_clear_throttle_cache` (autouse) | Clears throttle LocMemCache before each test to prevent rate-limit bleed |
| `superadmin` | Superadmin User at super@example.com |
| `org_admin` | Org Admin User at orgadmin@example.com |
| `client_logged_in` | Django test Client force-logged in as superadmin |
| `api_client_superadmin` | DRF APIClient force-authenticated as superadmin |
| `api_client_orgadmin` | DRF APIClient force-authenticated as org_admin |
| `anon_api_client` | Unauthenticated DRF APIClient |
| `three_orgs` | 3 organisations: Alpha Retail (ACTIVE), Beta Pharmacy (DISABLED), Gamma Restaurant (ACTIVE) |

### Scaffolded Tests — xfail Inventory

All scaffolded tests use `pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — implemented in Plan 0X")`. They import implementation symbols inside the test function body (not at module top) so collection succeeds even when the symbols don't exist yet.

**test_selectors.py** (8 tests — Plan 02 removes xfail):
- `test_list_organisations_returns_not_deleted_only` — ORGL-02
- `test_list_organisations_search_by_name_case_insensitive` — ORGL-03
- `test_list_organisations_search_by_email_case_insensitive` — ORGL-03
- `test_list_organisations_filter_by_status` — ORGL-04
- `test_list_organisations_filter_by_org_type` — ORGL-05
- `test_list_organisations_ordered_by_created_at_desc` — ORGL-02
- `test_list_organisations_fixed_query_count_ceiling` — ORGL-08 (≤3 queries for 20 rows)
- `test_get_organisation_detail_includes_activation_status_and_last_invited_at` — VORG-02

**test_services.py** (10 tests — Plan 03 removes xfail):
- `test_create_organisation_persists_row` — CORG-01
- `test_create_organisation_creates_invitation_token` — CORG-03
- `test_create_organisation_sends_invitation_email` — CORG-04
- `test_create_organisation_atomic_rollback_if_email_fails` — atomicity requirement
- `test_update_organisation_does_not_change_email` — EORG-02
- `test_update_organisation_modifies_other_fields` — EORG-03
- `test_disable_organisation_sets_status_disabled` — ENBL-01
- `test_enable_organisation_sets_status_active` — ENBL-02
- `test_delete_organisation_soft_deletes_not_hard` — DORG-02
- `test_adjust_store_allocation_updates_number_of_stores` — STOR-01/03

**test_views.py** (15 tests — Plans 02/03/04 remove xfail):
- `test_org_list_template_requires_auth` — ORGL-01 (Plan 02)
- `test_org_list_template_renders_200_for_superadmin` — ORGL-01 (Plan 02)
- `test_org_list_template_embeds_orgs_json` — ORGL-02 (Plan 02)
- `test_org_list_template_per_page_default_10` — ORGL-06 (Plan 02)
- `test_org_list_template_per_page_25_respected` — ORGL-06 (Plan 02)
- `test_org_list_template_per_page_invalid_falls_back_to_10` — ORGL-06 (Plan 02)
- `test_org_list_empty_state_renders_when_no_orgs` — ORGL-07 (Plan 02)
- `test_api_list_organisations_query_count_ceiling` — ORGL-08 (Plan 03, ≤7 queries)
- `test_api_create_organisation_returns_201` — CORG-01 (Plan 03)
- `test_api_create_organisation_duplicate_email_returns_400` — CORG-02 (Plan 03)
- `test_api_update_organisation_email_field_is_ignored` — EORG-02 (Plan 03)
- `test_api_delete_organisation_soft_deletes` — DORG-01/02 (Plan 03)
- `test_api_organisations_requires_authentication` — ORGL-01 (Plan 03)
- `test_api_organisations_rejects_non_superadmin` — ORGL-01 (Plan 03)
- `test_api_enable_disable_via_patch_status` — ENBL-01 (Plan 03)

## Verification Results

```
pytest apps/accounts/tests/test_permissions.py apps/common/tests/test_email_service.py apps/organisations/tests/ -q --no-cov
20 passed, 32 xfailed, 1 xpassed, 20 warnings in 0.33s
```

- 11 Wave 0 utility tests pass (5 permission + 6 email)
- 9 existing model tests still pass
- 33 scaffolded tests xfail (1 xpassed — `test_org_list_template_requires_auth` passes already because Phase 2 installed the placeholder redirect view)
- 0 failures, 0 errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type error on email service context parameter**
- **Found during:** Task 1 (pre-commit hook)
- **Issue:** `context: dict` triggers `mypy` error `Missing type parameters for generic type "dict" [type-arg]`
- **Fix:** Changed to `context: dict[str, object]`
- **Files modified:** `apps/common/services/email.py`
- **Commit:** bca790b (included in fix)

**2. [Rule 1 - Bug] Fixed PT018 compound assertion lint errors**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** ruff PT018 rule requires compound assertions (`assert a and b`) to be split into separate statements
- **Fix:** Split 7 compound assertions across test_selectors.py, test_services.py, and test_views.py
- **Files modified:** test_selectors.py, test_services.py, test_views.py
- **Commit:** fe09f67

## Self-Check: PASSED
