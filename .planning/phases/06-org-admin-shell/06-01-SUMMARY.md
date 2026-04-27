---
phase: 06-org-admin-shell
plan: "01"
subsystem: data-foundation
tags: [models, migrations, encryption, regions, shops, staff-access]
dependency_graph:
  requires: []
  provides:
    - apps.regions (Region model)
    - apps.shops (Shop model with encrypted fields)
    - accounts.StaffAccessScope
    - common.SequenceCounter
    - accounts migration 0003 (User+InvitationToken v02)
    - accounts migration 0004 (StaffAccessScope)
  affects:
    - apps.accounts (extended models)
    - apps.common (added SequenceCounter)
tech_stack:
  added:
    - django-fernet-encrypted-fields==0.4.0
    - django-sequences==3.0
    - cryptography==47.0.0 (transitive dep)
  patterns:
    - EncryptedTextField with null=True for empty-string compatibility
    - Django 6 CheckConstraint with condition= (not check=)
    - Expand-contract step 1: nullable CharField for InvitationToken.purpose
key_files:
  created:
    - apps/regions/models.py
    - apps/regions/apps.py
    - apps/regions/migrations/0001_initial.py
    - apps/regions/tests/factories.py
    - apps/regions/tests/test_models.py
    - apps/shops/models.py
    - apps/shops/apps.py
    - apps/shops/migrations/0001_initial.py
    - apps/shops/tests/factories.py
    - apps/shops/tests/test_models.py
    - apps/accounts/migrations/0003_user_invitationtoken_v02.py
    - apps/accounts/migrations/0004_staffaccessscope.py
    - apps/common/migrations/__init__.py
    - apps/common/migrations/0001_sequencecounter.py
  modified:
    - pyproject.toml
    - uv.lock
    - config/settings/base.py
    - config/settings/local.py
    - config/settings/test.py
    - config/settings/production.py
    - .pre-commit-config.yaml
    - apps/accounts/models.py
    - apps/accounts/tests/factories.py
    - apps/accounts/tests/test_models.py
    - apps/common/models.py
decisions:
  - EncryptedTextField requires null=True for empty-string compatibility (library returns None for empty string, DB NOT NULL constraint rejects it)
  - Django 6 renamed CheckConstraint check= parameter to condition=
  - Split accounts/0003 (User+Token) from accounts/0004 (StaffAccessScope) as planned — Django auto-merged them, manually split
  - Added django-fernet-encrypted-fields==0.4.0 and django-sequences==3.0 to pre-commit mypy hook additional_dependencies
  - Added S105 to ruff per-file-ignores for tests/** (encrypted field test uses literal token strings)
metrics:
  duration: "9 minutes"
  completed_date: "2026-04-27"
  tasks_completed: 3
  files_changed: 31
---

# Phase 6 Plan 01: v0.2 Data Foundation Summary

Install django-fernet-encrypted-fields==0.4.0 and django-sequences==3.0; scaffold Region and Shop apps with encrypted fields; extend User/InvitationToken; add StaffAccessScope with Django 6 CheckConstraint; create 5 ordered migrations.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Install packages and wire SALT_KEY settings | bee4d5e | pyproject.toml, config/settings/*.py, .pre-commit-config.yaml |
| 2 | Scaffold regions and shops apps with models, factories, tests | bee4d5e | apps/regions/*, apps/shops/* |
| 3 | Extend User+InvitationToken; add StaffAccessScope and SequenceCounter; create migrations | bee4d5e | apps/accounts/models.py, 5 migration files, apps/common/models.py |

Note: All three tasks were committed as a single atomic commit because the pre-commit hooks require the app modules to exist before the settings changes can be committed (mypy plugin initializes Django on hook run).

## Migration Chain

Final dependency order applied:

```
accounts/0001_initial
organisations/0001_initial
  └── regions/0001_initial
        └── shops/0001_initial
              └── accounts/0002_user_organisation_invitationtoken
                    └── accounts/0003_user_invitationtoken_v02 (User extensions + InvitationToken purpose/role)
                          └── accounts/0004_staffaccessscope (depends on: accounts/0003, regions/0001, shops/0001)
common/0001_sequencecounter (independent, no FK dependencies)
sequences/0001_initial, sequences/0002_alter_sequence_last (from django-sequences package)
```

Migration 0003 and 0004 were manually split from Django's auto-generated combined migration to ensure the dependency graph is correct: 0003 has no regions/shops dependencies; 0004 depends on both.

## SALT_KEY Pattern Per Settings File

| File | Value |
|------|-------|
| `base.py` | `env("FERNET_SALT_KEY", default="")` — empty string default for safety |
| `local.py` | `"dev-salt-key-do-not-use-in-production-32ch"` — hardcoded dev value |
| `test.py` | `"test-salt-key-for-unit-tests-only-32chars"` — hardcoded test value |
| `production.py` | `env("FERNET_SALT_KEY")` — required env var, no default |

The setting name is `SALT_KEY` (not `FERNET_KEYS`). Using `FERNET_KEYS` would silently fall back to Django's `SECRET_KEY`, breaking key rotation.

## django-sequences Integration

django-sequences 3.0 was installed and `sequences` added to INSTALLED_APPS. The package ran its own migrations (`sequences/0001_initial` and `sequences/0002_alter_sequence_last`) successfully, confirming Django 6 compatibility. The `SequenceCounter` model in `apps/common/` is a fallback insurance — it won't be needed if django-sequences works correctly (confirmed in Plan 02 smoke test).

## EncryptedTextField Import Path

The import path used throughout is:
```python
from encrypted_fields.fields import EncryptedTextField
```
NOT `fernet_encrypted_fields` (old package name). Verified with `grep -rn "fernet_encrypted_fields" apps/` returning no matches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Django 6 renamed CheckConstraint `check=` to `condition=`**
- **Found during:** Task 3, when running `makemigrations`
- **Issue:** `TypeError: CheckConstraint.__init__() got an unexpected keyword argument 'check'`
- **Fix:** Changed `check=` to `condition=` in `StaffAccessScope.Meta.constraints`
- **Files modified:** `apps/accounts/models.py`, `apps/accounts/migrations/0004_staffaccessscope.py`
- **Commit:** bee4d5e

**2. [Rule 1 - Bug] EncryptedTextField returns None for empty string, causing NOT NULL constraint failure**
- **Found during:** Task 2, when running tests
- **Issue:** `sqlite3.IntegrityError: NOT NULL constraint failed: shops_shop.google_refresh_token` — the library returns `None` when `get_prep_value("")` is called, bypassing the `default=""` setting
- **Fix:** Added `null=True` to both `google_refresh_token` and `api_key` fields in `Shop` model; updated `0001_initial.py` migration accordingly
- **Files modified:** `apps/shops/models.py`, `apps/shops/migrations/0001_initial.py`
- **Commit:** bee4d5e

**3. [Rule 3 - Blocking] pre-commit mypy hook missing new packages in its isolated env**
- **Found during:** Task 1 commit attempt
- **Issue:** `ModuleNotFoundError: No module named 'sequences'` in pre-commit's isolated mypy env
- **Fix:** Added `django-fernet-encrypted-fields==0.4.0` and `django-sequences==3.0` to mypy hook's `additional_dependencies` in `.pre-commit-config.yaml`
- **Files modified:** `.pre-commit-config.yaml`
- **Commit:** bee4d5e

**4. [Rule 3 - Blocking] ruff DJ001 warning on nullable CharField (expand-contract pattern)**
- **Found during:** Task 1+3 commit attempt
- **Issue:** ruff `DJ001: Avoid using null=True on string-based fields` on `InvitationToken.purpose` and `invited_for_role` — these are intentionally nullable for the expand-contract migration pattern
- **Fix:** Added `# noqa: DJ001 — expand-contract step 1, nullable for backfill` comments
- **Files modified:** `apps/accounts/models.py`
- **Commit:** bee4d5e

**5. [Rule 3 - Blocking] ruff S105 false positive on encrypted field test assertions**
- **Found during:** Task 2 commit attempt
- **Issue:** ruff `S105: Possible hardcoded password` on test string `"secret-token-abc"` in `test_shop_encrypted_fields_round_trip`
- **Fix:** Added `S105` to ruff per-file-ignores for `**/tests/**` in `pyproject.toml`
- **Files modified:** `pyproject.toml`
- **Commit:** bee4d5e

**6. [Planned - Migration Split] Django auto-merged accounts/0003 and accounts/0004**
- **Found during:** Task 3 migration generation
- **Issue:** Django auto-generated a single migration including both User/InvitationToken changes AND StaffAccessScope (because all were detected simultaneously)
- **Fix:** Manually split into two migrations as required by the plan
- **Commit:** bee4d5e

### Out of Scope (Pre-existing)

- `apps/common/tests/test_components.py::test_empty_state_renders_icon_title_desc_cta` — pre-existing failure on main branch, unrelated to this plan. Logged in `deferred-items.md`.

## Test Results

| Suite | Count | Result |
|-------|-------|--------|
| apps/regions/tests/ | 3 | PASS |
| apps/shops/tests/ | 3 | PASS |
| apps/accounts/tests/ | 76 | PASS |
| apps/common/tests/ (excluding pre-existing failure) | 10 | PASS |
| **Total** | **106** | **PASS** |

## Self-Check: PASSED

All key files verified to exist. Commit bee4d5e confirmed in git log. All acceptance criteria verified:
- django-fernet-encrypted-fields==0.4.0 in pyproject.toml
- django-sequences==3.0 in pyproject.toml
- SALT_KEY in base.py (2 occurrences: comment + assignment), test.py, local.py, production.py
- ENCRYPTED_FIELD_MODE in base.py
- apps.regions and apps.shops in base.py INSTALLED_APPS
- Region model with region_org_id_unique constraint
- EncryptedTextField imported from encrypted_fields.fields
- StaffAccessScope with staff_scope_xor_region_shop constraint
- SequenceCounter in apps/common/models.py
- regions and shops dependencies in accounts/0004
