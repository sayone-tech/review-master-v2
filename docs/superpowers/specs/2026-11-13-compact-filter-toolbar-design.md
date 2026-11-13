# Compact filter toolbar (Reviews, Action items, Reports) — design

**Date:** 2026-11-13
**Status:** draft for owner review
**Chosen direction:** option A from the brainstorm mockups ("one toolbar, slim numbers").
Mockups: `.superpowers/brainstorm/7608-1794569358/content/reviews-compact.html` (option A) and
`.../toolbar-all-pages.html` (all three pages) — local, not committed.

## 1. Intent

On the Reviews page the 8 filters (two rows, each with an all-caps label) plus 4 tall stat cards fill about half the
screen before the first review. Action items has the same two-row filter card, and Reports a tall one-row card.
The owner wants the list to start near the top, with the same compact pattern on all three pages.

Success: on a 1440×900 screen the first Reviews row starts within roughly the top quarter of the page panel; every
filter and every number available today is still reachable; the three pages look and behave the same way.

## 2. Goals

1. **One toolbar row** per page, built from a shared React toolbar (one implementation used by all three widgets):
   - **Reviews:** Search (grows to fill) · Store · Rating · Sentiment · "More filters" button.
     More filters panel: Tags, Date range, Reply, Comment.
   - **Action items:** Search · Store · Status · Assignee · "More filters".
     More filters panel: Scope (only where it is shown today — Staff never see Scope), Category, Date range.
     Staff get the same row and a panel with Category and Date range; any control hidden from Staff today stays hidden.
   - **Reports:** Period · Reply · Sentiment, and the existing sort links on the same row (right-aligned). No "More
     filters" button (only three filters). Choosing the custom period shows the existing from/to date inputs inline
     in the row. The sort state moves from `ReportsTable` up to `ReportsWidget` and is passed down as props, so the
     sort links can sit in the toolbar row; the table's rendering and sort behaviour are unchanged.
2. **Controls:** 34px-high white pills with an icon, the current value as the label, and a chevron (no separate field
   label above). The "More filters" button is black with white text and a yellow count badge = number of active
   filters inside the panel (badge hidden at 0).
3. **Applying (decided by me, owner delegated):**
   - Main-row dropdowns apply immediately on change.
   - Search applies as you type using the pages' existing 300 ms debounce (reuse `useReviews` / `useActionItems`), immediately on Enter; clearing the box applies immediately.
   - The More filters panel edits a draft and has **Reset** (clears only the panel's filters, applies) and **Apply**
     (applies and closes). Closing the panel without Apply (Escape, click outside) discards the draft.
   - The yellow page-level Apply button goes away on all three pages.
   - The panel's draft is re-synced from the applied filters every time the panel opens, so filters changed from
     elsewhere (e.g. clicking a tag chip on a review row) are reflected. Chips and the badge always show applied
     filters, never the draft.
   - **Reports custom period:** the from/to inputs apply only once both dates are set and valid (from ≤ to, at most
     365 days); a partial or invalid range sends no request and shows today's inline error message.
4. **Active filter chips** under the toolbar for every non-default filter that is NOT visible in the main row
   (i.e. the More filters ones; e.g. "Not replied", "Category: Service", "Tags: Cleanliness"). Each chip has an × that
   removes that filter immediately. A "Clear all" link resets every filter on the page (main row + panel + search).
   The chip row is not rendered when there are no such filters. "Clear all" resets to the page's own defaults (what
   the page loads with). Date range shows as one chip: "Date: 1 Nov – 13 Nov", "From 1 Nov" or "Until 13 Nov"; its ×
   clears both dates. Tags show one chip per selected tag.
   **Reports** has no panel and so no chips; instead a "Reset" link appears at the end of its row whenever Period,
   Reply or Sentiment differs from the defaults (last 30 days, all replies, any sentiment) and restores them.
5. **Reviews numbers** become one slim white bar under the toolbar/chips: "128 reviews | 4.3 avg rating |
   17 awaiting reply | 67% positive" (separators are thin vertical rules, not characters), same data and the same
   filter-dependence as today's cards; awaiting reply in amber, positive in green (current card colours).
   Action items and Reports get no number bar (they have no cards today).
6. **Panel:** white, 12px radius, shadow, ~300–330px wide, anchored under the "More filters" button, right-aligned;
   fields stacked with a small sentence-case label each; keyboard: opens with Enter/Space, focus moves into the panel,
   Escape closes and returns focus to the button, Tab stays usable. Nested dropdowns inside the panel (the Reviews tag
   multi-select) stay nested lists at full panel width: Escape closes the innermost open list first, and clicks inside
   a nested list never count as "outside" the panel.
7. Behaviour that must not change: which filters exist, their options and API parameters, URL/query persistence of
   filters if a page has it today, pagination reset to page 1 when a filter changes, the Reviews tags multi-select
   with its search, Staff scoping, and every existing sort.

## 3. Non-goals

- New filters, saved filter sets, new stats or charts.
- Changing how the review/action-item/report tables look or sort (Reports' sort state may move up a level, §2.1).
- Other pages (Shops, Regions, Team, etc. already use the compact search row).

## 4. Anti-goals

- A filter that becomes unreachable, or a filter that silently stops being sent to the API.
- Firing a request on every keystroke (search must be debounced) or double requests on one change.
- A layout that wraps into two messy rows at 1280px wide; below ~1024px the row may wrap, and on phones the
  controls stack — but nothing overflows horizontally.

## 5. Constraints

- React widgets under `frontend/src/widgets/` (Vite islands), Tailwind v4 tokens, Lucide icons, Geist (CLAUDE.md §26/§27).
- Requirements first (CLAUDE.md §24): add `UI-FILTER-01` (shared compact toolbar on Reviews, Action items, Reports)
  and `UI-FILTER-02` (Reviews slim number bar) to `.planning/REQUIREMENTS.md`.
- Vitest coverage for the shared toolbar (instant apply, debounce, panel draft/apply/reset/discard, chips, Clear all,
  badge count, keyboard) and updated widget tests (filters still reach the API with the same params).

## 6. Decided by me (owner can override)

- Instant apply + debounced search; panel keeps Apply (see §2.3).
- Which filters sit in the main row per page (§2.1) — the most-used ones, matching the approved mockup.
- Chips only for panel filters (main-row filters already show their value in the row).
- Reports keeps Period/Reply/Sentiment in the row and moves the sort links onto it.

## 7. Left to the builder

- Exact component split (e.g. `FilterToolbar`, `FilterSelect`, `MoreFiltersPanel`, `FilterChips` under
  `frontend/src/components/filters/` or similar) and how each widget maps its filter state onto it.
- Exact spacing within the mockup's look.
