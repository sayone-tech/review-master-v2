---
phase: 09-team
plan: "01"
subsystem: team-foundation
tags: [migration, services, selectors, tdd, team-management]
dependency_graph:
  requires: [06-01, 06-02, 07-01, 08-01]
  provides: [team-service-layer, team-selectors, migration-0005]
  affects: [09-02, 09-03, 09-04, 09-05]
tech_stack:
  added: []
  patterns: [expand-contract-migration, services-selectors, tdd-red-green, prefetch-to-attr, last-manager-guard, session-flush-best-effort]
key_files:
  created:
    - apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py
    - apps/accounts/services/team.py
    - apps/accounts/selectors/team.py
    - apps/accounts/exceptions.py
    - apps/accounts/selectors/__init__.py
    - apps/accounts/tests/test_migrations.py
    - apps/accounts/tests/test_services_team.py
    - apps/accounts/tests/test_selectors_team.py
    - templates/emails/team_invitation.html
    - templates/emails/team_invitation.txt
    - templates/emails/team_invitation_resent.html
    - templates/emails/team_invitation_resent.txt
  modified:
    - apps/accounts/models.py
    - apps/accounts/forms.py
    - apps/accounts/tests/conftest.py
    - apps/accounts/tests/factories.py
    - apps/accounts/tests/test_models.py
    - apps/organisations/services/organisations.py
decisions:
  - "Migration 0005: RunPython backfill BEFORE AlterField NOT NULL — execution order in operations list guarantees no IntegrityError"
  - "resend_team_invitation nulls out old token's invited_user before creating new token — required to avoid OneToOneField uniqueness violation (Pitfall 4)"
  - "last-manager guard counts active ORG_ADMINs via .exclude(pk=member.pk) — disabled managers don't protect the last-active-manager invariant"
  - "Selector uses to_attr='prefetched_scopes' (not 'access_scopes') — distinct name avoids shadowing the relation manager with a plain list"
  - "Email send is caller's responsibility in invite_member/resend — decouples email failure from DB state rollback"
  - "Session flush is best-effort (try/except) — is_active=False is the authoritative gate, flush is optional for instant termination"
  - "Placeholder email templates created inline (5 lines each) — Plan 03 overwrites with production templates"
  - "test_migrations.py uses mock-based testing (not raw SQL to bypass NOT NULL) — SQLite enforces NOT NULL even with raw SQL update"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-29T18:51:09Z"
  tasks_completed: 3
  files_changed: 19
---

# Phase 09 Plan 01: Team Foundation (Data Migration + Services + Selectors) Summary

**One-liner:** Migration 0005 (backfill purpose=ORG_ADMIN, NOT NULL constraint) + 8-function team service layer + N+1-safe team selectors with ≤4-query ceiling for 20 staff x 3 scopes.

---

## What Was Built

### Migration 0005 — Expand-Contract Step 2

`apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py` implements the second step of the expand-contract pattern started in Phase 6:

1. `RunPython(backfill_purpose)` — sets `purpose='ORG_ADMIN'` and `invited_for_role='ORG_ADMIN'` on all rows where `purpose IS NULL`
2. `AlterField` — removes `null=True` from `purpose`, making it NOT NULL
3. `AlterField` — removes `null=True` from `invited_for_role`, making it NOT NULL

Declaration order in `operations` is execution order. RunPython runs first within a single transaction, guaranteeing zero NULL rows before the NOT NULL constraint is applied.

### Team Service Layer

`apps/accounts/services/team.py` exports 8 functions:

| Function | What it does |
|----------|-------------|
| `invite_member` | Creates `User(is_active=False)` + `InvitationToken(purpose=TEAM_MEMBER)` + `StaffAccessScope` rows atomically |
| `activate_team_member` | Updates existing User (set_password, is_active=True, accepted_at) + marks token used; select_for_update race guard |
| `update_member` | Replaces full_name, role, and access scopes (delete-all + bulk_create) atomically |
| `enable_member` | Sets is_active=True |
| `disable_member` | Sets is_active=False + best-effort session flush |
| `remove_member` | Last-manager guard + is_active=False + invalidate tokens + best-effort session flush |
| `resend_team_invitation` | Nulls old token's invited_user → creates new token (avoids OneToOne uniqueness error) |
| `send_team_invitation_email` | Composes email context + calls send_transactional_email; caller's responsibility |

### Team Selectors

`apps/accounts/selectors/team.py` exports 2 functions:

- `list_team_members(organisation_id, search, region_id, shop_id)` — returns QuerySet with `Prefetch(to_attr='prefetched_scopes')` enabling N+1-safe scope access; ≤4 queries for 20 staff with 3 scopes each
- `get_team_stats(organisation_id)` — single aggregate query returning `{total_members, managers, active_members}`

### Supporting Infrastructure

- `apps/accounts/exceptions.py` — `LastManagerError` only (no `SelfProtectionError` — self-protection is handled inline at ViewSet layer per plan spec)
- `apps/accounts/selectors/__init__.py` — empty module initializer
- Updated `CustomAuthenticationForm.error_messages["inactive"]` — "Your account has been disabled. Contact your administrator." (TEAM-12)
- `apps/accounts/tests/conftest.py` — re-exports `assert_query_ceiling` and `two_orgs_two_admins` from `apps.common.tests.fixtures`
- `apps/accounts/tests/factories.py` — added `OrgAdminFactory`, `StaffAdminFactory`; updated `InvitationTokenFactory` with `purpose=ORG_ADMIN` default
- `apps/organisations/services/organisations.py` — `create_organisation()` and `resend_invitation()` now set explicit `purpose=ORG_ADMIN` on token create

---

## Key Design Decisions

### 1. Migration 0005 Strategy (RunPython Before AlterField)

Declaring `RunPython` before `AlterField` in the same `operations` list ensures the backfill runs first within a single transaction. If AlterField ran first, any pre-existing NULL rows would cause `IntegrityError`.

### 2. Resend OneToOne Null-Out Fix (Critical Insight for Plan 02)

`InvitationToken.invited_user` is a `OneToOneField(null=True)`. When resending, the service must:
1. Set `old_token.invited_user = None` AND `old_token.is_used = True`
2. Save with `update_fields=["is_used", "invited_user", "updated_at"]`
3. THEN create the new token with `invited_user=member`

Without step 1, Django raises `UNIQUE constraint failed: accounts_invitation_token.invited_user_id`.

### 3. Last-Manager Guard Rule

`remove_member()` raises `LastManagerError` when:
- `member.role == ORG_ADMIN`
- `member.organisation_id is not None`
- No other active ORG_ADMIN exists in the same org (active = `is_active=True`)

Disabled managers do not count as protection — a disabled ORG_ADMIN cannot log in.

### 4. Session Flush — Best-Effort, Non-Fatal

Setting `is_active=False` is the authoritative security gate (Django's `ModelBackend.authenticate()` checks `is_active` on every request). Session flush from `django_session` table is best-effort — wrapped in `try/except` with `logger.warning`. Any failure is logged but swallowed.

### 5. Query-Count Ceiling

`list_team_members` achieves ≤4 queries for 20 staff with 3 scopes each:
1. User queryset with select_related("invited_by")
2. StaffAccessScope prefetch with select_related("region", "shop")
3-4. (SAVEPOINT/RELEASE in test transaction context)

Uses `Prefetch(to_attr="prefetched_scopes")` — distinct name avoids shadowing the `access_scopes` relation manager.

---

## Test Results

- `apps/accounts/tests/test_migrations.py`: 3 passed (migration backfill logic, NOT NULL field verification)
- `apps/accounts/tests/test_services_team.py`: 15 passed (all 8 service functions tested)
- `apps/accounts/tests/test_selectors_team.py`: 5 passed (query count, filters, cross-tenant, ordering, stats)
- Full `apps/accounts/tests/`: 123 passed

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite NOT NULL prevents raw SQL bypass in test_migrations.py**
- **Found during:** Task 1 test execution
- **Issue:** Plan spec suggested using raw SQL update to force NULL values for migration test; SQLite enforces NOT NULL constraints on all SQL updates
- **Fix:** Used mock-based testing approach (MagicMock of Django apps registry) to test `backfill_purpose()` function logic directly without needing to insert NULL rows
- **Files modified:** `apps/accounts/tests/test_migrations.py`
- **Commit:** 678abdc

**2. [Rule 1 - Bug] Existing test_models.py asserted `purpose is None`**
- **Found during:** Task 1 full suite run
- **Issue:** `test_invitation_token_purpose_defaults_null` asserted `token.purpose is None` which fails after migration 0005 makes purpose NOT NULL with factory default ORG_ADMIN
- **Fix:** Renamed test to `test_invitation_token_purpose_defaults_org_admin` and updated assertion
- **Files modified:** `apps/accounts/tests/test_models.py`
- **Commit:** 678abdc

**3. [Rule 2 - Missing] `resend_team_invitation` parameter name mismatch**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec used `resent_by` as parameter name but tests used `resented_by` (consistent with existing org service pattern)
- **Fix:** Used `resented_by` parameter name in both service and tests for consistency
- **Files modified:** `apps/accounts/services/team.py`, `apps/accounts/tests/test_services_team.py`

**4. [Rule 2 - Missing] mypy type annotations for organisation_id and organisation fields**
- **Found during:** Task 2 pre-commit
- **Issue:** `User.organisation_id` can be `None` (ForeignKey nullable), and `User.organisation` can be `None` — mypy flagged both
- **Fix:** Added `is not None` guards before accessing `organisation_id` in remove_member, added null guard + fallback in send_team_invitation_email
- **Files modified:** `apps/accounts/services/team.py`
- **Commit:** 7a1ac57

**5. [Rule 2 - Missing] Ruff RUF002 Unicode character in test docstring**
- **Found during:** Task 3 pre-commit
- **Issue:** Unicode `×` (MULTIPLICATION SIGN) in docstring triggered RUF002
- **Fix:** Replaced `×` with `x` (LATIN SMALL LETTER X)
- **Files modified:** `apps/accounts/tests/test_selectors_team.py`
- **Commit:** 279bd8d

---

## Self-Check

Checking created files exist:
- `apps/accounts/migrations/0005_invitationtoken_purpose_backfill.py` — FOUND
- `apps/accounts/services/team.py` — FOUND
- `apps/accounts/selectors/team.py` — FOUND
- `apps/accounts/exceptions.py` — FOUND
- `apps/accounts/selectors/__init__.py` — FOUND

Checking commits exist:
- 678abdc (Task 1) — FOUND
- 7a1ac57 (Task 2) — FOUND
- 279bd8d (Task 3) — FOUND

## Self-Check: PASSED
