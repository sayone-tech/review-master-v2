**REQUIREMENTS DOCUMENT**

Multi-Tenant Review Management Platform

**Phase 4 — Dashboard**

Performance Overview, KPI Cards, and Sentiment Distribution

Version 1.0 • May 2026

# 1. Document Overview

This document specifies Phase 4 of the multi-tenant Review Management Platform — the Organisation Admin Dashboard. It builds on the conventions, design system, data model, and infrastructure established in Phases 1, 2, and 3.

All global UI patterns, branding, design tokens, accessibility rules, and confirmation popup conventions defined in earlier phases apply unchanged to Phase 4 and are not repeated here. Refer to the Phase 1 document and design contract for those baselines.

Phase 4 transforms the Dashboard placeholder shipped in Phase 2 into a functional multi-widget overview page. The widgets surface review-volume metrics, performance ranking across shops, and AI-derived sentiment distribution, with a flexible filter bar that scopes the data.

## 1.1 Phase 4 Scope

- Replace the Dashboard placeholder page with the functional dashboard
- Filter bar with Region, Store, and Date Range selectors (cascading)
- Top Performing Outlets section — bar chart + Performance Highlights card
- Single-shop "Your Store" card variant for users with access to only one shop
- KPI card row — Total Reviews, Average Rating, Negative Reviews
- Overall Sentiment Distribution card with donut chart and summary
- URL state for filters (shareable / bookmarkable)
- Session-scoped filter persistence
- Caching layer for dashboard queries (Redis, 5-minute TTL)

## 1.2 Out of Scope for Phase 4

- Superadmin dashboard (deferred)
- Review volume over time (line chart)
- Rating trend over time (line chart)
- Tag breakdown widgets (top positive / top negative tags)
- Recent reviews preview
- Open action items preview / status breakdown
- Reply rate widget
- Custom user-configurable widgets
- Export of dashboard data (CSV / PDF)
- Email-delivered dashboard summaries
- Real-time live-updating widgets (Channels scope discipline per CLAUDE.md §13.2)

## 1.3 Phase Dependencies

Phase 4 depends on data and infrastructure from prior phases:

- Phase 2 — Shops, Regions, Team scoping (filter sources)
- Phase 3a-ii — Review and ReviewReply models, populated review data
- Phase 3b-i — AI enrichment fields on Review (sentiment), AiUsageLog (not displayed but reused for filtering)
Phase 4 must NOT depend on Phase 3b-ii (Action Items module) — the dashboard widgets in this spec do not reference action items. A future phase will add action-item-related widgets.

# 2. Roles and Permissions

The Dashboard is accessible to Organisation Admin, Manager, and Staff roles. Superadmin does not have a dashboard in Phase 4.

| **Role** | **Dashboard Access** | **Data Scope** |
| --- | --- | --- |
| Org Admin / Manager | Full dashboard | All shops in their organisation |
| Staff (multi-shop access) | Full dashboard | Only the shops in their StaffAccessScope |
| Staff (single-shop access) | Single-shop variant of the dashboard | Only their single shop; Top/Worst chart hidden |
| Superadmin | No dashboard in Phase 4 | Not applicable |

## 2.1 Tenant Scoping (Authoritative)

- All dashboard queries filter by request.user.organisation_id at the base permission layer (per CLAUDE.md §9).
- For Staff users, queries additionally filter by the shops in their StaffAccessScope.
- Cross-organisation access is impossible by construction — every dashboard query uses the user's accessible shops as the input set.
- URL parameters (?region=, ?store=) are validated against the user's accessible scope before executing queries; out-of-scope IDs return 403.

# 3. Page Layout

## 3.1 Route and Navigation

**Route:** /admin/org/dashboard/

**Sidebar item:** Dashboard (LayoutDashboard icon) — already present from Phase 2

**Default landing:** Yes — Org Admin / Manager / Staff land here on login

## 3.2 Page Structure (Top to Bottom)

- Page header — "Dashboard" title and subtitle ("Overview of your reviews and performance")
- Filter bar — Region, Store, Date Range, Clear Filters
- Top Performing Outlets section — bar chart on the left, Performance Highlights card on the right (multi-shop) OR single "Your Store" card (single-shop)
- KPI card row — three cards (Total Reviews, Average Rating, Negative Reviews)
- Overall Sentiment Distribution card — donut + summary

## 3.3 Filter Scope Rules

Two filter scopes apply on this page, intentionally.

| **Section** | **Filters Applied** | **Reason** |
| --- | --- | --- |
| Top Performing Outlets (bar chart + Performance Highlights) | Date range only (the Region and Store filters do NOT apply) | The chart's purpose is comparing all shops in the user's scope. Filtering to a single store breaks the comparison. |
| KPI card row | Region + Store + Date range (full) | Deep-dive metrics where store-level scoping is the point. |
| Sentiment Distribution | Region + Store + Date range (full) | Same as KPI cards — supports drilling into a specific store. |

## 3.4 Responsive Behaviour

- Desktop (≥ 1024px) — full layout as described, multi-column where shown
- Tablet (768–1023px) — KPI cards remain in a row of 3; Top Performing section stacks (chart on top, Highlights card below); Sentiment card spans full width
- Mobile (< 768px) — every section stacks vertically; filter bar wraps; KPI cards become a single column; donut chart and summary stack

# 4. Filter Bar

## 4.1 Filters

Three filters appear in a single horizontal bar at the top of the dashboard, with a "Clear Filters" button at the right end.

| **Filter** | **Type** | **Default** | **Behaviour** |
| --- | --- | --- | --- |
| Region | Dropdown | All Regions | Lists every region in the organisation that contains at least one shop in the user's accessible scope. |
| Store | Dropdown | All Stores | Lists shops in the user's accessible scope. If a Region is selected, narrows to shops within that region. Selecting "All Regions" while a Store is selected does NOT clear the Store selection. |
| Date Range | Dropdown with optional Custom inputs | Last 30 days | Options: Last 7 days, Last 30 days, Last 90 days, Custom range. Custom shows two date pickers (From, To) in a small inline panel. |

## 4.2 Clear Filters

- Position: right end of the filter bar
- Visibility: enabled only when at least one filter differs from default
- On click: resets Region to All Regions, Store to All Stores, Date Range to Last 30 days; updates URL accordingly

## 4.3 Filter Persistence

- Filter state is persisted within the user's session (server-side session storage or sessionStorage on the client — implementation choice, but state must survive route changes within the same session).
- State is reset on logout or new browser session.
- URL state takes precedence over session state when both are present (e.g., a shared link overrides the user's last filter values).

## 4.4 URL State

Filter state is reflected in the URL as query parameters so dashboards can be shared and bookmarked.

- region — Region ID (e.g., ND001), or omitted for "All Regions"
- store — Shop UUID, or omitted for "All Stores"
- range — One of: 7d, 30d, 90d, custom. Default omitted means 30d.
- from — ISO date (YYYY-MM-DD), only when range=custom
- to — ISO date (YYYY-MM-DD), only when range=custom
Example: /admin/org/dashboard?region=ND001&store=abc-123&range=custom&from=2026-04-01&to=2026-04-30

### URL Parameter Validation

- Invalid or out-of-scope region or store IDs return 403 (do NOT silently fall back to defaults).
- Custom range with from > to returns 400 with a clear error message.
- Custom range with to in the future is allowed (won't break anything; queries return only past data).
- Custom range exceeding 365 days is rejected with 400: "Date range must be 365 days or less."

# 5. Top Performing Outlets Section

## 5.1 Purpose and Layout

This section combines a bar chart and a Performance Highlights card to give users a fast visual ranking of their shops by average rating within the selected date window. Filter scope: date range only (Region and Store filters do NOT apply here).

### Layout

- Multi-shop users (≥ 2 accessible shops): two-column layout — bar chart on the left (~ 2/3 width), Performance Highlights card on the right (~ 1/3 width)
- Single-shop users (1 accessible shop): replaced by the "Your Store" card — see §5.5

## 5.2 Bar Chart — "Best Performing Outlets"

**Title:** Best Performing Outlets

**Subtitle:** Top outlets based on average review stars

**Icon:** TrendingUp (green)

### Display Rules

- If the user has 10 or fewer accessible shops, all shops with at least 3 reviews in the date window are displayed, sorted highest rating first.
- If the user has more than 10 accessible shops, the chart shows the Top 5 (highest ratings) and Worst 5 (lowest ratings), with a small visual gap between the two groups. Top 5 shown first, sorted descending; Worst 5 shown after the gap, sorted ascending.
- Shops with fewer than 3 reviews in the date window are excluded from the chart entirely.
- If, after exclusion, no shops qualify, an empty state is shown (see §5.4).

### Bar Coloring (Hardcoded Thresholds)

| **Average Rating** | **Bar Color** | **Hex** |
| --- | --- | --- |
| 4.0 – 5.0 | Green | #22C55E |
| 3.0 – 3.99 | Amber | #F59E0B |
| 0.0 – 2.99 | Red | #EF4444 |

### Axes and Scale

- Y-axis: Average Rating, fixed scale 0 to 5 with gridlines at integer values
- X-axis: shop names, rotated 30–45 degrees to prevent overlap
- Y-axis label: "Average Rating"
- No X-axis label needed (shop names are self-explanatory)

### Interactivity

- Hover on a bar shows a tooltip: shop name, exact rating, review count in the window
- Click on a bar navigates to the Reviews page filtered to that shop and the same date range

## 5.3 Performance Highlights Card

**Title:** Performance Highlights

**Subtitle:** Top and bottom performing stores

### Top Performing Store sub-card (green)

- Header: "Top Performing Store" with TrendingUp icon, green text
- Shop name (bold)
- Star icon + average rating + review count in parentheses (e.g., "4.52 (485 reviews)")
- Highlight line in green: "{N} positive reviews ({percent}%)"
- Background tint: light green (matches Phase 1 success palette)

### Needs Attention sub-card (red)

- Header: "Needs Attention" with TrendingDown icon, red text
- Shop name (bold)
- Star icon + average rating + review count
- Highlight line in red: "{N} negative reviews ({percent}%)"
- Background tint: light red

### Selection Logic

- Top Performing Store: the single shop with the highest average rating in the window, with at least 3 reviews
- Needs Attention: the single shop with the lowest average rating in the window, with at least 3 reviews
- If the same shop is both top and bottom (only one qualifying shop), only the top sub-card is shown — the bottom sub-card is hidden
- If no shops qualify (none have ≥ 3 reviews in window), the entire card shows an empty state

### Card Empty State

- Centred TrendingUp icon
- Heading: "No data yet"
- Body: "No shops have enough reviews in the selected period to highlight performance."

## 5.4 Top Performing Section — Combined Empty State

When neither the bar chart nor the Performance Highlights card has data (because no shops have ≥ 3 reviews in the window), the entire section collapses into a single empty state spanning both columns.

- Centred BarChart icon
- Heading: "No reviews in the selected period"
- Body: "Try a longer window to see performance comparisons."
- CTA button: "View last 90 days" — sets the date filter to last 90 days

## 5.5 Single-Shop Variant — "Your Store" Card

When the user has access to only one shop (typical for Staff with single-shop StaffAccessScope), the bar chart and Performance Highlights card are replaced with a single "Your Store" card. Ranking against itself is meaningless, so the card emphasises the shop's own metrics with a trend indicator.

### Card Contents

- Header: shop name (bold) and shop region badge
- Average rating: large number with star icon (e.g., "4.2 ★") and "/ 5.0" suffix
- Total reviews in window: "485 reviews"
- Positive reviews count + percentage (green)
- Negative reviews count + percentage (red)
- Rating distribution mini-chart: 5 horizontal bars showing the count of reviews at each star level (5, 4, 3, 2, 1)
- Trend indicator vs previous period: arrow icon + delta (e.g., "↑ 0.3 from previous 30 days" or "↓ 0.5 from previous 30 days"). Green for upward trend, red for downward, gray for unchanged.

### Trend Calculation

- Previous period is the same length as the selected window, immediately before its start date.
- Example: if window is Last 30 days (today minus 30), previous period is days -60 to -30.
- Trend value = current_average_rating − previous_average_rating, rounded to 1 decimal place.
- If the previous period has fewer than 3 reviews, trend is shown as "— no previous data" (gray).

# 6. KPI Card Row

## 6.1 Layout

Three cards in a row, equal width, with subtle border and shadow per Phase 1 design contract. Each card has a metric name, a date-range subtitle, the metric value, and a footer with context.

## 6.2 Card 1 — Total Reviews

**Title:** Total Reviews

**Subtitle:** Reflects the active Date Range filter (e.g., "Last 30 days")

**Icon:** MessageSquare (gray, top-right)

### Metric

- Large number (e.g., 1250) — the count of reviews matching the active filters (Region + Store + Date Range)
- All reviews count regardless of enrichment status (Total Reviews is a volume metric, not an analysis metric)

### Footer

- Multi-store filter (Region or Store filter not narrowed to a single shop): "Across N stores" where N is the count of shops contributing to the metric
- Single-store filter (Store filter set to a specific shop): the shop name (e.g., "Downtown Store")
- If N is zero (no reviews in window across the filtered scope): "No reviews in this period"

## 6.3 Card 2 — Average Rating

**Title:** Average Rating

**Subtitle:** Active Date Range

**Icon:** Star (yellow, filled, top-right)

### Metric

- Large number with one decimal place + " / 5.0" suffix (e.g., "4.1 / 5.0")
- Computed as the arithmetic mean of all qualifying reviews' ratings within the active filters
- If there are no reviews, displays "— / 5.0" with footer "No reviews in this period"

### Visual Aid

- Star rating row beneath the number — five stars, with the number of yellow (filled) stars matching the rounded average
- Half-star representation: if the decimal is .25 to .74, the next star is half-yellow

## 6.4 Card 3 — Negative Reviews

**Title:** Negative Reviews

**Subtitle:** Active Date Range

**Icon:** AlertTriangle (red, top-right)

### Metric Definition

A review is counted as Negative when its enriched sentiment is NEGATIVE. This is the AI-derived sentiment from Phase 3b-i — NOT the star rating. A 3-star review with strongly negative text is counted; a 1-star review with sarcastic-but-positive text is not.

### Metric

- Large number in red (e.g., 118)
- Counted only from reviews with enrichment_status = SUCCESS within the active filters

### Footer

- Percentage line: "{percent}% of total reviews" — computed as negative_count / total_enriched_count_in_window × 100, rounded to 1 decimal
- Note: the denominator is enriched reviews in the window, not all reviews. This keeps the percentage meaningful even when some reviews are still being processed.

## 6.5 KPI Card Loading and Error States

- Loading: each card individually shows a skeleton placeholder while its query runs. Cards may finish at different times — they do not block one another.
- Error: if a query fails, the card shows a small error icon and helper text "Could not load. Refresh to try again."
- Stale data: if the cached response is older than 5 minutes, the cache is invalidated server-side. Clients always see fresh-or-cached data, never visibly-stale.

# 7. Overall Sentiment Distribution

## 7.1 Purpose and Layout

**Title:** Overall Sentiment Distribution

**Subtitle:** Sentiment breakdown across all selected outlets

**Icon:** BarChart (gray)

**Layout:** Two-column inside one card: donut chart on the left, Sentiment Summary list on the right

## 7.2 Donut Chart

- Three segments — Positive (green #22C55E), Neutral (amber #F59E0B), Negative (red #EF4444)
- Segment angles proportional to the count of each sentiment in the active filtered window
- Hollow center (donut, not pie) with no inner text
- Legend below the chart: "Positive Neutral Negative" with colored markers
- Hover on a segment shows tooltip: sentiment name + count + percentage

## 7.3 Sentiment Summary (Right Column)

Three rows, one per sentiment, each with:

- Colored marker (matching donut color) + sentiment label
- Right-aligned: count + percentage in parentheses (e.g., "572 (45.8%)")
- Beneath each label: a horizontal progress bar showing the percentage, colored to match

## 7.4 Data Source — Enriched Reviews Only

The Sentiment Distribution card uses ONLY reviews with enrichment_status = SUCCESS. Reviews that are still PENDING, IN_PROGRESS, or FAILED are excluded from the donut entirely.

### Coverage Footer

A small footnote below the card content shows the analysis coverage when it is less than 100%:

- If 100% of reviews in the window are enriched: no footnote
- If less than 100%: "Based on N enriched reviews ({percent}% of total)" in small gray text
- If less than 50%: the message becomes "Based on N enriched reviews. Analysis is still in progress." with a small spinner icon to indicate active processing

## 7.5 Empty State

- If no reviews exist in the active window: "No reviews to analyze in this period."
- If reviews exist but none are enriched yet: "Sentiment analysis is in progress. Check back shortly." with a spinner icon

# 8. Data Computation Rules

## 8.1 Date Window Boundaries

- All windows are inclusive of both endpoints in the user's local timezone (read from the user's profile or browser; default UTC if unavailable).
- Last 7 days = midnight 7 days ago through end-of-day today
- Last 30 days = midnight 30 days ago through end-of-day today
- Last 90 days = midnight 90 days ago through end-of-day today
- Custom range = midnight on the From date through end-of-day on the To date, in the user's local timezone
- The review's review_created_at (Google's reported review date) is the field used for window matching, NOT the local created_at.

## 8.2 Minimum Review Threshold

A shop must have at least 3 reviews within the active date window to be eligible for ranking on the bar chart and Performance Highlights card.

- Shops below the threshold are excluded silently from comparison widgets — they do not appear with a "low data" indicator.
- They DO still contribute to the KPI card row metrics (Total Reviews, Average Rating, Negative Reviews) since those are aggregate metrics where individual shop sample sizes don't matter.

## 8.3 Average Rating Calculation

- Arithmetic mean of all qualifying reviews' rating values
- Rounded to 1 decimal place for display
- Uses 0 decimal places for the bar chart Y-axis labels

## 8.4 Sentiment-Based Counts

- "Negative Reviews" KPI counts review.sentiment = NEGATIVE among reviews in the window with enrichment_status = SUCCESS
- Sentiment Distribution donut counts each sentiment value among enriched reviews in the window
- Percentages in both widgets use the count of enriched reviews in the window as the denominator (NOT total reviews)

## 8.5 Performance Highlights — "Positive Reviews" and "Negative Reviews" Counts

The green sub-card displays "{N} positive reviews ({percent}%)" and the red sub-card displays "{N} negative reviews ({percent}%)". These counts use the AI-derived sentiment values, computed within the date window for the specific top-performing or bottom-performing shop. The percentage is computed against that shop's enriched reviews in the window.

## 8.6 Trend Calculation (Single-Shop "Your Store" Card)

- Current period = the active date window
- Previous period = the same length immediately before the current window's start date
- Trend = current_avg − previous_avg, rounded to 1 decimal
- Display format: arrow icon (↑ green / ↓ red / — gray) followed by the absolute delta and the comparison label (e.g., "↑ 0.3 from previous 30 days")
- If the previous period has fewer than 3 reviews, show "— no previous data" in gray

# 9. Technical Design

The Phase 1 / 2 / 3 tech design baselines apply unchanged. This section documents Phase 4 specifics.

## 9.1 Service and Selector Layout

- apps/dashboard/ — new app for dashboard endpoints and aggregation logic
- apps/dashboard/selectors/aggregations.py — query primitives that compute aggregates over the Review table
- apps/dashboard/services/cache.py — cache key builder and invalidation helpers
- apps/dashboard/views.py — DRF viewsets exposing the dashboard endpoints

## 9.2 API Endpoints

All dashboard endpoints are under /api/v1/dashboard/. Each is a focused endpoint that returns one widget's data — the frontend assembles the dashboard by calling them in parallel.

| **Endpoint** | **Returns** |
| --- | --- |
| GET /api/v1/dashboard/top-performing/ | { top_shops: [...], worst_shops: [...], total_eligible_shops, mode: 'all' \| 'top-and-worst' \| 'single-shop' } |
| GET /api/v1/dashboard/highlights/ | { top: { shop, rating, review_count, positive_count, positive_pct }, bottom: { ... }, has_data: bool } |
| GET /api/v1/dashboard/your-store/ | Single-shop variant: { shop, rating, review_count, rating_distribution, positive_count, negative_count, trend_delta, has_previous_data } |
| GET /api/v1/dashboard/kpis/ | { total_reviews, average_rating, negative_count, negative_pct, store_count, single_store_name } |
| GET /api/v1/dashboard/sentiment-distribution/ | { positive: { count, pct }, neutral: { ... }, negative: { ... }, enriched_count, total_count, coverage_pct } |

### Common Query Parameters

- region — Region ID (optional)
- store — Shop UUID (optional)
- range — One of: 7d, 30d, 90d, custom (default 30d)
- from, to — ISO dates (only when range=custom)

### Permissions

- All endpoints require authentication
- All endpoints filter by request.user.organisation_id at the base permission layer
- For Staff, filtered additionally by StaffAccessScope before any aggregation runs
- Top-performing endpoint ignores region and store filters per §3.3 (date range only)
- If a Staff user has only one accessible shop, calls to /top-performing/ and /highlights/ return mode=single-shop and the frontend uses /your-store/ instead

## 9.3 Caching

Dashboard queries are cached in Redis (DB index 0, the default cache) with a 5-minute TTL.

### Cache Key Format

- dashboard:{endpoint}:{org_id}:{user_id}:{filter_hash}
- filter_hash is a deterministic hash of (region, store, range, from, to, accessible_shop_ids)
- user_id is included so two users with different shop access don't share cache entries

### Cache Invalidation

- TTL-based — cache entries expire after 5 minutes regardless of underlying data changes
- Event-based invalidation is NOT used in Phase 4 — too many events would invalidate dashboard cache (every new review, every reply, every enrichment). Eventual consistency at 5 minutes is acceptable for a dashboard.

## 9.4 Query Optimisation

Dashboard queries aggregate across the Review table, which can grow large. Performance discipline is critical.

- All endpoints must execute their query in a fixed query count regardless of result size (CaptureQueriesContext test required)
- Aggregations use ORM annotations + aggregates (Avg, Count, Q with filter), not Python-side iteration
- Index requirements added to the Review table for Phase 4:
- (organisation_id, review_created_at, sentiment) — supports KPI and sentiment queries
- (shop_id, review_created_at) — supports per-shop ranking
- (organisation_id, review_created_at, enrichment_status) — filters enriched-only queries efficiently
- Verify index usage with EXPLAIN ANALYZE on representative datasets (1k, 10k, 100k reviews per organisation)

## 9.5 Performance Targets

- P95 dashboard load (all five endpoints in parallel) under 800ms for 10k reviews per organisation
- P95 dashboard load under 2 seconds for 100k reviews per organisation
- Cache hit ratio above 70% in steady-state (most users land on the dashboard with the same default filters)

## 9.6 Frontend Architecture

- The dashboard page is a React island within a Django template (per CLAUDE.md frontend pattern)
- React Query handles parallel fetching and per-card loading states
- Each widget component handles its own loading skeleton, empty state, and error state independently
- Filter bar state is the React island's source of truth; updates write to URL via replaceState (no full navigation)

## 9.7 Data Model Updates

Phase 4 introduces NO new models. It uses Review, Shop, Region, User, and StaffAccessScope from earlier phases.

Index additions (see §9.4) are the only schema changes. They go in a migration in the reviews app since the indexes are on the Review table.

# 10. Phase 4 Acceptance Criteria

Phase 4 is complete when all of the following criteria are met.

## 10.1 Page Load and Layout

- On login, Org Admin / Manager / Staff land on the Dashboard page (replacing the Phase 2 placeholder).
- All five widgets load in parallel; each shows a skeleton until its data arrives.
- Layout is correct at desktop, tablet, and mobile breakpoints.

## 10.2 Filter Bar

- Region, Store, and Date Range filters render with correct defaults.
- Selecting a Region narrows the Store dropdown to that region's shops.
- Custom date range opens a From / To picker and validates the inputs.
- Clear Filters resets all three filters to defaults.
- URL state updates as filters change; reload preserves filter state from URL.
- Out-of-scope region or store IDs in URL parameters return 403.
- Custom range exceeding 365 days returns 400 with a clear message.

## 10.3 Top Performing Section

- Bar chart shows all shops if the user has ≤ 10; Top 5 + Worst 5 if > 10.
- Bar colors match the threshold rules (green ≥ 4.0, amber 3.0–3.99, red < 3.0).
- Shops with fewer than 3 reviews in the window are excluded.
- Region and Store filters do NOT affect this section — only date range does.
- Bar hover shows a tooltip with shop, rating, review count.
- Bar click navigates to the Reviews page filtered to that shop and the same date range.
- Performance Highlights card shows correct top/bottom shops with positive/negative counts.
- Single-shop user sees "Your Store" card instead, with trend indicator vs previous period.
- Empty state shows when no shops qualify; CTA to extend to 90 days works.

## 10.4 KPI Cards

- Total Reviews shows the correct count and adapts the footer for single-store views (shop name).
- Average Rating shows one decimal with star visual aid.
- Negative Reviews uses AI sentiment (NOT star rating) for the count.
- Negative percentage is computed against enriched reviews in the window.
- Each card has independent loading, empty, and error states.

## 10.5 Sentiment Distribution

- Donut + summary render with correct colors and proportions.
- Counts and percentages are based only on enriched reviews.
- Coverage footer appears when enrichment is below 100%.
- Loading state shows the in-progress message when enrichment coverage is below 50%.
- Empty states render correctly when no reviews or no enriched reviews exist.

## 10.6 Performance and Reliability

- All dashboard endpoints have CaptureQueriesContext tests asserting fixed query counts.
- Required indexes are in place; EXPLAIN ANALYZE confirms index usage on representative datasets.
- P95 dashboard load is under 800ms for 10k reviews per organisation.
- Cache hit ratio is at least 70% under steady-state usage.
- Cached responses are correctly scoped per (org, user, filters); no cross-tenant or cross-user leakage.

## 10.7 Tenant Scoping

- Org Admin / Manager see all org shops; Staff see only their accessible shops.
- URL parameters cannot bypass scoping — out-of-scope IDs always return 403.
- All endpoints have role + tenant permission tests in CI.

# 11. Risks and Mitigations

| **Risk** | **Mitigation** |
| --- | --- |
| Dashboard slow on large organisations (100k+ reviews) | Indexes designed for the exact query shapes used; CI tests assert query counts; performance benchmarks at 10k and 100k reviews on representative data; consider materialised views in a future phase if benchmarks slip. |
| Stale data confuses users | 5-minute cache TTL is fast enough that users rarely see truly stale data. The Sentiment card's coverage footer transparently shows when analysis is still in progress. |
| Single-shop users see a confusing comparison view | Single-shop variant of Top Performing replaces the bar chart with a focused "Your Store" card; trend indicator gives time-based context instead of cross-shop comparison. |
| Custom date ranges enable expensive queries | 365-day cap; query-count tests prevent N+1 introduction; cache absorbs repeated identical requests. |
| Enrichment lag on first deploy makes Sentiment widget look broken | Coverage footer states the partial state explicitly; in-progress messaging when below 50%; no false zero counts. |
| Trend indicator on single-shop card shows misleading values for low-volume shops | Minimum 3 reviews required in the previous period; otherwise shows '— no previous data'. |
