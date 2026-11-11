---
phase: 32-superadmin-credit-controls
plan: 05
subsystem: credits
tags: [postgres, concurrency, pg_concurrency, deadlock, select-for-update, no-key-update, docs, phase-gate]
status: complete

requires:
  - phase: 32-superadmin-credit-controls (plans 01-04)
    provides: update_organisation CRED-06 branch, allocate_bonus, Superadmin credit endpoints, org-management UI
provides:
  - Four pg_concurrency tests proving org edit, bonus, reserve and first use are lossless and deadlock-free on real PostgreSQL
  - Production fix for a real organisation-row deadlock (FOR NO KEY UPDATE) found by those tests
  - CLAUDE.md section 3 credits rows and the rewritten rollout runbook (Superadmin UI, D-22)
  - Phase 32 gate results, inline auditor dispositions, 32-VALIDATION.md signed off locally
affects: [33 credit visibility UI, /gsd-verify-work 32]

requirements-completed: [CRED-06, CSUP-01, CSUP-02]

actuals:
  tokens: 3900
  tasks: 3
  commits: 4
plan_head_before: 77351f4acee41357ead3ebc5040df7dd03ee45ba
plan_head_after: ec5a007c4a9855a3d9830842e4e922798f971ea0

coverage:
  - deliverable: "Concurrent bonuses on a never-used shop sum exactly (CSUP-01)"
    verification:
      - kind: test
        ref: "apps/credits/tests/test_pg_concurrency.py#test_concurrent_bonuses_sum_exactly_when_n_threads_allocate_to_one_never_used_shop"
        status: pass
    human_judgment: false
  - deliverable: "Org edit vs first use materialises one row per shop at the old value (CRED-06, D-20)"
    verification:
      - kind: test
        ref: "apps/credits/tests/test_pg_concurrency.py#test_org_edit_materialises_one_row_per_shop_at_old_value_when_first_uses_race"
        status: pass
    human_judgment: false
  - deliverable: "Bonus vs reserve keeps the ledger consistent"
    verification:
      - kind: test
        ref: "apps/credits/tests/test_pg_concurrency.py#test_bonus_and_reserve_keep_ledger_consistent_when_racing_on_one_balance"
        status: pass
    human_judgment: false
  - deliverable: "Bonus vs 0 -> N edit leaves no zero-allocation row, both orderings (D-18)"
    verification:
      - kind: test
        ref: "apps/credits/tests/test_pg_concurrency.py#test_bonus_and_zero_to_n_edit_leave_no_zero_allocation_row_when_racing"
        status: pass
    human_judgment: false
  - deliverable: "CLAUDE.md section 3 and rollout runbook match shipped behaviour"
    verification:
      - kind: command
        ref: "greps in 32-05-PLAN Task 3 acceptance_criteria"
        status: pass
    human_judgment: true
    rationale: "Prose accuracy of the runbook is reviewed by a human operator before the rollout"
  - deliverable: "Frontend/backend contract agreement"
    verification:
      - kind: command
        ref: "contract cross-check command (CONTRACT_OK) plus a field-by-field read of serializers.py, views.py and creditsApi.ts"
        status: pass
    human_judgment: false

duration: 9 min
completed: 2026-11-11
---

# Phase 32 Plan 05: Postgres Races, Docs and Phase Gate Summary

**Four real-PostgreSQL race tests prove concurrent bonuses, org edits, reservations and first uses stay lossless; they exposed a genuine deadlock (FOR UPDATE on the organisation row against a concurrent balance insert) that is fixed with FOR NO KEY UPDATE, and every local Phase 32 gate is green.**

## Performance

- **Duration:** 9 min (start 2026-11-11T15:53Z, code complete 16:01Z)
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files:** 5 modified (test file, two services, CLAUDE.md, runbook) plus 32-VALIDATION.md; 0 created

## Accomplishments

- **Tracer (CSUP-01, Task 1):** 8 barrier-released `allocate_bonus(+5)` calls on one never-used shop of an organisation at 10. Result: exactly one balance row (allocated 10, bonus 40), one INITIAL (+10), 8 BONUS rows (+5, COMMITTED, actor set), 8 `shop.credits.bonus_allocated` and 1 `shop.credits.allocated` AuditLog rows, ledger reconciles. Passed 3 of 3 runs.
- **Org edit vs first use (CRED-06, D-20):** 3 rounds, 6 shops per organisation, 1 edit thread (10 to 20) racing 6 `ensure_balance` threads. Every shop ends with one current-month row at 10, 6 INITIAL rows, 6 `shop.credits.allocated` rows, field 20, one `organisation.credits.set` with effective `next_month`.
- **Bonus vs reserve:** 4 bonus threads and 8 reserve threads on one balance at allocation 4: no unexpected errors, bonus 4, 4 BONUS rows, `consumed_credits` equal to the success count and within `allocated + bonus`, ledger reconciles.
- **Bonus vs 0 -> N edit (Pitfall 6):** 6 rounds, a 3 ms delay in the bonus thread on odd rounds and in the edit thread on even rounds. Every round ends at allocated 20, bonus 5, one INITIAL (+20), one BONUS, one `organisation.credits.set` with effective `immediate`; no zero-allocation row left behind.
- **Docs (D-22):** CLAUDE.md section 3 lists `bonus.py`, `shop_credits.py`, `serializers.py`, `views.py`, `api_urls.py` and the extended `allocation.py` comment (glyphs kept). The runbook's enable section now points at Edit Organisation and Manage Credits, states the Django admin field is read-only, and replaces the queryset `update(...)` snippet with `update_organisation(...)`.
- **Contract:** `CONTRACT_OK`, plus a field-by-field read: list response (`count/next/previous/period/allocation_per_shop/results`), row keys (`id/name/allocated/bonus/consumed/remaining/is_materialized`), bonus request and 201 body, and the 409 `period_mismatch` body all match `creditsApi.ts`.

## Task Commits

1. **Task 1 (tracer): concurrent bonuses on PostgreSQL** - `a368bc8` (test)
2. **Task 2: deadlock fix + three more races** - `4cc0ede` (fix)
3. **Task 3: docs and VALIDATION sign-off** - `ec5a007` (docs)

`bf8e6e3` (`docs(phase-33): add research and validation strategy`) landed on the branch between Tasks 2 and 3 from outside this plan, so the measured `rev-list` count is 4 although this plan made 3 commits.

## Deviations from Plan

**1. [Rule 1 - Bug] Organisation-row deadlock on PostgreSQL** - Found during: Task 2 (first full PG run).
- **Issue:** `update_organisation` and `allocate_bonus` locked the organisation row with plain `FOR UPDATE`. A concurrent first-use `ensure_balance` inserts a balance row (holding its unique-index entry) and then needs a `FOR KEY SHARE` on the organisation row for its foreign-key check, which `FOR UPDATE` blocks. The lock holder, in turn, waits on that uncommitted unique-index entry (the org edit's `bulk_create` over the same shop, or the bonus's own `ensure_balance` for the same shop). Result: `OperationalError: deadlock detected`. This was a production bug (org edit while a reply is being generated for a never-used shop, or a bonus racing a first reservation), invisible on SQLite.
- **Fix:** `select_for_update(of=("self",), no_key=True)` (`FOR NO KEY UPDATE`) in both places, with comments. It still serialises edits and bonuses against each other and keeps the organisation-row then balance-row order; it just no longer conflicts with the FK `KEY SHARE`. The `UPDATE` of the allocation column takes the same non-key lock.
- **Non-vacuity:** with the fix reverted, `test_org_edit_materialises_...` and `test_bonus_and_reserve_...` fail on Postgres in two consecutive runs; restored, 20 of 20 pass in three consecutive runs and once more at the end.
- **Files modified:** `apps/organisations/services/organisations.py`, `apps/credits/services/bonus.py`. **Commit:** `4cc0ede`.

**2. [Test design] Race scope** - The bonus-vs-edit test asserts both orderings by delay but accepts either winner; it records the outcome via assertions only (no print), since both orderings converge on the same final state.

**Total deviations:** 1 auto-fixed bug, 1 test-design note. **Impact:** a real concurrency defect fixed before rollout; no migration, no behaviour change on the happy path. Not changed: `apps/shops/services/shops.py:32` also uses plain `FOR UPDATE` on the organisation row (shop creation); it never touches credit balances, so it is out of scope, noted for the architect.

## Phase Gate Reviews (inline)

The Agent tool was not available to this executor, so each auditor's checklist was walked inline over the real files (same approach as Phase 31-03).

### tenant-security-auditor

- Both new views are `IsAuthenticated` + `IsSuperadmin` with scoped throttles (`superadmin_credits_read` 120/min, `superadmin_credits_write` 30/min); the organisation for a bonus is derived from the shop row, never from the request. Accepted.
- `monthly_credit_allocation` appears only in the Superadmin-only `OrganisationViewSet` serializers (`permission_classes = [IsAuthenticated, IsSuperadmin]`); no Org Admin or Staff serializer references it (grep over `apps/` non-test code). PATCH 403 tests exist for an Org Admin targeting their own organisation and for Staff. Accepted.
- D-22: Django admin shows the field read-only; admin test present. Accepted.
- Audit payloads carry ids and integers only (`has_reason` boolean, not the reason text); the free-text reason lives only in `CreditTransaction.note`. Logs carry ids and ints only. Accepted.
- POST bonus uses DRF session auth, so CSRF is enforced; the client sends `X-CSRFToken`. Accepted.
- Selectors in `shop_credits.py` are unscoped by tenant by design and documented as Superadmin-only; Phase 33 must add tenant scoping before exposing them to Org Admin (noted for Phase 33). Accepted.
- **Finding (fixed):** the organisation-row deadlock above was an availability defect on a tenant-facing path (reply generation); fixed in `4cc0ede`.
- No blockers remain.

### orm-performance-auditor

- `materialise_org_balances` / `raise_zero_balances`: constant query counts, pk-ordered bulk inserts, `ignore_conflicts` so a concurrent winner keeps its row; query-count tests pass (plan 32-01). Accepted.
- `org_current_month_allocation_expression`: a `Subquery` served by `credit_bal_org_period_idx`; the organisation list ceilings are unchanged (tests pass). Accepted.
- Shop list: `FilteredRelation` plus the `(organisation, is_active, connection_status)` index; query count fixed across 2 vs 12 shops (tested). Accepted.
- `name__icontains` has no supporting index: accepted at the expected scale (<= 1,000 shops per organisation, one organisation per request); revisit with a trigram index only if an organisation grows past that.
- `QuerySet.update()` calls set `updated_at` explicitly (`raise_zero_balances`, bonus). Accepted.
- No migration added (credits 5, organisations 4, `makemigrations --check` clean).
- **Locking:** see deviation 1; the global order is organisation row (FOR NO KEY UPDATE) then balance rows, proven deadlock-free by the PG races. Accepted.
- No blockers.

### code-reviewer

- Views are thin (validate, call service or selector, shape response); logic in `services/bonus.py`, `services/allocation.py`, selectors (CLAUDE.md section 5). Accepted.
- Every new endpoint has explicit permissions, a throttle and pagination (the list is `PageNumberPagination` fixed at 10, the client cannot change the size) (section 8). Accepted.
- drf-spectacular: `spectacular --validate` reports no warning or error for the credits views (the remaining ones are pre-existing in dashboard, reports, shops, reviews, common). Accepted.
- mypy strict: 351 files, no issues. ruff check and format clean.
- Observation (accepted): `OrganisationListSerializer.current_month_credit_allocation` requires the annotated queryset; every list and detail path goes through `_base_queryset`, and write responses use the update or create serializer, which do not include it.
- No business logic in serializers. No blockers.

### frontend-react-builder

- Tailwind tokens and the brand palette follow the existing widget conventions; the three hex colours (`#991B1B`, `#92400E`, `#FBFBFB`) are already used in other widgets. Accepted.
- Font weights in the new code are 400 and 600 only; `font-medium` in `OrgTable.tsx` is the pre-existing status pill, not from this phase. Accepted.
- Accessibility: search and pagination buttons have `aria-label`s, amount and reason inputs have `htmlFor` labels, errors use `role="alert"`, the amount preview and page count are `aria-live="polite"`. Accepted.
- Reuses the shared `Modal` (focus trap does not remount between list and bonus views). Accepted.
- Manual-only (open for `/gsd-verify-work`): 360px layout backstop checks and the visual UX walk.
- No blockers.

Optional project skills `security-checklist` and `feature-impact` were not run.

## Verification Results (real output)

- **pg_concurrency on a throwaway PostgreSQL 14.20** (local Homebrew, not CI's 16; cluster under the scratchpad on port 54351, `REQUIRE_PG=1 --ds=config.settings.test_pg -m pg_concurrency`): **20 passed, 0 skipped** (`1565 deselected`), run 4 times (three in a row after the fix, once at the end). Before the fix: 2 failed, 13 passed in the credits file. The 20 are 11 in `apps/credits/tests/test_pg_concurrency.py` plus 4 new there, and 5 in `apps/reviews/tests/test_pg_reply_concurrency.py` (16 existing + 4 new).
- Full suite `.venv/bin/pytest apps/ -q -o addopts=""` -> **1563 passed, 22 skipped** (all skips are Postgres-only).
- `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` -> required coverage met, **89.88%** total; `credits/selectors/shop_credits.py` 100%, `selectors/balances.py` 100%, `serializers.py` 100%, `views.py` 100%, `services/bonus.py` 96%, `services/allocation.py` 96%.
- `mypy .` -> no issues in 351 files; `ruff check .` and `ruff format --check .` clean.
- `makemigrations --check --dry-run` -> No changes detected. `check --deploy` (test settings, as the plan specifies) -> exit 0 with 21 warnings (test-settings artefacts and pre-existing serializer-guess warnings); not run against production settings.
- Frontend: `npm test` -> **29 files, 193 tests passed**; `npx tsc --noEmit` clean.
- Acceptance greps: `pg_concurrency` markers 15; `update_organisation(` in the PG file 2+; `shop_credits.py` 1 and `bonus.py` 1 in CLAUDE.md; "until Phase 32" 0 and `update(monthly_credit_allocation=` 0 in the runbook; "Manage Credits" 1 and `update_organisation` 2; migrations credits 5 and organisations 4; reviews-import invariant 0; contract `CONTRACT_OK`.
- Postgres stopped with `pg_ctl -m fast stop`, data directory and log deleted, no postgres process left; no background commands started and no docker used.

**Not run:** CI `backend-pg` on PostgreSQL 16 (needs a push); the `security-checklist` and `feature-impact` skills; EXPLAIN on the shop-list and organisation-list queries; a production-settings `check --deploy`.

## Known Stubs

None.

## Threat Flags

None. T-32-27, T-32-28 and T-32-29 are mitigated by the PG races (and the deadlock they found); T-32-30 by the runbook rewrite and its acceptance greps; T-32-31 by the inline auditor dispositions plus the CSUP-02 403 tests in the full suite.

## Next Phase Readiness

Phase 32 plans are complete. For `/gsd-verify-work 32`: confirm CI `backend-pg` on PostgreSQL 16 ran 20 `pg_concurrency` tests with none skipped; walk the Manage Credits UX (including a forced month rollover for the 409 banner); check the two 360px backstop items. Phase 33 must add tenant scoping around the unscoped Superadmin selectors before reusing them for Org Admin or Staff reads.

## Self-Check: PASSED

Modified files exist; commits `a368bc8`, `4cc0ede`, `ec5a007` are ancestors of HEAD; `git rev-list --count` from the plan base gives 4 (3 plan commits plus the interleaved `bf8e6e3`).
