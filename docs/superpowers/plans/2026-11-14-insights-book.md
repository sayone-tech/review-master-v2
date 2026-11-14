# Insights ("the book") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily, rule-based insight snapshot per organisation and an Org-Admin-only dark "book" page that pages through up to 8 insights, each linking to the exact reviews behind it.

**Architecture:** New app `apps/insights/` owns a `InsightSnapshot` model (one JSON payload per org per day), pure rule functions that each return candidate insights from aggregate queries, a ranking/build service, a thin daily Celery task, and a selector `get_latest_insights` that resolves names and drops stale items at read time. A DRF endpoint serves the selector; a Vite React island renders the book. The Reviews page learns `tags`, `rating`, `replied` URL params.

**Tech Stack:** Django 6 / DRF, Celery + django-celery-beat, PostgreSQL JSONField, React + TypeScript (Vite island), Tailwind v4 tokens, Vitest, pytest + factory-boy.

**Spec:** `docs/superpowers/specs/2026-11-14-insights-book-design.md`

## Global Constraints

- Org Admin only (page, menu item, API). Active shops only; non-deleted reviews; every query filtered by `organisation_id` (CLAUDE.md §9/§22).
- Window: *now* = 30 full UTC days ending yesterday; *before* = the 30 full UTC days before that (by `review_create_time`). Snapshot daily at 02:00 UTC, `default` queue, DB-only (no OpenAI, no credits).
- Negative review = `sentiment == "negative"`. A tag mention = a distinct review with a `ReviewTag` whose `label` iexact the tag text **or** whose `canonical_tag.label` iexact it (Ruling: same rule as the Reviews tag filter after Task 5, so link and number match).
- Insight types, thresholds, headlines, visuals and links exactly as spec §2.4 table + §2.7; chapters `attention` / `good`; at most 2 per type, at most 8 total, attention first, then by score (§4).
- Snapshot stores ids + numbers + title templates with `{store}` / `{tag}` placeholders; names resolved at read; items whose store is inactive/missing or tag text no longer matches any review are dropped at read.
- Book UI per the approved prototype `.superpowers/brainstorm/63266-1794631467/content/insights-book.html` (option A): yellow cover, spread = visual left / story right, 3D turn ~0.9 s, swipe ≥ 40 px, ‹ › and ← →, chapter tabs, page edges, end page, empty state, phones < 768 px single page, reduced motion = instant, aria-live title announcement. Brand: #FACC15 / #0A0A0A / red #F87171 on dark; Geist; sentence case; frontend-design + dataviz skills.
- Copy (verbatim): empty state "Not enough new reviews yet to spot changes. Insights appear once your stores have more reviews in the last 30 days."; end page "That's all for now" / "New insights arrive as new reviews come in."

## Review Focus

1. An organisation with zero active shops or zero reviews — snapshot is empty, page shows the empty state, nothing crashes (Task 3 test).
2. A store deactivated after the snapshot ran — its insights disappear from the book on the next read, cover counts drop accordingly (Task 4 test).
3. Ties and caps — 3 qualifying "complaint rising" insights → only the top 2 kept; 12 qualifying insights → 8 shown, attention first (Task 3 test).
4. Clicking an insight link — the Reviews page loads with store/tag/rating/sentiment/replied/from/to applied and its count equals the insight's number for the same data (Task 5 test + controller browser check).
5. Running the snapshot task twice on the same day — one snapshot row (update in place), no duplicate (Task 3 test).

---

### Task 1: App, model, requirements check

**Files:** Create `apps/insights/{__init__,apps,models,admin}.py`, `apps/insights/migrations/0001_initial.py`, `apps/insights/tests/{__init__,factories,test_models}.py`. Modify `config/settings/base.py` (INSTALLED_APPS).

**Interfaces — Produces:** `InsightSnapshot(organisation: FK Organisation on_delete=CASCADE, computed_for: date, window_from: date, window_to: date, payload: JSONField(default=dict), created_at, updated_at)`; `Meta.constraints = UniqueConstraint(organisation, computed_for, name="insight_snapshot_org_day")`; index `(organisation, -computed_for)`. Read-only Django admin. `InsightSnapshotFactory`.

- [ ] **Step 1:** Failing test `test_one_snapshot_per_org_per_day` (second create same org/day raises IntegrityError) and `test_latest_index_exists` (Meta indexes include the org/-computed_for index).
- [ ] **Step 2:** Run `uv run pytest apps/insights -q -p no:cacheprovider --no-cov` → FAIL.
- [ ] **Step 3:** Implement; `uv run python manage.py makemigrations insights` (name the migration `0001_initial`), verify reversible (`migrate insights zero` then forward on a scratch DB in tests is fine).
- [ ] **Step 4:** Run → PASS; `uv run python manage.py makemigrations --check --dry-run` → no changes.
- [ ] **Step 5:** Commit `feat(insights): snapshot model`.

---

### Task 2: Rule functions (types 1–8)

**Files:** Create `apps/insights/services/windows.py`, `apps/insights/services/rules.py`, `apps/insights/tests/test_rules.py`.

**Interfaces — Produces:**
- `Window(now_from: date, now_to: date, before_from: date, before_to: date)` and `windows_for(today: date) -> Window` (now = today−30 … today−1; before = today−60 … today−31).
- `Candidate` (frozen dataclass): `type: int`, `chapter: Literal["attention","good"]`, `score: float`, `headline: str`, `title: str` (template with `{store}`/`{tag}`), `body: str` (template), `visual: dict`, `link: dict` (query params incl. `from`/`to`), `store_id: int | None`, `tag_text: str | None`, `review_count: int`.
- One function per type, all `(*, organisation_id: int, window: Window) -> list[Candidate]`: `complaint_rising`, `waiting_negative`, `store_below_brand`, `five_star_share_change`, `reply_rate_change`, `best_month`, `new_tag`, `volume_drop`.
- Visual dict kinds: `before_now` {before, now}, `waiting_days` {days: list[int] ≤10}, `rating_line` {store: float, brand: float}, `share_line` {points: list[float] 6}, `progress` {before, now}, `monthly_bars` {points: list[float] 6}, `store_bars` {items: list[{store_id, count}]}.

- [ ] **Step 1: Failing tests** (factories: OrganisationFactory, ShopFactory, ReviewFactory, ReviewTagFactory, OrgCanonicalTagFactory; freeze `today` by passing it):
  - each type: fires exactly at its threshold and not one below (e.g. complaint rising: now 5 / before 2 → fires; now 4 → no; now 5 / before 3 → no); headline/visual/link values exactly as spec (e.g. `{"store": shop.id, "tags": "Wait time", "sentiment": "negative", "from": "...", "to": "..."}`);
  - inactive shops, deleted reviews and other organisations are never counted (one test per concern, across all rules via a parametrised fixture);
  - tag mention matching: a review whose raw label is "long wait" but canonical tag "Wait time" counts for "Wait time";
  - `test_each_rule_runs_in_fixed_queries` — CaptureQueriesContext, 2 shops vs 6 shops → equal count, ≤ 4 per rule.
- [ ] **Step 2:** Run `uv run pytest apps/insights/tests/test_rules.py -q -p no:cacheprovider --no-cov` → FAIL.
- [ ] **Step 3:** Implement with grouped aggregates (`values(...).annotate(Count/Avg, filter=Q(...))`); one helper `_mention_q(tag_text)` = `Exists(ReviewTag(review=OuterRef pk) & (label__iexact | canonical_tag__label__iexact))`. Copy templates, e.g. type 1 title "{tag} complaints doubled at {store}" when ratio ≥ 2 and < 3, "tripled" ≥ 3, else "{tag} complaints up {pct}% at {store}"; body "{now} reviews mentioned {tag_lower} in the last 30 days, up from {before}."
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(insights): rule functions for the eight insight types`.

---

### Task 3: Ranking, snapshot service, daily task

**Files:** Create `apps/insights/services/build.py`, `apps/insights/tasks.py`, `apps/insights/migrations/0002_beat_daily_insights.py`, `apps/insights/tests/test_build.py`. Modify `config/settings/base.py` (CELERY_TASK_ROUTES), CLAUDE.md §12.5 Beat table (one row).

**Interfaces — Consumes:** Task 2. **Produces:** `rank(candidates: list[Candidate]) -> list[Candidate]`; `build_snapshot(*, organisation_id: int, today: date) -> InsightSnapshot` (update_or_create on (org, today); payload = `{"cover": {"reviews", "stores", "attention", "good"}, "items": [Candidate as dict ...]}`; deletes this org's snapshots older than 14 days); `compute_all_insights() -> int` (orgs with ≥1 active shop); task `apps.insights.tasks.compute_daily_insights_task` (thin, `default` queue, standard retry settings); Beat `insights_compute_daily` at 02:00 UTC seeded by reversible data migration (pattern: `apps/credits/migrations/0003_beat_credit_lapse.py`).

- [ ] **Step 1: Failing tests:** score order attention-first then score desc; ties → higher review_count first; max 2 per type; max 8; `build_snapshot` idempotent same day (one row, updated payload) (Review Focus 5); empty org → payload items `[]` and cover zeros (Review Focus 1); 14-day retention; task calls the service (mock-free: run eagerly, assert snapshot exists); migration seeds the PeriodicTask (query django_celery_beat).
- [ ] **Step 2:** Run `uv run pytest apps/insights -q -p no:cacheprovider --no-cov` → FAIL.
- [ ] **Step 3:** Implement; scoring per spec §4 with type weights `{2: 1.3, 1: 1.2, 3: 1.1}` (others 1.0).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(insights): ranking, daily snapshot and beat schedule`.

---

### Task 4: Reader, API, page, menu item

**Files:** Create `apps/insights/selectors.py`, `apps/insights/serializers.py`, `apps/insights/views.py`, `apps/insights/urls.py`, `templates/insights/book.html`, `apps/insights/tests/test_selectors.py`, `test_views.py`. Modify `config/urls.py`, `apps/common/navigation.py` (Org Admin "Customer feedback": add `NavItem("Insights", "/admin/org/insights/", "book-open")` after Reports), `apps/common/tests/test_navigation.py`, `config/settings/base.py` (throttle `insights: "120/minute"`).

**Interfaces — Produces:** `get_latest_insights(*, organisation_id: int) -> InsightsBook | None` (dataclass: `cover`, `window_from`, `window_to`, `items: list[dict]` with `title`/`body` rendered and `link` including resolved tag text; drops items whose store is inactive/missing; recomputes cover attention/good counts after drops); `GET /api/v1/insights/` (name `insights-book`, `IsOrgAdmin`, ScopedRateThrottle `insights`) → `{"cover": {...}, "window": {"from","to"}, "items": [...]} | {"cover": null, "items": []}`; page `/admin/org/insights/` (name `org_insights`, `org_admin_required`, `page_title="Insights"`, mounts `#insights-root` + vite entry `src/entrypoints/insights.tsx`).

- [ ] **Step 1: Failing tests:** reader resolves names into titles; drops an item whose store was deactivated after the snapshot and fixes cover counts (Review Focus 2); returns None without a snapshot; other org's snapshot never returned; endpoint 200 shape for Org Admin, 403 Staff, 403 Superadmin, unauthenticated rejected; query count fixed ≤ 4; nav: Org Admin sees Insights after Reports, Staff does not; page 200 Org Admin / 403-or-redirect Staff (match reports page behaviour).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement (OpenAPI `extend_schema`). **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(insights): reader, API and page`.

---

### Task 5: Reviews page link params + tag filter matches canonical tags

**Files:** Modify `frontend/src/widgets/review-management/useReviews.ts` (`parseUrlParams`), `apps/reviews/filters.py` (`filter_tags`), tests: `frontend/src/widgets/review-management/useReviews.test.ts` (create if absent), `apps/reviews/tests/test_filters.py` (or the existing filter test module).

**Interfaces — Produces:** URL params on `/admin/org/reviews/`: `tags` (comma list → `filters.tags`), `rating` (1–5 → `filters.rating`), `replied=false|true` (→ `filters.is_replied`), plus existing `store`, `sentiment`, `from`, `to`. `filter_tags` per label matches `Q(label__iexact=l) | Q(canonical_tag__label__iexact=l)` inside the existing `Exists` (Ruling: links and insight counts use one definition; broadens tag filtering to synonyms, which is intended).

- [ ] **Step 1: Failing tests:** each new param parses and invalid values are ignored (`rating=9`, `replied=maybe`); `filter_tags("Wait time")` returns a review tagged raw "long wait" whose canonical is "Wait time" and still matches raw labels; query count of the reviews list unchanged.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run `cd frontend && npx vitest run src/widgets/review-management` and `uv run pytest apps/reviews -q -p no:cacheprovider --no-cov` → PASS.
- [ ] **Step 5:** Commit `feat(reviews): link params for insights and canonical tag matching`.

---

### Task 6: The book (React)

**Files:** Create `frontend/src/entrypoints/insights.tsx`, `frontend/src/widgets/insights/{api.ts,types.ts,InsightsBook.tsx,Spread.tsx,Visual.tsx,useBook.ts,index.ts}`, `frontend/src/widgets/insights/InsightsBook.test.tsx`. Modify `frontend/vite.config.ts` (entry), `frontend/src/widgets/insights` only otherwise.

**Interfaces — Consumes:** Task 4 API shape. **Produces:** `useBook(total: number)` → `{ page, next, prev, jump(chapterStart) }` (page 0 = cover, 1..N = spreads, N+1 = end); `Visual({visual})` renders the 7 visual kinds as SVG with number labels; links built with `URLSearchParams` from `item.link` to `/admin/org/reviews/?…`.

- [ ] **Step 1: Failing tests** (mock `fetch` only): cover shows organisation copy and counts; next/prev buttons and ← → keys move pages; swipe (pointerdown/up dx < −40) goes next; chapter tab jumps to first "good" item and is highlighted only in its chapter; a chapter with no items has no tab; end page copy; empty state copy when `items` is empty; every visual kind renders its numbers; links contain the exact params; reduced-motion media → no transition class; at width < 768 (matchMedia mock) one page per step.
- [ ] **Step 2:** Run `cd frontend && npx vitest run src/widgets/insights` → FAIL.
- [ ] **Step 3:** Implement following the prototype's CSS (port into Tailwind classes + a small CSS module for the 3D leaf), frontend-design + dataviz skills.
- [ ] **Step 4:** Run → PASS; `npm run build` OK.
- [ ] **Step 5:** Commit `feat(insights): book page`.

---

### Task 7: Verification and close-out

- [ ] **Step 1:** `uv run pre-commit run --all-files`, `uv run pytest -q -p no:cacheprovider`, `uv run python manage.py makemigrations --check --dry-run`, `cd frontend && npx vitest run && npm run build` → all pass.
- [ ] **Step 2:** (controller) Run `compute_all_insights()` against local data, open `/admin/org/insights/` as Org Admin at 1440 and phone width: cover, page turns, tabs, a link opening Reviews with matching count (Review Focus 4); Staff cannot see it.
- [ ] **Step 3:** Mark INSIGHT-01..04 `✅ Delivered`; update CLAUDE.md §3 app list (insights) and §12.5 Beat table if not done; commit `docs: insights delivered`.
