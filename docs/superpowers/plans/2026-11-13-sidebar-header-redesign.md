# Sidebar and Header Redesign ("Black Frame") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat sidebar and white top bar with one black frame (grouped, foldable menu + dark header) that holds every app page on a rounded light panel, plus count badges and an AI-credits meter for Org Admin and Staff.

**Architecture:** One read endpoint (`GET /api/v1/me/nav-summary/`) backed by a selector returns badge counts and credit totals scoped to the caller's shops. The sidebar menu is defined once in Python (per role) and rendered by one template for both shells. `app-shell.ts` keeps the persistent (Turbo) sidebar's active pill, fold state and numbers up to date on each navigation.

**Tech Stack:** Django 6 templates, DRF, Tailwind v4 tokens, Alpine.js, Turbo, Lucide, TypeScript + Vitest (jsdom), pytest + factory-boy.

**Spec:** `docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md`

## Global Constraints

- Brand: yellow `#FACC15` (`yellow` token), black `#0A0A0A` (`black` token), page panel `#FAFAFA` (`bg` token), font Geist — use the existing Tailwind tokens in `frontend/src/styles/tailwind.css`, no new hex values except where the mockup needs a zinc shade already used in today's sidebar (`#27272A`, `#52525B`, `#71717A`, `#A1A1AA`, `#D4D4D8`).
- Group labels in sentence case, never all caps: Org Admin — (ungrouped) Dashboard · Customer feedback: Reviews, Action items, Reports · Locations: Shops, Regions · Workspace: Tags, Reply templates, Team, Activity log. Staff — Customer feedback: Reviews, Action items, Activity log. Superadmin — Platform: Dashboard, Organisations · AI spend: AI cost, AI pricing · Developer: Django admin, API docs.
- URLs and role gating unchanged (copy hrefs from today's `templates/partials/sidebar.html` / `sidebar_org.html`).
- Active item: solid yellow pill, black text/icon, ~9px radius. Badges hidden at 0, `99+` above 99. Meter text: "AI reply credits this month" / "X of Y left"; hidden when total is 0 or null.
- Scoping: credits + Reviews badge = active shops only (Org Admin: all org active shops; Staff: active shops in `get_accessible_shop_ids`). Action items badge = open (`TODO`/`IN_PROGRESS`) rows of `list_action_items(...)` defaults. Superadmin: no badges, no meter, no fetch.
- Django admin (`/django-admin/`), auth pages, emails and page content are out of scope.
- Requirements first (CLAUDE.md §24); selectors for reads (§5); explicit permission + throttle + query-count test + OpenAPI on the endpoint (§8, §6.9).
- Responsive: ≥lg full 240px sidebar; md 64px icon rail (group headings become dividers, badges become a yellow dot, meter hidden); <md slide-out drawer (existing `$store.nav.mobileOpen`).

## Review Focus

1. Navigating (Turbo) to a page whose group the user folded earlier — the group must open and show the pill; the stored fold for other groups stays.
2. Organisation with allocation 0 but a bonus this month — total > 0, so the meter shows (bonus counts toward Y).
3. Staff whose region scope includes an inactive shop — that shop's credits and reviews are not counted.
4. Nav-summary fetch fails (network, 403, 500) after a navigation — badges and meter disappear rather than showing the previous page's numbers.
5. `localStorage` unavailable (private mode, throws) — menu renders fully expanded and works; no console error breaks the shell.

Each line has a test in the owning task (Tasks 1, 2, 4).

---

### Task 1: Requirements + credit totals selector

**Files:**
- Modify: `.planning/REQUIREMENTS.md` (Post-v0.10 changes table)
- Modify: `apps/credits/selectors/balances.py`
- Test: `apps/credits/tests/test_selectors.py`

**Interfaces:**
- Produces: `CreditTotals` (frozen dataclass: `remaining: int`, `total: int`) and `sum_credit_balances(*, shop_ids: Sequence[int], period: Period | None = None) -> CreditTotals | None` in `apps/credits/selectors/balances.py`.

- [ ] **Step 1: Add requirement rows** to the "Post-v0.10 changes" table in `.planning/REQUIREMENTS.md`, status `🚧 In progress`, acceptance `spec docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md`:
  - `UI-NAV-01` Black frame shell + grouped, foldable sidebar and dark header for all three roles (spec §2.1–2.5, §2.8)
  - `UI-NAV-02` Reviews / Action items badges scoped per spec §2.6, §4
  - `UI-NAV-03` AI-credits meter: sum over the person's active shops (spec §2.7, §4)

- [ ] **Step 2: Write failing tests** in `apps/credits/tests/test_selectors.py`:

```python
def test_sum_credit_balances_adds_allocated_bonus_and_remaining_across_shops(): ...
    # org allocation 100; shop A row (allocated 100, bonus 20, consumed 30); shop B no row
    # -> CreditTotals(remaining=100+20-30 + 100, total=100+20 + 100) == CreditTotals(190, 220)
def test_sum_credit_balances_returns_none_for_empty_shop_ids(): ...      # [] -> None
def test_sum_credit_balances_returns_none_when_total_is_zero(): ...      # allocation 0, no rows -> None
def test_sum_credit_balances_counts_bonus_when_allocation_zero(): ...    # allocation 0, row bonus 15 -> CreditTotals(15, 15)
def test_sum_credit_balances_uses_one_query_for_any_shop_count(): ...    # CaptureQueriesContext: 2 shops vs 6 shops -> same count, == 1
```

- [ ] **Step 3: Run** `uv run pytest apps/credits/tests/test_selectors.py -q -k sum_credit_balances` — Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `sum_credit_balances`** — `annotate_credit_state(queryset=Shop.objects.filter(pk__in=shop_ids))` then one `.aggregate(Sum("credit_remaining"), Sum(F("credit_allocated") + F("credit_bonus")))`; return `None` when `shop_ids` is empty or the total is 0. Does not filter `is_active` (caller passes the right ids — keep the module's "unscoped primitive" contract).

- [ ] **Step 5: Run** the same command — Expected: PASS.

- [ ] **Step 6: Commit** `feat(credits): sum credit balances across a set of shops` (+ the REQUIREMENTS rows).

---

### Task 2: Nav summary selector + endpoint

**Files:**
- Create: `apps/accounts/selectors/nav_summary.py`
- Modify: `apps/accounts/serializers.py`, `apps/accounts/views.py`, `apps/accounts/api_urls.py`, `config/settings/base.py` (throttle rate)
- Test: `apps/accounts/tests/test_nav_summary.py`

**Interfaces:**
- Consumes: `sum_credit_balances`, `CreditTotals` (Task 1); `base_reviews_queryset`, `get_accessible_shop_ids` (`apps/reviews/selectors/reviews.py`); `list_action_items` (`apps/action_items/selectors/items.py`).
- Produces:
  - `NavSummary` (frozen dataclass: `reviews_awaiting_reply: int`, `open_action_items: int`, `credits: CreditTotals | None`) and `get_nav_summary(*, user: User) -> NavSummary`.
  - `GET /api/v1/me/nav-summary/` (URL name `nav-summary`) → `200 {"reviews_awaiting_reply": int, "open_action_items": int, "credits": {"remaining": int, "total": int} | null}`; `403` for Superadmin / no organisation; throttle scope `nav_summary` = `"240/minute"`.

- [ ] **Step 1: Write failing tests** in `apps/accounts/tests/test_nav_summary.py` (factories: `OrganisationFactory`, `ShopFactory`, `ReviewFactory`, `ActionItemFactory`, `OrgAdminFactory`, `StaffAdminFactory`, `ShopCreditBalanceFactory`):

```python
def test_org_admin_counts_unreplied_reviews_of_active_shops_only(): ...
    # active shop: 2 unreplied + 1 replied; inactive shop: 3 unreplied -> reviews_awaiting_reply == 2
def test_org_admin_open_action_items_include_brand_items_and_exclude_done_and_duplicates(): ...
    # TODO shop, IN_PROGRESS brand, COMPLETE, WONT_DO, TODO merged duplicate (canonical set) -> 2
def test_staff_counts_only_scoped_shops_and_no_brand_items(): ...
    # staff scoped to shop A; reviews/items in shop B and a BRAND item ignored
def test_staff_region_scope_excludes_inactive_shop_credits_and_reviews(): ...    # Review Focus 3
def test_credits_sum_active_shops_and_null_when_disabled(): ...                  # org allocation 0, no rows -> credits is None
def test_credits_show_when_only_bonus_this_month(): ...                          # Review Focus 2
def test_user_with_no_shops_gets_zero_counts_and_null_credits(): ...             # staff without scope
def test_other_organisation_data_never_counted(): ...
def test_endpoint_returns_payload_shape_for_org_admin(): ...                     # 200 + exact keys
def test_endpoint_forbidden_for_superadmin(): ...                                # 403
def test_get_nav_summary_query_count_fixed(): ...  # CaptureQueriesContext on the selector: 1 shop vs 5 shops same count, <= 5 (spec §7)
```

- [ ] **Step 2: Run** `uv run pytest apps/accounts/tests/test_nav_summary.py -q` — Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `get_nav_summary`** in `apps/accounts/selectors/nav_summary.py`: Superadmin or `organisation_id is None` → zero counts, `credits=None`. Shop ids: Org Admin → org's `is_active=True` shop ids; Staff → `Shop.objects.filter(pk__in=get_accessible_shop_ids(user_id=...), organisation_id=org, is_active=True)`. Reviews count from `base_reviews_queryset(organisation_id=org)` (+ `shop_id__in` accessible ids for Staff) `.filter(is_replied=False).count()`. Action items: `list_action_items(organisation_id=org, user=user).filter(status__in=[TODO, IN_PROGRESS]).count()` (call `.order_by()` / avoid the `duplicate_count` annotation cost if it adds a GROUP BY — use `.values("pk")` count). Credits: `sum_credit_balances(shop_ids=...)`.

- [ ] **Step 4: Implement the endpoint**: `NavSummarySerializer` (+ nested `CreditTotalsSerializer`, `allow_null=True`) in `apps/accounts/serializers.py`; `NavSummaryView(APIView)` in `apps/accounts/views.py` with `permission_classes = [IsOrgScoped]` (`apps/common/permissions.py`), `ScopedRateThrottle`, `throttle_scope = "nav_summary"`, `@extend_schema(responses={200: NavSummarySerializer, 403: ..., 429: ...}, tags=["accounts"])`; route `path("me/nav-summary/", NavSummaryView.as_view(), name="nav-summary")` in `apps/accounts/api_urls.py`; add `"nav_summary": "240/minute"` to `DEFAULT_THROTTLE_RATES`. (`IsOrgScoped` already allows only Org Admin / Staff with an organisation, so Superadmin gets 403.)

- [ ] **Step 5: Run** `uv run pytest apps/accounts/tests/test_nav_summary.py -q` and `uv run python manage.py spectacular --file /dev/null --validate` — Expected: PASS, no schema warnings for the new view.

- [ ] **Step 6: Commit** `feat(accounts): nav summary endpoint for sidebar badges and credits`.

---

### Task 3: Black frame shell, grouped sidebar and dark header (templates)

**Files:**
- Create: `apps/common/navigation.py`, `templates/partials/_nav_group.html`
- Modify: `apps/common/templatetags/ui.py`, `templates/partials/sidebar.html` (becomes the single sidebar), `templates/partials/sidebar_org.html` (becomes `{% include "partials/sidebar.html" %}` or is deleted with its include sites updated), `templates/partials/_nav_item.html`, `templates/partials/topbar.html`, `templates/partials/shell_open.html`, `shell_org_open.html`, `shell_close.html`, `shell_org_close.html`, `templates/base.html`, `templates/base_org.html`
- Test: `apps/common/tests/test_navigation.py`; update `apps/common/tests/test_base_template.py`, `test_responsive.py` where they assert old classes

**Interfaces:**
- Produces:
  - `NavItem(label: str, href: str, icon: str, badge_key: str | None = None)`, `NavGroup(key: str, label: str | None, items: tuple[NavItem, ...])` and `nav_groups_for(*, role: str) -> tuple[NavGroup, ...]` in `apps/common/navigation.py` (group keys: `overview`, `feedback`, `locations`, `workspace`, `platform`, `ai-spend`, `developer`; `badge_key` is `"reviews"` on Reviews and `"action_items"` on Action items).
  - Template tag `{% nav_groups as groups %}` (takes context, reads `request.user.role`).
  - DOM contract for Task 4: sidebar root `#main-sidebar`; each group `<section data-nav-group="<key>">` with a toggle `<button data-nav-group-toggle aria-expanded="true" aria-controls="nav-group-<key>">` and list `<ul id="nav-group-<key>">`; links `nav a[href]` inside; badge slot `<span data-nav-badge="reviews|action_items" hidden>`; meter `<div data-nav-credits hidden>` containing `[data-nav-credits-text]` and `[data-nav-credits-bar]` (inner element whose width is set); `data-nav-summary-url="{% url 'nav-summary' %}"` on `#main-sidebar` only for Org Admin / Staff.

- [ ] **Step 1: Write failing tests** in `apps/common/tests/test_navigation.py`:

```python
def test_org_admin_groups_and_items_in_order(): ...
    # [g.label for g in nav_groups_for(role="ORG_ADMIN")] == [None, "Customer feedback", "Locations", "Workspace"]
    # labels of items == ["Dashboard"], ["Reviews","Action items","Reports"], ["Shops","Regions"], ["Tags","Reply templates","Team","Activity log"]
def test_staff_sees_only_reviews_action_items_activity_log(): ...
def test_superadmin_groups(): ...   # Platform / AI spend / Developer with today's hrefs
def test_rendered_org_admin_sidebar_has_badge_slots_meter_and_summary_url(client): ...
def test_rendered_superadmin_sidebar_has_no_badges_meter_or_summary_url(client): ...
def test_staff_page_never_renders_org_admin_only_links(client): ...   # no /admin/org/shops/, /admin/org/team/ ...
def test_active_item_rendered_as_yellow_pill_with_aria_current(client): ...  # on /admin/org/reviews/
```

- [ ] **Step 2: Run** `uv run pytest apps/common/tests/test_navigation.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** `apps/common/navigation.py` + `nav_groups` tag, then the templates:
  - Shell: outer wrapper `bg-black`; header row black; `<main id="main-content">` keeps its id, `data-page-title`, `tabindex` and `overflow-y-auto`, and becomes the rounded light panel (`bg-bg rounded-[14px]`, inset `mr-2.5 mb-2.5` on ≥md; full-bleed on mobile).
  - Sidebar: logo (existing `dashboard_logo.png` / `mobile_logo.png`), groups via `_nav_group.html` (Alpine `x-data` per group for the toggle; Dashboard group `label=None` renders without heading/toggle), meter at the bottom above the user/log-out block (Org Admin/Staff only).
  - `_nav_item.html`: active = `bg-yellow text-black font-semibold rounded-[9px]` + `aria-current="page"`; inactive = `text-[#D4D4D8] hover:text-white`; badge slot after label.
  - Topbar: black, left `{{ organisation name }} / <strong id="topbar-breadcrumb">` (Superadmin: "Platform"), right bell root, sync root, avatar menu (unchanged behaviour, dark button styles).
  - Rail (md): headings `md:hidden lg:block` with a `md:block lg:hidden` divider; badge `md:` variant = yellow dot.
  - Update the old assertions in `test_base_template.py` / `test_responsive.py` only where they check classes this task intentionally changed.

- [ ] **Step 4: Run** `uv run pytest apps/common apps/accounts apps/organisations -q` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(ui): black frame shell with grouped sidebar and dark header`.

---

### Task 4: Shell behaviour — active pill, fold memory, badges and meter

**Files:**
- Create: `frontend/src/shell/nav.ts`, `frontend/src/shell/nav.test.ts`
- Modify: `frontend/src/entrypoints/app-shell.ts`

**Interfaces:**
- Consumes: Task 3 DOM contract; Task 2 payload.
- Produces (exported from `frontend/src/shell/nav.ts`):
  - `syncActiveItem(sidebar: HTMLElement, path: string): void` — same match rule as today (`path.startsWith(href) && href !== "/"`, plus exact `/` for Dashboard); toggles the pill classes and `aria-current`; opens the group containing the active item.
  - `restoreFolds(sidebar: HTMLElement, storage: Pick<Storage, "getItem" | "setItem"> | null): void` and `rememberFold(groupKey: string, folded: boolean, storage): void` — key `"rb.nav.folded"`, JSON array of group keys; every storage call in try/catch.
  - `formatBadge(n: number): string | null` — `0 → null`, `1..99 → "n"`, `>99 → "99+"`.
  - `renderSummary(sidebar: HTMLElement, summary: NavSummary | null): void` — `null` hides all badges and the meter.
  - `refreshSummary(sidebar: HTMLElement, fetchImpl?: typeof fetch): Promise<void>` — no-op when `data-nav-summary-url` is absent; on non-2xx or throw calls `renderSummary(sidebar, null)`.

- [ ] **Step 1: Write failing tests** in `frontend/src/shell/nav.test.ts`:

```ts
it("marks the matching link active and clears the previous one", ...)          // aria-current moves
it("opens a folded group when navigating into it", ...)                          // Review Focus 1
it("restores folded groups from storage but keeps the active group open", ...)
it("renders the menu expanded when storage throws", ...)                         // Review Focus 5
it("formats badges: 0 hidden, 7, 99, 99+", ...)
it("shows meter text 'X of Y left' with bar width X/Y and hides it when credits is null", ...)
it("hides badges and meter when the fetch fails or returns 403", ...)           // Review Focus 4
it("does not fetch when the sidebar has no summary url (Superadmin)", ...)
```

- [ ] **Step 2: Run** `cd frontend && npx vitest run src/shell/nav.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement `nav.ts`**; meter text exactly `` `${remaining.toLocaleString()} of ${total.toLocaleString()} left` ``, bar width `Math.max(0, Math.min(100, remaining / total * 100))%`. In `app-shell.ts` replace `updateSidebarActiveState` and the old `NAV_ACTIVE`/`NAV_INACTIVE` lists with calls to `syncActiveItem`, `restoreFolds` (on `DOMContentLoaded`) and `refreshSummary` (on `DOMContentLoaded` and `turbo:load`). Fold toggles call `rememberFold` (wire via a delegated `click` on `[data-nav-group-toggle]` or Alpine — one place only).

- [ ] **Step 4: Run** `cd frontend && npx vitest run && npm run build` — Expected: all PASS, build OK.

- [ ] **Step 5: Commit** `feat(ui): sidebar fold memory, active pill and live badges/credits`.

---

### Task 5: Dark header widgets, Superadmin pages and full verification

**Files:**
- Modify: `frontend/src/widgets/notif-bell/NotifBell.tsx` (trigger button styles only), `frontend/src/entrypoints/topbar-sync-indicator.tsx` (trigger styles only), their existing tests if they assert classes; any Superadmin page template (`templates/ai_cost/explorer.html`, `templates/ai_pricing/page.html`, `templates/organisations/*`) that hard-codes its own white page header or background that clashes with the panel.
- Modify: `.planning/REQUIREMENTS.md` (UI-NAV-01..03 → `✅ Delivered`)

- [ ] **Step 1:** Restyle the bell and sync-indicator triggers for the black header (icon `text-[#D4D4D8] hover:text-white`, hover `bg-white/10`, focus ring yellow); dropdown panels stay white. Run `cd frontend && npx vitest run src/widgets/notif-bell` — Expected: PASS.
- [ ] **Step 2:** Open each page in the browser (`docker compose restart web`, rebuild frontend) as Superadmin (Dashboard, Organisations, AI cost, AI pricing), Org Admin (all 10 pages) and Staff (3 pages) at 1440px, 900px and 390px widths. Check: frame and rounded panel, pill on the right item after clicking around, folds remembered, badges and meter numbers match the Reviews "Awaiting reply" card / Action items list / shop credits, keyboard Tab reaches group toggles and links with a visible focus ring, mobile drawer opens/closes. Fix only shell/template issues found.
- [ ] **Step 3:** Run full checks: `uv run pre-commit run --all-files`, `uv run pytest -q`, `uv run python manage.py makemigrations --check --dry-run`, `cd frontend && npx vitest run && npm run build` — Expected: all pass, no migrations.
- [ ] **Step 4:** Mark UI-NAV-01..03 `✅ Delivered`; commit `feat(ui): dark header widgets and superadmin pages in the black frame`.
