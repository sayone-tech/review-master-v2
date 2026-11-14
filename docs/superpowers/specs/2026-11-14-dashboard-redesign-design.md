# Dashboard redesign ("night panels") — design

**Date:** 2026-11-14
**Status:** delivered
**Approved look:** Dashboard A ("night panels") with every existing report and the S3 "Spotlight" strip, from
`.superpowers/brainstorm/63266-1794631467/content/dashboard-insights-v2.html` (local, not committed).
**Depends on:** `2026-11-14-insights-book-design.md` (the Spotlight reads the Insights snapshot).

## 1. Intent

Replace the Dashboard's traditional charts with brand-made visuals in the black + yellow look, without losing any
report that exists today, and surface the top insights at the top.

## 2. Goals

Keep the existing filter bar (region, store, period), data, endpoints and permissions. Restyle every section:

1. **Spotlight strip** (top, Org Admin only — Staff do not see it):
   a yellow block with the single top "Needs attention" insight's number and line plus its action link, and beside it
   (black) the next two insights as one-line rows with coloured dots and links, and "N more on the Insights page".
   Reads the latest Insights snapshot; hidden when there are no insights. Not affected by the dashboard filters
   (it is brand-wide, last 30 days).
2. **Headline band** (one black band, 4 parts) — today's KPI tiles:
   total reviews (+ small 6-point trend line and change vs previous period), average rating (number + **star meter**
   filled to the exact value + change), negative reviews (% and count, red, change), awaiting reply (count, yellow,
   oldest wait).
3. **Sentiment** (black panel) — today's donut becomes a **100-square grid** (positive yellow, neutral grey,
   negative red) with "67 positive, 21 neutral, 12 negative" and "from X analysed (Y%)".
4. **Top tags** (black panel) — today's tag polarity chart becomes the **tug-of-war**: tag name centred, complaints
   bar to the left (red), praise bar to the right (yellow), counts at both ends; same tags and data as today.
5. **Best and weakest stores** (black panel) — today's top 5 / bottom 5 bar chart becomes the **rating ladder**: one
   3★–5★ line, each qualifying store a dot, brand-average notch, top 5 labelled above (yellow), bottom 5 below (red),
   others as small grey dots; same "3+ reviews" rule and date-only filtering as today.
6. **Top performer / Needs attention** — today's highlight cards, restyled as two dark cards with yellow / red badges.
7. **Your Store** (single-store organisations, replaces 5–6 as today) — star breakdown as 5 vertical bars (5★–1★)
   with percentages, dark panel.
8. Empty, loading and error states for each section keep today's behaviour, restyled for the dark panels.
9. Hover tooltips on the ladder dots, tug-of-war bars and grid (per dataviz interaction rules); numbers are always
   also printed, so nothing is colour-only.

### 2.10 Data additions the new visuals need (builder check, decided by me)

- **`/kpis/` gains** (same filters as today): `previous` totals for the same-length window immediately before the
  selected range (none for "all time" → no change line shown), a 6-point `trend` per headline number (the selected
  range split into 6 equal buckets; for "all time", the last 6 calendar months), and `oldest_awaiting_days` (oldest
  unreplied review in the filtered set). Query-count test updated to a new fixed ceiling.
- **`/top-performing/` gains** an `all_stores` list (every qualifying store with its average, capped at 200 dots);
  top 5 / bottom 5 stay as today and are the only labelled dots; the brand-average notch uses the KPI average for the
  same date range.
- **Top tags** stay as today: organisation-wide and not affected by the dashboard filters. The panel says so
  ("All stores, all time").
- **Staff:** see the band and panels scoped to their stores, exactly as today; only the Spotlight is hidden.
- **Single-store organisations:** same as today (band, sentiment, tags, and "Your store" instead of the ladder and
  highlight cards); the Spotlight shows for their Org Admin.
- **Build order:** Insights ships first; the Spotlight reads the Insights snapshot through the reader that spec
  defines (top items with chapter, headline number, title, link; total count).

## 3. Non-goals

- New filters; new endpoints (only the fields above are added to existing ones).
- The Insights page itself (separate spec).

## 4. Constraints

- Same React widget (`frontend/src/widgets/dashboard/`), same hooks/API; visuals rewritten. Frontend-design + dataviz
  skills. Palette validated (dark surface): yellow #FACC15, grey #52525B, red #F87171 — direct labels on every mark.
- No horizontal overflow; panels stack on narrow screens (ladder labels may abbreviate store names).
- Backend changes limited to §2.10 plus the Spotlight read (reuses the Insights snapshot reader).

## 5. Decided by me (owner can override)

- Spotlight for Org Admin only; it ignores dashboard filters; the top "Needs attention" insight goes in the yellow
  block (if there is none, the top Good news one).
- Ladder shows all qualifying stores as dots but names only top 5 / bottom 5 (matches today's report).
