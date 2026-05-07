# Feature Research

**Domain:** Analytics dashboard UI — Organisation Admin Dashboard (v0.4 milestone)
**Researched:** 2026-05-07
**Confidence:** HIGH (UX patterns well-established; implementation choices verified against existing codebase constraints)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features analytics dashboard users assume exist. Missing these = product feels broken or unfinished.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Filter bar persists state in URL | Every analytics tool (GA4, Looker, Metabase) does this; users share and bookmark filtered views | MEDIUM | Use `history.replaceState` + `URLSearchParams` — no router needed since page is Django-rendered with a React island. `replaceState` (not `pushState`) avoids cluttering browser history. Read params on mount to hydrate initial state. |
| Cascading Region → Store dropdown | If a Region is selected, the Store list must narrow to that region instantly — any other behavior confuses users | MEDIUM | On Region change: clear Store selection, re-populate Store options (filter client-side if already loaded, or re-fetch). Disable Store dropdown while Region is loading. Default to "All Stores". |
| Date range presets (7d / 30d / 90d) | Standard in every analytics product; users expect quick shortcuts | LOW | Render as a pill/tab group, not a dropdown. Active preset highlighted. Custom range reveals date pickers. Default to 30d on first load. |
| Custom date range with date pickers | Presets cover 80% of use; power users need arbitrary ranges | MEDIUM | Show two calendar inputs (from / to). Validate: `from <= to`, neither in future, max range <= 365d. On mobile use native `<input type="date">`; on desktop show a popover calendar. |
| Clear Filters button | Users need a fast reset escape hatch; manually resetting each filter is tedious | LOW | Disabled (not hidden) when all filters are at defaults. One click: Region → All, Store → All, Date → 30d default. Clears URL params simultaneously. |
| KPI skeleton loading | Users expect the page skeleton immediately; a blank white card box feels broken | LOW | Each KPI card renders its own skeleton rectangle matching the card dimensions. Skeleton pulses with a shimmer animation. Cards load independently — do not block the whole page on a single slow endpoint. |
| Independent per-card error states | If one API call fails, remaining cards must still show data | MEDIUM | Each widget (KPI row, bar chart, donut, highlights card) fetches from its endpoint independently. Error state shows a minimal inline message + Retry button within the card boundary. No full-page error overlay. |
| Bar chart tooltip on hover | Every charting product shows a tooltip on hover; omitting it feels incomplete | LOW | Show: store name, average rating (1 decimal), review count. Tooltip must not clip at viewport edges — position it inside the chart container. |
| Donut chart tooltip on hover | Users hover segments to read exact percentages | LOW | Show: sentiment label (Positive / Neutral / Negative), count, percentage (1 decimal). Tooltip positioned near cursor without clipping. |
| Average Rating half-star display | Users expect a visual star representation for ratings, not just a number | LOW | Use SVG half-star clip approach. `aria-label="4.2 out of 5 stars"` on the container. Display-only (not interactive). |
| Responsive layout | Dashboard is accessed on laptop and tablet; layout must not break at 768px | MEDIUM | KPI cards: 3-col on desktop → 1-col stack on mobile. Charts: `<ResponsiveContainer width="100%">` — never fixed pixel widths. Filter bar: wraps to two rows on tablet. |
| Coverage footer on Sentiment donut | AI enrichment is not 100% complete; users need to know what share of reviews the donut represents | LOW | Footer text: "Based on X of Y reviews (Z% enriched)". Grey italic text below the chart. If coverage < 20%, show a yellow warning callout: "Limited data — sentiment may not be representative." |
| Empty state for no data | Filters may legitimately return zero reviews; charts must not render broken or empty | LOW | Each widget has a distinct empty state message. Bar chart: "No review data for this period." Donut: "Sentiment data will appear once AI processing completes." KPIs: show 0 / — with no error. |
| Trend indicator vs previous period | Users need directional context — a number without trend is incomplete | LOW | Arrow up (green) / arrow down (red) / dash (neutral, <1% change). Always show: "+12% vs previous period" label. Previous period = same duration ending at the `from` date. Used in "Your Store" variant and on KPI cards. |
| "Your Store" single-shop variant | Staff Admin (or Org Admin with one store) should see a personalised view — multi-shop rankings reveal no context for a single-store user | MEDIUM | Detect: if exactly 1 store in scope, render "Your Store" card instead of bar chart + highlights. Show: KPIs + mini rating-distribution bars + trend vs previous period. Bar chart and Performance Highlights card are hidden. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Threshold-based bar coloring (≥4.0 green, 3.0–3.99 amber, <3.0 red) | Instant visual triage — managers see problem stores without reading numbers | LOW | Recharts `Cell` component maps per-bar fill via a `getBarColor(rating)` function. Color constants from the Tailwind palette: `#16a34a` (green-600), `#d97706` (amber-600), `#dc2626` (red-600). Consistent with existing design system. |
| Performance Highlights card (top + bottom) | Executives want the answer surfaced, not just a chart to interpret | LOW | Two sub-cards: top performer (green tint, trophy icon) + bottom performer (red tint, warning icon). Each shows: store name, avg rating, review count. Clicking either navigates to the Reviews page filtered to that store. |
| Bar chart click → Reviews page navigation | Bridges from insight to action — users can immediately investigate a problem store | LOW | `onClick` on the bar: navigate to `/reviews/?store_id={storeId}&range={currentDateRange}`. Cursor changes to pointer on bar hover. |
| Redis-cached API responses (5-min TTL) | Dashboard data is expensive to compute; caching prevents DB overload under concurrent use | MEDIUM | Cache key: `dashboard:{org_id}:{endpoint}:{params_hash}`. Explicit invalidation on new review sync completion (via Celery task post-hook). 5-min TTL is the fallback — explicit invalidation is the primary path. |
| Session persistence of filter state | Users return to the same filters they left — reduces repetitive reconfiguration | LOW | On filter change, write params to `sessionStorage` keyed by `org_id`. On mount: URL params → sessionStorage fallback → hardcoded defaults. URL params always win so shared links override session. |
| Rating distribution mini-bars ("Your Store") | Shows how reviews are distributed across 1–5 stars — more informative than a single average | LOW | 5 horizontal bars, each proportionally width-filled. Star labels on left, count on right. No extra endpoint needed if included in the store KPI response. |

### Anti-Features (Commonly Requested, Often Problematic)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| WebSocket live-updating dashboard | Feels modern; "real-time data" sounds impressive | Channels scope must stay narrow (CLAUDE.md §13.2); adding a dashboard consumer requires architecture review sign-off and adds significant complexity for marginal value — review sync runs every 6 hours, not continuously | HTTP fetch on mount. Dashboard data is not time-critical. A manual Refresh button is sufficient if users request it. |
| Global error boundary replacing all widgets | Simplest error handling to implement | Hides which widget failed; users lose all data when one endpoint fails; violates table-stakes independent error state requirement | Per-widget error boundaries with inline Retry. Each widget is independent. |
| Date range beyond 365 days | Power users will ask for it | Large ranges generate expensive queries even with indexes; Redis TTL cache does not help; P95 < 400ms constraint becomes hard to hold | Cap at 365d with a clear validation message. Offer CSV export (future phase) for longer-range analysis. |
| Animated chart transitions on every filter change | Looks polished | Animations during data reload create a jarring flash as old data animates out and new data animates in — noticeably worse UX than no animation | Animate only on initial mount (gate `isAnimationActive` on a `hasLoaded` flag). Disable animation on filter-change re-fetches. |
| Inline "compare to previous period" toggle on bar chart | Useful for trend analysis | Doubles API calls; significantly complicates filter state machine | Trend arrow on "Your Store" KPI cards covers 90% of the use case. Keep bar chart clean. |
| Filterable / sortable table inside the dashboard | Some users want to drill into outlet data inline | The Reviews page already has a full-featured table with filters. Duplicating it here creates a maintenance burden and confuses the purpose of each page | Bar chart provides visual ranking; clicking a bar navigates to the Reviews page for detailed table interaction. |
| Custom color theme per org | Brand consistency is a real ask | Adds significant styling complexity with no clear revenue justification at this stage | Fixed brand palette: Yellow #FACC15, Black #0A0A0A, Tailwind semantic colors for status. |

---

## Feature Dependencies

```
Filter Bar (Region + Store + Date Range)
    └──feeds──> All 5 dashboard API endpoints (passed as query params)
    └──requires──> Region list API  (existing Regions app — already built)
    └──requires──> Store list API   (existing Stores app, filtered by region — already built)
    └──owns──>  Shared filter context (React Context or page-root prop-drill)

KPI Card Row (Total Reviews, Average Rating, Negative Reviews)
    └──requires──> Filter Bar (provides date range + store scope)
    └──requires──> Review model (v0.3, already exists)
    └──requires──> enrichment_status / sentiment field on Review (v0.3, already exists)
    └──renders──>  Half-Star Rating Display (sub-component, no dependency)

Sentiment Distribution Donut
    └──requires──> AI enrichment pipeline (v0.3, already exists)
    └──requires──> Filter Bar
    └──requires──> Coverage footer logic (enriched_count / total_count from same endpoint)
    └──shows-empty-state-when──> enriched_count === 0

Best Performing Outlets Bar Chart
    └──requires──> Filter Bar (date range only — Store filter collapses to "Your Store" variant)
    └──requires──> 2+ stores in scope (single store → "Your Store" variant instead)
    └──same-endpoint-as──> Performance Highlights Card (top/bottom derived from same response)

Performance Highlights Card
    └──requires──> Best Performing Outlets data (same endpoint, derived values)
    └──enhances──> Bar Chart (surfaces top/bottom without requiring chart interpretation)
    └──hidden-when──> "Your Store" variant is active

"Your Store" Single-Shop Variant
    └──requires──> KPI data for the current store
    └──requires──> Rating distribution (1–5 star counts) for current store
    └──requires──> Trend calculation (previous period, same endpoint or derived)
    └──conflicts──> Bar Chart + Performance Highlights (render one OR the other, never both)
    └──active-when──> exactly 1 store in scope (Staff single-scope or single-shop org)

Redis TTL Cache
    └──requires──> apps/dashboard/ endpoints exist
    └──enhanced-by──> Cache invalidation hook in Celery review sync task (v0.3 infra — already exists)
```

### Dependency Notes

- **Filter Bar is the shared state owner.** All widgets on the page consume from a single filter context (React Context at the page root or explicit prop-drill). Do not let each widget independently manage its own filter state.
- **Bar chart requires 2+ stores.** If filters narrow to 1 store, switch to "Your Store" variant client-side. The same API endpoint can serve both paths — the frontend decides which component to render based on `stores.length`.
- **Sentiment donut requires enrichment data.** If `enriched_count === 0`, render a specific empty state rather than an empty chart. Do not render a donut with zero data points.
- **"Your Store" variant conflicts with multi-store components.** Never render both the bar chart and the "Your Store" card simultaneously. The single-store detection is the branch condition.

---

## MVP Definition

### Launch With (v0.4)

All items below are required for the milestone — none are optional.

- [ ] Filter bar — Region, Store, Date Range (presets + custom date pickers), Clear Filters — URL state via `history.replaceState` + `sessionStorage` fallback
- [ ] KPI card row — Total Reviews, Average Rating (with half-star display), Negative Reviews (AI sentiment-based) — with skeleton loading and independent per-card error states
- [ ] Best Performing Outlets bar chart — threshold coloring (green / amber / red), hover tooltip, click-to-reviews navigation
- [ ] Performance Highlights card — top + bottom performer sub-cards (multi-store path only)
- [ ] "Your Store" card — KPIs + rating distribution mini-bars + trend indicator (single-store path, mutually exclusive with bar chart)
- [ ] Sentiment Distribution donut — 3 segments (Positive / Neutral / Negative), hover tooltips, legend, coverage footer, enrichment-aware empty state
- [ ] `apps/dashboard/` Django app with 5 focused API endpoints + Redis 5-min TTL caching
- [ ] 3 new indexes on the Review table covering dashboard query shapes
- [ ] `CaptureQueriesContext` tests asserting fixed query count ceiling on all 5 endpoints

### Add After Validation (v1.x)

- [ ] Manual Refresh button on dashboard — if user research shows staleness complaints
- [ ] Export to CSV — when users need historical analysis beyond the 365d cap
- [ ] Weekly email digest — after engagement data shows Org Admins want async reporting

### Future Consideration (v2+)

- [ ] Real-time dashboard via WebSocket — only after explicit Channels scope review and evidence that 6-hour sync staleness causes churn
- [ ] Compare-to-previous-period toggle on bar chart — after validating trend arrow on "Your Store" KPI cards is insufficient for multi-store users
- [ ] AI-powered anomaly callout ("Store X rating dropped 0.8 stars this week")

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Filter bar with URL state | HIGH | MEDIUM | P1 |
| KPI cards with skeletons + error states | HIGH | MEDIUM | P1 |
| Bar chart with threshold coloring | HIGH | MEDIUM | P1 |
| "Your Store" single-shop variant | HIGH | MEDIUM | P1 |
| Sentiment donut with coverage footer | HIGH | MEDIUM | P1 |
| Performance Highlights card | MEDIUM | LOW | P1 |
| Half-star rating display | MEDIUM | LOW | P1 |
| Trend indicator ("Your Store") | MEDIUM | LOW | P1 |
| Bar chart click → Reviews navigation | MEDIUM | LOW | P1 |
| Redis TTL caching + invalidation | HIGH | MEDIUM | P1 |
| Session persistence of filters | LOW | LOW | P2 |
| Manual Refresh button | LOW | LOW | P2 |

**Priority key:**
- P1: Required for v0.4 launch
- P2: Add in same phase if time permits, low risk
- P3: Nice to have, defer to v1.x

---

## UX Behavior Reference (Per Component)

### 1. Cascading Filter Dropdowns + URL State

**Expected behaviors (table-stakes):**

- Region dropdown: "All Regions" as default option. On Region change → clear Store selection → re-populate Store options. Disable Store dropdown with a spinner while Region options are loading.
- Store dropdown: disabled if no regions have loaded yet. "All Stores" is default within the selected region. If Region = "All", Store dropdown shows all stores across the org.
- Selecting a Store auto-sets Region to that store's parent region if Region was "All" (optional but polished behavior — avoids an inconsistent state where Store is filtered but Region shows "All").
- Date presets: pill/tab group, one active at a time. Clicking the active preset does nothing (no re-fetch). Selecting "Custom" reveals two date inputs; selecting a preset hides them.
- On any filter change: call `history.replaceState(null, '', '?' + params.toString())` immediately (not debounced). Also write to `sessionStorage`.
- On mount: read `window.location.search` → parse with `URLSearchParams` → hydrate filter state. Validate: if a store ID is not in the org's store list, silently ignore it (prevents tampered or stale URLs leaking cross-tenant state at the UI layer; the API enforces the real check with a 403).
- 403 from API (out-of-scope store): reset Store filter to "All Stores" + display an inline toast: "Selected store is not accessible."
- Clear Filters: disabled (greyed, cursor: not-allowed) when all filters are at their defaults (All Regions, All Stores, 30d preset). Enabled as soon as any filter deviates from the default. One click restores all defaults and clears URL params.
- The URL must be shareable: another Org Admin from the same organisation opening the link sees the same filtered view.

**Implementation approach (confidence: HIGH):**
Use `URLSearchParams` + `history.replaceState` directly — no routing library needed since this is a React island mounted in a Django template page. `replaceState` over `pushState` avoids polluting browser history with every filter change. Read from `window.location.search` on component mount; fall back to `sessionStorage` if no URL params present.

### 2. Bar Chart — Threshold-Based Coloring

**Expected behaviors (table-stakes):**

- Vertical bars. X-axis: store names (truncate to ~20 chars; full name in a tooltip on label hover). Y-axis: average rating, domain fixed at [0, 5].
- Color logic: `rating >= 4.0` → green `#16a34a`, `3.0 <= rating < 4.0` → amber `#d97706`, `rating < 3.0` → red `#dc2626`. Applied per-bar using the Recharts `<Cell>` component inside `<Bar>`.
- Horizontal reference line at y=4.0: dashed, grey, labelled "Target" — makes the green/amber threshold visible without explanation.
- Bars sorted descending by `avg_rating` so best performers appear on the left.
- Tooltip on hover: store name + avg rating (1 decimal) + review count for the period. Custom `<Tooltip content={<CustomTooltip />}>`.
- Bar click: navigate to `/reviews/?store_id={storeId}&range={currentDateRange}`. Change cursor to `pointer` on bar hover using `cursor: "pointer"` on the BarChart component.
- `<ResponsiveContainer width="100%" height={300}>` — never a fixed pixel width.
- Animation: `isAnimationActive={hasInitiallyLoaded}` — animate once on first mount; skip animation on filter-driven re-fetches.
- Empty state (no reviews in date range): replace chart with "No review data for this period." centered placeholder text.
- Only rendered when 2+ stores are in scope. At exactly 1 store: switch the entire section to "Your Store" variant.

**Implementation: Recharts over Nivo for this project.**
Rationale: Recharts has a smaller initial bundle (~150kB vs Nivo's 500kB+ for a full install). This matters in a React-island pattern where the chart bundle is loaded on a Django-rendered page. Recharts per-bar `Cell` coloring is well-documented and confirmed working. Recharts is already likely in the project's frontend dependencies from prior phases (verify in `frontend/package.json`). If not present, add `recharts` — do not add Nivo.

### 3. KPI Cards — Skeleton Loading + Independent Error States

**Expected behaviors (table-stakes):**

- 3 cards in a row: Total Reviews, Average Rating, Negative Reviews.
- Single `/api/v1/dashboard/kpis/` endpoint returns all three metrics. The React component handles loading/error state independently per card field using the single response.
- Skeleton state (`isLoading === true`): grey pulsing shimmer rectangle fills the number area of each card (approximately 40px tall, full card width minus padding). Skeleton is not a spinner — it mimics the layout of the real content.
- On filter change: immediately replace current data with skeleton — do not show stale numbers while re-fetching.
- Error state: replace the metric number with "—" + a small "Failed to load" label + a "Retry" link that re-triggers the fetch. Error is contained within the card; other cards are unaffected.
- Success: show the metric number. On first load only, animate a brief count-up from 0 (optional, low-cost differentiator). Skip animation on filter-change re-fetches.
- Total Reviews card: integer, large font.
- Average Rating card: numeric value (e.g. "4.2") + half-star visual below the number.
- Negative Reviews card: integer with a red accent on the number. An `(i)` tooltip icon beside the label: "Based on AI sentiment analysis of enriched reviews." Uses `review.sentiment === 'negative'` count, not star rating.

**Implementation note:** If the KPI endpoint returns partial data (e.g., enrichment count unavailable due to a DB error), Negative Reviews shows its error state independently while Total Reviews and Average Rating display correctly. Model this as three `status` fields derived from a single fetch, not three separate fetches.

### 4. Donut Chart — Percentage Tooltips + Coverage Footer

**Expected behaviors (table-stakes):**

- 3 segments: Positive (green `#16a34a`), Neutral (grey `#6b7280`), Negative (red `#dc2626`). Order: Positive → Neutral → Negative (clockwise from top).
- Hollow donut: Recharts `<Pie innerRadius="60%" outerRadius="80%">`.
- No labels on the segments themselves — the legend handles labeling.
- Center of donut: largest segment's label + its percentage as static text (e.g., "Positive 72%"). Rendered as an SVG `<text>` element at `cx, cy`.
- Tooltip on hover: `{Label}: {count} reviews ({percentage}%)`. Percentage formatted to 1 decimal. Custom tooltip component.
- Legend: 3 rows below (or to the right of) the donut. Each row: colored circle swatch + sentiment label + count + percentage. Order matches segment order.
- Zero-value segments: do not render the segment (a 0% sliver creates visual noise). Show the legend row with "0%" and a greyed swatch.
- Coverage footer: `"Based on {enriched_count} of {total_count} reviews ({pct}% enriched)"`. Grey italic `<p>` below the chart.
- Warning callout: if `enriched_count / total_count < 0.20` (less than 20% enriched), show a yellow callout above the chart: "Limited enrichment data — sentiment distribution may not be representative."
- Empty state (enriched_count === 0): do not render the donut. Show placeholder: "Sentiment data will appear once AI processing completes." No broken empty chart.
- Accessibility: `role="img"` with `<title>` on the SVG container. `aria-label="Sentiment distribution: 72% positive, 18% neutral, 10% negative"` updated from data.

### 5. Half-Star Rating Display

**Expected behaviors (table-stakes):**

- Display-only. Not interactive (no click, hover, or focus states beyond the container `aria-label`).
- Supports: full star (fully filled), half star (left 50% filled via `<clipPath>`), empty star (outline only).
- Rounding: `Math.floor(rating)` full stars; if `(rating % 1) >= 0.5`, add one half star; fill remaining positions with empty stars to total 5.
  - 4.2 → 4 full + 0 half + 1 empty (fractional part 0.2 < 0.5)
  - 4.5 → 4 full + 1 half + 0 empty
  - 4.7 → 4 full + 1 half + 0 empty (fractional part 0.7 >= 0.5)
- SVG implementation: each of 5 stars is an SVG path. For the half-star position, render the filled star SVG clipped to 50% width using an inline `<clipPath>`. Empty star uses `fill="none" stroke="#FACC15"`.
- Color: `#FACC15` (brand primary yellow — consistent with the existing design system).
- Wrapper: `<span role="img" aria-label="4.2 out of 5 stars">`. Individual SVG stars are `aria-hidden="true"`.
- Size: 16px star icons in a 24px line-height in the KPI card context. Can be made a size-prop for reuse.
- Do not use emoji stars (`★`) — inaccessible, rendering inconsistent across platforms.
- Do not pull in a third-party star-rating library for a display-only component — implement with SVG directly (< 30 lines, no extra bundle weight).

---

## Existing Phase Dependencies (v0.3 Components to Reuse)

| Existing Component | Dashboard Usage | Location |
|--------------------|-----------------|----------|
| Region list API | Populates Region dropdown | `apps/stores/` — already built |
| Store list API | Populates Store dropdown (filtered by region) | `apps/stores/` — already built |
| `Review` model + `enrichment_status` / `sentiment` field | All dashboard metrics derive from this | `apps/reviews/` — already built |
| `AiUsageLog` | Negative Reviews KPI + Sentiment donut | `apps/reviews/` / `apps/integrations/openai/` — already built |
| Redis cache infrastructure (DB 0) | TTL caching on dashboard endpoints | `apps/common/` + existing `django-redis` setup |
| Celery task infrastructure | Post-sync cache invalidation hook | `apps/reviews/tasks.py` — already built |
| `TenantScopedViewSet` | All 5 dashboard endpoints inherit tenant scoping | `apps/common/` — already built |
| React island pattern | Dashboard page mounts an embedded React root | Established in v0.3 (Action Items, Notification Bell) |
| Tailwind design tokens (yellow `#FACC15`, black `#0A0A0A`) | All chart colors, button states, card styling | `static/css/` — already defined |
| `CursorPagination` | Not needed for dashboard endpoints (aggregates, not lists) | N/A — dashboard endpoints return scalar aggregates |
| Recharts | Bar chart + Donut chart | Verify in `frontend/package.json`; add if absent |

---

## Sources

- Cascading dropdown + URL state: [LogRocket — Advanced React state management via URL parameters](https://blog.logrocket.com/advanced-react-state-management-using-url-parameters/), [DEV Community — Sync React State with URL Search Params](https://dev.to/kphr99/sync-react-state-with-url-search-parameters-using-usequeryparamsstate-hook-1pgi)
- KPI skeleton + independent error states: [Carbon Design System — Loading Pattern](https://carbondesignsystem.com/patterns/loading-pattern/), [Medium — How Senior React Developers Handle Loading States](https://medium.com/@sainudheenp/how-senior-react-developers-handle-loading-states-error-handling-a-complete-guide-ffe9726ad00a)
- Bar chart threshold coloring via Cell: [Recharts GitHub — Dynamic Fill Color Per Bar](https://github.com/recharts/recharts/issues/280), [Recharts GitHub — Positive/Negative Referenced Chart discussion](https://github.com/recharts/recharts/discussions/4278)
- Donut chart UX patterns: [Domo — What Is a Donut Chart?](https://www.domo.com/learn/charts/donut-charts), [PatternFly — Donut Chart](https://pf3.patternfly.org/v3/pattern-library/data-visualization/donut-chart/), [GeeksforGeeks — Recharts Donut](https://www.geeksforgeeks.org/reactjs/create-a-donut-chart-using-recharts-in-reactjs/)
- Half-star rating accessibility: [DEV Community — Dynamic Star Rating in React](https://dev.to/ramcpucoder/how-you-can-build-a-dynamic-star-rating-component-in-reactjs-full-half-and-empty-stars-included-j0k), [Material UI Rating](https://mui.com/material-ui/react-rating/)
- Filter bar UX: [Pencil & Paper — Filter UX Design Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-filtering), [Eleken — Filter UX and UI for SaaS](https://www.eleken.co/blog-posts/filter-ux-and-ui-for-saas)
- Chart library selection: [PkgPulse — Recharts vs Chart.js vs Nivo 2026](https://www.pkgpulse.com/guides/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026), [LogRocket — Best React chart libraries 2025](https://blog.logrocket.com/best-react-chart-libraries-2025/)
- Dashboard design principles: [Carbon Design System — Loading Pattern](https://carbondesignsystem.com/patterns/loading-pattern/), [Pencil & Paper — Dashboard UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards)

---

*Feature research for: Organisation Admin Dashboard (v0.4)*
*Researched: 2026-05-07*
