# Requirements: Multi-Tenant Review Management Platform

**Defined:** 2026-05-07
**Core Value:** Org Admins and Staff can view, respond to, and action Google reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.

## v0.4 Requirements

Requirements for the Dashboard milestone (Phase 14). One phase.

### Filter Bar (FILT)

- [x] **FILT-01**: User can filter dashboard data by Region (All Regions default; lists regions containing at least one accessible shop)
- [x] **FILT-02**: User can filter dashboard data by Store (All Stores default; cascades to shops within the selected region only)
- [x] **FILT-03**: User can filter by Date Range: Last 7 days / Last 30 days (default) / Last 90 days / Custom
- [x] **FILT-04**: User can enter a custom From/To date range with inline date pickers and client-side validation
- [x] **FILT-05**: User can clear all filters to defaults with a single "Clear Filters" button (enabled only when at least one filter differs from default)
- [x] **FILT-06**: Filter state is reflected in URL query params (?region, ?store, ?range, ?from, ?to) via history.replaceState — shareable and bookmarkable
- [x] **FILT-07**: Filter state persists within the session; URL params take precedence over session state when both are present
- [x] **FILT-08**: Out-of-scope region or store IDs in URL params return 403 (do NOT silently fall back to defaults)
- [x] **FILT-09**: Custom date range exceeding 365 days returns 400 with a clear error message
- [x] **FILT-10**: Custom range with from > to returns 400 with a clear error message

### Top Performing Outlets (TOP)

- [x] **TOP-01**: Multi-shop users see a Best Performing Outlets bar chart scoped to date range only (Region and Store filters do NOT apply to this section)
- [x] **TOP-02**: Bar chart shows all eligible shops when ≤10 accessible; shows Top 5 + Worst 5 with a visual gap when >10 accessible; shops with fewer than 3 reviews in the window are excluded silently
- [ ] **TOP-03**: Each bar is colored by rating threshold: green ≥4.0, amber 3.0–3.99, red <3.0
- [ ] **TOP-04**: Hovering a bar shows a tooltip: shop name, exact average rating, review count in the window
- [ ] **TOP-05**: Clicking a bar navigates to the Reviews page filtered to that shop and the same date range
- [x] **TOP-06**: Performance Highlights card shows the highest-rated shop (green sub-card, AI-derived positive review count) and lowest-rated shop (red sub-card, AI-derived negative review count); requires ≥3 reviews per shop
- [x] **TOP-07**: Combined empty state renders when no shops qualify (none have ≥3 reviews); includes a "View last 90 days" CTA that sets the date filter to 90d

### Your Store — Single-Shop Variant (STORE)

- [x] **STORE-01**: Single-shop users see a "Your Store" card instead of the bar chart and Performance Highlights card (date range only; Region/Store filters do not apply)
- [x] **STORE-02**: "Your Store" card shows shop name, region badge, average rating, total reviews, positive/negative counts with percentages, and a 5-star rating distribution mini-bar chart
- [x] **STORE-03**: "Your Store" card shows a trend indicator vs the previous equivalent period (↑ green / ↓ red / — gray); gray "no previous data" shown when the previous period has fewer than 3 reviews

### KPI Cards (KPI)

- [x] **KPI-01**: Total Reviews card shows the count of reviews matching the active full filters (Region + Store + Date Range); footer shows "Across N stores" (multi-store) or the store name (single-store)
- [x] **KPI-02**: Average Rating card shows the arithmetic mean to 1 decimal place with a star visual aid; half-star display used when the decimal is .25–.74
- [x] **KPI-03**: Negative Reviews card counts reviews where AI-derived sentiment = NEGATIVE and enrichment_status = SUCCESS — NOT by star rating
- [x] **KPI-04**: Negative Reviews percentage uses the count of enriched reviews in the window as the denominator (not total reviews)
- [x] **KPI-05**: Each KPI card has an independent loading skeleton, empty state ("No reviews in this period"), and error state ("Could not load. Refresh to try again.")

### Sentiment Distribution (SENT)

- [x] **SENT-01**: Donut chart shows Positive / Neutral / Negative segments computed from enriched reviews only (enrichment_status = SUCCESS, active full filters)
- [x] **SENT-02**: Sentiment summary list shows count, percentage, and a color-coded horizontal progress bar for each sentiment (Positive green #22C55E, Neutral amber #F59E0B, Negative red #EF4444)
- [x] **SENT-03**: Hovering a donut segment shows a tooltip: sentiment label, count, and percentage
- [x] **SENT-04**: Coverage footer appears when enrichment coverage is below 100%: "Based on N enriched reviews (X% of total)"
- [x] **SENT-05**: Coverage footer adds a spinner and "Analysis is still in progress." message when coverage is below 50%
- [x] **SENT-06**: Empty states render correctly: "No reviews to analyze in this period." (no reviews in window) and "Sentiment analysis is in progress. Check back shortly." with spinner (reviews exist but none enriched yet)

### Technical Foundation (TECH)

- [x] **TECH-01**: New `apps/dashboard/` app with `selectors/aggregations.py`, `services/cache.py`, and `views.py`; five focused read-only endpoints registered under `/api/v1/dashboard/`
- [x] **TECH-02**: All five endpoints use Redis TTL caching (5-minute TTL); cache key format: `dashboard:{endpoint}:{org_id}:{user_id}:{filter_hash}` where filter_hash includes `accessible_shop_ids` to prevent cross-user leakage
- [x] **TECH-03**: Migration adds three composite indexes to the Review table: `(organisation_id, review_created_at, sentiment)`, `(shop_id, review_created_at)`, and `(organisation_id, review_created_at, enrichment_status)`
- [x] **TECH-04**: All five dashboard endpoints have `CaptureQueriesContext` tests asserting a fixed query count ceiling regardless of data volume
- [x] **TECH-05**: Dashboard page at `/admin/org/dashboard/` replaces the Phase 2 placeholder; Org Admin, Manager, and Staff land here after login
- [x] **TECH-06**: All five widgets load in parallel via parallel API calls; each renders an independent loading skeleton until its data arrives

### Error Pages (ERR)

- [x] **ERR-01**: User sees a branded 404 page matching the platform design system instead of Django's plain "Not Found" response; includes a navigation action (authenticated users → Dashboard, unauthenticated → Login)
- [x] **ERR-02**: User sees a branded 500 page matching the platform design system instead of Django's plain "Server Error" response; includes a navigation action (authenticated users → Dashboard, unauthenticated → Login)

## Future Requirements

Deferred to later milestones.

### Dashboard — Future Widgets

- **DASH-F-01**: Review volume over time — line chart
- **DASH-F-02**: Rating trend over time — line chart
- **DASH-F-03**: Top positive / top negative tag breakdown widgets
- **DASH-F-04**: Recent reviews preview panel
- **DASH-F-05**: Open action items preview / status breakdown
- **DASH-F-06**: Reply rate widget
- **DASH-F-07**: Custom user-configurable widgets
- **DASH-F-08**: Dashboard data export (CSV / PDF)
- **DASH-F-09**: Email-delivered dashboard summaries
- **DASH-F-10**: Superadmin dashboard

## Out of Scope

Explicitly excluded for Phase 4.

| Feature | Reason |
|---------|--------|
| Real-time live-updating widgets | Channels scope discipline per CLAUDE.md §13.2; HTTP polling acceptable for a dashboard |
| 403 error page | Handled as a UI-level redirect; no dedicated page needed |
| Superadmin dashboard | Deferred — Superadmin role has different metrics and access patterns |
| Action Items widgets on dashboard | Phase 4 must NOT depend on the Action Items module per §1.3 of requirements doc |
| Tag breakdown widgets | Deferred to future milestone |
| Reply rate widget | Deferred to future milestone |
| Export (CSV / PDF) | Deferred to future milestone |
| User timezone field | UTC with a notice is acceptable for Phase 4; user timezone field deferred |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FILT-01 | Phase 14 | Complete |
| FILT-02 | Phase 14 | Complete |
| FILT-03 | Phase 14 | Complete |
| FILT-04 | Phase 14 | Complete |
| FILT-05 | Phase 14 | Complete |
| FILT-06 | Phase 14 | Complete |
| FILT-07 | Phase 14 | Complete |
| FILT-08 | Phase 14 | Complete |
| FILT-09 | Phase 14 | Complete |
| FILT-10 | Phase 14 | Complete |
| TOP-01 | Phase 14 | Complete |
| TOP-02 | Phase 14 | Complete |
| TOP-03 | Phase 14 | Pending |
| TOP-04 | Phase 14 | Pending |
| TOP-05 | Phase 14 | Pending |
| TOP-06 | Phase 14 | Complete |
| TOP-07 | Phase 14 | Complete |
| STORE-01 | Phase 14 | Complete |
| STORE-02 | Phase 14 | Complete |
| STORE-03 | Phase 14 | Complete |
| KPI-01 | Phase 14 | Complete |
| KPI-02 | Phase 14 | Complete |
| KPI-03 | Phase 14 | Complete |
| KPI-04 | Phase 14 | Complete |
| KPI-05 | Phase 14 | Complete |
| SENT-01 | Phase 14 | Complete |
| SENT-02 | Phase 14 | Complete |
| SENT-03 | Phase 14 | Complete |
| SENT-04 | Phase 14 | Complete |
| SENT-05 | Phase 14 | Complete |
| SENT-06 | Phase 14 | Complete |
| TECH-01 | Phase 14 | Complete |
| TECH-02 | Phase 14 | Complete |
| TECH-03 | Phase 14 | Complete |
| TECH-04 | Phase 14 | Complete |
| TECH-05 | Phase 14 | Complete |
| TECH-06 | Phase 14 | Complete |
| ERR-01 | Phase 14 | Complete |
| ERR-02 | Phase 14 | Complete |

**Coverage:**
- v0.4 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-07 after initial definition*
