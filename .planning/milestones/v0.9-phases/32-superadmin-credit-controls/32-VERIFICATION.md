---
phase: 32-superadmin-credit-controls
verified: 2026-11-11T16:20:00Z
status: human_needed
score: 4/4 roadmap success criteria verified (2 backstop UI truths routed to human)
covered_files:
  - ".planning/phases/32-superadmin-credit-controls/32-01-PLAN.md"
  - ".planning/phases/32-superadmin-credit-controls/32-01-SUMMARY.md"
  - ".planning/phases/32-superadmin-credit-controls/32-02-PLAN.md"
  - ".planning/phases/32-superadmin-credit-controls/32-02-SUMMARY.md"
  - ".planning/phases/32-superadmin-credit-controls/32-03-PLAN.md"
  - ".planning/phases/32-superadmin-credit-controls/32-03-SUMMARY.md"
  - ".planning/phases/32-superadmin-credit-controls/32-04-PLAN.md"
  - ".planning/phases/32-superadmin-credit-controls/32-04-SUMMARY.md"
  - ".planning/phases/32-superadmin-credit-controls/32-05-PLAN.md"
  - ".planning/phases/32-superadmin-credit-controls/32-05-SUMMARY.md"
  - "apps/credits/api_urls.py"
  - "apps/credits/exceptions.py"
  - "apps/credits/selectors/balances.py"
  - "apps/credits/selectors/shop_credits.py"
  - "apps/credits/serializers.py"
  - "apps/credits/services/allocation.py"
  - "apps/credits/services/bonus.py"
  - "apps/credits/views.py"
  - "apps/organisations/admin.py"
  - "apps/organisations/selectors/organisations.py"
  - "apps/organisations/serializers.py"
  - "apps/organisations/services/organisations.py"
  - "apps/organisations/views.py"
  - "config/settings/base.py"
  - "config/urls.py"
  - "frontend/src/entrypoints/org-management.tsx"
  - "frontend/src/widgets/org-management/CreateOrgModal.tsx"
  - "frontend/src/widgets/org-management/EditOrgModal.tsx"
  - "frontend/src/widgets/org-management/ManageCreditsModal.tsx"
  - "frontend/src/widgets/org-management/OrgTable.tsx"
  - "frontend/src/widgets/org-management/ViewOrgModal.tsx"
  - "frontend/src/widgets/org-management/creditHint.ts"
  - "frontend/src/widgets/org-management/creditsApi.ts"
  - "frontend/src/widgets/org-management/types.ts"
  - "frontend/src/widgets/org-management/useCreditShops.ts"
covered_digest: "v4:sha256:2df6db8d30a1b03d5c0b7cef5c79511f42a9491070b2f3206d659f16316495e1"
behavior_unverified: 0
overrides_applied: 0
re_verification: false
human_verification:
  - test: "CI job backend-pg on postgres:16 (branch is unpushed)"
    expected: "All pg_concurrency tests pass (20 passed on local PostgreSQL 14; 15 skip on SQLite by design), including the three 32-05 races (org edit vs first use, bonus vs reserve, bonus vs 0->N edit) and concurrent-bonus exact sums"
    why_human: "Needs a pushed branch and the CI Postgres service; SQLite serialises writers and cannot exhibit these races"
  - test: "Manage Credits UX walk-through as Superadmin, including a forced UTC month rollover 409"
    expected: "Org row > Manage Credits > list > Add bonus > preview > Allocate > toast + refreshed row; with the month rolled while the dialog is open, the amber banner shows, the new-month balance is applied, typed amount and reason are kept and a fresh click is required"
    why_human: "Visual, focus and real-time behaviour; month rollover needs a controlled clock"
  - test: "360px layout backstop 1: bonus balance block collapses to 2 columns with no overflow"
    expected: "No horizontal overflow at 360px"
    why_human: "UI-SPEC backstop truth (insufficient_spec): grep and unit tests cannot prove layout"
  - test: "360px layout backstop 2: long org/shop names wrap in the modal subtitle without overlapping the close button"
    expected: "Wrapped text, close button unobstructed"
    why_human: "UI-SPEC backstop truth (insufficient_spec)"
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  status: human_needed
---

# Phase 32: Superadmin Credit Controls Verification Report

**Phase Goal:** Superadmin can set each organisation's monthly credit budget and top up any shop's current month with bonus credits. No other role can change a credit budget.
**Verified:** 2026-11-11
**Status:** human_needed (no gaps, no blockers; only environment/visual human items remain)
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Superadmin sets monthly credits per shop (0-10,000, default 0) on Create/Edit Org; persists; out-of-range rejected; each real change writes one `organisation.credits.set` AuditLog | VERIFIED | `Organisation.monthly_credit_allocation` with DB CHECK `org_monthly_credit_allocation_range` and validators (models.py:34,58); serializers.py:67,89 bound the field; `create_organisation` accepts it (default 0) and audits only when > 0 (organisations.py:54-80); `update_organisation` audits only when `new != old` under the org lock (organisations.py:240-290); `_UPDATABLE_FIELDS` includes the field (:31); React Create/Edit fields default 0 and validate 0-10,000 (CreateOrgModal.tsx:57,74; EditOrgModal.tsx:63,82, sent only when changed since open). Tests pass (531 backend passed). |
| 2 | 0 -> N makes N available immediately this month; N -> M mid-month leaves current-month balances at N and applies M next month | VERIFIED | `update_organisation` reads `old` under `select_for_update(of=("self",), no_key=True)`, then either `raise_zero_balances` (old == 0 and no current-month allocation > 0, D-18) or `materialise_org_balances` at the OLD value, both BEFORE the field save, in one atomic (organisations.py:240-285). Set-based helpers in allocation.py:149-240 write INITIAL ledger and `shop.credits.allocated` audit rows. Proof matrix tests (test_org_allocation.py) and 3 PG races (skipped on SQLite; passed on local PG14 per summary and security record). |
| 3 | From any org row: Manage Credits lists the org's shops with balances, pick shop, 1-10,000 bonus + optional reason, before/after preview, confirm; balance rises for current UTC month only with one BONUS_ALLOCATION ledger row and one `shop.credits.bonus_allocated` AuditLog row | VERIFIED | Backend: `CreditShopListView` (views.py:46-85, paginated 10/page, active shops only, `annotate_credit_state`, never writes) and `BonusAllocationView` (views.py:88-139) -> `allocate_bonus` (bonus.py): period echo (409) -> availability (404) -> one atomic: org lock, `ensure_balance`, balance lock, `F()` increment, ledger row, audit row (reason only in `note`, audit has `has_reason`). Frontend: `OrgTable` "Manage Credits" action -> `org-management.tsx` handler -> `ManageCreditsModal` with list, Add bonus, preview, Allocate, 409/404/400 states, `useCreditShops` (debounced, abortable, paginated). 18 modal tests and 92 org-management vitest tests pass; `tsc --noEmit` clean. |
| 4 | Every Superadmin credit endpoint returns 403 to Org Admin and Staff; no Org Admin/Staff path changes an allocation or adds bonus | VERIFIED | Both credit views: `[IsAuthenticated, IsSuperadmin]` + scoped throttles (views.py:51,95). `OrganisationViewSet` is `IsSuperadmin` (organisations/views.py:238); grep of non-test code shows `monthly_credit_allocation` appears only in Superadmin serializers, the service, selectors and a read-only admin field (admin.py:12, D-22); no Org Admin/Staff serializer exposes it. 403 tests for Org Admin (same org), Staff, and anonymous exist for list, bonus and PATCH (test_views.py:290-322, 474-497). |

**Score:** 4/4 roadmap criteria verified. Plan-04 backstop truths (2) are human items, not counted.

### Locked decisions D-01..D-23 spot-check

D-01/D-18/D-21 hint uses server `current_month_credit_allocation` (creditHint.ts:100-130; backend rule matches). D-02 N -> 0 deferred (same branch). D-04 default 0. D-05 active-only (`is_active=True`). D-06/D-07 virtual balances, 10/page, search. D-08..D-13 two-view modal, preview, toast, 409 keeps typed values (ManageCreditsModal.tsx:176-215). D-14 "Credits/shop" column with muted "Off" (OrgTable.tsx:55-58,151). D-15 pending pill (ViewOrgModal.tsx:96-109). D-17/UI-SPEC label "Manage Credits" (UI-SPEC/plan wording wins over CONTEXT's lowercase). D-19/D-23 404 toast "This shop is no longer active." D-20 set-based helpers. D-22 admin read-only. No deviations found.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| CRED-01 | 32-01, 32-02 | SATISFIED | Truth 1 |
| CRED-06 | 32-01, 32-02, 32-04, 32-05 | SATISFIED | Truth 2 |
| CSUP-01 | 32-03, 32-04, 32-05 | SATISFIED | Truth 3 |
| CSUP-02 | 32-01, 32-03, 32-05 | SATISFIED | Truth 4 |

All four IDs are claimed in PLAN frontmatter, defined in REQUIREMENTS.md and mapped to Phase 32 (traceability table lines 86,91,108,109). No orphaned requirements.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend phase suites | `pytest apps/credits apps/organisations apps/shops` | 531 passed, 15 skipped (pg_concurrency, by design on SQLite) | PASS |
| Frontend widget suite | `npx vitest run src/widgets/org-management` | 9 files, 92 tests passed | PASS |
| Type check | `npx tsc --noEmit` | no errors | PASS |
| WR-01 interleaving probes (throwaway test, deleted) | see below | 4/4 probes behaved as analysed | PASS |

### Resolution of the disputed finding (WR-01 vs ORM audit)

Callers of `ensure_balance` in non-test code: exactly two, `reserve_credits` (consumption.py:127, no org lock) and `allocate_bonus` (bonus.py:88, under the org lock, read inside the atomic so READ COMMITTED sees the committed edit). No other code path creates a `ShopCreditBalance` except the set-based `materialise_org_balances` (org lock held).

I forced the interleavings deterministically on SQLite by hooking the seams (single connection, ordering enforced by hooks; a throwaway test, deleted afterwards; no Postgres cluster was started):

1. Direct call to the primitive with the 0 -> N edit committed between the allocation read and the insert: **a zero-allocation row IS created** (`allocated_credits == 0`). The reviewer's mechanism is real at the primitive level.
2. `reserve_credits` on a shop with no row and org allocation 0: raises 402 `not_enabled` from the read-only pre-check; `ensure_balance` is never called; zero rows written (`GEN-ZERO not_enabled 0 0`).
3. `reserve_credits` with a 0 -> N edit committed immediately after the pre-check: still 402, zero rows (`GEN-0toN-after-precheck 0`).
4. `reserve_credits` with allocation 100 at pre-check, then an N -> 0 edit committed before `ensure_balance`: the edit has already materialised the row at 100, so the generate path finds it (`allocated_credits == 100`).

Reasoning: for the generate path to reach an `INSERT` with no existing row it must have passed the pre-check with a live allocation > 0 (no row, bonus 0). For `ensure_balance` to then read 0, an N -> 0 edit must have committed in between, and that edit materialises a row at N for every shop of the org, so the insert finds it. The only residual is a three-event coincidence across a UTC month boundary (pre-check in month p1, month rolls, N -> 0 then 0 -> N' edits before the insert), which I judge not reachable in practice. **Classification: ADVISORY (latent hardening), not a gap.** CRED-06 / SC2 holds on every reachable path. Recommendation: the primitive stays unsafe for any future unlocked caller, so either document "caller must hold the org lock or have passed the virtual pre-check" in `ensure_balance`, or take the allocation read inside the atomic block under `select_for_share`, plus a regression test. Phase 33 and later must not add an unlocked caller without that.

### Other review-gate findings, classified

| Finding | Classification | Evidence / judgement |
|---------|----------------|----------------------|
| WR-02 availability check outside the lock | ADVISORY | A shop deactivated in the microsecond window still receives a valid, ledgered, additive bonus; inactive shops keep balances (Phase 29 D-13). D-19 contract (deactivated while the dialog is open -> 404) holds for every request that starts after the deactivation commits (test `test_bonus_returns_404_without_writing_when_shop_unavailable`). Cheap fix: re-check inside the atomic. |
| WR-03 / tenant LOW 2 stale period + inactive shop -> 409 instead of 404 | ADVISORY | Requires month rollover AND deactivation in the same dialog session. D-19 and CSUP-01 are satisfied for the single-condition cases (each tested). The 409 body is Superadmin-only data. Fix is to swap the order of the two checks. |
| WR-04 bonus POST not idempotent; retry after a lost post-commit response double-credits | ADVISORY | CSUP-01 and D-10 specify additive, uncapped allocations with no extra guard; no idempotency is required by any criterion. UI-SPEC/plan locked "other failure: generic toast, keep form and values". Double-credit needs a network/5xx failure after commit, is Superadmin-initiated, bounded and fully visible in the ledger. Recommended follow-up: reload and warn "may have applied" on non-HTTP/5xx failures, or add an idempotency key (IN-03 ref guard). |
| Tenant MEDIUM 1 no cross-org test for the shop list | ADVISORY | Verified in code: `list_org_shop_credits` filters `organisation_id=organisation_id` and `is_active=True` (shop_credits.py:26-28); existing tests use a single org, so a regression would not be caught. Add a two-org test (and rules/testing-python.md requires one). Phase 33 must add a scoped variant before Org Admin/Staff reuse the selector. |
| WR-05 `useCreditShops` no recovery on out-of-range page 404 | ADVISORY | Reproduced by reading `useCreditShops.ts:31-50`: any failure sets `error`, Retry re-requests the same page. Recovery needs closing and reopening the modal; no data is lost or corrupted and no must-have requires auto-recovery. Fix: on 404 with `page > 1`, reset to page 1. |
| IN-01..IN-04 | INFO | Not goal-affecting. IN-04 (new shop mid-month takes the live allocation) deserves a line in the rollout doc. |

None of these fails a ROADMAP success criterion, a requirement or a locked decision, so none are gaps. They are recorded here (and remain `open` in `32-REVIEW-DISPOSITION.md`) for triage; I recommend fixing WR-01 hardening, WR-02/WR-03 ordering and WR-05 before ship since each is a few lines.

### Anti-Patterns Found

None blocking. No TBD/FIXME/XXX debt markers in the reviewed files. No stubs: all list, bonus and modal paths are backed by real queries and real HTTP calls (Level 4: list rows come from `annotate_credit_state` over real balances; bonus result comes from the locked row).

### Human Verification Required

1. **CI backend-pg on postgres:16** - push the branch; expect all pg_concurrency tests to pass (local PG14: 20 passed).
2. **Manage Credits UX walk-through** including a forced month-rollover 409 (banner, refreshed month, kept values, fresh click).
3. **360px backstop: bonus balance block** collapses to 2 columns without overflow.
4. **360px backstop: long names** wrap in the modal subtitle without overlapping the close button.

### Gaps Summary

No gaps. The phase goal is achieved in the code: Superadmin-only allocation set with CRED-06 timing, Superadmin-only bonus top-up with ledger and audit, enforced server-side. Status is `human_needed` solely because CI-on-Postgres confirmation and visual/UX checks cannot be proven programmatically. The disputed WR-01 is resolved as advisory (latent primitive hardening, unreachable through the shipped callers).

---

_Verified: 2026-11-11_
_Verifier: Claude (gsd-verifier)_
