# Sidebar and header redesign ("black frame") — design

**Date:** 2026-11-13
**Status:** draft for owner review
**Chosen direction:** option C from the brainstorm mockups ("black frame with the page set inside").
Mockup: `.superpowers/brainstorm/7608-1794569358/content/sidebar-directions.html` (local, not committed).

## 1. Intent

The Organisation Admin sidebar is one flat "Manage" list of ten links, and the top bar only carries
the page title, sync indicator, bell and avatar. The owner wants a modern, grouped navigation in the
same black + yellow brand, so the team can find things faster and see at a glance what needs
attention (unreplied reviews, open action items) and how many AI reply credits are left.

Success: every role sees a grouped menu inside one black frame; the page content sits inside it
on a rounded light panel; badges and the credits meter are correct for exactly the shops the
person can see.

## 2. Goals

1. **One black frame.** Sidebar and header form a single black L shape (`#0A0A0A`). Every app page
   renders inside it on a light (`#FAFAFA`) panel with rounded corners (about 14px), inset from
   the frame on the right and bottom (about 10px).
2. **Grouped menu, per role** (labels in sentence case, not all caps):
   - **Organisation Admin:** Dashboard (ungrouped, top) · *Customer feedback*: Reviews, Action
     items, Reports · *Locations*: Shops, Regions · *Workspace*: Tags, Reply templates, Team,
     Activity log.
   - **Staff:** Dashboard (ungrouped) · *Customer feedback*: Reviews, Action items, Activity log.
     (Staff cannot see Reports, Shops, Regions, Tags, Reply templates or Team today; that does not
     change.)
   - **Superadmin:** *Platform*: Dashboard, Organisations · *AI spend*: AI cost, AI pricing ·
     *Developer*: Django admin, API docs (links kept, unchanged destinations).
   - Same URLs and the same role gating as today (`templates/partials/sidebar.html`,
     `sidebar_org.html`). No page is added or removed.
3. **Foldable groups.** Each group heading toggles its items (chevron down/right). The browser
   remembers folded groups per user in `localStorage` (wrapped in try/catch; works without it).
   The group containing the current page is always shown open.
4. **Active page** = solid yellow pill (`#FACC15`) with black text and icon, about 9px radius.
   Inactive items: light grey text, hover to white. This must keep working with Turbo navigation
   (the sidebar is `data-turbo-permanent`; today `frontend/src/entrypoints/app-shell.ts`
   swaps classes on navigation — update its class lists to the new styles).
5. **Header (black, part of the frame):** left — organisation name / current page title
   (Superadmin: "Platform" / page title), keeping the existing `#topbar-breadcrumb` behaviour.
   Right — existing sync indicator, notification bell and avatar menu (Profile, Log out),
   restyled for a dark background. Mobile hamburger stays.
6. **Badges** (Organisation Admin and Staff only):
   - *Reviews*: reviews awaiting a reply — reuse the Reviews page queryset
     (`base_reviews_queryset`, which already hides deleted reviews and inactive shops, plus the
     Staff `get_accessible_shop_ids` filter, as `ReviewViewSet.get_queryset` does) and count
     `is_replied=False`, all time. This equals the Reviews page "Awaiting reply" card with no filters.
   - *Action items*: open items — reuse `list_action_items(organisation_id=…, user=…)` with its
     defaults (Org Admin: every item in the organisation, brand items included; Staff: shop items in
     their scope only; merged duplicates hidden) and count status `TODO` or `IN_PROGRESS`. The badge
     must equal what the Action items page lists as open, so it is not additionally shop-filtered.
   - Hidden when 0; shown as `99+` above 99.
7. **AI-credits meter** at the bottom of the sidebar (Organisation Admin and Staff only):
   "AI reply credits this month" · "**X of Y left**" · a yellow progress bar (X / Y).
   - Y = sum over the person's shops of this month's allocated + bonus credits.
   - X = sum over the same shops of remaining credits.
   - Uses the existing virtual-balance rules (`apps/credits/selectors/balances.py`): a shop with
     no balance row this month counts the organisation's live monthly allocation.
   - Hidden when Y is 0 (credits not enabled for the organisation).
   - Not clickable in this version.
8. **Superadmin pages** (Dashboard, Organisations, AI cost, AI pricing, API docs shell) use the same
   frame and menu. No badges, no credits meter.

## 3. Non-goals

- Django admin (`/django-admin/`) styling — explicitly excluded by the owner.
- Login / auth pages, emails, page content inside the panel.
- Global search, "Sync now" button, live-updating counts (WebSocket — CLAUDE.md §13.2 forbids
  new real-time surfaces without sign-off).
- Making the credits meter clickable or adding a credits page.

## 4. "The person's shops" (scoping — authoritative)

| Role | Shops counted |
|---|---|
| Organisation Admin | all **active** shops of their organisation |
| Staff | **active** shops in their `StaffAccessScope` (shop- and region-scoped entries; reuse `get_accessible_shop_ids`) |
| Superadmin | none (no badges, no meter) |

This table governs the **credits meter** and the **Reviews badge**. Inactive shops are excluded,
consistent with CRED-INACTIVE-01 (their reviews are hidden and they get no credits).
`get_accessible_shop_ids` does not filter `is_active` (region scopes include inactive shops), so the
credits selector adds `is_active=True` on top of it; the Reviews badge gets this for free from
`base_reviews_queryset`. The **Action items badge** follows the Action items page instead (§2.6).
Every query filters by the caller's `organisation_id` (CLAUDE.md §9/§22).

A person with no shops (or Staff with no access scope) gets zero counts (badges hidden) and
`credits: null` (meter hidden).

## 5. Anti-goals (would be a failure even if it "works")

- A badge or meter number that includes a shop the person cannot see, an inactive shop, another
  organisation's data, or (for Staff) brand-scoped action items.
- Counts that are N+1 or grow with the number of shops/reviews in query count (CLAUDE.md §6).
- Breaking Turbo navigation: active highlight or folded groups going wrong after clicking around.
- Losing keyboard access: groups and menu items must be reachable and operable by keyboard, with
  visible focus and correct `aria-expanded` / `aria-current`.

## 6. Constraints

- Django templates + Tailwind v4 tokens (`frontend/src/styles/tailwind.css`), Alpine.js for the
  fold/toggle, Lucide icons, Geist font — as today. Brand: `--color-yellow #FACC15`,
  `--color-black #0A0A0A`.
- Requirements-first (CLAUDE.md §24): add REQ rows to `.planning/REQUIREMENTS.md` before building.
- New read-side code goes in selectors (CLAUDE.md §5); any new endpoint is thin, has explicit
  permissions, throttling, a query-count test and OpenAPI schema entry (§8, §24).
- Responsive behaviour stays as today: full sidebar (240px) on large screens, icon rail (64px) on
  medium, slide-out drawer on mobile.

## 7. Decided by me (owner can override)

- **Counts delivery:** because the sidebar persists across Turbo navigations, server-rendering the
  numbers into it would go stale. Proposed: one small read endpoint
  `GET /api/v1/me/nav-summary/` returning `{reviews_awaiting_reply, open_action_items,
  credits: {remaining, total} | null}`, fetched by `app-shell.ts` on first load and on each
  `turbo:load`. Org Admin / Staff only (403 for Superadmin); scoped per §4; fixed query count
  (target ≤ 5); throttled. No caching in v1 — add a short per-user cache only if the
  query-count/latency test shows a need. `app-shell.ts` does not call it for Superadmin (the
  sidebar markup for Superadmin has no badge/meter slots). If the fetch fails, badges and meter
  are hidden (no stale numbers, no error shown).
- **Action items badge matches the Action items page**, not the active-shop rule: the page today
  still lists open items of inactive shops (and Org Admin brand items), and a badge that disagrees
  with the page it links to would be confusing. Hiding inactive-shop action items everywhere is a
  separate follow-up if wanted.
- **Icon rail (medium screens):** group headings become thin dividers; badges become a small
  yellow dot on the icon; the credits meter is hidden.
- **Header on Superadmin:** the "organisation name" slot shows "Platform".
- Group names: *Customer feedback*, *Locations*, *Workspace*, *Platform*, *AI spend*, *Developer*.
- Group icons are not added; groups are text headings only (rail uses dividers).

## 8. Left to the builder

- Exact spacing, font sizes and transitions within the mockup's look.
- How the dark restyle of the React bell / sync indicator is done (props vs. CSS variant), as long
  as their behaviour is unchanged.
- Whether `sidebar.html` and `sidebar_org.html` are merged into one template with per-role menu
  definitions (encouraged if it makes the change smaller).

## 9. Testing expectations

- Template/view tests: each role renders exactly its groups and items (and Staff never sees Org
  Admin–only links).
- Endpoint/selector tests: Org Admin vs Staff scoping, inactive shops excluded, cross-organisation
  isolation, Staff excludes `BRAND` action items, meter hidden (null) when total is 0,
  virtual-balance shops counted, Superadmin 403, fixed query count independent of shop count.
- Vitest for `app-shell.ts`: active pill swaps on navigation; fold state restored; counts render,
  `99+` cap, hidden at 0.
- Manual check in the browser for all three roles at desktop, tablet and phone widths.
