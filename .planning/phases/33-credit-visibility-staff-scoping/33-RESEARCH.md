# Phase 33: Credit Visibility & Staff Scoping - Research

**Researched:** 2026-11-11
**Domain:** Django/DRF tenant-scoped read endpoints + annotated list selector + React widget state (credits card, badge, composer, modal) + Activity Log selector change
**Confidence:** HIGH (everything below was read from the code on branch `feat/v0.9-ai-reply-credits` this session; the few `[ASSUMED]` items are listed in the Assumptions Log)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Clicking a badge **opens the Shop Details modal with the credits card visible** (spec §9.2). Roadmap SC4's "Buy More opens from the Shops-list badge" is satisfied **via the card's Buy More link** (badge -> card -> Buy More), not by the badge opening Buy More directly. The planner should note this as a clarification of SC4's wording.
- **D-02:** Zero states are distinguished by **text, not colour alone**: an org with 0 monthly credits shows a muted grey **"Not enabled"** badge; a shop that has used everything shows **"0 credits"** in dark grey.
- **D-03:** Colour bands follow the spec and are **shared by the badge and the Shop Details progress bar** via one helper: green when remaining > 25% of total, amber 5-25%, red < 5%, dark grey at 0 (the card's "used 75% / 95%" boundaries are the same thresholds). Total = allocated + bonus.
- **D-04:** Badge text is **"{n} credits"** ("1 credit" singular) with tooltip and aria-label **"{n} credits remaining this month"**.
- **D-05:** A muted line **above the composer** reads "This shop has {n} credits remaining this month." (spec §9.4), updated from `credits_remaining` after every generate.
- **D-06:** Because every generate charges, including tone switches and regenerates (Phase 30 D-11), **once a draft exists each tone pill shows its cost** (e.g. "Friendly · 2 cr"). No extra confirm step beyond the composer's existing replace-draft confirm.
- **D-07:** Disabled reasons are shown as **inline text, not tooltip-only**: Not enabled: "AI replies aren't enabled for this shop." - **no** Buy More link here (D-12 covers the card). Not enough credits: "Not enough credits — this reply needs {cost}, you have {remaining}." with a **Buy More Credits link directly beneath the composer** (spec §9.4).
- **D-08:** A **402 from generate switches the composer to the matching disabled state** using the 402 body (`reason`, remaining) - no generic error toast - and **keeps any draft text the user typed**.
- Carried (not re-decided): AI button hidden for star-only reviews; label and aria-label "Generate with AI · {N} credits"; tone pills disabled while generating; cost always from the server (`credit-cost` endpoint) - roadmap SC3 / Phase 30 D-10.
- **D-09:** The card sits **at the top of `ShopDetailsModal`, above the existing detail rows**, so a badge click (D-01) shows it without scrolling.
- **D-10:** **Org Admin and Staff see the same card**, including the "Monthly {allocated} · Bonus {bonus}" breakdown. No role branching in the component.
- **D-11:** The card **fetches fresh on every modal open** (endpoint sends `Cache-Control: no-store`); **no polling**. The composer refreshes its own number after generate.
- **D-12:** **"Not enabled" (total 0)**: the card shows "AI replies aren't enabled for this shop.", **no progress bar** (no divide-by-zero), and a **Buy More Credits** link.
- Carried: remaining / total, colour-coded bar (D-03), "{used} credits used · {available} credits available", "Renews {date} (UTC)" from server `renews_on`, period label from server `period_label`; a shop with no activity this month shows its full allocation (virtual balance, never writes) - roadmap SC1.
- **D-13:** **Contact Admin mails `REVIEWBEE_SUPPORT_EMAIL` for every role**. No per-org admin routing.
- **D-14:** The mailto **pre-fills subject and body**: subject "Credit request — {Org} / {Shop}"; body lists org, shop, month, current remaining / total, and a blank line for the amount needed. **No review text** (CLAUDE.md §22). URL-encode all values.
- **D-15:** The modal component takes **optional shop context**; without a shop it references the **org only**.
- **D-16:** **Soften the spec's SLA**: replace "Credits are added within 24 hours of request." with wording like "Your administrator will add credits as soon as possible."
- Carried: title "Buy More Credits", mail icon, primary "Contact Admin" + secondary "Close", focus trap, ARIA labels, ESC / backdrop close, no payment flow - roadmap SC4 / spec §9.5.
- Carried forward (locked by earlier phases / roadmap): server is the source of truth for cost, remaining, `is_enabled`, `period_label`, `renews_on`; dates render with `timeZone: "UTC"`; shop credits GET returns the virtual balance, never writes, `Cache-Control: no-store`; `list_shops(with_credits=True)` as one annotation (fixed query count 1 vs 20 shops), serializer fields default `None`; one shared `get_accessible_shop_for_credits` selector; Activity Log selector change.
- SCOPE-01 resolves research option (b): **`list_shops` gains real Staff scoping** - a deliberate behaviour change (Staff stop seeing out-of-scope shops).
- CVIS-05: Org Admin sees `shop.credits.*` and `organisation.credits.set` in the Activity Log; Staff do not (event filtering, not hiding the whole log - exact mechanism is the planner's).
- Frontend: balance store keyed by `shop_id`, refreshed after generate; `api.ts` gets a 402 branch.
- Phase 30 contracts: generate returns `{draft, credits_charged, credits_remaining}`; 402 `reason` distinguishes not-enabled vs insufficient; 409 for a duplicate in-flight generate.
- Mandatory `tenant-security-auditor` + `orm-performance-auditor` (CLAUDE.md §27).
- At milestone close: confirm the CQA-02 deploy note still matches, and move the spec `docs/in-progress/` -> `docs/completed/` (CLAUDE.md §28).

### Claude's Discretion
- Exact copy, layout, icon and colour tokens - defer to `/gsd-ui-phase 33` (done: `33-UI-SPEC.md`, approved).
- 409 (generation already in progress) message in the composer - reuse the existing composer error pattern.
- How Shop Details is opened from the badge (same modal component, focus moved to the card heading).

### Deferred Ideas (OUT OF SCOPE)
- Routing Staff's credit requests to their own Org Admin instead of platform support (rejected, D-13).
- Live polling of the credits card (rejected, D-11).
- Real purchase/checkout flow (future; the Buy More modal is the swap point).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CVIS-01 | Shop Details "AI Reply Credits" card (remaining/total, bar, used/available, allocation+bonus, renews, Not enabled, Buy More) | New `GET /api/v1/shops/<id>/credits/` built on `get_shop_credit_balance` (virtual balance); `CreditsCard` + `creditsStore`; UTC date helper reuse (`creditHint.ts`) |
| CVIS-02 | Shops list credits badge, fixed query count | `list_shops(with_credits=True)` wrapping `annotate_credit_state`; serializer fields `read_only=True, default=None`; query-count test 1 vs 20 |
| CVIS-03 | Composer: hidden for star-only, cost on label, remaining, distinct disabled states, tone pills, 402 | `GET /reviews/<id>/credit-cost/` (exists); `generateReply` typing widened; composer state machine; `ApiError` already carries 402 body |
| CVIS-04 | Buy More modal from card + composer (badge via card), mailto, a11y | Reuse `widgets/modal/Modal.tsx` (focus-trap-react, Esc, backdrop); support email + org name via `json_script` bootstrap |
| CVIS-05 | Org Admin sees `shop.credits.*` + `organisation.credits.set`; Staff do not | Add a credit-only `Q` to `list_audit_logs_for_org` ONLY; Staff selector untouched (already excludes by explicit type/id pairing); `shop_name` subquery annotation |
| SCOPE-01 | Shops list + every credit endpoint scoped to StaffAccessScope; negative tests | Staff-aware `list_shops`; `get_accessible_shop_for_credits`; negative-test matrix below |
</phase_requirements>

## Summary

Phase 33 is almost entirely **plumbing over code that already exists**. Backend: `apps/credits/selectors/balances.py` already supplies the virtual-balance read (`get_shop_credit_balance`) and the one-query Shops-list annotation (`annotate_credit_state`); `GET /api/v1/reviews/<id>/credit-cost/` and the 402/409/422/502 bodies already exist and are already Staff-scoped. What is genuinely new on the backend is: (1) a Staff/Org-scoped shop credits GET, (2) `list_shops(with_credits=..., user=...)` with real Staff scoping, (3) one shared `get_accessible_shop_for_credits` selector, (4) a credit-only widening of the **Org** Activity Log selector plus a `shop_name` annotation, (5) bootstrap plumbing for org name + `REVIEWBEE_SUPPORT_EMAIL`.

The Activity Log research flag resolves cleanly: today **nobody** sees credit events because `AUDIT_ENTITY_FILTER` whitelists only `action_item` and three `review` actions. The Staff selector additionally re-filters by explicit `(entity_type, entity_id)` pairs for reviews and action items only, so Staff cannot see credit rows even if the shared constant were widened - but the plan should NOT widen the shared constant; add a separate credit `Q` used only by `list_audit_logs_for_org`, and add a Staff negative test with PK-colliding rows.

Two **material discrepancies** the planner must surface before writing plans: (a) the Shops *page* (`shop_list`) is `@org_admin_required`, so Staff are redirected to `/login/` and never reach the Shops list UI - SCOPE-01 therefore bites at the **API** (`GET /api/v1/shops/`, which Staff can call, including with JWT), and the UI-SPEC's Staff empty state is currently unreachable (Open Question 1); (b) UI-SPEC says to format dates with `en-GB` + `timeZone: "UTC"`, but Phase 32 already documented that `en-GB` renders September as "Sept" and built hard-coded month-name helpers in `creditHint.ts` - reuse those (Pitfall 3).

**Primary recommendation:** Build the shop credits endpoint as an `APIView` in `apps/credits` (`/api/v1/shops/<int:shop_id>/credits/`, `IsOrgScoped`, new `shop_credits` throttle scope, `Cache-Control: no-store`, 404 for out-of-scope), wire `with_credits=True` + Staff `user` scoping into `list_shops`, widen only the Org audit selector, and reuse every Phase 29-32 helper (`creditHint.ts` formatters, `Modal`, `ApiError`) rather than writing new ones.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Virtual balance + remaining/total/`is_enabled` | API / Backend (`apps/credits/selectors`) | Database (LEFT JOIN + Coalesce) | Server is source of truth; read never writes (CRED-05) |
| Credit cost per review | API / Backend (`credit_cost()` via `credit-cost` action) | — | Price must equal charge; client never computes (Phase 30 D-10) |
| Staff scope enforcement (shops, credits, audit) | API / Backend selectors | — | Layer-1 defence (CLAUDE.md §9); UI hiding is belt-and-braces only |
| Period label / `renews_on` | API / Backend | Browser (formatting only) | Server owns the UTC month; client formats a date-only string with UTC getters |
| Colour band, progress %, copy | Browser / Client (`creditBand.ts`) | — | Pure presentation of server numbers |
| Balance store keyed by `shop_id` | Browser / Client (module-level) | — | Shares card/badge/composer; server remains authority (re-fetched on open / after generate) |
| Buy More mailto | Browser / Client | Frontend Server (template bootstrap of org name + support email) | No server round trip; values arrive via `json_script` |
| Activity Log credit events | API / Backend selector | Browser (labels/pill) | Event visibility is a selector decision, not a UI one |
| Audit `shop_name` | Database (correlated Subquery) | API serializer | One annotation, org-bounded, avoids N+1 |

## Standard Stack

No new libraries. Everything below is already installed and in use [VERIFIED: `frontend/package.json` read this session; `.venv` DRF 3.17.1 run this session].

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django / DRF | Django 6.0.x, DRF 3.17.1 (run in `.venv`) | Endpoint, selector, serializer | Project stack (CLAUDE.md §2) |
| `drf-spectacular` | in repo | OpenAPI for the new GET (`@extend_schema`) | Already used on credit endpoints |
| react 19.2.5, lucide-react 1.8.0, focus-trap-react 12.0.0 | pinned | Widgets, icons (`Coins`, `Mail`), modal focus trap | Already pinned; `Modal.tsx` already wraps `FocusTrap` |
| vitest 2.1.8 + @testing-library/react 16.1.0 + user-event 14.5.2 | pinned | Frontend tests | Existing harness (`frontend/vitest.config.ts`) |
| pytest 8.3.3 + pytest-django 4.9.0 + factory-boy | pinned | Backend tests | Existing harness; test DB is SQLite (`config/settings/test.py:52`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `APIView` in `apps/credits` | `@action(detail=True)` on `ShopViewSet` | `shops/views.py` is already 634 lines and its `get_queryset` is org-only (no Staff scope), so the shared selector must be used either way. Recommend the `APIView` (mirrors Phase 32 `CreditShopListView`, keeps credit logic in `apps/credits`). |
| `useSyncExternalStore` module store | React context / Redux / zustand | Table root and modals root are two separate React roots on the Shops page; a context cannot span them. A module-level store in the same Vite entrypoint bundle can. No new dependency. |

**Installation:** none. **Package Legitimacy Audit:** no external packages are installed by this phase, so the legitimacy gate (`gsd-tools query package-legitimacy check`) is not applicable. Packages removed (SLOP): none. Flagged (SUS): none.

## Existing Assets Map (reuse, do not reimplement)

| Asset | Path | What it gives Phase 33 |
|-------|------|------------------------|
| `get_shop_credit_balance(*, shop_id, period=None) -> CreditBalanceView` | `apps/credits/selectors/balances.py:53` | Virtual balance: `allocated, bonus, consumed, remaining, is_enabled, is_materialized, renews_on` (date). 1 query when row exists, 2 otherwise. Raises `Shop.DoesNotExist` for unknown shop with no row, so resolve the shop under scope first. Never filters `is_active`. |
| `annotate_credit_state(*, queryset, period=None)` | `apps/credits/selectors/balances.py:97` | Annotates a `Shop` queryset: `credit_allocated`, `credit_bonus`, `credit_consumed`, `credit_remaining`, `credit_materialized` via FilteredRelation + Coalesce. Docstring explicitly says wiring into `list_shops` is Phase 32/33 work. |
| `renews_on` | `balances.py:93` `renews_on=next_period_start(p).date(),` | Date (UTC first-of-next-month); DRF `DateField` renders `YYYY-MM-DD`. |
| `current_period()`, `Period`, `next_period_start()` | `apps/credits/services/periods.py` | The UTC seam. Read once per request and pass `period=` to every selector. **No `period_label` helper exists yet** - add one here (hard-coded English month names; do NOT use locale-dependent `strftime("%B")` / `date_format`). |
| `credit-cost` action | `apps/reviews/views.py` (`credit_cost`, `url_path="credit-cost"`) | `{cost, remaining, is_enabled}`; scope is `get_queryset()` (Staff filtered by `get_accessible_shop_ids`); 404 for out-of-scope. Existing tests cover in-scope/out-of-scope Staff, cross-tenant, Superadmin 403, never-writes, fixed query count. |
| `generate_reply` bodies | `apps/reviews/views.py` | 200 `{draft, credits_charged, credits_remaining}` (`credits_remaining` is **nullable** per the OpenAPI `IntegerField(allow_null=True)`); 402 `{code: "insufficient_credits", reason, required, remaining}` with `reason` in `not_enabled | exhausted`; 409 `generation_in_progress`; 422 `content_moderated` and 502 `ai_unavailable` both carry `credits_charged` + `credits_remaining` (also nullable). |
| `get_accessible_shop_ids(*, user_id)` | `apps/reviews/selectors/reviews.py:11` | Staff scope expansion (SHOP + REGION). **Not org-bounded** (region expansion is `Shop.objects.filter(region_id__in=...)`); new selector must add the org filter itself. 1-2 queries. |
| Superadmin credit endpoints | `apps/credits/api_urls.py` -> `superadmin/organisations/<int:org_id>/credits/shops/`, `superadmin/shops/<int:shop_id>/credits/bonus/` | Already `IsAuthenticated + IsSuperadmin`; Staff/Org-Admin/anon 403 tests already exist in `apps/credits/tests/test_views.py` (lines ~290-330, ~470-500). Phase 33 adds a sweep, not new behaviour. |
| Throttle scopes | `config/settings/base.py:436-440` `"credit_cost": "120/minute"`, `"superadmin_credits_read": "120/minute"`, `"audit_log_list": "120/minute"` | Add `"shop_credits": "120/minute"` (new). |
| `REVIEWBEE_SUPPORT_EMAIL` | `config/settings/base.py:253` `REVIEWBEE_SUPPORT_EMAIL = env("REVIEWBEE_SUPPORT_EMAIL", default="support@reviewbee.in")` | Exists. Not yet passed to any template. |
| Frontend formatters | `frontend/src/widgets/org-management/creditHint.ts`: `MONTH_NAMES_SHORT`, `MONTH_NAMES_LONG`, `formatNextMonthStart(nowUtc)`, `formatMonthYear(year, month)`, `formatCount(n)` (`toLocaleString("en-US")`) | UTC-safe, locale-independent. Reuse or lift to a shared module; do not re-derive with `Intl`. |
| `Modal` | `frontend/src/widgets/modal/Modal.tsx` | `role="dialog"`, `aria-modal`, `aria-label={title}`, `FocusTrap`, X button, Esc listener on `document` gated by `dismissible`, backdrop click closes when `dismissible`. Already satisfies CVIS-04 a11y. Stacking: both modals register a document Esc listener -> pass `dismissible={false}` to the lower one (UI-SPEC). |
| `ApiError` / `handle()` | `frontend/src/widgets/review-management/api.ts` | `handle()` already throws `new ApiError(resp.status, data, retryAfter)` for **every** non-OK incl. 402 with the parsed JSON body. The "402 branch" is therefore mostly **typing + parsing** in `ReplyComposer`, plus widening `generateReply`'s return type; no change to `handle()` is strictly required. |
| `ShopReadSerializer`, `list_shops` callers | `apps/shops/serializers.py`, `apps/shops/selectors/shops.py` | Callers: `shop_list` page (`views.py:94`), `ShopViewSet.list` (`views.py:184`), and `apps/organisations/views.py:215` (team page, `active_only=True`). The third must keep working unchanged (new params optional). |
| Audit selectors/serializer/filter | `apps/common/selectors/audit_logs.py`, `apps/common/serializers.py`, `apps/common/filters.py`, `apps/common/views.py` | See "Activity Log findings". |

## Architecture Patterns

### System Architecture Diagram

```
Browser (Org Admin / Staff)
 |
 |-- Shops page (Org Admin only; shop_list is @org_admin_required)
 |     server render: list_shops(with_credits=True) -> ShopReadSerializer -> json_script "shop-data"
 |                    + json_script "shop-org-data" {allow_custom_sync_depth, organisation_name, support_email}
 |     ShopTableWidget --(shop:refresh)--> GET /api/v1/shops/?...  -> list_shops(user=request.user, with_credits=True)
 |        |                                    |-- Staff: user -> get_accessible_shop_ids -> filter pk__in (None != [])
 |        |                                    `-- annotate_credit_state (1 LEFT JOIN, 1 query) -> rows carry credits_*
 |        `-- CreditBadge click -> CustomEvent "shop:open-credits"(row)
 |     ShopModals root --> ShopDetailsModal(focusCredits)
 |        `-- CreditsCard mount -> GET /api/v1/shops/<id>/credits/ (no-store, abort on close)
 |                |-- get_accessible_shop_for_credits(user, shop_id) -> Shop | None (None -> 404)
 |                `-- get_shop_credit_balance(shop_id, period=current_period()) + period_label + renews_on
 |        `-- "Buy More Credits" -> BuyMoreCreditsModal (sibling of Details Modal) -> mailto:REVIEWBEE_SUPPORT_EMAIL
 |
 |-- Reviews page (Org Admin + Staff) -> ReviewManagementWidget -> ReplyComposer (per expanded row)
 |        mount: GET /api/v1/reviews/<id>/credit-cost/ (Staff-scoped queryset) -> {cost, remaining, is_enabled}
 |        generate: POST .../generate-reply/ -> 200{draft,credits_charged,credits_remaining|null}
 |                                             402{reason,required,remaining} -> composer state (draft kept)
 |        every response -> creditsStore.set(shop_id, ...) -> card/badge/composer re-render (useSyncExternalStore)
 |
 `-- Activity Log (Org Admin + Staff) -> GET /api/v1/audit-logs/
          Org:   list_audit_logs_for_org   = org filter AND (AUDIT_ENTITY_FILTER | CREDIT_AUDIT_FILTER) + shop_name Subquery
          Staff: list_audit_logs_for_staff = unchanged (explicit review/action_item pairs only -> no credit rows possible)
```

### Recommended Project Structure
```
apps/credits/
  selectors/access.py        # get_accessible_shop_for_credits(*, user, shop_id) -> Shop | None   (NEW)
  services/periods.py        # + period_label(period) -> "November 2026"  (hard-coded names)       (EDIT)
  views.py                   # + ShopCreditsView (GET, no-store)                                  (EDIT)
  serializers.py             # + ShopCreditsSerializer                                            (EDIT)
  api_urls.py                # + shops/<int:shop_id>/credits/                                     (EDIT)
  tests/test_shop_credits_view.py, test_access_selector.py, test_scope_sweep.py                    (NEW)
apps/shops/selectors/shops.py   # list_shops(+ user=None, with_credits=False)                      (EDIT)
apps/shops/serializers.py       # + credit fields, default None                                    (EDIT)
apps/shops/views.py             # list/shop_list pass user + with_credits; org_data gains name/email (EDIT)
apps/common/selectors/audit_logs.py  # + CREDIT_AUDIT_FILTER (org only) + shop_name annotation      (EDIT)
apps/common/serializers.py      # + shop_name (read-only, default None)                            (EDIT)
apps/reviews/views.py           # review_list context: organisation_name, support_email              (EDIT)
templates/shops/shop_list.html, templates/reviews/review_list.html  # json_script bootstrap          (EDIT)
config/settings/base.py         # + "shop_credits": "120/minute"                                    (EDIT)
frontend/src/widgets/credits/   # creditBand.ts, format.ts, creditsStore.ts, creditsApi.ts, CreditBadge.tsx,
                                # CreditsCard.tsx, BuyMoreCreditsModal.tsx, mailto.ts + *.test.ts(x) (NEW)
frontend/src/widgets/{shop-management,review-management,audit-log}/  # wire-in edits per UI-SPEC
```

### Pattern 1: Shop-scoped credit read (single shared selector)
**What:** one selector decides "can this user read credits for this shop", returning `None` (-> 404, never 403, to avoid existence leaks - matches `credit-cost` behaviour).
**Example:**
```python
# apps/credits/selectors/access.py
def get_accessible_shop_for_credits(*, user: User, shop_id: int) -> Shop | None:
    from apps.accounts.models import User as UserModel          # function-level: credits -> shops edge
    from apps.reviews.selectors.reviews import get_accessible_shop_ids
    from apps.shops.models import Shop

    org_id = getattr(user, "organisation_id", None)
    if org_id is None:                      # Superadmin / org-less: no tenant, no access
        return None
    qs = Shop.objects.filter(pk=shop_id, organisation_id=org_id)   # org bound ALWAYS (get_accessible_shop_ids is not org-bounded)
    if user.role == UserModel.Role.STAFF_ADMIN and shop_id not in get_accessible_shop_ids(user_id=user.pk):
        return None
    return qs.first()                        # inactive shops allowed (D-13: never filter is_active)
```
Keep it keyword-only and read-only (`.claude/rules/selectors.md`).

### Pattern 2: `list_shops` with optional Staff scope and credits
**What:** distinguish "no restriction" (Org Admin/Superadmin helpers) from "Staff with zero scope" (empty). Pass the **user**, as `list_reviews(*, organisation_id, user)` does, rather than a raw id list - this makes the `None`-vs-`[]` bug impossible.
```python
def list_shops(*, organisation_id, search="", status="", region_id=None, active_only=False,
               user: User | None = None, with_credits: bool = False, period: Period | None = None):
    qs = Shop.objects.filter(organisation_id=organisation_id).select_related("region")
    if user is not None and getattr(user, "role", None) == User.Role.STAFF_ADMIN:
        qs = qs.filter(pk__in=get_accessible_shop_ids(user_id=user.pk))   # [] -> empty queryset, correct
    ...existing filters...
    if with_credits:
        qs = annotate_credit_state(queryset=qs, period=period)
    return qs
```
Do not `.only()` the annotated queryset in a way that drops `region` (serializer reads `region.name`, `region.region_id`).

### Pattern 3: Serializer fields that default to `None` when un-annotated
[VERIFIED: run in `.venv` with DRF 3.17.1 this session] `serializers.IntegerField(source="credit_remaining", read_only=True, default=None)` returns `None` when the instance has no such attribute and the value when it does. Use for `credits_remaining`, `credits_allocated`, `credits_bonus`; compute `credits_total` (= allocated + bonus) with a `SerializerMethodField` that returns `None` if the annotation is absent. Add all to `Meta.fields` (ModelSerializer requires it). `create`/`update`/`activate`/`deactivate` responses stay un-annotated -> fields `None` (frontend must not blank a known badge; but note every mutation calls `shop:refresh` -> full list refetch, so in practice rows are replaced by annotated rows).

### Pattern 4: Activity Log Org-only widening + `shop_name`
```python
CREDIT_AUDIT_FILTER = (
    Q(entity_type="shop", action__startswith="shop.credits.")
    | Q(entity_type="organisation", action="organisation.credits.set")
)
# list_audit_logs_for_org: .filter(AUDIT_ENTITY_FILTER | CREDIT_AUDIT_FILTER)
# list_audit_logs_for_staff: UNCHANGED (still AUDIT_ENTITY_FILTER + explicit (type, id) pairs)
```
`shop_name` (UI-SPEC E): annotate with a `Case(When(entity_type="shop", then=Subquery(...)))`, org-bounded (`organisation_id=OuterRef("organisation_id")`), compared **as text** (see Pitfall 5).

### Pattern 5: Frontend balance store
`creditsStore.ts` module singleton: `Map<number, {remaining, total?, isEnabled, periodLabel?}>` + `subscribe`/`getSnapshot` consumed by `useSyncExternalStore`. Written by: card fetch, composer cost fetch, every generate outcome that carries `credits_remaining` **non-null**. Never write from a 5xx body lacking numbers; never write `null`. One shared `creditBand(remaining, total)` per UI-SPEC (integer maths; `total===0` first; clamp remaining >= 0).

### Anti-Patterns to Avoid
- **Widening the shared `AUDIT_ENTITY_FILTER`** - it is used by both selectors (`audit_logs.py:29,43,89`); a shared widening re-opens the Staff question. Add a separate constant used by the Org selector only.
- **Passing `accessible_shop_ids=[]`-style lists to `list_shops` with truthiness checks** - `if ids:` silently turns "Staff with no scope" into "see everything".
- **Annotating credits in the serializer per row** (`get_shop_credit_balance` in a `SerializerMethodField`) - 1-3 queries per shop; N+1 blocker (§6).
- **Computing cost, remaining or month names on the client** - server owns them.
- **Writing in the credits GET** (`ensure_balance`) - violates CRED-05/CRED-06; the card must show the live org allocation for unmaterialised shops.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Virtual balance read | New SQL/ORM balance logic | `get_shop_credit_balance` / `annotate_credit_state` | Already handles unmaterialised shops, period filter, no fan-out |
| Staff shop scope | New StaffAccessScope walker | `get_accessible_shop_ids` (+ explicit org filter) | Handles SHOP + REGION scopes; tested in reviews/audit |
| Credit price | Client or new server tiering | `credit_cost()` via `credit-cost` action | Price shown must equal price charged |
| UTC date/month text | `Intl.DateTimeFormat("en-GB")`, `strftime("%B")` | `creditHint.ts` `MONTH_NAMES_*`, a server `period_label` helper with literal names | Locale quirks ("Sept"), server-locale dependence |
| Modal a11y | Custom focus trap/Esc | `widgets/modal/Modal.tsx` | Already trap + Esc + backdrop + aria |
| mailto assembly | String concat | `encodeURIComponent` per value, `%0D%0A` breaks (UI-SPEC D) | Header/param injection, emoji, 200-char names |
| Throttling | Custom limiter | `ScopedRateThrottle` + new `shop_credits` rate | Project pattern (`credit_cost`, `superadmin_credits_*`) |
| No-cache header | Middleware | `response["Cache-Control"] = "no-store"` on the view's Response | One endpoint; explicit |

**Key insight:** every hard problem here (race-safe balances, scope expansion, pricing, modal a11y, UTC) was solved in Phases 29-32 or earlier. Phase 33's risk is *integration* (scope correctness, `None` vs `[]`, annotation SQL, store consistency), not new algorithms.

## Activity Log findings (research flag, answered)

- **Current visibility:** `AUDIT_ENTITY_FILTER = Q(entity_type="action_item") | Q(\n    entity_type="review",\n    action__in=["reply_posted", "reply_deleted", "reply_failed"],\n)` [VERIFIED: `apps/common/selectors/audit_logs.py:29-32`]. Credit rows (`entity_type="shop"` / `"organisation"`) match neither branch, so **no role sees credit events today** (including Org Admin). CVIS-05's job is to *add* them for Org Admin.
- **Staff path:** `list_audit_logs_for_staff` re-filters with `Q(entity_type="review", entity_id__in=review_ids) | Q(entity_type="action_item", entity_id__in=action_item_ids)` (CR-01 type+id pairing). A `shop`/`organisation` row can never satisfy that, so Staff exclusion is structural. **Do not touch the Staff selector**; add a negative test.
- **Rows written** (verbatim): `entity_type="shop"` with actions `"shop.credits.allocated"`, `"shop.credits.bonus_allocated"`, `"shop.credits.consumed"`, `"shop.credits.late_commit"`, `"shop.credits.refunded"`, `"shop.credits.lapsed"` [VERIFIED: grep of `apps/credits/services/*.py`], and `entity_type="organisation"` action `"organisation.credits.set"` [VERIFIED: `apps/organisations/services/organisations.py:75,288`]. `entity_id=str(shop_id)` / `str(org.pk)`. These are the **only** `entity_type="shop"` / `"organisation"` audit writers in `apps/` [VERIFIED: grep], so `startswith("shop.credits.")` + type is exact.
- **Tenant isolation:** every writer sets `organisation_id` from the shop's/org's own row, and both selectors start with `AuditLog.objects.filter(organisation_id=...)`. No cross-org exposure from widening.
- **Filters/serializer:** `AuditLogFilterSet.entity_type` is a `ChoiceFilter` whitelist of `review`/`action_item` (400 otherwise); credit rows appear under "All types" only (matches UI-SPEC). `filter_shop` returns review rows only (`entity_type="review"`), so a shop filter hides credit rows - acceptable, note in docs. `AuditLogReadSerializer.Meta.fields` today: `id, created_at, entity_type, entity_id, action, actor_id, actor_name, after_data` - add read-only `shop_name`.
- **Query budget:** existing test `test_list_query_count` asserts `<= 5` queries for 50 rows; the `shop_name` Subquery is part of the same SELECT, so the ceiling must stay unchanged (add a credits-rows variant).
- **Volume:** `shop.credits.consumed` is written per generate, so the Org log grows; cursor pagination handles it; the `(organisation, entity_type, created_at)` index `audit_org_entity_date_idx` serves the new OR branches. No action needed beyond noting it.
- **Actor exposure (decision needed, Open Question 2):** `bonus_allocated` and `organisation.credits.set` rows have a **Superadmin** `actor`; `actor_name` and the `audit_log_view` actor dropdown (built from `list_audit_logs_for_org`) would show Superadmin names to Org Admins.
- **`after_data` content** is ids/counters only (`has_reason` boolean, no free text; `review_id`, `ai_usage_log_id`, `transaction_id`) [VERIFIED: `bonus.py:108-120`, `consumption.py:217-231`], consistent with CLAUDE.md §22 (no review text).

## Common Pitfalls

### Pitfall 1: `None` vs `[]` in Staff scoping
**What goes wrong:** Staff with zero `StaffAccessScope` rows get the whole org's shops because a falsy empty list skips the filter.
**How to avoid:** key off `user.role == STAFF_ADMIN`, not off list truthiness; test "Staff with no scope -> empty list" explicitly.
**Warning signs:** `if accessible_shop_ids:` anywhere in the new code.

### Pitfall 2: `get_accessible_shop_ids` is not org-bounded
**What goes wrong:** REGION-scope expansion is `Shop.objects.filter(region_id__in=region_ids)` with no organisation filter [VERIFIED: `reviews.py:31-32`]; bad data (a region from another org in a Staff scope) would leak a foreign shop.
**How to avoid:** the new selector and `list_shops` both always keep `organisation_id=user.organisation_id`; add a test with a foreign-org region scope.

### Pitfall 3: Date formatting divergence (UI-SPEC vs Phase 32)
**What goes wrong:** UI-SPEC says `en-GB` + `timeZone: "UTC"` -> `1 Dec 2026`; `creditHint.ts` documents that `en-GB` renders September as "Sept" and that locale formatting must never be used. `new Date("2026-12-01T00:00:00")` (no `Z`) parses as local time.
**How to avoid:** parse the server's `YYYY-MM-DD` by string split (or `Date.UTC`) and index `MONTH_NAMES_SHORT`; reuse `formatMonthYear`/`formatCount`. Satisfies the roadmap's "UTC" intent with no locale risk. Add a September fixture test. Never reuse `ShopDetailsModal.formatDate` for credit dates (locale/zone dependent).

### Pitfall 4: Nullable `credits_remaining`
**What goes wrong:** 200/422/502 bodies can carry `credits_remaining: null` (read failure) [VERIFIED: view schema `allow_null=True`; `read_credits_remaining` returns `None` on failure]; writing `null` into the store shows "NaN credits" or flips to not-enabled.
**How to avoid:** store writes require a finite number; on null keep the previous value (and optionally re-fetch `credit-cost`).

### Pitfall 5: `Cast(entity_id -> Integer)` in the audit subquery
**What goes wrong:** `AuditLog.entity_id` is a free `CharField(max_length=200)` shared by every entity type. Casting it to integer in SQL raises on non-numeric rows in PostgreSQL (SQLite tests will not catch it). Also an unconditional subquery would name a *shop* for a *review* row whose `entity_id` equals a shop PK (PK collisions across tables are routine, see CR-01).
**How to avoid:** wrap in `Case(When(entity_type="shop", then=Subquery(...)), default=None)` and compare **as text** by annotating the inner `Shop` queryset with `Cast("pk", CharField())` filtered `== OuterRef("entity_id")`, plus `organisation_id=OuterRef("organisation_id")`. Add tests: review row with colliding id gets `shop_name=None`; other-org shop id gets `None`; deleted shop gets `None`. [ASSUMED: Postgres cast-error behaviour, A2] - run the audit API test under `config.settings.test_pg` if available.

### Pitfall 6: Stacked modals / Esc
`Modal` registers a `document` keydown listener per open modal; without `dismissible={false}` on the Shop Details modal while Buy More is open, one Esc closes both. Render Buy More as a **sibling**, not a child (child click events bubble through the portal's React tree to the parent's backdrop `onClick`). [CITED: UI-SPEC Interaction A; `Modal.tsx` read this session]

### Pitfall 7: Initial-focus race for the badge -> card flow
`FocusTrap` focuses the first tabbable (the X) on activation; moving focus to the card `h3` must be deferred a tick (`requestAnimationFrame`/`setTimeout 0`). [CITED: UI-SPEC]; verify in a vitest with fake timers.

### Pitfall 8: StrictMode double-fetch
Both `main` entrypoints render in `<StrictMode>`; effects mount twice in dev. Cost/card fetches must abort the first request (`AbortController`) and swallow `AbortError` (the composer already does for generate).

### Pitfall 9: Throttle ordering
`ScopedRateThrottle` needs `throttle_scope` set on the view; a view with only `throttle_scope` but default classes works because `DEFAULT_THROTTLE_CLASSES` includes `ScopedRateThrottle` [VERIFIED: base.py ~425-427]; mirror Phase 32's explicit `throttle_classes = [ScopedRateThrottle]` for clarity. Missing rate in `DEFAULT_THROTTLE_RATES` raises `ImproperlyConfigured` at request time - add `"shop_credits"` and a settings test (see `test_credit_cost_is_throttled_on_its_own_scope`).

### Pitfall 10: Annotated `list_shops` with Paginator `.count()`
Both the page view (`django.core.paginator.Paginator`) and `ShopsPagination` call `.count()` on the annotated queryset; the FilteredRelation join is harmless (no row multiplication - unique `(shop, year, month)`), but assert ordering is deterministic (`Shop` default ordering `-created_at` is kept) and cover `search`/`status`/`region` filter combos with credits on.

## Code Examples

### Shop credits endpoint (sketch)
```python
# apps/credits/views.py
class ShopCreditsView(APIView):
    permission_classes = [IsOrgScoped]                    # Superadmin / anon refused; Org Admin + Staff pass
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "shop_credits"

    def get(self, request: Request, shop_id: int) -> Response:
        shop = get_accessible_shop_for_credits(user=request.user, shop_id=shop_id)
        if shop is None:
            return Response({"code": "shop_not_found", "detail": "Shop not found."}, status=404)
        period = current_period()                          # read once
        bal = get_shop_credit_balance(shop_id=shop.pk, period=period)   # never writes
        resp = Response(ShopCreditsSerializer(...).data)
        resp["Cache-Control"] = "no-store"
        return resp
# payload: shop_id, period{year,month}, period_label, renews_on, allocated, bonus, consumed (="used"),
#          remaining (="available"), total (=allocated+bonus), is_enabled
```
`IsOrgScoped.has_object_permission` is not invoked by `APIView.get` (no `get_object`), which is why scoping must be explicit in the selector (it is). Existing 404-shape precedent: `{"code": ..., "detail": ...}` in `CreditShopListView`.

### Composer 402 handling
```ts
catch (e) {
  if (e instanceof ApiError && e.status === 402) {
    const b = e.data as { reason: "not_enabled" | "exhausted"; required: number; remaining: number };
    creditsStore.set(row.shop_id, { remaining: b.remaining, isEnabled: b.reason !== "not_enabled" });
    setCost(b.required);                 // exhausted: server's cost wins over the stale local value
    setGeneratorOpen(false); setGeneratingTone(null);   // keep `comment` untouched; no banner, no toast
    document.getElementById(`reply-textarea-${row.id}`)?.focus();
    return;
  }
  ...existing 409/422/429/502 handling...
}
```
`generateReply` must be retyped to `{ draft: string; credits_charged: number; credits_remaining: number | null }`; note 422/502 numbers come from `e.data` (`credits_charged`, `credits_remaining`).

## Runtime State Inventory

Not a rename/refactor/migration phase - omitted. (No model/migration change is expected; `makemigrations --check` must stay clean.)

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Phase 29 docstring: balance selectors "unscoped primitives... Phase 32/33 endpoints" scope them | Phase 33 adds the first tenant-scoped consumer (`get_accessible_shop_for_credits`) | `shop_credits.py` docstring says its selectors "must only be called from Superadmin-only views" - do not call them from tenant views; use `balances.py` primitives + the new access selector |
| `list_shops` unscoped by Staff | Staff-aware via `user=` | Behaviour change (intentional, SCOPE-01) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `focus-trap-react` 12 supports two simultaneously-open `Modal`s (nested traps pause/resume) so Buy More over Shop Details keeps focus inside the top modal | Pitfall 6 / Existing Assets | Focus could leak to the lower modal; cover with the UI-SPEC backstop test (Esc closes only Buy More) and a manual check |
| A2 | PostgreSQL raises on `CAST(<non-numeric text> AS integer)` even in a correlated subquery, so a text-compare is required | Pitfall 5 | Low: text-compare is correct on both engines regardless |
| A3 | A 120/minute `shop_credits` throttle is adequate (card fetches once per modal open) | Existing Assets | Low; trivially adjustable, mirrors `credit_cost` |
| A4 | Org Admins seeing Superadmin actor names on credit rows is acceptable | Activity Log findings | Possible privacy/UX objection; see Open Question 2 |
| A5 | Flat list fields (`credits_remaining`, `credits_total`, ...) are preferable to a nested `credits` object in `ShopReadSerializer` | Pattern 3 | Cosmetic; planner's call |

## Open Questions

1. **Staff cannot reach the Shops page, so the Staff empty state and the badge are Org-Admin-only in practice.**
   - What we know: `shop_list` is `@org_admin_required` [VERIFIED: `apps/shops/views.py:90`]; the decorator redirects non-Org-Admin to `/login/`. The sidebar hides "Shops" for `STAFF_ADMIN` (`templates/partials/sidebar_org.html:32`). `GET /api/v1/shops/` however is open to Staff (and JWT Staff, test `test_staff_admin_jwt_can_list_shops`). Staff therefore see credits only in the **composer** (Reviews page).
   - What's unclear: whether the UI-SPEC's Staff "No shops assigned" empty state (user-confirmed) and CVIS-01/02 "Org Admins and Staff" intend to open the Shops page to Staff.
   - Recommendation: keep the page Org-Admin-only (opening it would expose Edit/Deactivate controls the API 403s for Staff - scope creep); satisfy SCOPE-01 at the API; implement the `isOrgAdmin` empty-state prop per UI-SPEC (cheap, vitest-testable) but note in the plan that it is defensive today. Ask the user only if they want Staff on the Shops page.
2. **Superadmin identity in the Org Admin Activity Log.**
   - What we know: bonus/`organisation.credits.set` rows carry the Superadmin as `actor` and `actor_name`; the actor dropdown includes them.
   - Recommendation: accept (an Org Admin seeing who changed their credits is normal), but have the `tenant-security-auditor` disposition it explicitly; alternative is to null `actor_name` for credit rows (shows "System").
3. **Staff `GET /api/v1/shops/{id}/` (retrieve) is not Staff-scoped** (`ShopViewSet` has no `get_queryset` override; base scoping is org-only). Out-of-scope shop details (name/address/phone/place_id) are readable by Staff today.
   - Recommendation: include retrieve in SCOPE-01 hardening (override `get_queryset` to apply the same Staff filter - one small change, plus a negative test). It is beyond the roadmap's literal wording ("list and every credit endpoint"), so flag it to the user as an optional inclusion; credits are not exposed by retrieve either way (no annotation there).
4. **Composer-launched Buy More has no `total` or `period_label`** (`credit-cost` returns only `cost, remaining, is_enabled`). Recommendation: do not change the Phase 30 contract; follow UI-SPEC "omit rather than guess" (omit `Month` and `Current balance` lines unless the store has them from a card fetch).
5. **Phase 32 plan 32-05 has no SUMMARY yet** (STATE: 15/16 plans). Phase 33 only needs the Phase 32 endpoints/`ManageCreditsModal` already merged; confirm 32-05 does not touch `list_shops`, `ShopReadSerializer`, `audit_logs.py` or `shop-management/*` before executing in parallel.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | backend tests | yes | `.venv` Python 3.12, DRF 3.17.1 | — |
| Node | vitest/tsc | yes | v22.17.1 | — |
| pytest baseline | audit + shops selector tests | yes | 3 test files ran green this session | — |
| vitest baseline | `ShopTable.test.tsx` | yes | 5/5 passed this session | — |
| PostgreSQL (`config.settings.test_pg`) | optional `pg` check of the audit text-cast | not probed | — | SQLite unit tests + CI `backend-pg` job |

No blocking dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Backend: pytest 8.3.3 + pytest-django 4.9.0 + factory-boy (SQLite in `config.settings.test`). Frontend: vitest 2.1.8 + @testing-library/react 16.1.0 (jsdom, `frontend/src/test-setup.ts`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `--ds=config.settings.test`), `frontend/vitest.config.ts` |
| Quick run command | `.venv/bin/pytest apps/credits apps/shops apps/common apps/reviews/tests/test_views.py --no-cov -q` ; `cd frontend && npx vitest run src/widgets/credits src/widgets/shop-management src/widgets/review-management src/widgets/audit-log` |
| Full suite command | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` ; `cd frontend && npm test && npx tsc --noEmit` |
| Extra gates | `.venv/bin/python manage.py makemigrations --check --dry-run`, `mypy .`, `ruff` / `pre-commit run --all-files`, `spectacular --validate` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CVIS-01 | Credits GET returns virtual balance (unmaterialised shop = full allocation, no rows written), `period_label`, `renews_on`, `Cache-Control: no-store`, inactive shop works, total 0 -> `is_enabled false` | API | `pytest apps/credits/tests/test_shop_credits_view.py -x` | No - Wave 0 |
| CVIS-01 | Card states: loading skeleton, error+Retry, not-enabled (no bar), populated, band colours, `aria-valuenow`, no divide-by-zero, refetch each open, abort on close | vitest | `npx vitest run src/widgets/credits/CreditsCard.test.tsx` | No - Wave 0 |
| CVIS-01 | `creditBand` boundaries (25% and 5% exact = amber, 0 = empty, total 0 = not_enabled); UTC date helper incl. September/Dec rollover | vitest | `npx vitest run src/widgets/credits/creditBand.test.ts src/widgets/credits/format.test.ts` | No - Wave 0 |
| CVIS-02 | `list_shops(with_credits=True)` annotates; query count identical for 1 vs 20 shops (selector + `GET /api/v1/shops/`); fields `None` without flag; unmaterialised vs materialised; filter combos | selector/API | `pytest apps/shops/tests/test_selectors.py apps/shops/tests/test_views.py -k credit -x` | Files exist; tests new |
| CVIS-02 | Badge text/aria-label/title for all 6 states, `—` for `None`, click dispatches `shop:open-credits`, store wins over row | vitest | `npx vitest run src/widgets/shop-management/ShopTable.test.tsx src/widgets/credits/CreditBadge.test.tsx` | ShopTable.test exists; CreditBadge new |
| CVIS-03 | Composer state machine (hidden star-only, loading, ready, not-enabled, insufficient + Buy More link, load-error fail-open), label/aria-label, tone pill cost with draft, pills disabled while generating, 402 keeps draft + switches state + focus, 409 banner, null `credits_remaining` ignored | vitest | `npx vitest run src/widgets/review-management/ReplyComposer.test.tsx` | No - Wave 0 |
| CVIS-03 | `credit-cost` contract + Staff scoping remain green | API | `pytest apps/reviews/tests/test_views.py -k credit_cost -x` | Yes |
| CVIS-04 | Buy More modal: focus trap, Esc closes only top modal, backdrop closes, mailto = encoded subject/body, 200-char + emoji + newline names, no review text, org-only variant, not-enabled copy | vitest | `npx vitest run src/widgets/credits/BuyMoreCreditsModal.test.tsx src/widgets/credits/mailto.test.ts` | No - Wave 0 |
| CVIS-04 | Support email + org name bootstrap rendered in both templates | API/template | `pytest apps/shops/tests/test_views.py apps/reviews/tests/test_views.py -k bootstrap -x` | Files exist; tests new |
| CVIS-05 | Org selector returns credit rows (all 7 actions) ordered with others; Staff selector/API returns none (rows with colliding entity_ids); other-org credit rows excluded; `shop_name` populated only for shop rows, `None` for collision/other-org/deleted; list query ceiling unchanged (<=5) | selector/API | `pytest apps/common/tests/test_audit_log_selectors.py apps/common/tests/test_audit_log_api.py -x` | Files exist; tests new |
| CVIS-05 | Activity Log UI: `Credits` pill, 7 action labels, `Label — Shop name` / `Shop #id` fallback, org row label only | vitest | `npx vitest run src/widgets/audit-log` | Partial |
| SCOPE-01 | Staff list returns only in-scope shops (SHOP scope, REGION scope, both); Staff with no scope -> empty; foreign-org region scope not leaked; Org Admin sees all org shops; cross-org excluded | selector/API | `pytest apps/shops/tests/test_selectors.py apps/shops/tests/test_views.py -k staff -x` | Files exist; tests new |
| SCOPE-01 | Credits GET: in-scope Staff 200; out-of-scope Staff 404; cross-org Org Admin 404; Superadmin 403; anon 401/403; inactive shop 200 | API | `pytest apps/credits/tests/test_shop_credits_view.py apps/credits/tests/test_access_selector.py -x` | No - Wave 0 |
| SCOPE-01 | Sweep: every route in `apps.credits.api_urls` refuses Staff/Org Admin/anon (Superadmin-only) and `generate-reply` / `credit-cost` refuse out-of-scope Staff | API | `pytest apps/credits/tests/test_scope_sweep.py -x` | No - Wave 0 |
| SCOPE-01 (opt.) | Staff `GET /api/v1/shops/{id}/` out-of-scope -> 404 (if Open Question 3 accepted) | API | `pytest apps/shops/tests/test_views.py -k staff_retrieve -x` | No |
| Gates | No N+1 on every new list/annotation; throttle rate configured; `makemigrations --check` clean; OpenAPI valid | settings/CI | `pytest apps/credits/tests/test_settings.py -x` ; `manage.py makemigrations --check --dry-run` | settings test exists; case new |

### Sampling Rate
- **Per task commit:** the quick-run commands above scoped to the touched app/widget (+ `npx tsc --noEmit` when `types.ts` changes).
- **Per wave merge:** `pytest apps/credits apps/shops apps/common apps/reviews --no-cov -q` + `cd frontend && npm test && npx tsc --noEmit`.
- **Phase gate:** full suite + gates green, `tenant-security-auditor` and `orm-performance-auditor` (mandatory, CLAUDE.md §27) dispositions recorded, `code-reviewer` run, then `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `apps/credits/tests/test_shop_credits_view.py`, `test_access_selector.py`, `test_scope_sweep.py` (Staff/Org/Superadmin client fixtures exist in `apps/credits/tests/conftest.py` + `StaffAdminFactory`, `StaffAccessScope`)
- [ ] Credit tests in `apps/shops/tests/test_selectors.py` + `test_views.py` and audit tests (reuse `AuditLogFactory` from `apps/reviews/tests/factories.py`)
- [ ] `frontend/src/widgets/credits/*.test.ts(x)` and `review-management/ReplyComposer.test.tsx` (no composer test exists today)
- Framework install: none.

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (inherited) | Session auth; endpoints `IsOrgScoped` |
| V3 Session Management | no change | — |
| V4 Access Control | **yes - primary** | Selector-level tenant + `StaffAccessScope` filter; 404 not 403 for out-of-scope; Superadmin refused on tenant endpoints; audit selector split by role |
| V5 Input Validation | yes | `<int:shop_id>` path converter; mailto values `encodeURIComponent`; no free-text input added |
| V6 Cryptography | no | — |
| V7 Logging/Data Protection | yes | No review text in mailto or logs (§22); `after_data` ids/counters only |
| V8 Data Protection | yes | `Cache-Control: no-store` on balance GET |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on `/shops/<id>/credits/` (cross-org or out-of-scope Staff) | Information disclosure | `get_accessible_shop_for_credits` (org-bound + Staff scope) -> 404; negative tests |
| Staff sees out-of-scope shops/balances via list annotation | Information disclosure | Staff filter applied before annotation; `None`-vs-`[]` test; foreign-org region test |
| Credit audit rows reaching Staff via widened shared filter | Information disclosure | Org-only `CREDIT_AUDIT_FILTER`; Staff selector untouched; PK-collision negative test |
| `shop_name` subquery naming a shop from another tenant / wrong entity type | Information disclosure | `Case(entity_type="shop")` + `organisation_id=OuterRef` condition; tests |
| Stale/cached balance served to another user | Information disclosure | `no-store`; per-request fetch |
| mailto parameter/header injection via shop/org names | Tampering | `encodeURIComponent` on every value; CRLF -> `%0D%0A` only for intended line breaks; test with newline/`&`/emoji names |
| Allocation/limit leak to Staff via list envelope (`allocation_status`, `has_regions`) | Information disclosure (low) | Pre-existing; note for auditor |
| Throttle exhaustion of the card GET | DoS | `shop_credits` scoped throttle |

## Project Constraints (from CLAUDE.md)
- Thin views; logic in `services/`/`selectors/`; selectors read-only with keyword-only args (`.claude/rules/selectors.md`, `drf-views.md`).
- Explicit permission class and scoped throttle on every new view; tenant scope by `organisation_id`; Staff by `StaffAccessScope` (§9).
- No N+1 (blocker): one annotation for the list; `CaptureQueriesContext` fixed-ceiling test on every list endpoint (§6.9); `select_related` for forward FK.
- Pagination on list endpoints (existing `ShopsPagination`, cursor pagination for audit).
- Requirements-first gate (§24): CVIS/SCOPE IDs exist in `.planning/REQUIREMENTS.md`.
- Tests first for services/selectors; >= 85% coverage; never hit external APIs; frontend tests per `.claude/rules/testing-frontend.md` (behaviour, role/text queries, mock fetch + bootstrap, no sibling-component mocks).
- Mandatory `tenant-security-auditor` + `orm-performance-auditor` before PR (§27); `code-reviewer`; `pre-commit run --all-files` and `pytest` before done.
- No review text in logs/emails/mailto; Channels surface unchanged (no new consumer; credits use HTTP, §13.2).
- Surgical changes: do not refactor adjacent code (e.g. `ShopDetailsModal.formatDate`); remove only what you orphan.
- Doc hygiene (§28): at milestone close move `docs/in-progress/Requirements_Credits_System.md` -> `docs/completed/`.
- Commit messages: Conventional Commits (`feat(33-xx): ...`).

## Sources

### Primary (HIGH confidence - code read this session)
- `apps/credits/selectors/balances.py`, `shop_credits.py`, `views.py`, `serializers.py`, `api_urls.py`, `services/{periods,credit_cost,bonus,allocation,consumption,lapse}.py`, `exceptions.py`
- `apps/common/selectors/audit_logs.py`, `views.py`, `serializers.py`, `filters.py`, `models.py`
- `apps/shops/{views,serializers,selectors/shops,models}.py`, `apps/organisations/views.py` (list_shops caller), `apps/organisations/services/organisations.py`
- `apps/reviews/views.py` (generate-reply, credit-cost, review_list), `selectors/reviews.py`
- `apps/accounts/{models,permissions}.py`, `apps/common/{viewsets,permissions}.py`, `config/{urls,settings/base,settings/test}.py`
- `frontend/src/widgets/{shop-management,review-management,modal,audit-log,data-table,org-management}/*`, `frontend/src/entrypoints/{shop-management,review-management}.tsx`, `templates/{shops/shop_list,reviews/review_list,partials/sidebar_org}.html`
- `.planning/{REQUIREMENTS,ROADMAP,STATE}.md`, `33-CONTEXT.md`, `33-UI-SPEC.md`, `.planning/research/{SUMMARY,PITFALLS,FEATURES}.md`
- Executed: DRF 3.17.1 `read_only=True, default=None` serializer probe in `.venv`; baseline pytest (3 files) and vitest (`ShopTable.test.tsx`) green.

### Secondary / Tertiary
- None used (no external docs needed; no web research performed; no new packages).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies; all versions read from pinned files/venv.
- Architecture: HIGH - every integration point was read in code; only A1/A2 depend on library/DB behaviour not exercised here.
- Pitfalls: HIGH for 1-4, 6-10 (code-evidenced); MEDIUM for 5 (Postgres behaviour assumed, mitigated by text-compare design).

**Research date:** 2026-11-11
**Valid until:** 2026-12-11 (stable code; re-check if Phase 32-05 lands changes to `list_shops`, `ShopReadSerializer`, `audit_logs.py`, or `shop-management/*`)
