# Phase 32: Superadmin Credit Controls - Research

**Researched:** 2026-11-11
**Domain:** Django/DRF Superadmin write paths over the Phase 29 credits ledger + React org-management widget (Create/Edit/View org, "Manage Credits" modal)
**Confidence:** HIGH (all findings come from reading the shipped code this session; no new libraries; the few design choices that are judgement calls are tagged `[ASSUMED]` in the Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Allocation edit — mid-month change UX (CRED-01, CRED-06)**
- **D-01:** The Create/Edit Organisation forms show a **live inline hint** under "Monthly credits per shop" that updates as the value changes — no confirm dialog. Wording intent:
  - 0 → N (N > 0): "Takes effect immediately for this month."
  - N → M (any other change, including → 0): "Takes effect {1st of next month, e.g. Dec 1}. Shops keep {N} this month."
  - Value 0 on Create (or unchanged at 0): the spec §8.1 helper ("Each shop in this organisation gets this many credits at the start of every month. Unused credits lapse.") plus a note that 0 means AI replies are off.
  Exact copy and placement are for `/gsd-ui-phase 32`.
- **D-02:** **N → 0 follows the same N → M rule** — shops keep N for the rest of the current month and get 0 from next month. There is no immediate "kill switch"; CRED-06 stays as written.
- **D-03:** The allocation is **editable regardless of organisation status** (active/disabled). No credit-specific behaviour is tied to org status.
- **D-04:** Create Organisation **defaults to 0** (feature off), per CRED-01 and the Phase 30 deploy note (CQA-02).

**"Manage credits" modal — shop list (CSUP-01)**
- **D-05:** The modal lists the org's **active shops only**. Deactivated shops are not shown and cannot receive bonus.
- **D-06:** Each row shows the shop name, **"Remaining {n}"** prominently, and a muted breakdown **"Monthly {allocated} · Bonus {bonus} · Used {consumed}"** (spec §8.2 read-only state). A shop with no current-month balance row shows its **virtual** balance (Phase 29 CRED-05 selector semantics) — listing must never create rows.
- **D-07:** The list has a **name search box and server-side pagination** (CLAUDE.md §8: every list endpoint paginated; must handle a ~200-shop brand).
- **D-08:** Each row has an **"Add bonus" button**; clicking switches the modal to that shop's bonus form, with a **Back to list** control. (No dropdown picker.)

**Bonus allocation flow (CSUP-01)**
- **D-09:** **Single-step confirm with a live preview**: as the amount is typed, the form shows before → after (e.g. "Remaining 35 → 85 · Bonus 20 → 70"); the **Allocate** button is the only confirmation. No separate review screen.
- **D-10:** **No extra guard** beyond the per-allocation 1–10,000 range: no large-amount warning, no cumulative monthly bonus cap.
- **D-11:** On success: a toast ("Added {n} credits to {shop}"), then **return to the shop list** with that row's numbers refreshed, so several shops can be topped up in one session.
- **D-12:** On the **409 period mismatch** (UTC month rolled over while the dialog was open — roadmap note: request echoes the displayed period), show an explanatory message ("A new month started — balances have been refreshed. Review and try again."), **reload that shop's new-month numbers, and keep the typed amount and reason**. No generic error/close.
- **D-13:** Reason stays **optional** (spec §8.2), stored on the BONUS_ALLOCATION ledger row's note.

**Where the allocation is shown (Superadmin only)**
- **D-14:** The Superadmin organisations table gets a **"Credits/shop" column**; 0 renders as a muted "Off".
- **D-15:** The View Organisation modal shows **"Monthly credits per shop: {M}"** and, when the current month still runs on a different value because of an N → M change, a note such as **"This month: {N} (changes to {M} on {1st of next month})"**. How "pending" is derived (e.g. from current-month materialised balances vs the org field) is the planner's call; it must be a read that never writes.
- **D-16:** The "Manage credits" modal header shows **org name, current month, and allocation per shop** only (e.g. "Acme — November 2026 · 100 credits per shop"). **No org-level aggregate totals** — cross-shop usage reporting is out of scope (spec §8.3).
- **D-17:** The org row action is labelled **"Manage credits"**, placed alongside "Adjust stores" in the row actions menu.

**Edge cases settled during /gsd-ui-phase 32**
- **D-18:** A change counts as "immediate" (the 0 → N case) **only when every shop in the org had 0 credits for the whole current month**, i.e. no current-month balance exists with `allocated_credits > 0`. Otherwise (e.g. 100 → 0 earlier this month, then 0 → 50) it is an N → M change and applies from the 1st of next month. The Edit form's live hint (D-01) and the backend use this same rule.
- **D-19:** Allocating bonus to a shop that was **deactivated while the modal was open** returns **404**; the UI shows a toast ("This shop is no longer active") and returns to a reloaded list without that shop (consistent with D-05).

**Carried forward (locked by earlier phases / roadmap — do not re-decide)**
- Allocation range 0–10,000 is enforced by DB CHECK `org_monthly_credit_allocation_range` + model validators (Phase 29, T-29-08).
- `ensure_balance(shop_id=...)` is the only way to materialise a balance; read selectors (`get_shop_credit_balance`, `annotate_credit_state`) never write (Phase 29, CRED-05).
- Bonus: org derived server-side from the shop; the request echoes the displayed period (409 on mismatch); balance update is an `F()` increment after `ensure_balance()`; one BONUS_ALLOCATION ledger row + one `shop.credits.bonus_allocated` AuditLog row per allocation (ROADMAP Phase 32 notes, CSUP-01).
- CRED-01 persistence: add the field to `update_organisation`'s `_UPDATABLE_FIELDS`; write `organisation.credits.set` AuditLog **only on an actual change** (ROADMAP notes).
- CRED-06 mechanism: on N → M, materialise current-month balance rows at the old value inside the org-edit atomic; first-time 0 → N is effective immediately (ROADMAP notes).
- Endpoints are non-tenant (`IsAuthenticated & IsSuperadmin`, not `TenantScopedViewSet`), paginated and throttled; AuditLog payloads carry ids and counts only (CLAUDE.md §22).
- Run `tenant-security-auditor` + `orm-performance-auditor` (ROADMAP note; CLAUDE.md §27).

### Claude's Discretion
- Exact copy, layout, toast styling and empty states — defer to `/gsd-ui-phase 32` (roadmap says run it before planning). *(UI-SPEC now exists and is approved.)*
- Page size and search semantics for the shop list (prefix vs contains), within D-07.
- API shape (endpoint paths, nested under the org viewset vs separate) and how D-15's "pending change" is computed, within the carried-forward constraints.

### Deferred Ideas (OUT OF SCOPE)
- Org-level aggregate credit totals / cross-shop usage reporting for Superadmin — spec §8.3 future scope.
- Immediate "kill switch" (N → 0 effective now) — rejected for this phase (D-02); would need a CRED-06 change.
- Cumulative monthly bonus cap or large-amount warning — rejected (D-10).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRED-01 | Superadmin sets monthly credits per shop (0–10,000, default 0) on Create/Edit Organisation; persists via `update_organisation` whitelist; every change writes `organisation.credits.set` | §Org service changes (actor kwarg, `_UPDATABLE_FIELDS`, create kwarg, serializers, audit only on real change), §Pitfall 1/2/9 |
| CRED-06 | 0 → N immediate for current month; any other change next month; current-month balances keep previous value | §CRED-06 algorithm (D-18 detection, bulk materialise at old value, zero-row bump), §Pitfalls 3–6 |
| CSUP-01 | Org-row credits action: shop list with current balances, pick shop, bonus 1–10,000 + reason, before/after preview, one BONUS_ALLOCATION ledger row + one `shop.credits.bonus_allocated` AuditLog row | §Bonus service, §List endpoint, §Frontend (ManageCreditsModal), §Pitfalls 4/7/8 |
| CSUP-02 | Superadmin credit endpoints return 403 to non-Superadmins; no Org Admin/Staff path changes allocation/bonus | §Security Domain, §Validation map (403 for ORG_ADMIN and STAFF_ADMIN on all 3 write/read surfaces + PATCH) |
</phase_requirements>

## Summary

Everything Phase 32 needs from Phase 29 is already shipped and verified by reading it: `ShopCreditBalance` / `CreditTransaction` with DB CHECKs, `ensure_balance`, `current_period`/`next_period_start`, `get_shop_credit_balance`, and `annotate_credit_state`. `Organisation.monthly_credit_allocation` and its CHECK exist (migration `organisations/0003`). `update_organisation` currently has no actor, no atomic block, no audit write, and a whitelist that excludes the credit field; the org list is rendered by `OrganisationListSerializer` on **both** the server-rendered page (`orgs_json`) and the DRF API, so one serializer + one selector annotation feeds the table, Edit and View modals. No new dependencies are needed on either side.

The hard part is CRED-06, not the bonus. Three facts from the shipped code drive the design: (1) the virtual-balance fallback reads the org's **live** allocation, so on an N → M change every shop without a current-month row would silently jump to M — hence rows must be materialised at the old value *before* the org field is saved; (2) `ShopCreditBalance.organisation` has `related_name="+"`, so there is no reverse accessor from `Organisation` — "this month's value" must be a `Subquery` on `credit_bal_org_period_idx`; (3) a balance row with `allocated_credits=0` can legitimately exist (a bonus to a 0-allocation org calls `ensure_balance`, which writes a row with no INITIAL ledger row), so "0 → N is immediate" is **not** achieved by virtual reads alone — those zero rows must be raised to N or those shops would never see the allocation this month.

**Primary recommendation:** Put all org-edit credit orchestration in `update_organisation` (new `actor` kwarg, `@transaction.atomic`, `select_for_update` on the org row, branch on D-18), with two set-based helpers in `apps/credits/services/allocation.py` (`materialise_org_balances`, `raise_zero_balances`); put bonus in `apps/credits/services/bonus.py`; serve the two new endpoints from `apps/credits/views.py` at the spec paths (`/api/v1/superadmin/...`); add `monthly_credit_allocation` + `current_month_credit_allocation` to `OrganisationListSerializer`; build one `ManageCreditsModal` with an internal `view` state.

### Items that contradict or tighten CONTEXT / UI-SPEC (planner must resolve)

1. **UI-SPEC hint rule vs D-18 (real contradiction).** UI-SPEC says "N is the org's saved `monthly_credit_allocation`" and shows "N = 0 → Takes effect immediately". Under D-18 that is wrong after `100 → 0` then `0 → 50` in the same month (saved N = 0 but shops hold 100 this month → deferred). The Edit hint must key on the server-supplied `current_month_credit_allocation` (this month's value), not the saved field: *immediate iff saved == 0 AND current_month == 0*; otherwise the "Shops keep {current_month} this month" copy. [VERIFIED by reasoning against `apps/credits/models.py` + D-18; see Pitfall 3]
2. **"`ensure_balance` is the only way to materialise a balance" vs ROADMAP "materialise current-month rows for the org inside the edit atomic".** Looping `ensure_balance` per shop is ~6 queries/shop (≈6,000 in one request for the 1,000-store maximum, holding the org row lock). Recommended: a set-based sibling helper in the same module producing byte-identical rows/ledger/audit, guarded by an equivalence test. Looping `ensure_balance` is an acceptable fallback for small orgs. Planner/user should confirm; treat the carried-forward line as "no materialisation on read paths". [CITED: apps/credits/services/allocation.py:30-70]
3. **UI-SPEC subtitle "A = allocation in force … (the value virtual balances use)"** is ambiguous during a pending N → M (virtual balances use the live M; materialised shops hold N). Use `current_month_credit_allocation` (D-15's "This month: N") for the modal subtitle and the View note so they agree.
4. **UI-SPEC/D-19 copy mismatch.** D-19 says toast "This shop is no longer active"; UI-SPEC says "This shop is no longer available." Pick one (UI-SPEC is the later, approved artefact).
5. **Spec §10 paths vs repo.** Spec lists `POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/` and `PATCH /api/v1/superadmin/organisations/{org_id}/`; the repo's org viewset is at `/api/v1/organisations/` (no `superadmin/` prefix). Keep the PATCH where it is (the React widget uses it); give the **new** endpoints the spec `superadmin/` paths.
6. **Django admin bypass.** `OrganisationAdmin` has only `readonly_fields = ("created_at", "updated_at")`, so `monthly_credit_allocation` is editable there with no materialisation and no audit row. Recommend making it read-only in admin once Phase 32 ships (Open Question 2).
7. **Phase 31 in flight.** Baseline `pytest apps/credits apps/organisations` currently has 2 failing tests in `apps/credits/tests/test_reaper.py` (Phase 31-02 WIP, unrelated). Phase 32 must not depend on `lapsed_at` (it does not: current-month rows are never lapsed).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist allocation + audit + CRED-06 timing | API / Backend (`organisations` service orchestrating `credits` helpers) | Database (CHECK `org_monthly_credit_allocation_range`) | Multi-step write that must be atomic and lock-ordered |
| Materialise / raise balance rows | API / Backend (`credits` service) | Database (unique + CHECK constraints) | Ledger invariants live in `apps/credits` |
| Bonus allocation | API / Backend (`credits.services.bonus`) | Database (`credit_balance_no_overspend`, `credit_tx_delta_sign`) | Single atomic: lock → F() → ledger → audit |
| Shop list with virtual balances | API / Backend (selector via `annotate_credit_state`) | Database (LEFT JOIN) | Never writes; one query |
| "Pending change" derivation (D-15/D-18) | API / Backend (org list annotation) | Browser (hint copy) | Server owns truth; browser only formats |
| Live hint, preview, 409 handling, modal state machine | Browser / Client (React widget) | — | Pure presentation over server numbers |
| Superadmin-only enforcement | API / Backend (`IsAuthenticated & IsSuperadmin`) | Browser (row action only rendered in Superadmin page) | Server is authoritative; UI hiding is belt-and-braces |
| Org list page shell | Frontend Server (Django template + `json_script`) | Browser (React hydrates) | Existing pattern, unchanged |

## Standard Stack

No new packages on either side. [VERIFIED: apps/credits, apps/organisations, frontend/package.json read this session]

### Core (already installed — reuse)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.x | ORM, `select_for_update`, `transaction.atomic` | Project stack (CLAUDE.md §2) |
| djangorestframework | pinned in pyproject | `APIView`/`GenericAPIView`, `PageNumberPagination`, `ScopedRateThrottle` | Project stack (CLAUDE.md §8) |
| drf-spectacular | pinned | `extend_schema` for the 2 new endpoints | CLAUDE.md §24 step 11 |
| pytest 8.3.3 / pytest-django 4.9.0 / factory-boy 3.3.3 | pinned | Backend tests | `pyproject.toml` |
| React 19.2.5, lucide-react 1.8.0, focus-trap-react 12.0.0, Tailwind 4.2.4 | pinned | Modal UI | `frontend/package.json` |
| vitest 2.1.8 + @testing-library/react 16.1.0 + user-event 14.5.2 | pinned | Widget tests | `frontend/package.json` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Set-based `materialise_org_balances` | Loop `ensure_balance` per shop | Loop = exact reuse + zero drift risk, but ~6 queries/shop under an org-row lock (up to 1,000 shops). Use only if orgs stay small |
| `Subquery(Max(allocated))` annotation for "this month" | Python-side second query per org page | Subquery keeps the org list at its existing query count; Python-side needs one extra query anyway |
| New views in `apps/credits/views.py` | `@action` on `OrganisationViewSet` | Viewset is a `ModelViewSet` with a `get_serializer_class` switch; separate small views keep `credits` the owner of its endpoints and give each its own throttle scope |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed or recommended by this phase. Audit not applicable. **Packages removed due to [SLOP] verdict:** none. **Packages flagged [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
 Superadmin browser (React widget, org-management)
   |
   |  PATCH /api/v1/organisations/{id}/  {monthly_credit_allocation: M, ...}
   v
 OrganisationViewSet.perform_update  --(actor=request.user)-->  update_organisation()  [@atomic]
   |                                                             1. lock org row (FOR UPDATE)  -> authoritative OLD
   |                                                             2. if M != OLD:
   |                                                                  D-18: exists(current-month balance allocated>0)?
   |                                                                    no & OLD==0 -> raise_zero_balances(M)   (immediate)
   |                                                                    else       -> materialise_org_balances(OLD)  (rows at OLD for all shops)
   |                                                             3. save org field
   |                                                             4. AuditLog organisation.credits.set (before/after/effective/counts)
   |
   |  GET /api/v1/superadmin/organisations/{org}/credits/shops/?search=&page=
   v
 CreditShopListView [IsAuthenticated & IsSuperadmin, scope superadmin_credits_read]
   -> org = not_deleted().get(pk)   (404)
   -> annotate_credit_state(Shop.filter(org, is_active=True)[.name search]).order_by(name, pk)  (1 LEFT JOIN, never writes)
   -> paginated {count,next,previous,period,allocation_per_shop,results[]}

 POST /api/v1/superadmin/shops/{shop}/credits/bonus/  {amount, reason?, period_year, period_month}
   v
 BonusAllocationView [scope superadmin_credits_write] -> allocate_bonus()
   1. period echo != current_period()  -> 409 (BEFORE any write; body carries fresh balance)
   2. shop active & org not deleted    -> else 404
   3. atomic: lock org row -> ensure_balance(period) -> lock balance row
              -> UPDATE bonus_credits = F()+n, updated_at
              -> CreditTransaction BONUS_ALLOCATION (+n, COMMITTED, actor, note)
              -> AuditLog shop.credits.bonus_allocated
   -> 201 {balance snapshot, transaction_id}

 Phase 30 reserve_credits (concurrent):  balance-row lock only (never the org lock)  => no lock cycle
```

### Recommended Project Structure
```
apps/credits/
  services/allocation.py     # + materialise_org_balances, raise_zero_balances (next to ensure_balance)
  services/bonus.py          # NEW  allocate_bonus
  selectors/balances.py      # + get_org_current_month_allocation, org_has_current_month_allocation
  selectors/shop_credits.py  # NEW  list_org_shop_credits (annotate_credit_state + active + search + order)
  exceptions.py              # + PeriodMismatchError, ShopNotAvailableError
  serializers.py             # NEW  CreditShopRowSerializer, BonusAllocationSerializer, BonusResultSerializer
  views.py                   # NEW  CreditShopListView, BonusAllocationView
  api_urls.py                # NEW  included from config/urls.py under "api/v1/"
  tests/test_bonus.py, test_org_allocation.py (service), test_views.py, + additions to test_pg_concurrency.py
apps/organisations/
  services/organisations.py  # update_organisation(+actor, atomic, credit branch), create_organisation(+monthly_credit_allocation)
  selectors/organisations.py # _base_queryset + current_month_credit_allocation Subquery annotation
  serializers.py             # List(+2 fields), Create(+field), Update(+field)
  views.py                   # perform_update passes actor
frontend/src/widgets/org-management/
  ManageCreditsModal.tsx (+ .test.tsx), creditsApi.ts, useCreditShops.ts, creditHint.ts (+ .test.ts)
  types.ts, api.ts, CreateOrgModal.tsx, EditOrgModal.tsx, ViewOrgModal.tsx, OrgTable.tsx, (+ existing tests' OrgRow fixtures)
frontend/src/entrypoints/org-management.tsx   # creditsRow state + onOpenManageCredits (3 places)
```

### Pattern 1: Org edit orchestration (CRED-01 + CRED-06)
**What:** One atomic function owns the lock, the D-18 branch, the field save and the audit row.
**When:** every `monthly_credit_allocation` change.
**Key rules:** (a) lock the org row and read OLD from the locked row, not from the (possibly stale) instance; (b) materialise/raise **before** saving the new value (so any `ensure_balance` read inside the transaction still sees OLD); (c) audit only if `new != old`; (d) payload = ids and counts only.
```python
# apps/organisations/services/organisations.py  (sketch — not final code)
@transaction.atomic
def update_organisation(*, organisation, actor=None, **data):
    data.pop("email", None)
    ...  # existing number_of_stores guard unchanged
    credit_change = None
    if "monthly_credit_allocation" in data:
        old = (Organisation.objects.select_for_update(of=("self",))
               .values_list("monthly_credit_allocation", flat=True).get(pk=organisation.pk))
        organisation.monthly_credit_allocation = old          # generic loop now compares to truth
        new = data["monthly_credit_allocation"]
        if new != old:
            period = current_period()
            if old == 0 and not org_has_current_month_allocation(organisation_id=organisation.pk, period=period):
                touched = raise_zero_balances(organisation_id=organisation.pk, allocation=new, period=period)
                effective = "immediate"
            else:
                touched = materialise_org_balances(organisation_id=organisation.pk, allocation=old, period=period)
                effective = "next_month"
            credit_change = (old, new, effective, touched, period)
    ...  # existing setattr/save(update_fields) loop
    if credit_change:
        AuditLog.objects.create(organisation=organisation, actor=actor, entity_type="organisation",
            entity_id=str(organisation.pk), action="organisation.credits.set",
            before_data={"monthly_credit_allocation": old},
            after_data={"monthly_credit_allocation": new, "effective": effective,
                        "shops_touched": touched, "period_year": period.year, "period_month": period.month})
    return organisation
```
`[VERIFIED: apps/organisations/services/organisations.py:181-211]` the current function is non-atomic, has no actor and the whitelist at `:19`. `[ASSUMED]` AuditLog entity naming (`entity_type="organisation"`) — nothing in the repo constrains it yet (`AUDIT_ENTITY_FILTER` only exposes `action_item` / `review` to Org Admin, so these rows are invisible to tenants until Phase 33 decides).

### Pattern 2: CRED-06 helpers (set-based, idempotent, caller holds org lock)
```python
# apps/credits/services/allocation.py  (sketch)
def materialise_org_balances(*, organisation_id: int, allocation: int, period: Period | None = None) -> int:
    """Give every shop of the org (active AND inactive — Phase 29 D-13) a row for `period` at
    `allocation` if it has none. Mirrors ensure_balance: INITIAL_ALLOCATION + shop.credits.allocated
    only when allocation > 0, actor=None. Returns the number of rows this call created."""
    p = period or current_period()
    have = set(ShopCreditBalance.objects.filter(shop__organisation_id=organisation_id,
              period_year=p.year, period_month=p.month).values_list("shop_id", flat=True))
    missing = [pk for pk in Shop.objects.filter(organisation_id=organisation_id)
               .order_by("pk").values_list("pk", flat=True) if pk not in have]   # sorted: no bulk-insert deadlocks
    if not missing:
        return 0
    ShopCreditBalance.objects.bulk_create(
        [ShopCreditBalance(shop_id=s, organisation_id=organisation_id, period_year=p.year,
                           period_month=p.month, allocated_credits=allocation) for s in missing],
        ignore_conflicts=True)          # a concurrent ensure_balance winner already holds the row
    if allocation > 0:
        rows = list(ShopCreditBalance.objects.filter(organisation_id=organisation_id, period_year=p.year,
                    period_month=p.month, shop_id__in=missing).values_list("pk", "shop_id"))
        done = set(CreditTransaction.objects.filter(shop_credit_balance_id__in=[r[0] for r in rows],
                    transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION)
                   .values_list("shop_credit_balance_id", flat=True))
        todo = [r for r in rows if r[0] not in done]
        CreditTransaction.objects.bulk_create([...INITIAL +allocation, actor=None... for pk, s in todo],
                                              ignore_conflicts=True)
        AuditLog.objects.bulk_create([...shop.credits.allocated... for pk, s in todo])
    return len(missing)

def raise_zero_balances(*, organisation_id: int, allocation: int, period=None) -> int:
    """0 -> N immediate: rows that exist at allocated_credits=0 (created by a bonus on a 0-allocation
    org) are raised to `allocation`, each with one INITIAL_ALLOCATION (+allocation) and one
    shop.credits.allocated row, exactly as if lazily created at N. Shops with no row stay virtual."""
```
`bulk_create` on `CreditTransaction` is allowed (only `update_conflicts=True` is blocked). `[VERIFIED: apps/credits/managers.py:21-40]`. `QuerySet.update()` on `ShopCreditBalance` must set `updated_at` explicitly (model docstring, `apps/credits/models.py:25-27`). `bulk_create(ignore_conflicts=True)` does not return PKs, hence the re-SELECT.

### Pattern 3: Bonus service
```python
# apps/credits/services/bonus.py  (sketch)
def allocate_bonus(*, shop_id: int, amount: int, reason: str | None, period: Period, actor_id: int) -> BonusResult:
    current = current_period()
    if period != current:                       # BEFORE any write — must not materialise next month's row
        raise PeriodMismatchError(current=current)
    org_id = (Shop.objects.filter(pk=shop_id, is_active=True).exclude(organisation__status="DELETED")
              .values_list("organisation_id", flat=True).first())
    if org_id is None:
        raise ShopNotAvailableError(shop_id=shop_id)
    note = (reason or "").strip() or None       # D-04: NULL == no note
    with transaction.atomic():
        Organisation.objects.select_for_update(of=("self",)).values_list("pk", flat=True).get(pk=org_id)  # org lock FIRST
        balance, _ = ensure_balance(shop_id=shop_id, period=period)
        locked = (ShopCreditBalance.objects.select_for_update(of=("self",))
                  .values("allocated_credits", "bonus_credits", "consumed_credits").get(pk=balance.pk))
        ShopCreditBalance.objects.filter(pk=balance.pk).update(
            bonus_credits=F("bonus_credits") + amount, updated_at=timezone.now())
        tx = CreditTransaction.objects.create(shop_credit_balance_id=balance.pk, shop_id=shop_id,
            organisation_id=org_id, transaction_type=CreditTransaction.Type.BONUS_ALLOCATION,
            status=CreditTransaction.Status.COMMITTED, credits_delta=amount, actor_id=actor_id, note=note)
        AuditLog.objects.create(organisation_id=org_id, actor_id=actor_id, entity_type="shop",
            entity_id=str(shop_id), action="shop.credits.bonus_allocated",
            before_data={"bonus": locked["bonus_credits"]},
            after_data={"amount": amount, "bonus": locked["bonus_credits"] + amount,
                        "has_reason": note is not None, "transaction_id": tx.pk,
                        "period_year": period.year, "period_month": period.month})
```
Do **not** copy the reason text into AuditLog (free text; CLAUDE.md §22; CONTEXT "ids and counts only"). The ledger `note` (max 255) is the only place it lives.

### Pattern 4: Shop list endpoint
`list_org_shop_credits(organisation_id, search)` = `annotate_credit_state(queryset=Shop.objects.filter(organisation_id=…, is_active=True) [+ name__icontains]).order_by("name", "pk")` (order must include `pk`: names are not unique, pagination would otherwise be unstable). Subclass `PageNumberPagination` with `page_size = 10`; override the response in the view to add top-level `period` and `allocation_per_shop` (= this-month allocation, see Pitfall 3). Serializer reads the annotation names verbatim: `credit_allocated`, `credit_bonus`, `credit_consumed`, `credit_remaining`, `credit_materialized` `[VERIFIED: apps/credits/selectors/balances.py:94-137]`.

### Pattern 5: "This month's value" for D-15 / D-18 / hint (read-only)
```python
cur = current_period()
_this_month = (ShopCreditBalance.objects
    .filter(organisation_id=OuterRef("pk"), period_year=cur.year, period_month=cur.month)
    .order_by().values("organisation_id").annotate(m=Max("allocated_credits")).values("m"))
qs.annotate(current_month_credit_allocation=Coalesce(Subquery(_this_month, output_field=IntegerField()),
                                                    F("monthly_credit_allocation")))
```
Defined as MAX of this month's materialised `allocated_credits`, else the live field. A `Subquery` is required because `ShopCreditBalance.organisation` has `related_name="+"` `[VERIFIED: apps/credits/models.py:41]`. It is served by `credit_bal_org_period_idx` `[VERIFIED: apps/credits/models.py:79]` and adds **no query** to the org list (existing ceilings: selector `<= 3`, API `<= 7` `[VERIFIED: apps/organisations/tests/test_selectors.py:73, test_views.py:110]`). Pending note shows when `current_month_credit_allocation != monthly_credit_allocation`.

### Anti-Patterns to Avoid
- **Saving the org field before materialising** — `ensure_balance` in the same transaction would seed at M, defeating CRED-06.
- **Calling `ensure_balance` before the period check** — a stale-month 409 must not create a row.
- **Using `exclude(credit_balances__period_year=…, credit_balances__period_month=…)`** on the multi-valued relation to find shops lacking a row — conditions are not guaranteed to bind to the same related row; use a Python set difference or `~Exists(...)`.
- **`updated_at` omitted in `QuerySet.update()`** — `auto_now` does not fire.
- **Writing the reason into `AuditLog`.**
- **Treating `ApiError.fieldErrors` as field errors for a 409** — `handle()` stores any JSON error body there `[VERIFIED: frontend/src/widgets/org-management/api.ts:46-57]`; the 409 body is an object, not `string[]`. Preserve the raw body (add `body` to `ApiError` or use a dedicated `creditsApi.ts` handler).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Virtual balance for the list | Custom per-shop loop / Python merge | `annotate_credit_state` | One LEFT JOIN, never writes, N+1-safe, already tested (query-count and never-writes tests exist) |
| Single-shop balance snapshot (409 body, 201 body) | Ad-hoc `.get()` + arithmetic | `get_shop_credit_balance(shop_id, period)` | Same semantics as the list; read-only |
| Period math | `date.today()` / local time | `current_period()` / `next_period_start()` | UTC seam, single test patch point (`utc_now`) |
| Row creation + INITIAL + audit for one shop | New insert code | `ensure_balance` | Race-safe `get_or_create` in its own savepoint |
| Pagination | Manual offset/limit | DRF `PageNumberPagination` subclass | CLAUDE.md §8 |
| Throttling | Redis counters | DRF `ScopedRateThrottle` + new scopes in `DEFAULT_THROTTLE_RATES` | Existing pattern (`credit_cost`, `generate_reply`) |
| Toasts | New toast UI | `emitToast` | `frontend/src/lib/toast.ts` |
| Modal shell / focus trap | New dialog | `Modal` (size `lg`) | Esc, focus-trap, footer slot |
| Month label in subtitle | Locale-dependent `Intl` month names | Hard-coded month-name array + UTC fields | `en-GB` short month for September renders "Sept" in recent ICU — breaks deterministic tests and the "1 Dec 2026" contract `[ASSUMED]` |

**Key insight:** every invariant this phase must preserve (one INITIAL per balance, no overspend, append-only ledger, never-write reads) is already enforced by Phase 29 constraints; Phase 32's job is correct *ordering and locking*, not new invariants.

## Common Pitfalls

### Pitfall 1: Stale instance as the "old" allocation
**What goes wrong:** `update_organisation(organisation=…)` receives the instance loaded by `get_object()`; two concurrent edits both see the same OLD.
**Why:** current code compares against the instance and is not atomic.
**Avoid:** `select_for_update` on the org row inside `@transaction.atomic`, read OLD from the locked row, then reuse it for change detection and the audit `before_data`.
**Warning signs:** two `organisation.credits.set` rows with the same `before`; materialised rows at the wrong value.

### Pitfall 2: Stale Edit form silently reverting another admin's change
**What goes wrong:** Admin A opens Edit (allocation 0), Admin B sets 0 → 50, A saves a name change and the modal posts `monthly_credit_allocation: 0` → 50 → 0 (deferred).
**Avoid:** send the field only when it differs from the value captured at open (client-side) — cheap and removes the silent revert. `[ASSUMED]` UI-SPEC says "payload includes the field only alongside the other fields"; this is a small refinement within it.

### Pitfall 3: "This month" ≠ saved field (D-18 vs UI-SPEC)
**What goes wrong:** after `100 → 0` mid-month the saved field is 0 but every shop holds 100 this month. Hint, View note and modal subtitle must show 100 as "this month". After `100 → 0 → 50` the second change is *deferred* (rows with `allocated > 0` exist) and shops lacking rows are materialised at the **current live value (0)**.
**Avoid:** drive all three UI surfaces from `current_month_credit_allocation` (Pattern 5); backend D-18 test is `ShopCreditBalance.filter(organisation_id, period, allocated_credits__gt=0).exists()` with `old == 0`.

### Pitfall 4: 0 → N leaves zero-rows behind
**What goes wrong:** Superadmin bonus on a 0-allocation org creates a row `allocated=0, bonus=n` (no INITIAL, by design `[VERIFIED: apps/credits/services/allocation.py:49]`). A later 0 → N "immediate" change is invisible to that shop because the row has its own `allocated_credits`.
**Avoid:** `raise_zero_balances` (set `allocated_credits=N` where it is 0, add INITIAL + `shop.credits.allocated`). Test: bonus on 0-org, then 0 → 50, assert `remaining == 50 + bonus`.

### Pitfall 5: Month-boundary in CRED-06 and bonus
**What goes wrong:** period computed twice (check vs write) straddles midnight UTC.
**Avoid:** compute `current_period()` once per operation and pass the same `Period` to every helper/`ensure_balance`. For bonus, validate the echo against `current_period()` then write to the **echoed** period (what the user saw). Tests patch `apps.credits.services.periods.utc_now`.

### Pitfall 6: Lock ordering with Phase 30 `reserve_credits`
**What goes wrong:** deadlock if bonus locks balance then org while edit locks org then balance.
**Avoid:** global order **org row → balance row(s)**. Org edit and bonus take the org lock first; `reserve_credits` takes only the balance row lock `[VERIFIED: apps/credits/services/consumption.py:131-141]` and never the org lock, so no cycle. Insert balance rows in `pk` order. A bonus and a reservation on the same balance simply serialise on that row; the bonus only increases `allocated+bonus`, so `credit_balance_no_overspend` cannot trip. On a lost `get_or_create` race the loser blocks until the winner commits (documented in `allocation.py` module docstring).
**Why the org lock in bonus:** without it a bonus that creates a zero-row concurrently with a 0 → N edit can commit a row the edit's UPDATE never saw (SQLite hides this; only the `pg_concurrency` job can prove it).

### Pitfall 7: Deactivated shop / deleted org
`D-19` → 404 from `Shop.filter(pk, is_active=True)`; also exclude `organisation__status="DELETED"` (org viewset's `not_deleted()` already 404s the list endpoint for deleted orgs, the bonus path has no org in the URL so the service must check). One 404 body for "not found / inactive / deleted org" (no existence oracle needed for a Superadmin, but keep it uniform).

### Pitfall 8: Existing frontend fixtures and exact-payload tests
`OrgRow` gains required fields; `tsc --noEmit` (in `npm run build`) type-checks `*.test.tsx` (`tsconfig include: ["src"]`). Fixtures typed `OrgRow` in `OrgTable.test.tsx`, `StoreAllocationModal.test.tsx`, `DeleteConfirmModal.test.tsx`, `ResendInvitationModal.test.tsx` need the two new fields or the build breaks (vitest itself will not notice). `[VERIFIED: grep of allow_custom_sync_depth in *.test.tsx]`

### Pitfall 9: `create_organisation` TypeError
`perform_create` does `create_organisation(created_by=…, **serializer.validated_data)`; once `monthly_credit_allocation` is a serializer field the service **must** accept it or every create 500s `[VERIFIED: apps/organisations/views.py:268-273, services/organisations.py:33-43]`. Decide: audit on create only if `> 0` (a 0 default is not a "change"). `[ASSUMED]`

### Pitfall 10: Initial focus in the two-view modal
UI-SPEC wants focus on the search input. `Modal` wraps `FocusTrap` with no `initialFocus`; focus-trap 8.0.1 keeps `document.activeElement` if it is already inside the container `[VERIFIED: frontend/node_modules/focus-trap/index.js:316-317]`, so `autoFocus` on the input works; add a test. After a successful allocation, restore focus to that row's "Add bonus" button.

### Pitfall 11: Stale responses in the list
Debounced search + paging can interleave; use `AbortController` or a request counter (precedents: `useActionItems.ts`, `TeamTable.tsx` debounce at 300 ms).

## Runtime State Inventory

Not a rename/refactor phase — omitted. (Related stored state: no backfill; orgs start at 0 and are enabled through this phase — CQA-02.)

## Code Examples

### DRF view skeleton (Superadmin-only, scoped throttle, spectacular)
```python
# apps/credits/views.py  (sketch)
class CreditShopListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadmin]        # [VERIFIED: apps/accounts/permissions.py:13-25]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "superadmin_credits_read"

    @extend_schema(...)
    def get(self, request, org_id: int):
        org = get_object_or_404(Organisation.objects.not_deleted(), pk=org_id)
        qs = list_org_shop_credits(organisation_id=org.pk, search=request.query_params.get("search", ""))
        paginator = CreditShopPagination(); page = paginator.paginate_queryset(qs, request, view=self)
        resp = paginator.get_paginated_response(CreditShopRowSerializer(page, many=True).data)
        resp.data["period"] = {...}; resp.data["allocation_per_shop"] = get_org_current_month_allocation(org)
        return resp

class BonusAllocationView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "superadmin_credits_write"
    def post(self, request, shop_id: int):
        ser = BonusAllocationSerializer(data=request.data); ser.is_valid(raise_exception=True)
        try:
            result = allocate_bonus(shop_id=shop_id, actor_id=request.user.pk, period=Period(...), **...)
        except PeriodMismatchError as exc:   # 409 + fresh balance (read-only get_shop_credit_balance)
            ...
        except ShopNotAvailableError:        # 404
            raise NotFound(...)
        return Response(..., status=201)
```
Rates to add to `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` (`config/settings/base.py`, next to `credit_cost` at line ~436): `"superadmin_credits_read": "120/minute"`, `"superadmin_credits_write": "30/minute"` `[ASSUMED values]`. Throttle test must patch `ScopedRateThrottle.THROTTLE_RATES` (DRF snapshots rates at import) and `caches["throttle"].clear()` is already an autouse fixture in the org tests conftest.

### Request/response contract (recommended)
```
GET  /api/v1/superadmin/organisations/{org_id}/credits/shops/?search=&page=
  200 {count,next,previous, period:{year,month}, allocation_per_shop:int,
       results:[{id,name,allocated,bonus,consumed,remaining,is_materialized}]}
POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/
  body {amount:1..10000, reason?:str<=255, period_year:int, period_month:int}
  201 {shop_id, period:{year,month}, allocated,bonus,consumed,remaining, transaction_id}
  400 field errors {amount|reason|period_*: [msg]}
  409 {code:"period_mismatch", detail, period:{current}, balance:{...fresh, new month}}
  404 {code:"shop_unavailable", detail}
  403 non-Superadmin   429 throttled
PATCH /api/v1/organisations/{id}/   (existing)  + monthly_credit_allocation
GET   /api/v1/organisations/        (existing)  + monthly_credit_allocation, current_month_credit_allocation
```
Embedding the fresh balance in the 409 satisfies D-12 ("reload that shop's new-month numbers") with no extra endpoint. Route registration: plain `path()` entries in `apps/credits/api_urls.py` included under `path("api/v1/", include(...))` like `action_items_api_urls`; they do not collide with the `SimpleRouter` organisations routes (longer paths) `[VERIFIED: config/urls.py:26-58]`.

### Frontend pieces
- `creditHint.ts` — pure function `computeCreditHint({ saved, thisMonth, typed, nowUtc })` → `{kind: "off" | "immediate" | "deferred" | "deferred-off" | "hidden", date?: string, keep?: number}`; unit-test every UI-SPEC table row plus the D-18 `saved=0, thisMonth=100` case, December rollover, and invalid/empty input.
- `ManageCreditsModal.tsx` — one `<Modal size="lg">`, `view: "list" | "bonus"`; preview math is client-side from the row already loaded (`remaining + n`, `bonus + n`); submit sends the displayed `period` from the last list/409 response.
- Wiring: add `onOpenManageCredits` to `OrgTableHandlers` (`OrgTable.tsx`), the two `_orgModalHandlers` type literals and the object in `org-management.tsx`, a `creditsRow` state, and a `buildRowActions` entry (`key: "credits"`, `Coins` icon, after `stores`) `[VERIFIED: frontend/src/entrypoints/org-management.tsx, OrgTable.tsx]`. `RowActionsMenu` menu is `w-44` (176 px) — "Manage Credits" fits.
- Column: `buildColumns` entry after `stores` (`align: "right"` is supported by `DataTable`) and an `OrgCard` `dt/dd` row.
- Create/Edit: new field after "Number of Stores"; give the new input `id` + `htmlFor` (Edit's existing labels have no `htmlFor`; UI-SPEC requires bound labels for new controls).

## State of the Art

Not applicable (internal conventions, no ecosystem churn). Django 6.0 `select_for_update(of=("self",))` is already used by `consumption.py`/`lapse.py`; follow that.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Throttle rates 120/min read, 30/min write for the new scopes | Code Examples | Low; trivially tunable |
| A2 | Materialise current-month rows for **all** shops of the org (active and inactive), not only active | CRED-06 helpers | If only active: a shop reactivated mid-month would jump to M instead of keeping N (minor inconsistency) |
| A3 | Set-based bulk helper is acceptable despite CONTEXT line "ensure_balance is the only way to materialise" | Summary item 2 | If user insists on strict reuse, fall back to looping `ensure_balance` (perf cost only) |
| A4 | `current_month_credit_allocation = MAX(this month's allocated_credits) else live field` is the right D-15/D-18 derivation | Pattern 5 | Edge: org with mixed per-shop values (a shop created after an N→M edit shows M virtually while others hold N) displays N; harmless |
| A5 | `organisation.credits.set` uses `entity_type="organisation"`, `entity_id=str(org.pk)`; on **create** only audited when value > 0 | Pattern 1, Pitfall 9 | If the user wants every create audited (including 0) add the row unconditionally |
| A6 | Bonus 409 body embeds the fresh balance; no separate single-shop GET endpoint | Contract | If a GET is wanted for deep links, add `GET …/shops/{id}/credits/` (spec §10 has `/api/v1/shops/{id}/credits/` for Phase 33 already) |
| A7 | Client-side UTC "1st of next month" can differ from server only by clock skew at the boundary | Frontend | Cosmetic; server remains authoritative |
| A8 | `en-GB` `Intl` renders September as "Sept" in current ICU, so use a month-name array | Don't Hand-Roll | Without it a hint test could be locale-flaky |
| A9 | `IntegerField` (32-bit) `bonus_credits` cannot realistically overflow with no cumulative cap (D-10) | Summary | ~214k max-size allocations; effectively unreachable |
| A10 | Make `monthly_credit_allocation` read-only in Django admin after this phase | Open Q2 | Otherwise admin edits bypass CRED-06 and audit |

## Open Questions

1. **Strict `ensure_balance` reuse vs bulk helper (A3).** Recommendation: bulk helper + equivalence test; surface to the user as a one-line confirmation in plan-check since CONTEXT lists it as carried-forward.
2. **Django admin bypass (A10).** `OrganisationAdmin.readonly_fields` currently only covers timestamps `[VERIFIED: apps/organisations/admin.py:12]`. Adding `monthly_credit_allocation` is a one-line change but touches a file outside the strict phase scope — user call. The Phase 30 manual-UAT note ("set via shell or Django admin until Phase 32") is the reason it is editable today.
3. **Singular/plural copy** ("1 credit") is specified in UI-SPEC; no backend impact.
4. **Org Admin Activity Log exposure of the two new audit actions** — out of scope (Phase 33); `AUDIT_ENTITY_FILTER` currently hides `organisation` and `shop` entity types `[VERIFIED: apps/common/selectors/audit_logs.py:27-30]`, so Phase 32 rows cannot leak to tenants.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | backend tests | ✓ | 3.12.9 (`.venv/bin/pytest`) | — |
| Node / npm | frontend tests, `tsc` | ✓ | v22.17.1 | — |
| PostgreSQL | `pg_concurrency` tests (lock-ordering proof) | ✗ locally (`pg_isready`: no response; binaries present) | — | CI `backend-pg` job (`make test-pg`, `REQUIRE_PG=1`); tests auto-skip on SQLite. Start a local PG or rely on CI; plan must not claim lock behaviour verified by SQLite runs |
| Docker | optional local PG | ✓ binary present | — | — |

**Baseline:** `.venv/bin/pytest apps/credits apps/organisations --no-cov -q` → only `test_reaper.py` (Phase 31 WIP) failing; `npx vitest run src/widgets/org-management` → 5 files / 27 tests pass.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend | pytest 8.3.3 + pytest-django 4.9.0 + factory-boy; SQLite in-memory (`config.settings.test`); `pg_concurrency` marker for real PG |
| Frontend | vitest 2.1.8 + @testing-library/react 16.1.0 (jsdom), `frontend/vitest.config.ts` |
| Config | `pyproject.toml [tool.pytest.ini_options]`, `frontend/vitest.config.ts` |
| Quick run | `.venv/bin/pytest apps/credits apps/organisations --no-cov -q -k "not reaper"` ; `cd frontend && npx vitest run src/widgets/org-management` |
| Full suite | `.venv/bin/pytest apps/ -q` (85% coverage gate) ; `cd frontend && npm test && npx tsc --noEmit` |
| PG races | `REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` (CI `backend-pg`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-01 | PATCH persists field; out of range (-1, 10001) → 400; DB CHECK still holds | API | `pytest apps/organisations/tests/test_views.py -k credit` | ❌ add to existing file |
| CRED-01 | Create accepts field, default 0; create with N>0 audits, 0 does not | API/service | `pytest apps/organisations/tests/test_services.py -k credit` | ❌ add |
| CRED-01 | `organisation.credits.set` written exactly once on real change (before/after/effective/actor), zero rows on no-op and on unrelated PATCH | service | same | ❌ |
| CRED-06 | 0 → N, no rows: shops report N via `get_shop_credit_balance`, no rows created, `effective="immediate"` | service | `pytest apps/credits/tests/test_org_allocation.py` | ❌ new |
| CRED-06 | N → M: every shop (active+inactive) gets row at N + one INITIAL(+N) + one `shop.credits.allocated`; reads show N; field saved = M; `effective="next_month"`; existing rows untouched | service | same | ❌ |
| CRED-06 | N → 0 (D-02): shops keep N, no kill switch | service | same | ❌ |
| CRED-06 | D-18: 100→0 then 0→50 same month is deferred (rows allocated>0 exist); new-shop rows materialised at 0 with no INITIAL | service | same | ❌ |
| CRED-06 | Bonus-first zero-row then 0 → N raises row to N with INITIAL; `remaining == N + bonus` | service | same | ❌ |
| CRED-06 | Next month (patch `utc_now`) after N→M: shops get M | service | same | ❌ |
| CRED-06 | Idempotent: second identical PATCH / re-run helper → 0 new rows, no extra audit | service | same | ❌ |
| CRED-06 | Equivalence: bulk helper output == looping `ensure_balance` (rows, ledger, audit) | service | same | ❌ |
| CRED-06 | Query ceiling: materialise 5 vs 50 shops uses same number of queries | service | same | ❌ |
| CRED-06 | Rollback: failure inside edit atomic leaves field and rows unchanged | service | same | ❌ |
| CRED-06 (PG) | N concurrent `ensure_balance` while org edit materialises → one row/shop, one INITIAL; edit vs bonus vs reserve no deadlock | pg_concurrency | `-m pg_concurrency` | ❌ add to `test_pg_concurrency.py` |
| CSUP-01 | List: active shops only, virtual balances shown, **never writes** (row count unchanged), search, ordering stable, pagination 10 | API | `pytest apps/credits/tests/test_views.py -k list` | ❌ new |
| CSUP-01 | List query ceiling identical for 2 vs 12 shops (§6.9) | API | same + `assert_query_ceiling` | ❌ |
| CSUP-01 | Bonus: balance +n, one BONUS_ALLOCATION (+n, COMMITTED, actor, note), one `shop.credits.bonus_allocated` (no reason text), `consumed <= allocated+bonus` holds, response numbers | service+API | `pytest apps/credits/tests/test_bonus.py` | ❌ new |
| CSUP-01 | Bonus on never-used shop materialises row via `ensure_balance` (+INITIAL when org>0); on 0-org creates zero row | service | same | ❌ |
| CSUP-01 | Validation: amount 0/10001/non-int, reason >255 → 400; blank reason → note NULL; boundary 1 and 10,000 accepted | API | same | ❌ |
| CSUP-01 | 409 on stale/future period echo, **no row created**, body has fresh balance; 404 inactive shop, unknown shop, deleted org | API | same | ❌ |
| CSUP-01 | Month rollover: echo of previous month after `utc_now` patched forward → 409 | API | same | ❌ |
| CSUP-01 (PG) | N concurrent bonuses = exact sum; bonus vs reserve on same balance never breaks CHECK; bonus vs 0→N edit leaves no zero-row | pg_concurrency | `-m pg_concurrency` | ❌ |
| CSUP-02 | 403 for ORG_ADMIN and STAFF_ADMIN, 401/403 anonymous, on list GET, bonus POST, and PATCH with `monthly_credit_allocation`; no row/audit/ledger written | API | `pytest apps/credits/tests/test_views.py -k forbidden` ; `apps/organisations/tests/test_views.py` | ❌ |
| CSUP-02 | Org Admin PATCH on **own** org with the field → 403 and value unchanged | API | org test_views | ❌ |
| Throttle | 429 on exceeding `superadmin_credits_write` (patch `ScopedRateThrottle.THROTTLE_RATES`) | API | `test_views.py -k throttle` | ❌ |
| D-14/D-15 | Org list/detail expose `monthly_credit_allocation` and `current_month_credit_allocation` (pending case, no-rows case); query ceiling unchanged (`<= 7`) | API | `pytest apps/organisations/tests/test_views.py` | ✅ extend existing ceiling test |
| UI D-01/D-18 | `creditHint` table rows incl. `saved=0,thisMonth=100`, Dec→Jan date, empty/out-of-range | vitest | `npx vitest run src/widgets/org-management/creditHint.test.ts` | ❌ |
| UI D-14 | Table column "Credits/shop" (N / muted "Off"), mobile card row | vitest | `OrgTable.test.tsx` | ✅ extend |
| UI CRED-01 | Create default 0 + payload; Edit hint states; server `monthly_credit_allocation` field error rendered | vitest | `CreateOrgModal.test.tsx`; new `EditOrgModal.test.tsx` | ✅/❌ |
| UI D-15 | ViewOrg shows value + pending pill only when values differ | vitest | new `ViewOrgModal.test.tsx` | ❌ |
| UI D-05..D-13/D-19 | ManageCredits: list rows/breakdown, search debounce + stale-response ignore, pagination, Add bonus → form, live preview, disabled Allocate states, success toast + list reload + highlight/focus, 409 banner keeps typed values and refreshes numbers, 404 toast + reload, generic error keeps form, reason omitted when empty | vitest | `npx vitest run src/widgets/org-management/ManageCreditsModal.test.tsx` | ❌ |
| UI wiring | Row action "Manage Credits" present for every status, opens modal | vitest | `OrgTable.test.tsx` | ✅ extend |

### Sampling Rate
- **Per task commit:** the two quick-run commands above (plus `npx tsc --noEmit` when `types.ts` changes).
- **Per wave merge:** `.venv/bin/pytest apps/credits apps/organisations apps/common --no-cov -q` and `cd frontend && npm test && npx tsc --noEmit`.
- **Phase gate:** `.venv/bin/pytest apps/ -q` (coverage ≥ 85%), `pre-commit run --all-files`, `makemigrations --check --dry-run` (no model change expected → no migration), `pg_concurrency` job green in CI, then `tenant-security-auditor`, `orm-performance-auditor`, `code-reviewer`; `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `apps/credits/tests/test_org_allocation.py`, `test_bonus.py`, `test_views.py` (+ conftest already re-exports `assert_query_ceiling`, `two_orgs_two_admins`; add a Superadmin/Staff client fixture if not present in credits conftest — it is in `organisations/tests/conftest.py` only)
- [ ] PG tests appended to `apps/credits/tests/test_pg_concurrency.py`
- [ ] `frontend/src/widgets/org-management/{creditHint.test.ts, ManageCreditsModal.test.tsx, EditOrgModal.test.tsx, ViewOrgModal.test.tsx}`
- [ ] Update `OrgRow` fixtures in 4 existing test files (Pitfall 8)
- [ ] No framework install needed.

## Security Domain

`security_enforcement` is not set to false in `.planning/config.json` → included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (inherited) | Session auth + `IsAuthenticated` |
| V3 Session Management | no (unchanged) | — |
| V4 Access Control | **yes — core of CSUP-02** | `IsAuthenticated & IsSuperadmin` on every new view; org-edit goes through the already-Superadmin `OrganisationViewSet`; no Org Admin/Staff serializer exposes the field (`grep model = Organisation` → only the 3 Superadmin serializers) |
| V5 Input Validation | yes | DRF serializer: `amount` `IntegerField(1..10000)`, `reason` `CharField(max_length=255, allow_blank=True)`, `period_*` ints; allocation `IntegerField(0..10000)` + model validators + DB CHECK |
| V6 Cryptography | no | — |
| V7 Logging | yes | Log ids/counts only; no reason text, no review text (CLAUDE.md §22) |
| V11 Business logic | yes | 409 period echo, atomic ledger+balance, lock ordering, idempotent edit |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Org Admin/Staff PATCHes allocation or posts bonus | Elevation of privilege | `IsSuperadmin` on viewset and new views; tests for ORG_ADMIN + STAFF_ADMIN + anon on all surfaces |
| Mass-assignment of `monthly_credit_allocation` via a tenant-facing serializer | Tampering | Field only in Superadmin serializers; `_UPDATABLE_FIELDS` whitelist |
| Replay / double-submit of a bonus | Tampering | Button disabled on first click; accepted risk server-side (each POST is an intentional additive allocation; period echo does not de-dupe) — note for reviewers |
| Cross-tenant bonus by guessing shop id | Info disclosure / tampering | Superadmin is cross-tenant by design; org is derived from the shop row, never from the request body |
| Stale-period write after rollover | Tampering (wrong month) | 409 before any write |
| Free-text reason leaking into audit/logs | Info disclosure | Reason only in ledger `note`; AuditLog stores `has_reason` bool |
| Django admin direct edit bypassing CRED-06/audit | Tampering | Open Question 2 |
| Enumeration/abuse via list endpoint | DoS | `ScopedRateThrottle` + pagination page_size 10 |

## Sources

### Primary (HIGH confidence — read this session)
- `apps/credits/models.py`, `services/{allocation,periods,ledger,consumption,lapse}.py`, `selectors/{balances,lapse}.py`, `managers.py`, `exceptions.py`, `tests/{conftest,helpers,factories,test_pg_concurrency}.py`
- `apps/organisations/{models,serializers,views,urls,admin}.py`, `services/organisations.py`, `selectors/organisations.py`, migration `0003`, tests (`test_views.py` ceiling `<= 7`, `test_selectors.py` ceiling `<= 3`)
- `apps/accounts/permissions.py`, `apps/common/models.py` (`AuditLog`), `apps/common/selectors/audit_logs.py`, `apps/shops/models.py`, `apps/shops/selectors/shops.py`
- `config/settings/base.py` (throttle rates, credit settings), `config/settings/test.py` (SQLite), `config/settings/test_pg.py`, `config/urls.py`, `pyproject.toml`, `Makefile`
- `frontend/src/widgets/org-management/*`, `frontend/src/widgets/modal/Modal.tsx`, `frontend/src/lib/toast.ts`, `frontend/src/entrypoints/org-management.tsx`, `frontend/node_modules/focus-trap/index.js`, `frontend/package.json`, `vitest.config.ts`, `tsconfig.json`
- `.planning/phases/32-*/32-CONTEXT.md`, `32-UI-SPEC.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (Phases 29–33), `docs/completed/Requirements_Credits_System.md` §3.4, §7.3, §8, §10; `.claude/rules/*.md`; CLAUDE.md §5–§9, §12, §16, §22, §24, §27
- Test runs: `pytest apps/credits apps/organisations` baseline, `vitest org-management` baseline

### Secondary / Tertiary
- None. No external documentation was needed; no web or Context7 lookups were performed (no new library surface).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all APIs read from source.
- Architecture: HIGH for locking/ordering and read-path reuse (verified against shipped services); MEDIUM for the bulk-materialisation shape (design choice, A3) and `this-month` derivation edge cases (A4).
- Pitfalls: HIGH — each traces to a line of shipped code or a locked decision.

**Research date:** 2026-11-11
**Valid until:** 2026-12-11 (stable internal code; re-check if Phase 31 changes `ShopCreditBalance` or `allocation.py` before execution)

## Project Constraints (from CLAUDE.md)

- Services/selectors pattern; views thin; no business logic in serializers, models, or tasks (§5). The org-edit orchestration therefore lives in the service, not `perform_update`.
- Strict no-N+1 with `CaptureQueriesContext` tests on every list endpoint; use `annotate`/`select_related`; `transaction.atomic` for multi-step writes; `select_for_update` for critical updates (§6).
- DRF: explicit permission classes, pagination on every list, throttling on every endpoint, two serializers when input ≠ output, URL path `/api/v1/...`, drf-spectacular schema (§8, §24 step 11).
- Superadmin is non-tenant: do not use `TenantScopedViewSet`; still never trust request data for org (derive from shop) (§9).
- AuditLog preferred for user-visible domain events; payloads carry ids and counts only; never log review text / secrets (§22, §29.4).
- Pre-pin versions; no new dependency without need (§2); migrations reversible, descriptive names (§18) — this phase needs **no migration**.
- Tests: pytest + factory-boy factories (no raw `.objects.create` in tests when a factory exists), ≥85% coverage on services/selectors/permissions, cross-tenant/role tests mandatory, real-PG races in `pg_concurrency` (§16; `.claude/rules/testing-python.md`).
- Frontend: Vite-per-widget entrypoint, Tailwind, behaviour-based vitest/RTL tests mocking the network boundary only (`.claude/rules/testing-frontend.md`, §26); use the `frontend-react-builder` subagent.
- Requirements-first gate: CRED-01/06, CSUP-01/02 are already in `.planning/REQUIREMENTS.md` (§24).
- Simplicity + surgical scope (§24): the only out-of-scope-adjacent touch recommended is Django admin read-only (Open Q2, needs user sign-off); do not refactor adjacent code.
- Mandatory reviews before PR: `tenant-security-auditor`, `orm-performance-auditor`, `code-reviewer`, `test-author` for gaps (§27); update CLAUDE.md §3 app tree/§27 if new files warrant it.
