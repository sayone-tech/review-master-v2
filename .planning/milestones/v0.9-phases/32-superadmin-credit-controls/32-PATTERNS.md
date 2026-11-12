# Phase 32: Superadmin Credit Controls - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 27 (new + modified)
**Analogs found:** 25 / 27 (all analog paths verified git-tracked; no gitignored mirrors)

Line numbers are from files read this session. Decisions D-01..D-23 and 32-RESEARCH.md Patterns 1-5 (service sketches) remain authoritative for behaviour. This file supplies the in-repo code to copy.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/credits/services/allocation.py` (+`materialise_org_balances`, `raise_zero_balances`) | service | batch / CRUD | same file, `ensure_balance` (L30-80) | exact |
| `apps/credits/services/bonus.py` (NEW `allocate_bonus`) | service | CRUD (atomic, locked) | `apps/credits/services/allocation.py::ensure_balance` + `consumption.py:131-141` (lock idiom) | role-match |
| `apps/credits/selectors/balances.py` (+`get_org_current_month_allocation`, `org_has_current_month_allocation`) | selector | read-only | same file (`get_shop_credit_balance` L50-91) | exact |
| `apps/credits/selectors/shop_credits.py` (NEW `list_org_shop_credits`) | selector | read-only list | `annotate_credit_state` (`balances.py` L94-137) | exact |
| `apps/credits/exceptions.py` (+`PeriodMismatchError`, `ShopNotAvailableError`) | exception | n/a | `InsufficientCreditsError` (L14-27) | exact |
| `apps/credits/serializers.py` (NEW) | serializer | request-response | `apps/organisations/serializers.py` | role-match |
| `apps/credits/views.py` (NEW `CreditShopListView`, `BonusAllocationView`) | view | request-response | `SyncProgressSnapshotView` (`apps/reviews/views.py` ~L800-830) + `AuditLogViewSet` throttle | role-match |
| `apps/credits/api_urls.py` (NEW) | route | n/a | `apps/action_items/urls.py` L1-16 | role-match |
| `config/urls.py` (include) | config | n/a | `path("api/v1/", include(action_items_api_urls))` | exact |
| `config/settings/base.py` (2 throttle scopes) | config | n/a | `credit_cost` rate (L433-437) | exact |
| `apps/organisations/services/organisations.py` (`update_organisation`, `create_organisation`) | service | CRUD | same file L19, L32-54, L181-208 | exact |
| `apps/organisations/selectors/organisations.py` (`_base_queryset` + Subquery annotation) | selector | read-only | same file L15-27 | exact |
| `apps/organisations/serializers.py` (List/Create/Update) | serializer | request-response | same file L15-101 | exact |
| `apps/organisations/views.py` (`perform_update` actor, `perform_create`) | view | request-response | same file L268-285 | exact |
| `apps/organisations/admin.py` (read-only field) | config | n/a | same file L12 | exact |
| backend tests (`apps/credits/tests/test_bonus.py`, `test_org_allocation.py`, `test_views.py`, `test_pg_concurrency.py` add; `apps/organisations/tests/test_views.py`/`test_services.py` add) | test | n/a | `apps/credits/tests/test_allocation.py`, `apps/organisations/tests/conftest.py` | exact |
| `frontend/.../ManageCreditsModal.tsx` (+test) | component | request-response, 2-view state | `StoreAllocationModal.tsx` (+`.test.tsx`) | role-match |
| `frontend/.../creditsApi.ts`, `useCreditShops.ts` | api/hook | request-response | `api.ts`; hook precedents `useActionItems.ts`, `TeamTable.tsx` (debounce) | role-match |
| `frontend/.../creditHint.ts` (+test) | utility | transform | none (pure fn) | no analog |
| `frontend/.../types.ts`, `api.ts` | types | n/a | same files | exact |
| `CreateOrgModal.tsx`, `EditOrgModal.tsx`, `ViewOrgModal.tsx`, `OrgTable.tsx` | component | form / display | same files | exact |
| `frontend/src/entrypoints/org-management.tsx` | wiring | event | same file L55-100, L177-218 | exact |
| existing OrgRow test fixtures (4 files) | test | n/a | `StoreAllocationModal.test.tsx` L9-24 | exact |

---

## Pattern Assignments

### `apps/credits/services/allocation.py` (service, batch) - add set-based helpers

**Analog:** same file, `ensure_balance` (L30-80). The bulk helpers MUST produce identical rows to this (D-20 equivalence test).

Imports already present (L18-25): `transaction`, `AuditLog`, `CreditTransaction, ShopCreditBalance`, `Period, current_period`, `Shop`.

Row shapes to mirror exactly (L43-71):
```python
balance, created = ShopCreditBalance.objects.get_or_create(
    shop_id=shop_id, period_year=period.year, period_month=period.month,
    defaults={"organisation_id": organisation_id, "allocated_credits": allocation},
)
if created and allocation > 0:
    CreditTransaction.objects.create(
        shop_credit_balance=balance, shop_id=shop_id, organisation_id=organisation_id,
        transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION,
        status=CreditTransaction.Status.COMMITTED, credits_delta=allocation, actor=None)
    AuditLog.objects.create(
        organisation_id=organisation_id, actor=None, entity_type="shop", entity_id=str(shop_id),
        action="shop.credits.allocated", before_data=None,
        after_data={"period_year": period.year, "period_month": period.month,
                    "allocated_credits": allocation})
```
Rules: allocation 0 => balance row only (no ledger, no audit). `bulk_create(ignore_conflicts=True)` then re-SELECT (no PKs returned). `QuerySet.update()` on `ShopCreditBalance` must set `updated_at` explicitly. Insert rows in `shop_id` order. `CreditTransaction.bulk_create` is allowed (only `update_conflicts` is blocked; `apps/credits/managers.py:21-40`). Materialise ALL org shops, active and inactive (Phase 29 D-13).

### `apps/credits/services/bonus.py` (service, atomic CRUD)

**Analog:** `ensure_balance` for create/ledger/audit shape; lock idiom from `apps/credits/services/consumption.py:131-141` (`select_for_update(of=("self",))`). Follow research Pattern 3 verbatim. Order: period echo check (409, no write) -> active-shop/non-DELETED-org lookup (404) -> `transaction.atomic()`: org-row lock -> `ensure_balance(shop_id, period)` -> balance-row lock -> `.update(bonus_credits=F("bonus_credits") + amount, updated_at=timezone.now())` -> `CreditTransaction.objects.create(... Type.BONUS_ALLOCATION, COMMITTED, credits_delta=amount, actor_id, note)` -> `AuditLog` (`action="shop.credits.bonus_allocated"`, ids/counts only; reason text goes only in `note`, never AuditLog).

### `apps/credits/selectors/balances.py` additions and `selectors/shop_credits.py`

**Analog:** `annotate_credit_state` (L94-137). The list selector is just:
```python
annotate_credit_state(queryset=Shop.objects.filter(organisation_id=org_id, is_active=True)
                      [.filter(name__icontains=search)]).order_by("name", "pk")
```
Annotation names for the serializer: `credit_allocated`, `credit_bonus`, `credit_consumed`, `credit_remaining`, `credit_materialized`. Never writes. Include `pk` in order_by (names not unique, stable pagination). Module docstring convention (L1-12): reads never create rows; function-level import of `Shop` avoids the credits->shops module-scope edge (L69-70), though `allocation.py` already imports `Shop` at module level (L25), so either is acceptable in a new selector module.

### `apps/credits/exceptions.py` (additions)

**Analog:** `InsufficientCreditsError` (L14-27): keyword-only `__init__`, `super().__init__(f"...")`, attributes stored.
```python
class InsufficientCreditsError(Exception):
    def __init__(self, *, reason: str, required: int, remaining: int) -> None:
        super().__init__(f"insufficient credits: {reason} required={required} remaining={remaining}")
        self.reason = reason; self.required = required; self.remaining = remaining
```
New: `PeriodMismatchError(current: Period)`, `ShopNotAvailableError(shop_id: int)`.

### `apps/credits/views.py` (NEW, request-response) + `api_urls.py` + `config/urls.py`

**Analog (APIView + ScopedRateThrottle):** `apps/reviews/views.py` `SyncProgressSnapshotView` (~L800-830):
```python
permission_classes = [IsAuthenticated]  # noqa: RUF012
throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
throttle_scope = "sync_progress"
def get(self, request: Request, shop_id: int) -> Response: ...
```
Use `permission_classes = [IsAuthenticated, IsSuperadmin]` (`apps/accounts/permissions.py:13-25`, `from apps.accounts.permissions import IsSuperadmin`; non-tenant, NOT `TenantScopedViewSet`). Scopes `superadmin_credits_read` / `superadmin_credits_write`. Pagination: subclass DRF `PageNumberPagination` (`apps/common/pagination.py:4-7` is the style precedent: `DefaultPageNumberPagination` with `page_size`, `page_size_query_param`, `max_page_size`); set `page_size = 10`. 404 for missing/DELETED org via `get_object_or_404(Organisation.objects.not_deleted(), pk=org_id)`. Add `@extend_schema` (drf-spectacular, CLAUDE.md section 24 step 11).

**Analog (URL module):** `apps/action_items/urls.py` L1-16 exposes `api_urlpatterns`; credits needs plain `path()` entries instead of a router:
```python
urlpatterns = [
    path("superadmin/organisations/<int:org_id>/credits/shops/", CreditShopListView.as_view(), name="superadmin-credit-shops"),
    path("superadmin/shops/<int:shop_id>/credits/bonus/", BonusAllocationView.as_view(), name="superadmin-credit-bonus"),
]
```
**Analog (include):** `config/urls.py` L50-52: `path("api/v1/", include(action_items_api_urls))` / `path("api/v1/", include("apps.accounts.api_urls"))`. Add `path("api/v1/", include("apps.credits.api_urls"))`. Does not collide with the `SimpleRouter` organisations routes.

### `config/settings/base.py` (throttles)

**Analog:** L430-438:
```python
"generate_reply": "10/minute",
# Phase 30 D-10: ...
"credit_cost": "120/minute",
"audit_log_list": "120/minute",
```
Add `"superadmin_credits_read": "120/minute"`, `"superadmin_credits_write": "30/minute"` (rates are assumed values). `ScopedRateThrottle` is already in the default throttle class list. Throttle tests: patch `ScopedRateThrottle.THROTTLE_RATES`; org tests conftest has an autouse `caches["throttle"].clear()`.

### `apps/organisations/services/organisations.py` (service)

**Analog (same file).** Current state to change:
- L19-21 `_UPDATABLE_FIELDS = frozenset({"name","org_type","address","number_of_stores","status","allow_custom_sync_depth"})` -> add `"monthly_credit_allocation"`.
- L32-54 `create_organisation(*, name, org_type, email, address="", number_of_stores, created_by, allow_custom_sync_depth=False)` is `@transaction.atomic` and calls `Organisation.objects.create(...)`. Add `monthly_credit_allocation: int = 0` kwarg and pass it through (otherwise `perform_create` 500s once the serializer field exists: `views.py` `create_organisation(created_by=..., **serializer.validated_data)`).
- L181-208 `update_organisation(*, organisation, **data)` is NOT atomic, has no actor, no audit. Preserve its structure: `data.pop("email", None)` (L189), SA-056 guard (L193-197), the whitelist/`changed` loop with `save(update_fields=changed + ["updated_at"])` (L198-207). Add `actor=None`, `@transaction.atomic`, and the credit branch from research Pattern 1 BEFORE the generic save loop (lock org row, read OLD from the locked row, `raise_zero_balances` vs `materialise_org_balances`, then audit `organisation.credits.set` only if new != old).
- Other writers in this file (`enable_organisation` L211, `adjust_store_allocation` L230) use `save(update_fields=[..., "updated_at"])`; keep that style.
- AuditLog precedent in this file's imports: `log_invitation_event` (accounts); for credits use direct `AuditLog.objects.create(...)` as in `allocation.py` L59-71 (fields: organisation, actor, entity_type, entity_id, action, before_data, after_data).

### `apps/organisations/selectors/organisations.py` (selector)

**Analog (same file) L15-27** `_base_queryset()`:
```python
Organisation.objects.not_deleted().select_related("created_by").annotate_store_counts()
    .prefetch_related(Prefetch("invitation_tokens", queryset=..., to_attr="prefetched_tokens"))
```
Append `.annotate(current_month_credit_allocation=Coalesce(Subquery(...Max("allocated_credits")...), F("monthly_credit_allocation")))` using research Pattern 5 (`ShopCreditBalance.objects.filter(organisation_id=OuterRef("pk"), period_year=..., period_month=...).order_by().values("organisation_id").annotate(m=Max(...)).values("m")`, `output_field=IntegerField()`). Required because `ShopCreditBalance.organisation` has `related_name="+"`. Existing query ceilings (selector <= 3, API <= 7; `apps/organisations/tests/test_selectors.py:73`, `test_views.py:110`) must still pass.

### `apps/organisations/serializers.py` (serializer)

**Analog (same file).**
- `OrganisationListSerializer` fields list L23-37: add `"monthly_credit_allocation"` and `"current_month_credit_allocation"`; declare the latter like L16-17: `current_month_credit_allocation = serializers.IntegerField(read_only=True)`. (`OrganisationDetailSerializer` L47 inherits.)
- `OrganisationCreateSerializer` (L51-74): declare `monthly_credit_allocation = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=0)` in the style of `number_of_stores = serializers.IntegerField(min_value=1, max_value=1000)` (L63); add to `Meta.fields` L67-74.
- `OrganisationUpdateSerializer` (L77-98): add `monthly_credit_allocation = serializers.IntegerField(min_value=0, max_value=10000, required=False)` in the style of L81; add to `Meta.fields` L92-99.

### `apps/organisations/views.py` (view)

**Analog (same file) L268-285:** `perform_update` currently calls `update_organisation(organisation=serializer.instance, **serializer.validated_data)`; pass `actor=self.request.user` (same `isinstance(self.request.user, User)` guard as `perform_create`, L262-263). `perform_create` already forwards `**serializer.validated_data` so no change beyond the service kwarg. Viewset is `IsAuthenticated, IsSuperadmin` (L238).

### `apps/organisations/admin.py`

**Analog:** L12 `readonly_fields = ("created_at", "updated_at")` -> add `"monthly_credit_allocation"` (D-22). Check `apps/credits/tests/test_admin.py` and any org admin tests for field expectations.

---

## Backend test patterns

**Service tests:** `apps/credits/tests/test_allocation.py` L1-50: `pytestmark = pytest.mark.django_db`; helper `_shop(allocation)` = `ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=allocation))`; assert on `CreditTransaction.objects.get()` fields (type, status, delta, actor None) and `AuditLog.objects.get(action=...)` (`entity_type`, `entity_id`, `set(after_data)`). Factories: `apps/credits/tests/factories.py` (`ShopCreditBalanceFactory`, `CreditTransactionFactory`). Month rollover: patch `apps.credits.services.periods.utc_now`.
**API tests:** `apps/organisations/tests/conftest.py`: fixtures `superadmin` (UserFactory role="SUPERADMIN"), `org_admin`, `client_logged_in`, `api_client_superadmin` (APIClient), autouse throttle-cache clear. For credits endpoints, add 403 cases for ORG_ADMIN and STAFF_ADMIN. Query-count tests: `assert_query_ceiling` from `apps/common/tests/fixtures.py` (re-exported in `apps/credits/tests/conftest.py`); assert identical query count for 2 vs 12 shops. PG races: add to `apps/credits/tests/test_pg_concurrency.py` (`pg_concurrency` marker; CI `backend-pg`; local PG unavailable).

---

## Frontend

### `ManageCreditsModal.tsx` (component, two-view state)

**Analog:** `frontend/src/widgets/org-management/StoreAllocationModal.tsx`.
- Imports/props (L1-12): `Modal, ConfirmModal` from `"../modal"`, `emitToast` from `"../../lib/toast"`, `OrgRow` type; `Props { org: OrgRow | null; onClose; onDone }`. ManageCredits needs only `org` + `onClose`; no `onDone` (UI-SPEC).
- Reset-on-org-change effect (L19-31) keyed on `org?.id`; early `if (!org) return null;` then `const currentOrg = org;` (L33-37) for closure narrowing.
- Submitting guard (L47-49): `if (submitting) return; setSubmitting(true); try {...} catch {...} finally { setSubmitting(false); }`.
- Error toast copy (L57-61): `emitToast({ kind: "error", title: "Something went wrong.", msg: "Please try again. If the problem persists, contact support." })`. Success: `emitToast({ kind: "success", title })`.
- Modal footer buttons (L69-93): secondary `inline-flex items-center ... bg-white text-ink border border-line rounded-md ... hover:bg-line-soft`; primary `bg-yellow text-black border border-yellow-hover ... hover:bg-yellow-hover`; disabled = `opacity-50 cursor-not-allowed pointer-events-none`. Note UI-SPEC overrides sizes (`h-10 px-4 text-[14px]`) and forbids `font-medium`.
- Warning/amber note class (L113-119): `bg-amber-tint text-[#92400E] ... rounded-md`, `role="alert"`; UI-SPEC changes padding to `px-4 py-2 text-[12px]`.
- Input class: use `inputCls` string from `CreateOrgModal.tsx` L235-239 (`w-full px-3 py-2 text-[14px] bg-white border rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink`, plus `border-red` / `border-line`).
- Differences: one `<Modal size="lg">` with `view: "list" | "bonus"` (not Modal<->ConfirmModal); `data-testid` convention `store-alloc-*` -> use `credits-*`.
- Frontend test analog: `StoreAllocationModal.test.tsx` L1-60: `vi.mock("./api", async () => { const actual = await vi.importActual(...); return { ...actual, updateOrg: vi.fn() }; })`, `mockReset` in `beforeEach`, `captureToasts()` listening for `app:toast` on window, `userEvent.clear/type`, `getByTestId(...).toBeDisabled()`. Mock `./creditsApi` the same way. Add tests for: 409 keeps typed values + banner, 404 toast "This shop is no longer active" (D-23), autoFocus on search input, focus restore to row "Add bonus".

### `creditsApi.ts` / `useCreditShops.ts`

**Analog:** `frontend/src/widgets/org-management/api.ts`.
- `getCsrfToken()` L9-12 (exported, reuse) and `headers(method)` L14-20 (sets `X-CSRFToken` for non-GET). Fetch shape L66-73: `fetch(url, { method, headers: headers(method), credentials: "same-origin", body: JSON.stringify(payload) })`.
- `handle()` L37-57 is the pitfall: any non-OK JSON body is stored as `fieldErrors` (typed `Record<string, string[]>`). The 409 body is an object (`{code, detail, period, balance}`), so `creditsApi.ts` needs its own error class/handler that preserves the raw `body` (do not reuse `handle()` for the bonus POST).
- Hook: debounce 300 ms + stale-response guard (AbortController or request counter); precedents `useActionItems.ts` and `TeamTable.tsx`.

### `creditHint.ts` (utility) - no analog

Pure function `computeCreditHint({ saved, thisMonth, typed, nowUtc })` per research. Rule per D-21: "immediate" only when saved == 0 AND thisMonth == 0 (overrides UI-SPEC hint rule); UTC month names from a hard-coded array (not `Intl`).

### `types.ts`

**Analog:** same file. `OrgRow` L5-19: add `monthly_credit_allocation: number; current_month_credit_allocation: number;`. `CreateOrgPayload` L28-35 add `monthly_credit_allocation: number`. `UpdateOrgPayload` (a `Partial<{...}>` L37-44) add `monthly_credit_allocation: number`. New types for credit shop rows, list response (`period`, `allocation_per_shop`, `results`) and bonus result.
Pitfall: adding required `OrgRow` fields breaks `tsc --noEmit` in test fixtures (`OrgTable.test.tsx`, `StoreAllocationModal.test.tsx` L9-24, `DeleteConfirmModal.test.tsx`, `ResendInvitationModal.test.tsx`); update each fixture.

### `CreateOrgModal.tsx`

**Analog:** same file.
- Validation (L42-54): `const n = Number(stores); if (!Number.isInteger(n) || n < 1 || n > 1000) e.number_of_stores = "..."` -> add the same for `monthly_credit_allocation` with `0..10000` and copy `Enter a whole number between 0 and 10,000.`.
- Payload (L60-68): add `monthly_credit_allocation: Number(credits)`.
- Server errors (L77-86): `err.fieldErrors` loop already maps keys; add nothing.
- Field markup (L186-203): `<Field label="Number of Stores" id="new-org-stores" error={errors.number_of_stores}><input id="..." type="number" ... className={inputCls(!!errors.X)} data-testid="field-number_of_stores" /></Field>`. Insert the new Field directly after this one (id `new-org-credits`, testid `field-monthly_credit_allocation`, default state `"0"`), followed by the static helper + live hint wrapper (`credit-allocation-hint`). `Field` (L241+) is local and not exported; `reset()` must reset the new state.

### `EditOrgModal.tsx`

**Analog:** same file.
- State/effect (L24-39): add `credits` state and set `String(org.monthly_credit_allocation)` in the `[org]` effect; also capture the opening value (a ref/state) so the payload includes the field only when it changed (research Pitfall 2).
- Validation L47-56 and payload L61-69 (`UpdateOrgPayload`).
- Field markup (L180-199) is inline, with a `<label>` lacking `htmlFor` and class `border-red`/`border-line` via `inputBase`; the new control must have `id` + `htmlFor` (UI-SPEC). testid `edit-field-monthly_credit_allocation`. Hint uses `org.current_month_credit_allocation`.

### `ViewOrgModal.tsx`

**Analog:** same file L81-89 `dt/dd` pair:
```tsx
<dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">Stores</dt>
<dd className="text-[14px] text-ink">{org.active_stores} used of {org.number_of_stores} allocated</dd>
```
Add "Monthly credits per shop" pair after it, with the amber pending pill when `current_month_credit_allocation !== monthly_credit_allocation`.

### `OrgTable.tsx`

**Analog:** same file.
- `OrgTableHandlers` L38-46: add `onOpenManageCredits: (row: OrgRow) => void`.
- `buildColumns` L87+: add after the `stores` column (L126-135) a `credits` column `{ key, label: "Credits/shop", skeletonWidth: "56px", align: "right", accessor }` rendering `Off` (`text-subtle`) for 0. Also an `OrgCard` `dt/dd` row between Stores and Created.
- `buildRowActions` L153+: add after the `stores` entry (L177-182):
```tsx
{ key: "credits", label: "Manage Credits", icon: <Coins size={14} aria-hidden="true" />, onSelect: handlers.onOpenManageCredits }
```
Import `Coins` from `lucide-react` (import block L2-10).

### `frontend/src/entrypoints/org-management.tsx`

**Analog:** same file. Add `onOpenManageCredits` in all places `onOpenAdjustStores` appears: first `_orgModalHandlers` type literal (L66-76), the assigned object (L76-86; `onOpenAdjustStores: (r) => setStoreRow(r)`), second type literal (~L195-205), and the `handlers={{...}}` bridge (L211-218: `onOpenAdjustStores: (r) => getHandlers()?.onOpenAdjustStores(r)`). Add state `const [creditsRow, setCreditsRow] = useState<OrgRow | null>(null);` next to `storeRow` (L57) and render `<ManageCreditsModal org={creditsRow} onClose={() => setCreditsRow(null)} />` beside the `StoreAllocationModal` usage.

---

## Shared Patterns

### Superadmin-only, non-tenant endpoint
**Source:** `apps/accounts/permissions.py:13-25` (`IsSuperadmin`), `apps/organisations/views.py:238`.
**Apply to:** both new credits views. `permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012`. Tests: 403 for ORG_ADMIN and STAFF_ADMIN, 401/403 anonymous.

### Scoped throttling
**Source:** `apps/common/views.py:237` (`throttle_classes = [ScopedRateThrottle]`, `throttle_scope = "audit_log_list"`) and `config/settings/base.py:430-437`. Apply to both credits views + settings rates.

### AuditLog write
**Source:** `apps/credits/services/allocation.py:59-71`. Fields: `organisation(_id)`, `actor(_id)`, `entity_type`, `entity_id` (string), `action`, `before_data`, `after_data`. Payloads hold ids and counts only (no reason text, CLAUDE.md section 22). Actions this phase: `organisation.credits.set` (`entity_type="organisation"`, actor = request user, only on real change), `shop.credits.bonus_allocated` (`entity_type="shop"`), `shop.credits.allocated` (bulk helpers, actor None).

### Period handling
**Source:** `apps/credits/services/periods.py` (`current_period()`, `next_period_start()`, `Period`). Compute once per operation and pass to every helper; never `date.today()`.

### Lock ordering
Org row -> balance row(s). `reserve_credits` (`consumption.py:131-141`) takes only the balance lock. Use `select_for_update(of=("self",))` as in `consumption.py` / `lapse.py`.

### No-N+1 on lists
**Source:** `annotate_credit_state` (balances.py L94-137) + `assert_query_ceiling` tests (CLAUDE.md section 6.9).

### Toasts and API errors (frontend)
**Source:** `frontend/src/lib/toast.ts` (`emitToast({ kind, title, msg? })`); generic error copy in `StoreAllocationModal.tsx` L57-61.

---

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `frontend/.../creditHint.ts` | utility | Pure formatter with no precedent; follow research spec and UI-SPEC hint table (with D-21 override) |
| Two-view modal body (shop row list, balance block, preview box, in-modal pagination) | component | UI-SPEC "New Compositions"; build from tokens. Inline pagination precedent: `TeamTable.tsx`; search look: `templates/components/filter_bar.html` |

## Contradictions the planner must honour (from CONTEXT post-research)

- D-21 overrides UI-SPEC: hint says "immediate" only when saved == 0 AND `current_month_credit_allocation` == 0; View note and Manage-credits subtitle also use `current_month_credit_allocation`.
- D-23 / D-19: toast copy is "This shop is no longer active" (UI-SPEC says "available"; D-19 wins).
- D-20 supersedes "`ensure_balance` is the only materialisation path" for the bulk org-edit case only; bonus and consumption keep using `ensure_balance`; equivalence test (rows, ledger, audit) is required.
- D-22: admin makes `monthly_credit_allocation` read-only.
- Spec paths: new endpoints under `/api/v1/superadmin/...`; the existing org PATCH/list stays at `/api/v1/organisations/`.
- Phase 31 is in flight: 2 `test_reaper.py` failures are unrelated; do not depend on `lapsed_at`.

## Metadata

**Analog search scope:** `apps/credits`, `apps/organisations`, `apps/accounts/permissions.py`, `apps/common` (views, pagination), `apps/reviews/views.py`, `apps/action_items/urls.py`, `config/urls.py`, `config/settings/base.py`, `frontend/src/widgets/org-management`, `frontend/src/entrypoints/org-management.tsx`, `frontend/src/lib/toast.ts`.
**Not read (relied on 32-RESEARCH.md):** research lines 515-607 (validation map tail / security section), `apps/credits/services/consumption.py` lock excerpt, `Modal.tsx` internals.
**Pattern extraction date:** 2026-11-11
