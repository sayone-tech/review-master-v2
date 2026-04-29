---
phase: 08-shops
plan: "06"
subsystem: api
tags: [django, drf, migration, cleanup, gap-closure]

# Dependency graph
requires:
  - phase: 08-shops-05
    provides: ShopModals, ShopViewSet, OAuth views, all prior shop backend
provides:
  - Shop model with only GOOGLE_OAUTH/NOT_CONNECTED + street_address (no api_key, city, state, zip_code)
  - Migration 0003 removing api_key, city, state, zip_code columns; altering connection_method choices
  - Cleaned serializers/services/viewset with no MANUAL/api_key/reveal_key/rotate_key
  - REQUIREMENTS.md: SHOP-03 trimmed; SHOP-10/19/20 marked RETIRED
  - ROADMAP.md Phase 8 success criterion 1 no longer mentions city
affects: [08-07-frontend-cleanup, future-verification-runs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Destructive gap-closure: delete dead code paths before adding new frontend"
    - "Migration consolidation: 4 RemoveField + 1 AlterField in a single migration file"
    - "Spec retirement: [~] markdown checkbox for RETIRED (not removed) requirements"

key-files:
  created:
    - apps/shops/migrations/0003_remove_manual_and_address_subfields.py
  modified:
    - apps/shops/models.py
    - apps/shops/serializers.py
    - apps/shops/services/shops.py
    - apps/shops/selectors/shops.py
    - apps/shops/views.py
    - apps/shops/tests/factories.py
    - apps/shops/tests/test_models.py
    - apps/shops/tests/test_services.py
    - apps/shops/tests/test_selectors.py
    - apps/shops/tests/test_views.py
    - templates/shops/oauth/callback.html
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "ShopAuditLog model and Action enum (API_KEY_REVEALED/API_KEY_ROTATED) retained at ORM level — table kept for forward compatibility, no service writes to it after this plan"
  - "api_key removed from ShopUpdateSerializer LOCKED_FIELDS — column gone, DRF silently ignores unknown fields (no 400 risk from legacy clients)"
  - "OAuth callback template now uses oauth_listings for all cases (single + multiple) — tests updated to match new template behavior"
  - "TestCreateShopManualValidation/TestRevealApiKey/TestRotateApiKey deleted outright — testing retired requirements"
  - "test_patch_connection_method_rejected updated to use GOOGLE_OAUTH (not MANUAL) as locked field rejection trigger"

patterns-established:
  - "Gap-closure plan pattern: delete code that tested retired requirements rather than fixing them to pass"
  - "Requirement retirement notation: [~] status + RETIRED datestamp + cross-reference in REQUIREMENTS.md"

requirements-completed: [SHOP-03, SHOP-08, SHOP-10, SHOP-13, SHOP-14, SHOP-16, SHOP-19, SHOP-20, XMOD-01]

# Metrics
duration: 28min
completed: "2026-04-29"
---

# Phase 8 Plan 06: Backend Cleanup — Drop MANUAL Connection Method and Address Subfields

**Surgical removal of MANUAL/api_key machinery from Shop model, serializers, services, and viewset; migration 0003 applies four RemoveField + one AlterField; SHOP-10/19/20 marked RETIRED in spec**

## Performance

- **Duration:** 28 min
- **Started:** 2026-04-29T14:03:34Z
- **Completed:** 2026-04-29T14:31:25Z
- **Tasks:** 4
- **Files modified:** 13

## Accomplishments

- Dropped `api_key` EncryptedTextField, `city`/`state`/`zip_code` CharFields from `Shop` model; removed `ConnectionMethod.MANUAL` enum value
- Migration `0003_remove_manual_and_address_subfields.py` consolidates all 5 schema operations in one file; `ShopAuditLog` model and `Action` enum retained unchanged
- Removed `reveal_api_key`/`rotate_api_key` services, `reveal_key`/`rotate_key` @actions, `RotateKeySerializer`, `_map_google_error_to_drf` helper; selector's city search removed
- Deleted 3 test classes (TestCreateShopManualValidation, TestRevealApiKey, TestRotateApiKey) and ~14 test methods; 79 tests pass green
- REQUIREMENTS.md SHOP-03 trimmed; SHOP-10/19/20 marked RETIRED with cross-references; ROADMAP.md success criterion 1 drops ", city"

## Task Commits

1. **Task 1: Schema migration + model changes** — `f364220` (feat)
2. **Task 2: Serializer + service + viewset + selector cleanup** — `aff0d89` (feat)
3. **Task 3: Test suite cleanup + factory updates + green run** — `4974eac` (feat)
4. **Task 4: Spec sync — REQUIREMENTS.md and ROADMAP.md** — `77f26e4` (docs)

## Files Created/Modified

- `apps/shops/migrations/0003_remove_manual_and_address_subfields.py` — New migration: RemoveField x4 + AlterField connection_method
- `apps/shops/models.py` — Removed MANUAL choice, api_key, city, state, zip_code fields; ShopAuditLog retained
- `apps/shops/serializers.py` — Removed city/state/zip_code/api_key_masked fields; deleted RotateKeySerializer; removed MANUAL validate() branch
- `apps/shops/services/shops.py` — Removed api_key/city/state/zip_code params from create_shop; deleted reveal_api_key + rotate_api_key
- `apps/shops/selectors/shops.py` — Removed city__icontains from list_shops search filter
- `apps/shops/views.py` — Removed reveal_key/rotate_key actions; deleted _map_google_error_to_drf; cleaned imports
- `apps/shops/tests/factories.py` — Removed city="" default from ShopFactory
- `apps/shops/tests/test_models.py` — Deleted test_shop_api_key_stored_as_ciphertext; trimmed encrypted_fields_round_trip
- `apps/shops/tests/test_services.py` — Deleted 3 test classes; cleaned imports
- `apps/shops/tests/test_selectors.py` — Deleted test_search_matches_city
- `apps/shops/tests/test_views.py` — Deleted TestShopSerializerFields, MANUAL create tests, reveal/rotate tests, test_patch_api_key_rejected; updated connection_method test to use GOOGLE_OAUTH
- `templates/shops/oauth/callback.html` — Pre-existing local change: unified to oauth_listings for all cases (confirmed by git log)
- `.planning/REQUIREMENTS.md` — SHOP-03 trimmed; SHOP-10/19/20 marked [~] RETIRED; status table updated
- `.planning/ROADMAP.md` — Phase 8 success criterion 1: removed ", city" from search list

## Decisions Made

- `ShopAuditLog` model and `Action` enum (API_KEY_REVEALED/API_KEY_ROTATED) retained at the ORM level — the table exists for forward compatibility; no service writes to it after this plan; keeping it avoids a no-op migration and preserves any historical audit rows
- `api_key` removed from `ShopUpdateSerializer.LOCKED_FIELDS` — the column no longer exists, DRF silently ignores undeclared fields so legacy clients sending `api_key` in PATCH get a 200 (correct behavior for a removed field)
- Test classes for MANUAL/api_key functionality were deleted outright rather than converted — they tested RETIRED requirements (SHOP-10/19/20); keeping them green would require mocking non-existent code paths

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] OAuth callback test updated to match pre-existing template change**
- **Found during:** Task 3 (test suite cleanup + green run)
- **Issue:** `test_callback_single_listing_renders_auto_close_script` asserted `b"oauth_success"` but the template (already modified as a local change before this plan) now sends `type: "oauth_listings"` for all listing cases; `test_callback_multiple_listings_renders_picker` asserted `b"<form"` but the form-based picker was removed
- **Fix:** Updated both tests to assert `b"oauth_listings"` and `b"window.opener"`; renamed `test_callback_multiple_listings_renders_picker` to `test_callback_multiple_listings_sends_all_listings`; both listing names still asserted in response content
- **Files modified:** `apps/shops/tests/test_views.py`
- **Committed in:** `4974eac` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The template change was pre-existing (not caused by this plan); fixing the tests aligns them with the actual template behavior. No scope creep.

## Issues Encountered

- Pre-commit `end-of-file-fixer` + `ruff-format` modified `serializers.py` and `test_views.py` on first commit attempt — re-staged and committed cleanly on second attempt.

## Lines of Code Deleted vs Added

- **Deleted:** ~450 lines (test classes, service functions, serializer fields, viewset actions)
- **Added:** ~30 lines (migration file 34 lines, minor test updates)

## ShopAuditLog Retention Rationale

`ShopAuditLog` model and `ShopAuditLog.Action` enum (API_KEY_REVEALED, API_KEY_ROTATED) are **retained at the ORM level**:
- The table may contain historical audit rows from earlier development/testing
- Deleting the model would require a separate migration that provides no functional benefit
- The `ShopAuditLogFactory` continues to work and the `TestShopAuditLog` test class remains valid
- No service functions write to `ShopAuditLog` after this plan — the table is frozen in place

## Final pytest Run

```
79 passed, 44 warnings in 12.76s
```

## Next Phase Readiness

- Backend contract simplified: Plan 08-07 (frontend cleanup) consumes `ShopReadSerializer` without `api_key_masked`, `city`, `state`, `zip_code` fields
- Migration 0003 must be applied before deploying any frontend changes that assume the simplified schema
- No blockers

---
*Phase: 08-shops*
*Completed: 2026-04-29*
