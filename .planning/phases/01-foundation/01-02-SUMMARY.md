---
phase: "01-foundation"
plan: "02"
subsystem: "data-models"
tags: ["models", "migrations", "accounts", "organisations", "auth", "invitations"]
dependency_graph:
  requires: ["01-01"]
  provides: ["User model", "Organisation model", "InvitationToken model", "accounts migrations", "organisations migrations"]
  affects: ["all subsequent phases"]
tech_stack:
  added: []
  patterns: ["AbstractBaseUser", "PermissionsMixin", "TextChoices enums", "custom QuerySet", "soft-delete", "SHA-256 token hashing", "TimestampedModel", "ClassVar type annotations"]
key_files:
  created:
    - "apps/accounts/models.py"
    - "apps/accounts/managers.py"
    - "apps/accounts/apps.py"
    - "apps/accounts/admin.py"
    - "apps/accounts/migrations/0001_initial.py"
    - "apps/accounts/migrations/0002_user_organisation_invitationtoken.py"
    - "apps/accounts/tests/factories.py"
    - "apps/accounts/tests/test_models.py"
    - "apps/organisations/models.py"
    - "apps/organisations/managers.py"
    - "apps/organisations/apps.py"
    - "apps/organisations/admin.py"
    - "apps/organisations/migrations/0001_initial.py"
    - "apps/organisations/tests/factories.py"
    - "apps/organisations/tests/test_models.py"
  modified:
    - "config/settings/test.py"
    - "pyproject.toml"
decisions:
  - "User.organisation FK deferred to 0002 migration to avoid circular dependency (accounts 0001 has no org FK; organisations 0001 depends on accounts 0001; accounts 0002 then adds FK)"
  - "annotate_store_counts() is Phase 1 stub returning zeros; Phase 2 updates it with real Count('stores') after Store model exists"
  - "InvitationToken uses SHA-256 for token hashing, not TimestampSigner directly (hash stored in DB)"
  - "ClassVar annotations added to Meta.ordering and Meta.indexes to satisfy ruff RUF012"
  - "mypy overrides added for factory.* and apps.*.tests.* modules due to missing factory-boy stubs"
metrics:
  duration: "12 minutes"
  completed_date: "2026-04-22"
  tasks_completed: 3
  files_created: 15
  files_modified: 2
---

# Phase 01 Plan 02: Core Data Models Summary

Three core data models created with proper migration ordering — `accounts.User`, `organisations.Organisation`, and `accounts.InvitationToken` — plus full test coverage and factory support.

## What Was Built

### Migration Graph (Critical Ordering)

```
accounts/0001_initial
  └── Creates User model WITHOUT organisation FK
      (no circular dependency here)

organisations/0001_initial
  └── Depends on: accounts/0001_initial (via swappable_dependency)
      Creates Organisation model with created_by FK to accounts.User

accounts/0002_user_organisation_invitationtoken
  └── Depends on: accounts/0001_initial + organisations/0001_initial
      AddField: User.organisation FK (null=True, SET_NULL)
      CreateModel: InvitationToken
```

**Why the FK is deferred to 0002:** Django's `AUTH_USER_MODEL` must be created before any other model references it. If `User` had the `organisation` FK in its first migration, Django would need `organisations` to exist first — but `organisations` needs `accounts` first. This circular dependency is resolved by splitting into two migrations (RESEARCH.md Pitfall 2).

### User Model (`apps/accounts/models.py`)

- Extends `AbstractBaseUser`, `PermissionsMixin`, `TimeStampedModel`
- `Role` enum: `SUPERADMIN`, `ORG_ADMIN`, `STAFF_ADMIN`
- `organisation` FK: nullable, `SET_NULL` on organisation delete
- `UserManager` with `create_user` and `create_superuser`
- Email normalization (lowercase domain) via `BaseUserManager.normalize_email`

### Organisation Model (`apps/organisations/models.py`)

- `Status` enum: `ACTIVE`, `DISABLED`, `DELETED`
- `OrgType` enum: `RETAIL`, `RESTAURANT`, `PHARMACY`, `SUPERMARKET`
- `soft_delete()` method: sets `status=DELETED`, does not remove row
- Custom `OrganisationQuerySet` with: `active()`, `disabled()`, `deleted()`, `not_deleted()`, `annotate_store_counts()` (Phase 1 stub)
- Composite indexes: `(status, created_at)` and `(org_type, status)`

### InvitationToken Model (`apps/accounts/models.py`)

- FK to `organisations.Organisation` (CASCADE)
- OneToOne to `accounts.User` (optional, SET_NULL)
- `token_hash`: 64-char SHA-256 hex digest, unique
- `expires_at`: defaults to 48h from creation via `_default_invitation_expiry()`
- `is_expired` property: `timezone.now() > self.expires_at`
- `hash_token()` classmethod: `hashlib.sha256(raw_token.encode()).hexdigest()`

## Test Coverage

| Module | Tests |
|--------|-------|
| User model + UserManager | 6 tests |
| User.organisation FK | 3 tests |
| InvitationToken | 5 tests |
| Organisation model | 9 tests |
| Common (from plan 01-03) | 5 tests |
| **Total** | **28+ tests passing** |

## Factory Usage for Downstream Phases

```python
# User with no organisation (superadmin pattern)
user = UserFactory()  # organisation=None by default

# Org Admin user
from apps.organisations.tests.factories import OrganisationFactory
org = OrganisationFactory()
org_admin = UserFactory(organisation=org, role=User.Role.ORG_ADMIN)

# Invitation token
from apps.accounts.tests.factories import InvitationTokenFactory
token = InvitationTokenFactory(organisation=org)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] RUF012 ClassVar annotations on model Meta**
- **Found during:** Task 2 + Task 3 pre-commit check
- **Issue:** ruff RUF012 requires `ClassVar` annotation on mutable class attributes like `ordering` and `indexes` inside `Meta` classes
- **Fix:** Added `from typing import ClassVar` and annotated both `ordering: ClassVar[list[str]]` and `indexes: ClassVar[list[models.Index]]`
- **Files modified:** `apps/organisations/models.py`, `apps/accounts/models.py`
- **Commit:** ae73d17, 0f4bfdc

**2. [Rule 2 - Missing Critical] mypy overrides for factory-boy stubs**
- **Found during:** Task 1 pre-commit check
- **Issue:** factory-boy lacks mypy stubs, causing `import-not-found` errors
- **Fix:** Added `[[tool.mypy.overrides]] module = ["factory.*"] ignore_missing_imports = true` and test module override to pyproject.toml
- **Files modified:** `pyproject.toml`
- **Commit:** pre-commit auto-fixed (included in Task 1 context)

**3. [Rule 1 - Bug] Django get_or_create factory pattern prevented IntegrityError tests**
- **Found during:** Task 1 and Task 2
- **Issue:** `UserFactory(email="dup@...")` with `django_get_or_create = ("email",)` returns existing record instead of raising IntegrityError
- **Fix:** Changed duplicate-email tests to use `User.objects.create_user()` / `Organisation.objects.create()` directly
- **Files modified:** `apps/accounts/tests/test_models.py`, `apps/organisations/tests/test_models.py`

**4. [Rule 1 - Bug] `timezone.datetime` type annotation error**
- **Found during:** Task 3 pre-commit
- **Issue:** `def _default_invitation_expiry() -> timezone.datetime` — `timezone.datetime` is not a valid type; it's not exported from `django.utils.timezone`
- **Fix:** Changed to `from datetime import datetime` and return type `-> datetime`
- **Files modified:** `apps/accounts/models.py`
- **Commit:** 0f4bfdc

**5. [Rule 3 - Blocking] OrganisationQuerySet type annotations conflicting ruff/mypy**
- **Found during:** Task 2 pre-commit
- **Issue:** `models.QuerySet["Organisation"]` caused ruff to remove the `Organisation` import (considered unused), leaving mypy with undefined name
- **Fix:** Used `models.QuerySet` (no generic param) + `# type: ignore[type-arg]` for ruff compatibility + `# type: ignore[no-any-return]` on `annotate()` return
- **Files modified:** `apps/organisations/managers.py`

## Self-Check: PASSED

All key files verified to exist:
- apps/accounts/models.py - FOUND
- apps/accounts/managers.py - FOUND
- apps/accounts/migrations/0001_initial.py - FOUND
- apps/accounts/migrations/0002_user_organisation_invitationtoken.py - FOUND
- apps/organisations/models.py - FOUND
- apps/organisations/managers.py - FOUND
- apps/organisations/migrations/0001_initial.py - FOUND

Commits verified:
- ae73d17: FOUND (organisations app)
- 0f4bfdc: FOUND (accounts 0002 + InvitationToken)
