# Phase 33: Credit Visibility & Staff Scoping - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 27 (new/modified)
**Analogs found:** 27 / 27 (all analogs verified git-tracked on branch feat/v0.9-ai-reply-credits)

Honours D-17 (shop retrieve Staff-scoped) and D-18 (Shops page stays Org-Admin-only; Staff empty state defensive only).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/credits/selectors/access.py` (NEW) `get_accessible_shop_for_credits` | selector | request-response | `apps/reviews/selectors/reviews.py::get_accessible_shop_ids` + `ReviewViewSet.get_queryset` | role-match |
| `apps/credits/services/periods.py` (+`period_label`) | utility | transform | same file (`next_period_start`) | exact |
| `apps/credits/views.py` (+`ShopCreditsView`) | controller (APIView) | request-response | `CreditShopListView` same file | exact |
| `apps/credits/serializers.py` (+`ShopCreditsSerializer`) | serializer | transform | existing `CreditBalanceSnapshotSerializer` same file | exact |
| `apps/credits/api_urls.py` | route | - | same file | exact |
| `config/urls.py` | route | - | where `apps.credits.api_urls` is included (tenant path needs non-superadmin prefix `shops/<id>/credits/`) | exact |
| `config/settings/base.py` (+`"shop_credits": "120/minute"`) | config | - | `credit_cost` scope ~L436 | exact |
| `apps/shops/selectors/shops.py::list_shops` | selector | CRUD read | same file + `list_reviews(user=)` | exact |
| `apps/shops/serializers.py::ShopReadSerializer` | serializer | transform | same file | exact |
| `apps/shops/views.py` (list, shop_list, `get_queryset` retrieve scoping, org_data) | controller | request-response | same file `list` L184; `ReviewViewSet.get_queryset` | exact |
| `apps/common/selectors/audit_logs.py` (+`CREDIT_AUDIT_FILTER`, `shop_name`) | selector | request-response | same file | exact |
| `apps/common/serializers.py` (+`shop_name`) | serializer | transform | `AuditLogReadSerializer` | exact |
| `apps/reviews/views.py::review_list` + templates (bootstrap `org name`, `support_email`) | view/template | request-response | `shops/shop_list.html` `json_script` L26-31 | exact |
| tests: `apps/credits/tests/test_shop_credits_view.py`, `test_access_selector.py`, `test_scope_sweep.py` | test | request-response | `apps/reviews/tests/test_views.py::TestReviewCreditCost` (L962+) | exact |
| tests: shops/common selectors + API | test | - | existing `apps/shops/tests/test_selectors.py`, `apps/common/tests/test_audit_log_*.py` | exact |
| `frontend/src/widgets/credits/creditBand.ts`, `format.ts` | utility | transform | `org-management/creditHint.ts` | role-match |
| `credits/creditsStore.ts` | store | event-driven | no analog (see below) | none |
| `credits/creditsApi.ts` | service | request-response | `review-management/api.ts` (`handle`, `ApiError`, `generateReply`) | exact |
| `credits/CreditBadge.tsx` | component | - | `shop-management/ConnectionStatusPill.tsx` | role-match |
| `credits/CreditsCard.tsx` | component | request-response | `ShopDetailsModal.tsx` `Row` layout | role-match |
| `credits/BuyMoreCreditsModal.tsx`, `mailto.ts` | component | - | `widgets/modal/Modal.tsx` + `ConfirmModal.tsx` | exact |
| `shop-management/ShopTable.tsx`, `ShopDetailsModal.tsx`, `ShopModals.tsx`, `types.ts` | component | event-driven | same files (`dispatchShopEvent` -> `shop:open-details`) | exact |
| `review-management/ReplyComposer.tsx`, `api.ts`, `types.ts` | component | request-response | same files L80-125 | exact |
| `audit-log/TypePill.tsx`, `utils.ts`, `types.ts` | component | - | same dir | exact |
| frontend tests (`*.test.tsx`) | test | - | `shop-management/ShopTable.test.tsx` | exact |

## Pattern Assignments

### `apps/credits/selectors/access.py` (selector, request-response)

**Analog:** `apps/reviews/selectors/reviews.py` L11-35 (`get_accessible_shop_ids`, not org-bounded) and `list_reviews` L55-65 (role keyed, not list truthiness).

```python
# reviews.py L56-65 - copy the role check, NOT `if ids:`
if user is not None and getattr(user, "role", None) == User.Role.STAFF_ADMIN:
    accessible = get_accessible_shop_ids(user_id=user.pk)
    qs = qs.filter(shop_id__in=accessible)
```
Use the function-level import style from `balances.py` L69 (`from apps.shops.models import Shop` inside function) to keep credits->shops/reviews edges out of module scope. Keyword-only, read-only, returns `Shop | None` (-> 404). ALWAYS add `organisation_id=user.organisation_id` (get_accessible_shop_ids region expansion is not org-bounded, RESEARCH Pitfall 2). Never filter `is_active`. Full sketch: RESEARCH Pattern 1.

### `apps/credits/views.py` `ShopCreditsView` (controller, request-response)

**Analog:** `CreditShopListView` (views.py L45-86).
```python
permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012   -> use [IsOrgScoped] (apps.common.permissions)
throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
throttle_scope = "superadmin_credits_read"                              -> "shop_credits"
# read period once:  period = current_period()
# 404 shape:  Response({"code": "...", "detail": "..."}, status=status.HTTP_404_NOT_FOUND)
# @extend_schema(responses={200:..., 403:..., 404: CreditErrorSerializer, 429: ...}, tags=[...])
```
Then `get_shop_credit_balance(shop_id=shop.pk, period=period)` (balances.py L53; returns `allocated, bonus, consumed, remaining, is_enabled, renews_on`), set `resp["Cache-Control"] = "no-store"`. IsOrgScoped is `has_permission` only on APIView, so scoping lives in the selector. Payload: `shop_id, period{year,month}, period_label, renews_on, allocated, bonus, consumed, remaining, total, is_enabled`.

### `apps/credits/services/periods.py` (+`period_label`)
Add beside `next_period_start` (L40). Use hard-coded English month names (copy list from `creditHint.ts` MONTH_NAMES_LONG), never `strftime("%B")`.

### `apps/shops/selectors/shops.py::list_shops`
**Analog:** same file L11-30 plus `annotate_credit_state` (balances.py L97-140). Add `user: User | None = None, with_credits: bool = False, period: Period | None = None`; apply Staff filter by role (`qs.filter(pk__in=get_accessible_shop_ids(user_id=user.pk))`) before annotation; `if with_credits: qs = annotate_credit_state(queryset=qs, period=period)`. Keep `.select_related("region")`. Other caller `apps/organisations/views.py:215` must keep working (new params optional).

### `apps/shops/serializers.py::ShopReadSerializer`
**Analog:** L11-13 `region_name = serializers.CharField(source="region.name", default="", read_only=True)`.
```python
credits_remaining = serializers.IntegerField(source="credit_remaining", read_only=True, default=None)
# also credits_allocated, credits_bonus; credits_total = SerializerMethodField (None when un-annotated)
```
Add to `Meta.fields` and `read_only_fields`. Verified in DRF 3.17.1 (RESEARCH Pattern 3).

### `apps/shops/views.py`
- `list` (L184): pass `user=request.user, with_credits=True` to `list_shops` alongside existing `search/status/region_id`.
- `shop_list` (L94, `@org_admin_required`, unchanged per D-18): `list_shops(organisation_id=org.pk, user=request.user, with_credits=True)`; extend `org_data` json_script (`shop-org-data`, template L31) with `organisation_name`, `support_email` (`settings.REVIEWBEE_SUPPORT_EMAIL`, base.py L253).
- D-17 retrieve scoping: `ShopViewSet` has no `get_queryset` override; copy the role branch from `ReviewViewSet.get_queryset` (apps/reviews/views.py L112-126): if `STAFF_ADMIN`, `qs.filter(pk__in=get_accessible_shop_ids(user_id=user.pk))` (this makes retrieve return 404). Check this does not break Org Admin mutation endpoints (activate/deactivate etc. stay Org Admin).

### `apps/common/selectors/audit_logs.py`
**Analog:** same file L28-47.
```python
AUDIT_ENTITY_FILTER = Q(entity_type="action_item") | Q(entity_type="review", action__in=[...])   # L29-32, DO NOT widen
CREDIT_AUDIT_FILTER = (
    Q(entity_type="shop", action__startswith="shop.credits.")
    | Q(entity_type="organisation", action="organisation.credits.set")
)
# list_audit_logs_for_org: .filter(AUDIT_ENTITY_FILTER | CREDIT_AUDIT_FILTER)
# list_audit_logs_for_staff: UNCHANGED (L50-85 CR-01 type+id pairing already excludes shop/org rows)
```
`shop_name`: `Case(When(entity_type="shop", then=Subquery(Shop.objects.annotate(_pk_s=Cast("pk", CharField())).filter(_pk_s=OuterRef("entity_id"), organisation_id=OuterRef("organisation_id")).values("name")[:1])), default=None)`. Compare as text (entity_id is free CharField; Pitfall 5). Keep list ceiling <=5 queries.

### Frontend: `ReplyComposer.tsx` + `api.ts`
**Analog:** `ReplyComposer.tsx` L80-125 (`handleGenerate`); `api.ts` L23-31 (`ApiError(status, data, retryAfterSeconds)`), L53-55 (`handle()` already throws ApiError with parsed body for 402), L147-162 (`generateReply`, return type currently `{ draft: string }`, widen to `{draft; credits_charged; credits_remaining: number | null}`).
```ts
} catch (e) {
  if (controller.signal.aborted) return;
  if (e instanceof DOMException && e.name === "AbortError") return;
  // add BEFORE setGeneratorOpen(false)/generic message:
  if (e instanceof ApiError && e.status === 402) { /* read e.data {reason, required, remaining}; set state; keep `comment` */ return; }
  ...existing 422 content_moderated / 429 branches...
```
Add `getCreditCost(reviewId, signal)` in `api.ts` mirroring `generateReply` (GET, `credentials: "same-origin"`, `handle(resp)`). Swallow AbortError (StrictMode double fetch). Never write null `credits_remaining` to the store.

### Frontend: `ShopTable.tsx` / `ShopDetailsModal.tsx`
**Analog:** `ShopTable.tsx` L11-13 `dispatchShopEvent(name,row)` -> `window.dispatchEvent(new CustomEvent(name, {detail: row}))`; badge click dispatches `shop:open-credits` (or `shop:open-details` with a focus flag) the same way. `ShopDetailsModal.tsx`: `Row` helper L21, `<Modal` L62, rows from L114; mount `CreditsCard` above the rows (D-09). Do NOT reuse its locale `formatDate` for credit dates.

### Frontend date/format helpers
**Analog:** `org-management/creditHint.ts` (`MONTH_NAMES_SHORT`, `MONTH_NAMES_LONG`, `formatNextMonthStart`, `formatMonthYear`, `formatCount`; header comment: never use locale formatting, en-GB renders "Sept"). Reuse/import; parse server `YYYY-MM-DD` by string split. This overrides UI-SPEC's en-GB suggestion (RESEARCH Pitfall 3).

### Frontend: `BuyMoreCreditsModal.tsx`
**Analog:** `widgets/modal/Modal.tsx` (props `open,onClose,title,size,dismissible,footer`; `role="dialog" aria-modal`, `FocusTrap`, Esc on `document` gated by `dismissible`, backdrop closes). Render as sibling of ShopDetails modal and pass `dismissible={false}` to the lower Modal while open (Pitfall 6). mailto: `encodeURIComponent` per value, support email from bootstrap json_script.

### `creditsStore.ts`
No in-repo analog (no existing module store). Use `useSyncExternalStore` with `Map<shop_id, ...>` (RESEARCH Pattern 5); needed because table and modals are separate React roots.

### Backend tests
**Analog:** `apps/reviews/tests/test_views.py` L962-1010 `TestReviewCreditCost`:
```python
@pytest.fixture(autouse=True)
def _clear_throttle_cache(self) -> None:
    caches["throttle"].clear()
def _client(user): client = APIClient(); client.force_authenticate(user=user)
org = OrganisationFactory(monthly_credit_allocation=10)
staff = StaffAdminFactory(organisation=org)
StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
assert client.get(url).status_code == 404   # out-of-scope Staff
```
Throttle/settings test: L1101-1110 (`rates["credit_cost"] == "120/minute"`; monkeypatch `ScopedRateThrottle.THROTTLE_RATES`). Query-count: `assert_query_ceiling` fixture from `apps/common/tests/fixtures.py` L41 (already re-exported by `apps/credits/tests/conftest.py`); wrap in `CaptureQueriesContext(connection)`; 1 vs 20 shops must be equal. Superadmin Staff/Org 403 analogs: `apps/credits/tests/test_views.py` ~L290-330, ~L470-500.

## Shared Patterns

### Tenant/Staff scope (Layer-1 selector defence)
**Source:** `reviews.py::list_reviews` L55-65; `ReviewViewSet.get_queryset` L112-126. Key off `role == STAFF_ADMIN`, never list truthiness (None vs [] bug); 404 not 403; always org-bound.

### Read-only credit balance
**Source:** `apps/credits/selectors/balances.py` (`get_shop_credit_balance`, `annotate_credit_state`). Never call `ensure_balance` in a GET; don't call `shop_credits.py` selectors (Superadmin-only per docstring).

### Scoped throttling on every new view
**Source:** `views.py` L51-53 + `base.py` rates (`credit_cost`, `superadmin_credits_read`); add `shop_credits`.

### UTC dates
**Source:** `periods.py` + `creditHint.ts`. Server owns `period_label`/`renews_on`.

### No review text in mailto/logs (CLAUDE.md §22)

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `frontend/src/widgets/credits/creditsStore.ts` | store | No module-level external store exists; follow RESEARCH Pattern 5 |
| `ReplyComposer.test.tsx` | test | No composer test exists; use `ShopTable.test.tsx` style (`vi.spyOn(api, ...)`, RTL role queries) |

## Open Items for Planner
- `config/urls.py` include path: `apps.credits.api_urls` currently holds only `superadmin/...` routes; add `shops/<int:shop_id>/credits/` there (confirm it does not collide with the shops router prefix `shops/<pk>/`).
- D-01 clarifies SC4 (badge -> card -> Buy More).
- Superadmin actor visible on credit rows to Org Admins (RESEARCH OQ2): auditor disposition required.
- Confirm Phase 32-05 does not touch `list_shops`, `ShopReadSerializer`, `audit_logs.py`, `shop-management/*`.

## Metadata
**Analog search scope:** apps/credits, apps/shops, apps/reviews, apps/common, frontend/src/widgets/{modal,shop-management,review-management,org-management,audit-log}
**Pattern extraction date:** 2026-11-11
