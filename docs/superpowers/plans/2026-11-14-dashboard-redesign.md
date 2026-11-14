# Dashboard Redesign ("night panels") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle every Dashboard report into the approved black-panel visuals and add the Spotlight insights strip, without losing any report or changing filters/permissions.

**Architecture:** Two existing dashboard endpoints gain the extra fields the new visuals need; the React dashboard widget's section components are rewritten (same hooks/API); the Spotlight fetches the Insights API built by the Insights plan. **Runs after** `docs/superpowers/plans/2026-11-14-insights-book.md`.

**Tech Stack:** Django/DRF, React + TypeScript, Tailwind v4, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-dashboard-redesign-design.md`

## Global Constraints

- Approved look: Dashboard A + S3 Spotlight in `.superpowers/brainstorm/63266-1794631467/content/dashboard-insights-v2.html`. Frontend-design + dataviz skills. Dark panel surface `#141414`, band `#0A0A0A`; marks: yellow `#FACC15`, grey `#52525B`, red `#F87171`; direct number labels on every mark; tooltips on ladder dots, tug bars, grid squares.
- Filters (region, store, period), endpoints' existing fields, permissions and Staff scoping unchanged. Top tags stay org-wide, all time, labelled "All stores, all time".
- Spotlight: Org Admin only; ignores dashboard filters; yellow block = top `attention` item (else top `good`); next two items as rows; "N more on the Insights page" link to `/admin/org/insights/`; hidden when there are no items.
- Previous period = same length immediately before the selected range; none for "all time". Trend = 6 equal buckets of the selected range; "all time" = last 6 calendar months.
- No horizontal overflow; panels stack under 1024px; ladder abbreviates long store names (ellipsis at 14 chars, full name in tooltip).

## Review Focus

1. "All time" period — no change lines rendered, trend uses 6 months, nothing shows "NaN%" (Task 1 + Task 3 tests).
2. A brand with only 1–2 qualifying stores — ladder still renders with the brand notch, no overlapping labels crash (Task 2 + Task 4 tests).
3. Staff user — no Spotlight request is made and no Spotlight renders (Task 5 test).
4. Zero reviews in range — every panel shows its existing empty state, star meter shows 0 filled, grid shows no squares with a "no reviews" note (Task 3/4 tests).
5. Insights API failing (500) — Spotlight hides, rest of the dashboard unaffected (Task 5 test).

---

### Task 1: `/kpis/` previous period, trend, oldest wait

**Files:** Modify `apps/dashboard/selectors/aggregations.py` (`dashboard_kpis`), `apps/dashboard/views.py` (serializer/schema), `apps/dashboard/tests/` (selector + view + query-count tests).

**Interfaces — Produces:** response gains `previous: {total_reviews, avg_rating, negative_pct, awaiting_reply} | null`, `trend: {total_reviews: number[6], avg_rating: (number|null)[6], negative_pct: (number|null)[6]}`, `oldest_awaiting_days: number | null`.

- [ ] **Step 1:** Failing tests: previous window equals the same length immediately before (7d, 30d, 90d, custom); `previous` is null for "all"; 6 trend buckets cover the range exactly (bucket edges asserted for a 30-day range) and for "all" are the last 6 calendar months; `oldest_awaiting_days` respects store/region filters and Staff scope; fixed query ceiling (state the measured number, ≤ 4).
- [ ] **Step 2:** Run `uv run pytest apps/dashboard -q -p no:cacheprovider --no-cov` → FAIL. **Step 3:** Implement with conditional aggregates (one query for current+previous, one grouped query for trend buckets, one for oldest). **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(dashboard): kpis previous period, trend and oldest wait`.

### Task 2: `/top-performing/` all stores

**Files:** Modify `apps/dashboard/selectors/aggregations.py` (`dashboard_top_performing`), views/schema, tests.

**Interfaces — Produces:** response gains `all_stores: [{shop_id, shop_name, avg_rating, review_count}]` (every qualifying store, same 3+ rule and date-only filtering, ordered by avg desc, capped at 200).

- [ ] **Step 1:** Failing tests: 12 qualifying stores → `shops` unchanged (top/bottom 5 split) and `all_stores` has 12; cap at 200; fixed query count. **Step 2–4:** FAIL → implement → PASS. **Step 5:** Commit `feat(dashboard): all qualifying stores for the rating ladder`.

### Task 3: Headline band (React)

**Files:** Modify `frontend/src/widgets/dashboard/KpiCards.tsx` (becomes the band; keep export name), `types.ts`; create `frontend/src/widgets/dashboard/StarMeter.tsx`, `Sparkline.tsx`; tests `KpiCards.test.tsx`.

**Interfaces — Consumes:** Task 1 fields. **Produces:** `StarMeter({ value: number, size?: number })` (5 stars, clip-filled to `value/5`, `aria-label="Average rating 4.3 out of 5"`); `Sparkline({ points: (number|null)[] })`.

- [ ] **Step 1:** Failing tests: four parts with total, average + star meter fill width 86% for 4.3, negative % + count (red), awaiting + "oldest N days"; change lines "+18% on last month"-style text derived from `previous` and hidden when null (Review Focus 1); zero-review state (Review Focus 4).
- [ ] **Step 2–4:** `cd frontend && npx vitest run src/widgets/dashboard` FAIL → implement → PASS. **Step 5:** Commit `feat(dashboard): headline band with star meter`.

### Task 4: Panels — sentiment grid, tag tug-of-war, rating ladder, highlights, Your Store

**Files:** Modify `SentimentDonut.tsx` (→ grid; keep export name or update the import in `DashboardWidget.tsx`), `TagPolarityChart.tsx`, `TopPerformingSection.tsx`, `PerformanceHighlights.tsx`, `YourStore.tsx`, `DashboardWidget.tsx` layout; tests per component.

- [ ] **Step 1:** Failing tests: grid renders 100 squares with counts rounded so they sum to 100 and the "from X analysed (Y%)" line; tug-of-war rows show left (negative) and right (positive) counts with widths proportional to the max; ladder places dots by rating, labels only top 5 / bottom 5, shows brand notch from the KPI average, works with 1–2 stores (Review Focus 2); highlight cards show badge, name, rating, counts; Your Store shows 5 bars with percentages; every existing empty/loading/error state still renders.
- [ ] **Step 2–4:** FAIL → implement (dark panels per the prototype) → PASS; `npm run build`. **Step 5:** Commit `feat(dashboard): night-panel visuals for every report`.

### Task 5: Spotlight strip

**Files:** Create `frontend/src/widgets/dashboard/Spotlight.tsx`, `useSpotlight.ts`; modify `DashboardWidget.tsx`; test `Spotlight.test.tsx`.

**Interfaces — Consumes:** `GET /api/v1/insights/` (Insights plan Task 4) → `items[]` with `chapter`, `headline`, `title`, `link`.

- [ ] **Step 1:** Failing tests: yellow block shows the top attention item's headline + title + action link; falls back to top good item; next two as rows with dots; "N more" shows `items.length − 3` and links to `/admin/org/insights/`; hidden with no items; not fetched or rendered for Staff (Review Focus 3); hidden when the API errors (Review Focus 5).
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** Commit `feat(dashboard): spotlight insights strip`.

### Task 6: Verification and close-out

- [ ] **Step 1:** Full checks: pre-commit, full pytest, makemigrations --check, vitest + build → pass.
- [ ] **Step 2:** (controller) Browser pass as Org Admin at 1440 / 1024 / 390 and as Staff; every report present; Spotlight links work.
- [ ] **Step 3:** Mark DASH-RD-01..03 `✅ Delivered`; commit `docs: dashboard redesign delivered`.
