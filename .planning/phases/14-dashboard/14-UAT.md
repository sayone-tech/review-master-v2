---
status: testing
phase: 14-dashboard
source: 14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md, 14-04-SUMMARY.md, 14-05-SUMMARY.md, 14-06-SUMMARY.md, 14-07-SUMMARY.md, 14-08-SUMMARY.md
started: 2026-05-07T11:00:00Z
updated: 2026-05-07T11:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Dashboard Page Loads
expected: |
  Navigate to /admin/org/dashboard/ as an ORG_ADMIN user.
  Page loads without errors. You should see: a filter bar at the top (date range selector,
  region/shop dropdowns), 3 KPI cards (Total Reviews, Average Rating, Negative Reviews),
  a Sentiment Distribution donut chart, and either Top Performing Stores chart OR Your Store
  card (depending on whether you have 1 or multiple stores).
awaiting: user response

## Tests

### 1. Dashboard Page Loads
expected: Navigate to /admin/org/dashboard/ as an ORG_ADMIN user. Page loads without errors. You should see: a filter bar at the top (date range selector, region/shop dropdowns), 3 KPI cards (Total Reviews, Average Rating, Negative Reviews), a Sentiment Distribution donut chart, and either Top Performing Stores chart OR Your Store card depending on store count.
result: [pending]

### 2. Filter Bar — Date Range
expected: The filter bar shows a date range selector with presets (Last 7 days, Last 30 days, Last 90 days). Selecting a different preset updates all dashboard widgets to reflect the new date range. URL params update in the address bar when you change filters (no page reload).
result: [pending]

### 3. Filter Bar — Region/Shop Dropdowns
expected: Region and Shop dropdowns are visible in the filter bar. If you have multiple regions/shops, selecting one filters the KPI cards and Sentiment Donut to that region/shop. Your Store / Top Performing section should NOT change when you change region/shop (they are date-only scoped).
result: [pending]

### 4. KPI Cards — Data Display
expected: Three cards showing: (1) Total Reviews with a count, (2) Average Rating with a star display and decimal value, (3) Negative Reviews with a count and percentage. Each card shows a loading skeleton briefly on first load, then data. If no data for selected period, cards show a "no data" empty state with a retry or date change suggestion.
result: [pending]

### 5. Sentiment Donut Chart
expected: A donut/pie chart showing Positive / Neutral / Negative sentiment distribution based on AI-enriched reviews (not star ratings). Shows percentage breakdown, a legend, and a coverage % footer (e.g. "72% of total"). If coverage is below 50%, a spinner or warning indicator shows.
result: [pending]

### 6. Top Performing Stores (multi-shop) OR Your Store (single-shop)
expected: For multi-shop org: a bar chart showing stores ranked by average rating with color-coded bars (green/amber/red threshold coloring). Clicking a bar navigates to that store's detail. For single-shop org: a "Your Store" card showing shop name, region badge, average rating (large number), review count, positive/negative counts, trend arrow, and 5-star distribution mini bars.
result: [pending]

### 7. Performance Highlights
expected: A section showing AI-extracted highlights from reviews (best/worst performing categories, notable trends). Visible for multi-shop orgs. Shows loading skeleton then content.
result: [pending]

### 8. Empty State — No Stores Connected
expected: If logged in as an ORG_ADMIN with NO connected stores, the dashboard shows a branded empty state instead of widgets. Should show: "Let's connect your first store" headline, a CTA button to add a store, and 3 preview cards showing what the dashboard will look like once connected.
result: [pending]

### 9. Filter Persistence — Page Reload
expected: After changing date range filter and reloading the page, the filter state is preserved (either via URL params or sessionStorage). The dashboard should restore to the same filter state without resetting to defaults.
result: [pending]

### 10. Branded 404 Page
expected: Navigating to a non-existent URL like /admin/org/doesnotexist/ shows a branded 404 page with the Review Master logo, a clear "Page not found" message, and a button to return to the dashboard (or login, if not authenticated).
result: [pending]

## Summary

total: 10
passed: 0
issues: 0
pending: 10
skipped: 0

## Gaps

[none yet]
