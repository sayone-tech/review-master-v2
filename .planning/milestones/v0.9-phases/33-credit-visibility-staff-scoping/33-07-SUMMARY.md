---
phase: 33-credit-visibility-staff-scoping
plan: 07
subsystem: testing
tags: [integration-test, tenant-security, orm-performance, postgres, runbook, validation]
requires:
  - phase: 33-credit-visibility-staff-scoping
    provides: Plans 33-01..33-06 (Staff-scoped Shops API, credits GET, Activity Log credit rows, credits widgets)
provides:
  - Whole-phase backend walk-through test across Org Admin, Superadmin and Staff
  - Frontend/backend contract cross-check (CONTRACT_OK)
  - Recorded section 27 review dispositions (tenant-security, orm-performance, code-review, frontend)
  - PostgreSQL proof of the audit text comparison and Shops/credits selectors
  - Runbook "Phase 33 behaviour changes" section and CLAUDE.md section 3 credits rows
  - Refreshed 33-VALIDATION.md (status validated, nyquist_compliant true)
affects: [/gsd-verify-work, /gsd-complete-milestone]

actuals:
  tokens: 14000
  tasks: 3
  commits: 3
plan_head_before: 99c5cb3fdf0703a1bd7280dbf1046b5145786610
plan_head_after: 28873ac1bd592883e2a6d7938d200918b51f5010

tech-stack:
  added: []
  patterns:
    - "Phase walk-through test: one org, one APIClient per role, every surface asserted against the same numbers"
key-files:
  created:
    - apps/credits/tests/test_phase33_flow.py
  modified:
    - CLAUDE.md
    - docs/sre/v0.9-credits-rollout.md
    - .planning/phases/33-credit-visibility-staff-scoping/33-VALIDATION.md
key-decisions:
  - "Superadmin actor names on credit rows and in the Org Admin actor dropdown stay visible (research open question 2, accepted)"
  - "Staff list/retrieve scoping change accepted for web and JWT mobile clients and documented in the runbook"
  - "ReviewTargetViewSet list/history and the allocation_status / has_regions envelope are recorded follow-ups, not fixed in this phase"
requirements-completed: [CVIS-01, CVIS-02, CVIS-03, CVIS-04, CVIS-05, SCOPE-01]
status: complete
---

# Phase 33 Plan 07: Whole-phase verification Summary

Phase-level walk-through test, contract cross-check, four dispositioned section 27 reviews, PostgreSQL proof, runbook and CLAUDE.md updates, and every gate green.

## Accomplishments

- `apps/credits/tests/test_phase33_flow.py` walks one organisation through the phase: Org Admin lists both shops (remaining 50), Superadmin bonus +10 to shop A, Org Admin credits GET and a fresh Shops list agree (60 / 60 / bonus 10), an in-scope Staff generate (OpenAI seam patched, called once) lowers remaining by the server cost read from `credit-cost`, the credits GET reflects it, the Org Admin Activity Log shows `shop.credits.bonus_allocated` and `shop.credits.consumed` for shop A with `shop_name == A.name`, and Staff sees only shop A, gets 404 for shop B's credits, and no `shop` / `organisation` audit rows.
- Contract cross-check command printed `CONTRACT_OK`: creditsApi.ts keys exist in `ShopCreditsSerializer`, ShopRow credit keys in `ShopReadSerializer`, `shop_name` on both sides of the audit contract, `credit-contact` in both templates and `contact.ts`, and the `shops/<int:shop_id>/credits/` route. No side deviated, so no fix was needed.
- Throwaway PostgreSQL run (initdb, port 54329, `config.settings.test_pg`) passed all 85 tests across the audit-log API and selector tests, Shops selector tests, shop credits view tests and the new walk-through. This closes RESEARCH Pitfall 5 / assumption A2 (text comparison of `entity_id`) and the Plan 33-02 note to re-run under `test_pg`.
- Runbook: the interim "composer shows generic failure copy" bullet is replaced with the shipped copy; a "## Phase 33 behaviour changes" section documents Staff scoping on `GET /api/v1/shops/` and `/{id}/` (web and JWT mobile; out-of-scope retrieve 404), the new `GET /api/v1/shops/{id}/credits/` (no-store, 120/minute), credit fields on the Shops list, Org Admin credit events with Superadmin names, Buy More mailto, and that organisations still start at 0 credits. CLAUDE.md section 3: the three credits rows now mention the tenant shop credits read.
- Gates: full backend suite 1650 passed / 22 skipped, coverage 90.34% (gate 85%); mypy (354 files), ruff check and ruff format clean; `makemigrations --check` no changes; `check --deploy` no errors (21 warnings from the non-production test settings module); frontend 349 tests passed (39 files) and `tsc --noEmit` clean. Migration counts unchanged (credits 5, shops 9, common 4); `apps/credits` non-test imports of `apps.reviews`: 0.

## Section 27 review dispositions

The Agent tool was not available in this execution environment, so the four reviews were not run as the named subagents. Each checklist from the plan was walked inline against the phase diff (`9d339eb..HEAD` for apps, config, templates) and the findings below are those inline results. A subagent pass at `/gsd-verify-work` or before the PR would still add independent coverage.

### tenant-security-auditor (inline)

- `restrict_to_staff_scope` / `list_shops`: role-keyed (not id-list truthiness), organisation filter applied first, so empty scope returns nothing and a foreign-organisation region cannot leak even though `get_accessible_shop_ids` region expansion is not organisation-bounded. Covered by the 33-01 scope matrix. Disposition: pass.
- `ShopViewSet.get_queryset`: organisation filter from `TenantScopedViewSet` then the shared Staff rule; write actions remain `IsOrgAdmin`. The `syncing` action was already Staff-scoped. Disposition: pass.
- `get_accessible_shop_for_credits` / `ShopCreditsView`: one gate shared with list and retrieve, uniform 404 `shop_not_found` for out-of-scope, cross-organisation and unknown shops, `IsOrgScoped` refuses Superadmin (403 in the sweep), no writes, `no-store`. Disposition: pass.
- `CREDIT_AUDIT_FILTER` is used only by `list_audit_logs_for_org`; the Staff selector and shared `AUDIT_ENTITY_FILTER` are untouched; `shop_name` is `entity_type`-gated, bound to the row's organisation and text-compared. Disposition: pass.
- `credit-contact` is rendered with `json_script` on both pages (escaping tested in 33-05); the mailto builder takes no review data. Disposition: pass.
- (a) Superadmin actor names visible to Org Admins on credit rows and in the actor dropdown: accepted per research open question 2 (user decision at plan time); no concrete privacy rule broken; pinned by `test_actor_dropdown_includes_superadmin_for_org_admin_not_for_staff`. Disposition: accepted.
- (b) SCOPE-01 list behaviour change for Staff web and JWT mobile clients: accepted (ROADMAP, pre-approved); mobile clients that relied on seeing every shop will now see only theirs. Documented in the runbook. Disposition: accepted.
- (c) D-17 retrieve scoping (404 for out-of-scope Staff retrieve, not 403): consistent with the credits GET and leaks no existence. Disposition: accepted.
- (d) Pre-existing Staff-readable surfaces outside SCOPE-01's wording, recorded as follow-ups, not fixed here:
  - `ReviewTargetViewSet` list and history for an out-of-scope shop in the Staff's own organisation: organisation-bounded but not Staff-scoped. Severity low to medium (same-tenant read of review-target counts).
  - `allocation_status` / `has_regions` in the Shops list envelope: organisation-level aggregates visible to Staff. Severity low.
  - Neither was rated high, so the phase was not widened.

### orm-performance-auditor (inline)

- `list_shops(with_credits=True)`: one `FilteredRelation` annotation, equal query counts for 1 vs 20 shops (33-01 test), Paginator `.count()` works on the annotated queryset. Disposition: pass.
- `shop_name` correlated subquery: compares `CAST(id AS text)` to `entity_id`, which cannot use the shop primary-key index, but the subquery is bound by `organisation_id` (indexed) and the `CASE` evaluates it only for `entity_type="shop"` rows, so the scanned set is one organisation's shops. Equal counts 1 vs 20 (33-02 test). Severity low. Disposition: accepted.
- Credits GET: fixed-ceiling query test (33-04), reads only, never materialises. Disposition: pass.
- No migration and no new index: the phase adds only annotations and reads over existing indexed columns (`makemigrations --check` clean). Disposition: pass.
- Nit: `review_list` runs one extra single-row query for the organisation name. Not per-row. Disposition: accepted.

### code-reviewer (inline)

- Thin views and keyword-only read-only selectors: pass. New endpoint has explicit permission (`IsOrgScoped`), scoped throttle (`shop_credits` 120/minute, registered in settings) and drf-spectacular annotations; single-object response so pagination does not apply.
- Serializers only shape data (`get_total`, `get_credits_total` are arithmetic on selector output). mypy strict clean. Surgical scope: no unrelated refactors. No blockers; no changes made.

### frontend-react-builder (inline)

- Only weights 400/600 on new elements; no `font-medium`. Existing `toLocale*` calls in `ReplyComposer.tsx` and `ShopDetailsModal.tsx` pre-date the phase (no added lines match) and credit dates use `formatUtcDate`.
- a11y: `role="progressbar"` with `aria-valuenow`, `role="status"` / `role="alert"`, `aria-describedby` on the generate button, shared `Modal` reused with `dismissible` for stacking, `AbortController` cleanup in the card and composer effects. No blockers. Visual and OS-mail checks remain manual (see below).

## Deviations from Plan

None - plan executed exactly as written, apart from running the PostgreSQL proof with the walk-through test added to the four listed test files (85 tests rather than 4 files' worth), and recording the inline-review limitation above.

## Issues Encountered

- The Agent tool was unavailable, so the section 27 reviews were inline walk-throughs (disclosed above).
- `check --deploy` run with `config.settings.test` (as the plan specifies) reports 21 non-production warnings and zero errors; it does not exercise production settings.

## Follow-ups

- ReviewTargetViewSet Staff scoping and the `allocation_status` / `has_regions` envelope (tenant-security (d)).
- Manual and UI-SPEC backstop checks for `/gsd-verify-work`: colour bands in the real UI, OS mail client opening, two 360px composer checks, the 200-character / emoji mailto check, two-Escape ordering over stacked modals. CI `backend-pg` (pg_concurrency) remains authoritative after push.

## Milestone close hand-off

`/gsd-complete-milestone` must move `docs/completed/Requirements_Credits_System.md` to `docs/completed/` and update every `.planning` reference (CLAUDE.md section 28). Phase 29's CRED-02, CRED-04, CRED-05 and CQA-01 still show "Gaps Found" in REQUIREMENTS.md. The spec was not moved in this plan.

## Self-Check: PASSED

- `apps/credits/tests/test_phase33_flow.py` exists; commits c50a2a1, def4f55, 28873ac present on the branch.
- Acceptance greps: walk-through def count 1; "## Phase 33 behaviour changes" count 1; "Until Phase 33 ships the composer UI" count 0; "tenant shop credits read" in CLAUDE.md count 3; spec still at `docs/in-progress/`; `33-07` appears in 33-VALIDATION.md.
