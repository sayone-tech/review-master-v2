# Insights ("the book") — design

**Date:** 2026-11-14
**Status:** draft for owner review
**Approved look:** the book prototype, option A in `.superpowers/brainstorm/63266-1794631467/content/insights-book.html`
(local, not committed): yellow cover, one spread per insight, real page turn, chapter tabs, page edges.

## 1. Intent

Organisation Admins should see what matters about their brand without digging through reviews: a handful of short,
true, plain-language facts ("Wait time complaints doubled at Kochi"), each with a comparison and a link to the reviews
behind it. Presented as a dark book you page through, so it reads like a monthly briefing rather than another report.

Success: an Org Admin opens Insights, reads the cover and a few spreads in under a minute, and clicks through to act
(reply, look at a store's reviews). Every number on a page is correct and traceable to the linked reviews.

## 2. Goals

1. **Page:** new sidebar item **Insights** in the *Customer feedback* group (after Reports), URL `/admin/org/insights/`,
   **Organisation Admin only** (Staff: not in the menu, direct URL → 403/redirect like other Org-Admin-only pages).
   No filters: always all **active** stores of the organisation; always **the last 30 days vs the 30 days before**
   (by `Review.review_create_time`; exact window in §2.7; non-deleted reviews).
2. **The book** (dark, inside the existing black frame):
   - **Cover** (yellow page): "<Organisation name>, this month" and "N things worth knowing from X reviews across
     Y stores", plus "A need attention, B good news" and "Turn the page".
   - **One spread per insight:** left page = big headline number + a small visual + one-line caption; right page =
     chapter label ("● Needs attention" red / "★ Good news" yellow), title, 1–2 sentence explanation with the
     comparison, one action button, the store name (or "All stores") and "k / N".
   - **End page:** "That's all for now. New insights arrive as new reviews come in."
   - **Page turn:** real 3D turn around the spine (~0.9 s); swipe/drag (≥40 px), ‹ › buttons, ← → keys when the book
     has focus; position label ("Cover", "Insight k of N", "End").
   - **Chapter tabs** on the right edge: "Needs attention" (red) and "Good news" (yellow); the current chapter's tab
     is highlighted; clicking jumps to that chapter's first insight. A chapter with no insights has no tab.
   - **Page edges:** stacked paper on each side shows how much is read / left (max 6 layers per side).
   - **Phones (< 768 px):** one page at a time (left then right page of each spread), same turn animation.
   - **Reduced motion:** turns switch instantly. Keyboard focus visible; the book has an accessible name; each spread
     is announced (aria-live polite) with its title.
   - **Empty state** (no insight qualifies): cover replaced by a page saying "Not enough new reviews yet to spot
     changes. Insights appear once your stores have more reviews in the last 30 days."
3. **Order:** "Needs attention" insights first, then "Good news"; within each chapter by score (§4). **At most 8.**
4. **Insight types (v1)** — each has a rule, a minimum sample, a headline number, a visual and a link:

| # | Type | Chapter | Fires when (last 30 d = *now*, prior 30 d = *before*) | Headline | Visual | Link |
|---|---|---|---|---|---|---|
| 1 | Complaint rising at a store | Needs attention | reviews at one store mentioning a canonical tag with negative sentiment: now ≥ 5 and now ≥ 2 × before | "2×" (ratio, 1 dp) | before/now bars | Reviews: that store + that tag |
| 2 | Negative reviews waiting for a reply | Needs attention | ≥ 3 negative-sentiment reviews in *now* with `is_replied = false` | count | bars of days waiting per review (max 10) | Reviews: not replied + negative |
| 3 | Store well below brand | Needs attention | a store with ≥ 10 reviews *now* whose average is ≥ 0.5★ below the brand average *now* | "−0.7★" | rating line with brand notch + store dot | Reviews: that store |
| 4 | 5-star share change at a store | Good news if up, Needs attention if down | store with ≥ 10 reviews in both windows and the 5-star share changed by ≥ 10 points | "62%" | 6-month share line | Reviews: that store, rating 5 |
| 5 | Reply rate change (brand) | Good news if up, Needs attention if down | ≥ 20 reviews in both windows and the reply rate changed by ≥ 10 points | "92%" | progress bar with "before" marker | Reviews: (up) all / (down) not replied |
| 6 | Store's best month | Good news | store with ≥ 10 reviews *now* whose *now* average is its highest of any 30-day window in the last 6 months (≥ 3 windows with ≥ 10 reviews) | "4.5★" | 6 monthly bars, latest highlighted | Reviews: that store |
| 7 | New tag | Needs attention if mostly negative, else Good news | a canonical tag with ≥ 5 mentions *now* and 0 *before* (and never before in the last 6 months) | count | mentions per store (small bars) | Reviews: that tag |
| 8 | Review volume dropped at a store | Needs attention | store with ≥ 10 reviews *before* and *now* ≤ 50 % of *before* | "−55%" | before/now bars | Reviews: that store |

   Copy is plain and specific (store and tag names, both numbers), e.g. "Wait time complaints doubled at Kochi" /
   "9 reviews mentioned wait time in the last 30 days, up from 4."
5. **Computation:** once a day per organisation (Celery Beat, `default` queue), DB-only (no OpenAI, no credits),
   results stored (one snapshot per organisation per day: the ranked list of insights with all numbers needed to
   render, plus cover totals). The page reads the latest snapshot; a new organisation without a snapshot shows the
   empty state. A per-organisation "refresh" happens automatically on the next run — no manual button in v1.
6. **Links** open the Reviews page with the matching filters pre-applied **and the insight's date window pinned**
   (`from`/`to`), so the page shows exactly the reviews the number counted (small drift from replies or syncs since the
   snapshot is acceptable). The Reviews page today reads only `store`, `sentiment`, `from`, `to` on load; add `tags`,
   `rating` and `replied` (`false`) URL parameters, mapped to its existing filters. No new filter types are added, so
   every insight is defined in terms of filters the Reviews page already has (§2.7).
7. **Definitions that keep numbers and links identical (decided by me):**
   - *Window:* "last 30 days" = the 30 full UTC days ending yesterday; "before" = the 30 full UTC days before that.
     The snapshot runs daily at 02:00 UTC.
   - *Negative review* = `sentiment = "negative"` (rating is not used), matching the Reviews sentiment filter.
     Type 2 therefore counts negative-sentiment, unreplied reviews; its link is `sentiment=negative&replied=false`.
   - *Mentions of a tag* = distinct reviews having a `ReviewTag` whose own label or whose canonical tag's label equals
     the tag (case-insensitive). The Reviews tag filter is changed to match the same way, so links and numbers agree.
   - *Type 1 (complaint rising)* counts reviews at the store that mention the tag **and** have negative sentiment; its
     link is `store + tags + sentiment=negative + window`.
   - *Type 7 (new tag)* counts reviews mentioning the tag; it is "Needs attention" when most of those reviews are
     negative-sentiment, otherwise "Good news"; link `tags + window`.
   - Type 4 links to the store with `rating=5` in both directions (the share being discussed); types 3, 6 and 8 link
     to the store + window.
8. **Snapshot contents:** store ids and canonical tag ids plus the numbers; store and tag **names are resolved when the
   page is read**. At read time, insights whose store is now inactive or whose tag no longer exists (e.g. merged) are
   dropped. Numbers may be up to a day old.
9. **Reader (also used by the Dashboard Spotlight):** a selector `get_latest_insights(*, organisation_id) ->
   InsightsBook | None` returning the cover totals (reviews, stores, counts per chapter, window dates) and the ranked
   items (type, chapter, headline value, title, body, visual data, link query params, store/tag names). Reads only the
   caller's organisation.
10. **Access:** Organisation Admin only. Superadmins do not use `/admin/org/` pages today and do not get this page.

## 3. Non-goals

- Filters, date pickers, store selection on the Insights page; Staff access.
- AI-written text, emails/notifications, dismissing or saving insights, history of past books.
- The Dashboard "Spotlight" strip (separate spec: `2026-11-14-dashboard-redesign-design.md`), though it reads the same
  snapshot.

## 4. Ranking (my call)

Score = how far past its threshold the insight is, normalised per type (e.g. type 1: now/before ratio ÷ 2; type 3:
gap ÷ 0.5★; type 2: count ÷ 3 + oldest days ÷ 7), multiplied by a small type weight so "waiting for a reply" (2) and
"complaint rising" (1) lead. Ties: more reviews behind the insight first. Max 2 insights of the same type; max 8
total. Exact weights are the builder's to tune with tests.

## 5. Anti-goals

- A number on a page that doesn't match what the link shows (counts must use the same filters as the link).
- Insights from tiny samples ("+50%" from 2 reviews) — every rule has the minimums above.
- Leaking data across organisations or including inactive shops, deleted reviews.
- Slow page loads: the page only reads the stored snapshot (fixed small number of queries).

## 6. Constraints

- CLAUDE.md: requirements first (add `INSIGHT-01..04` to `.planning/REQUIREMENTS.md`), services/selectors (§5),
  no N+1 and aggregate queries with query-count tests (§6), tenant scoping (§9), thin Celery task + Beat schedule
  seeded by data migration (§12), explicit permission + throttle on any endpoint (§8), new model fields with index
  decisions (§24), React widget per the Vite-island pattern (§27 `frontend-react-builder`).
- Design: frontend-design skill + dataviz skill; brand tokens (yellow #FACC15, black #0A0A0A, Geist); red for
  "needs attention" (#F87171 on dark), yellow for good news; every visual has number labels.

## 7. Decided by me (owner can override)

- Org Admin only; last 30 days vs prior 30; daily computation; max 8; thresholds and minimums in §2.4; ranking in §4;
  phones show single pages; empty-state copy.

## 8. Left to the builder

- Storage shape of the snapshot (a model with a JSON payload per org per day is fine), retention (keep e.g. 14 days).
- Exact visuals' SVG drawing within the prototype's look.
