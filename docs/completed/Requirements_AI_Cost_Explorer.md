# AI Cost Explorer — Superadmin Dashboard

**Version 1.0 · November 2026**

> Implementation notes and corrections against the current codebase live in
> `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md` — where the
> two disagree, the design doc wins.

## 1. Document Overview

This document specifies a minimal AI Cost Explorer for Superadmins. The purpose is simple: let the ReviewBee Superadmin see, at a glance, how much the platform is spending on OpenAI API calls, broken down by organisation, by shop within an organisation, by request type, and by model.

This is an internal operational tool. It is not a billing dashboard, not a forecasting tool, and not a budget-enforcement mechanism. It answers the question "Where did our AI spend go this month?" and nothing more.

All underlying data already exists in the `AiUsageLog` table. This feature is primarily a read-only aggregation view built on top of that table — no new models, no new background jobs, no new external integrations.

### 1.1 Scope

- New Superadmin-only page: AI Cost Explorer
- Top row of KPI cards summarising total spend and token usage for the selected date range
- Date-range filter (default: This month)
- Table of organisations with per-org totals (calls, input tokens, output tokens, cost)
- Compact badges on each org row showing cost breakdown by request type
- Drill-down from an organisation row → table of shops within that org with the same columns
- Second drill-down tab or section on the organisation detail: cost breakdown by model
- Shops with zero AI activity in the window are excluded (not shown as empty rows)
- Costs displayed in USD (matches how `AiUsageLog.estimated_cost_usd` is stored)

### 1.2 Out of Scope

- INR conversion or any currency other than USD
- Per-call detail view (individual `AiUsageLog` rows)
- Charts or time-series visualisation — this is a table-first view
- Cost forecasting or trend prediction
- Budget thresholds, alerts, or spend caps
- CSV / PDF export
- Sharing with Org Admin or Manager roles — this is Superadmin-only
- Pricing model changes (editing `AiPricing` rows — done via Django admin for now)
- Billing or invoicing of organisations
- Cost attribution per user within an organisation
- Anomaly detection (sudden cost spikes)

### 1.3 Dependencies

- `AiUsageLog` model already captures `organisation_id`, `review_id`, `model`, `request_type`, token counts, `estimated_cost_usd`, `created_at` (per CLAUDE.md §14.3)
- `Review → Shop → Organisation` relationships allow aggregating by shop
- Superadmin role and authentication already in place

## 2. Access

| Role | Access |
|---|---|
| Superadmin | Full access to all data across every organisation |
| Org Admin / Manager / Staff | No access — route returns 403 |

Route: `/admin/ai-cost/`

Sidebar entry in the Superadmin shell: **AI Cost** (icon: `Zap` or `Activity` from Lucide)

## 3. Page Structure

Top to bottom:

1. Page header: "AI Cost Explorer" + subtitle "Platform-wide OpenAI spend"
2. Date-range filter
3. KPI card row (4 cards)
4. Organisations table
5. On organisation row click → drill-down view (§5)

## 4. Main View — Platform Summary

### 4.1 Date-Range Filter

Single dropdown with options:

- This month (default)
- Last month
- Last 7 days
- Last 30 days
- Last 90 days
- Custom range (opens From / To date pickers inline)

The filter applies to every element on the page — KPI cards and the organisations table re-compute whenever the filter changes.

Boundary rule: periods are anchored to UTC midnight. "This month" means 00:00 UTC on the 1st of the current calendar month through now. Consistent with the Credits system's monthly boundary convention — easier to reconcile the two when they sit side by side.

Custom range cap: 365 days. A request exceeding this returns 400 with a clear message.

### 4.2 KPI Card Row

Four cards, equal width:

| Card | Primary Value | Footer |
|---|---|---|
| Total Cost | `$1,245.67` (bold, large) | "Across N organisations" |
| Total API Calls | `48,312` | "N calls succeeded, M failed" |
| Total Input Tokens | `12.4M` (abbreviated with M / K) | Average input tokens per call |
| Total Output Tokens | `3.8M` (abbreviated) | Average output tokens per call |

Each card has a Lucide icon top-right. Light grey border, white background, matches Phase 1 design contract KPI card style.

### 4.3 Organisations Table

Below the KPI cards. One row per organisation that had at least one AI call in the window.

Columns:

| Column | Content | Alignment |
|---|---|---|
| Organisation | Org name, bold; small subtitle with org type pill | Left |
| Active Shops | Count of shops in this org with at least one AI call in the window | Right |
| API Calls | Total `AiUsageLog` rows for this org in window | Right |
| Input Tokens | Sum of `prompt_tokens` | Right |
| Output Tokens | Sum of `completion_tokens` | Right |
| Cost (USD) | Sum of `estimated_cost_usd`, formatted `$X.XX` | Right |
| By Request Type | Compact badge group showing cost split: e.g., `Enrichment $45.20 · Reply $12.80 · Moderation $0.00` | Left |

Sort: default descending by Cost. Click any column header to sort by that column.

Organisations with zero AI activity in the window are excluded entirely.

Row behaviour: click a row → navigates to the organisation drill-down (§5).

Pagination: standard 10 / 25 / 50 / 100 per page. Default 25.

### 4.4 Empty States

- Platform has no AI calls in the window: centred icon, heading "No AI usage in this period", body "Try widening the date range."
- Platform has no `AiUsageLog` rows at all (fresh install): same empty state with different wording "No AI calls yet. Costs will appear here as reviews are enriched."

## 5. Drill-Down — Organisation Detail

Triggered by clicking an organisation row in the main table. The page transitions to a detail view (route: `/admin/ai-cost/organisations/{org_id}/`).

### 5.1 Header

- Back link: "← Back to AI Cost"
- Title: organisation name
- Subtitle: org type · N shops · active in date range
- Date-range filter (carries over from main view; user can change it here too)

### 5.2 KPI Card Row (Scoped to this Org)

Same four cards as §4.2, but scoped to this organisation only:

- Total Cost for this org in window
- API Calls for this org
- Input Tokens
- Output Tokens

### 5.3 Shops Table

One row per shop in this organisation that had at least one AI call in the window.

Columns:

| Column | Content |
|---|---|
| Shop | Shop name, with region badge |
| API Calls | Row count for this shop in window |
| Input Tokens | Sum |
| Output Tokens | Sum |
| Cost (USD) | Sum |
| By Request Type | Same badge group as §4.3 |

Sort default: descending by Cost. Standard pagination (25 per page default).

Shops with zero AI activity in the window are excluded.

### 5.4 Model Breakdown Section

Below the shops table, a small section titled **Cost by Model**.

A simple table (not a chart):

| Model | API Calls | Input Tokens | Output Tokens | Cost (USD) |
|---|---|---|---|---|
| gpt-4o-mini-2024-07-18 | 14,230 | 8.2M | 2.1M | $92.40 |
| gpt-4o-mini-2025-01-xx | 1,045 | 620K | 180K | $7.20 |

Rows sorted by Cost descending. Shows all models used by this org in the window.

If only one model has been used (common case today), the table still renders with one row — gives Superadmin a sanity check that the active model is what they expect.

### 5.5 Empty State

Shouldn't normally be reachable (the user clicked an org from the main table, so by construction it had data). But as a safety net: if filter changes result in zero activity for this org, show "No AI usage for this organisation in the selected period" with a link to reset the filter.

## 6. API Endpoints

All endpoints Superadmin-only. Return 403 for any other role.

| Method + Path | Purpose |
|---|---|
| `GET /api/v1/admin/ai-cost/summary/?range=...` | Platform-wide KPIs: total cost, calls, input tokens, output tokens, org count |
| `GET /api/v1/admin/ai-cost/organisations/?range=...&page=...&sort=...` | Paginated list of orgs with per-org aggregates + per-request-type cost breakdown |
| `GET /api/v1/admin/ai-cost/organisations/{org_id}/summary/?range=...` | Org-scoped KPIs |
| `GET /api/v1/admin/ai-cost/organisations/{org_id}/shops/?range=...&page=...&sort=...` | Paginated shops in this org with per-shop aggregates |
| `GET /api/v1/admin/ai-cost/organisations/{org_id}/models/?range=...` | Model-level breakdown for this org |

All endpoints accept the same date-range parameters: `range` (one of `this_month` / `last_month` / `7d` / `30d` / `90d` / `custom`) and `from` / `to` when `range=custom`.

## 7. Data Computation Rules

### 7.1 Which Rows Count

Only `AiUsageLog` rows with `status = SUCCESS` are included in cost and token totals. Failed and retrying calls are excluded from cost (they didn't actually complete and weren't billed).

The "API Calls" count on each card and table includes all status values so Superadmin can see failure volume. If the gap between "calls" and "successful calls" is large, that's a signal worth investigating. The footer under the Total API Calls KPI card reports this split.

### 7.2 Aggregation

Per-organisation totals are aggregated with a single SQL query using `GROUP BY organisation_id` on `AiUsageLog`, joined to `Organisation` for display fields.

Per-request-type breakdown is computed with a nested aggregation: `GROUP BY organisation_id, request_type`. The result is reshaped in the service layer into `{org_id: {request_type: cost}}` for rendering as compact badges.

Per-shop drill-down requires joining `AiUsageLog → Review → Shop` since `AiUsageLog` stores `review_id` but not `shop_id` directly. Consider denormalising `shop_id` onto `AiUsageLog` later if this query becomes slow — not necessary at current scale.

Model breakdown is `GROUP BY organisation_id, model` on `AiUsageLog` for the given org.

### 7.3 Active-Shops Count

"Active shops" for a given organisation and window = count of distinct `shop_id` values on `AiUsageLog` rows (via `Review` join) that match the org and window with `status = SUCCESS`.

## 8. Technical Design

### 8.1 Module Layout

- `apps/admin_dashboard/` — new Django app (or add to existing admin app if one exists)
  - `views.py` — Superadmin-permission DRF viewsets
  - `selectors/ai_cost.py` — all aggregation queries live here
  - `services/` — not needed; this is a read-only feature
  - `urls.py`
  - `templates/admin_dashboard/ai_cost.html` — Django template shell that loads the React island for the table interactivity

Alternative: if the admin area is already one app, just add `selectors/ai_cost.py` and new view classes there. Avoid proliferating apps.

### 8.2 Frontend

React island mounted in a Django template. Uses the existing Phase 1 React patterns for data tables + filter bars. No new libraries needed.

The drill-down to the organisation detail view is a route change inside the React island — not a full-page reload — so the date-range filter state and scroll position are preserved naturally.

### 8.3 Caching

Dashboard queries are cached in Redis with a **10-minute TTL**. Longer than the Phase 4 dashboard cache (5 min) because AI cost data moves slowly and doesn't need to feel real-time.

Cache key format: `admin:ai_cost:{endpoint}:{filter_hash}`

No per-user keying since this is Superadmin-only — all Superadmins see the same numbers.

### 8.4 Query Optimisation

Every endpoint must pass a `CaptureQueriesContext` test asserting a fixed query count ceiling. Expect 3–5 queries max per endpoint.

Index requirements on `AiUsageLog`:

- `(organisation_id, created_at)` — already in place per CLAUDE.md §14.3
- `(organisation_id, status, created_at)` — new index for the success-filtered queries
- `(organisation_id, request_type, created_at)` — new index for the request-type breakdown

Add these in a single migration. Use `EXPLAIN ANALYZE` on representative datasets (1k, 100k, 1M `AiUsageLog` rows) before shipping.

### 8.5 Performance Targets

- P95 page load (all five endpoints in parallel from the frontend) under 1.5 seconds for up to 1M `AiUsageLog` rows across the platform
- Cache hit ratio above 80% in steady state (Superadmin typically loads the same default view multiple times per day)

### 8.6 Display Conventions

- Costs: `$X.XX` with two decimal places. Amounts over `$1,000` get thousands separators.
- Token counts: abbreviated when large — `12.4M` for 12,400,000, `342K` for 342,000. Full number in tooltip on hover.
- Call counts: thousands separators, no abbreviation (counts under 100K are common and worth reading exactly).
- Dates: formatted per the user's locale (ISO default).

## 9. Acceptance Criteria

### 9.1 Access

1. Only Superadmin can access `/admin/ai-cost/` — other roles return 403
2. All API endpoints return 403 for non-Superadmin requests
3. Sidebar entry visible only for Superadmin

### 9.2 Main View

4. KPI cards render with correct totals for the selected date range
5. Organisations table lists only organisations with ≥1 AI call in the window
6. Organisations table sortable by every column; default descending by Cost
7. Request-type badges on each row sum to the row's total cost (within rounding)
8. Empty state renders when no AI activity exists in the window
9. Pagination works at 10 / 25 / 50 / 100 per page

### 9.3 Date-Range Filter

10. All filter options produce correct window boundaries (UTC-anchored)
11. Custom range with `from > to` returns 400
12. Custom range exceeding 365 days returns 400
13. Filter state persists across drill-down and back navigation

### 9.4 Drill-Down (Organisation Detail)

14. Clicking an org row navigates to `/admin/ai-cost/organisations/{org_id}/`
15. Org KPI cards scoped correctly to that org
16. Shops table lists only shops in this org with ≥1 AI call in window
17. Model breakdown table shows all models used by this org in the window
18. Back link returns to the main view with the same filter state

### 9.5 Data Correctness

19. Costs aggregate `SUCCESS`-only rows
20. API Call counts include all statuses; footer reports success vs failure split
21. Per-request-type breakdown sums match the per-org total
22. Per-shop sums (across all shops in an org) match the per-org total
23. Per-model sums (across all models in an org) match the per-org total

### 9.6 Performance

24. All endpoints have `CaptureQueriesContext` tests asserting a query-count ceiling
25. New indexes created via migration and verified with `EXPLAIN ANALYZE`
26. P95 full page load under 1.5 seconds at 1M `AiUsageLog` rows
27. Cache TTL is 10 minutes; Superadmin-scoped cache keys

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Aggregations over large `AiUsageLog` tables become slow | Required indexes (§8.4) address the common query shapes. Cache absorbs repeat loads. If the table grows past 10M rows, consider a materialised view or a nightly rollup table. |
| Per-shop drill-down requires joining through Review — slow at scale | Denormalise `shop_id` onto `AiUsageLog` in a future iteration. For now, the join is fine and the index on `AiUsageLog.review_id` + the `Review.shop_id` index together keep it fast enough. |
| Superadmin sees stale numbers due to 10-min cache | Acceptable for operational review. Not a billing-grade number. Documented in UI: small "Updated X min ago" label beside the filter. |
| Cost does not match what OpenAI actually charged us | `AiUsageLog.estimated_cost_usd` is computed from `AiPricing` at log time — can drift from OpenAI's actual invoice. Documented caveat in page footer: "Estimated based on configured pricing — actual OpenAI invoice is authoritative." |
| Failed calls hide real spend if they also cost money | OpenAI does not bill failed requests, so excluding them from cost is correct. Verify with a sanity check against the OpenAI billing dashboard once per month. |
| New request types added later break the badge rendering | Badge group renders whatever `request_type` values appear in the data — no hard-coded enum on the frontend. New types show up automatically. |
| Superadmin confused by missing shops | Filter wording is explicit ("shops that had AI calls in this period"). Shops with zero activity are intentionally hidden. |
