# Requirements — v0.10 AI Cost & Pricing (Superadmin)

**Planned via:** superpowers brainstorming → writing-plans (not the GSD flow).
**Design (authoritative where it differs from the specs):** `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md`
**Specs:** `docs/completed/Requirements_AI_Cost_Explorer.md` (CE §n) · `docs/completed/Requirements_AI_Pricing_Management.md` (PM §n)

Acceptance criteria are the numbered criteria in each spec's Acceptance Criteria
section, as amended by the design doc.

**Status:** ✅ all v0.10 requirements delivered (Phases 34–36, 2026-11-12) — milestone
complete, pending merge of `feat/v0.10-ai-cost-pricing`. Specs moved to `docs/completed/`.

## Phase 34 — AI Cost Explorer

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| COST-01 | Superadmin-only page `/admin/ai-cost/` + sidebar entry; all APIs under `/api/v1/superadmin/ai-cost/` return 403 for other roles | CE AC 1–3; design §4.4–4.5 | ✅ Delivered |
| COST-02 | Date-range filter (this month default, last month, 7/30/90 d, custom ≤365 d), UTC-anchored, persists across drill-down | CE AC 10–13 | ✅ Delivered |
| COST-03 | Platform KPI cards: cost, calls (success/failed/moderated split), input tokens, output tokens | CE AC 4; design §4.1–4.2 | ✅ Delivered |
| COST-04 | Organisations table: active orgs only, sortable, paginated, request-type cost badges | CE AC 5–9 | ✅ Delivered |
| COST-05 | Org drill-down: scoped KPIs, shops table with "Unattributed" row, cost-by-model table | CE AC 14–18; design §4.3 | ✅ Delivered |
| COST-06 | Data correctness: cost/tokens from SUCCESS only, calls from all statuses; type/shop/model breakdowns sum to org total | CE AC 19–23 as amended by design §4.2–4.3 | ✅ Delivered |
| COST-07 | Performance: fixed query-count tests per endpoint, index migration verified with EXPLAIN ANALYZE, 10-min cache, throttled endpoints | CE AC 24–27; design §4.8 | ✅ Delivered |

## Phase 35 — AI Pricing Page + Gap Detection

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| PRICE-01 | Superadmin-only page `/admin/ai-pricing/` + sidebar entry; APIs under `/api/v1/superadmin/ai-pricing/` | PM AC 1–3 | ✅ Delivered |
| PRICE-02 | Current prices table (one active row per model, 6-dp display, empty state) | PM AC 4–6 | ✅ Delivered |
| PRICE-03 | Add New Price: validation (0–1000), no backdating (5 s grace), locked close-current + insert in one transaction, audit entry | PM AC 7–12; design §5.6–5.7 | ✅ Delivered |
| PRICE-04 | Model autocomplete with unpriced models first + free-text entry + pre-fill from alert | PM AC 13–15 | ✅ Delivered |
| PRICE-05 | History view per model with source + who set it; delete only future-dated rows (reopens previous); at most one scheduled price per model; time-aware active-price lookup | PM AC 16–18; design §5.8–5.9 | ✅ Delivered |
| PRICE-06 | Platform-level audit events in `AuditLog` (nullable organisation), never visible to tenants | PM §8, AC 39; design §5.4 | ✅ Delivered |
| GAP-01 | Missing-pricing detection (90-day window + configured `OPENAI_MODEL`, known-free exemption, 10-min cache, rate-limited refresh) | PM AC 30–31, 35–36, 41; design §5.10 | ✅ Delivered |
| GAP-03 | Configured `OPENAI_MODEL` must have an active price: system check (Error) in `check --deploy --database default`; sync model set includes it | design §5.10 | ✅ Delivered |
| GAP-02 | Missing-pricing alert bar on AI Pricing and AI Cost Explorer pages | PM AC 32–34 | ✅ Delivered |

## Phase 36 — LiteLLM Auto-Sync

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| SYNC-01 | DB-backed sync config (off by default), toggle endpoint + audit | PM AC 19–20; design §5.2 | ✅ Delivered |
| SYNC-02 | Weekly Beat task (DB-seeded, Mon 09:00 UTC) with Case A/B/C behaviour, exact match, failure changes nothing; never overwrites a hand-set price | PM AC 21–26, 40; design §5.3, §5.11 | ✅ Delivered |
| SYNC-03 | Sync status banner (green/grey/amber overdue), manual "Sync Now" rate-limited 1/15 min | PM AC 27–29 | ✅ Delivered |
| SYNC-04 | Cost Explorer footer caveat shows sync status | PM §11 | ✅ Delivered |

## Cross-cutting

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| XCUT-01 | Historical `AiUsageLog.estimated_cost_usd` never altered | PM AC 38 | ✅ Delivered |
| XCUT-02 | Query-count tests on every endpoint; OpenAPI schema updated | PM AC 37; CLAUDE.md §24 | ✅ Delivered |

## Post-v0.10 changes

| ID | Requirement | Acceptance | Status |
|---|---|---|---|
| ORG-TYPE-01 | Organisation types: add Clinic, Hospital, Salon, Spa, Hotel & Resort, Gym & Fitness; relabel Restaurant → "Restaurant & Cafe" (stored value unchanged) | owner request 2026-11-13 | ✅ Delivered |
| CRED-INACTIVE-01 | Credit allocation skips inactive shops: Edit Organisation never creates or raises balances for inactive shops; a reactivated shop gets its allocation on first use. AI reply generation is blocked for inactive shops (server + UI): 409 `shop_inactive`, no balance/reservation/OpenAI call; manual replies unchanged. Reviews of inactive shops are hidden from the Reviews list, its stat cards and review actions (matches the Store filter and dashboard) | owner request 2026-11-13 | ✅ Delivered |
| UI-NAV-01 | Black frame shell + grouped, foldable sidebar and dark header for all three roles (spec §2.1–2.5, §2.8) | spec docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md | ✅ Delivered |
| UI-NAV-02 | Reviews / Action items badges scoped per spec §2.6, §4 | spec docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md | ✅ Delivered |
| UI-NAV-03 | AI-credits meter: sum over the person's active shops (spec §2.7, §4) | spec docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md | ✅ Delivered |
| UI-NAV-04 | Profile menu in the header (dark panel, option B); Profile and Log out removed from the sidebar | spec docs/superpowers/specs/2026-11-13-sidebar-header-redesign-design.md | ✅ Delivered |
| UI-NAV-05 | Pages inside the black frame no longer repeat their title as a page heading; the header title is the page title, with the list count shown next to it | owner decision 2026-11-13 | ✅ Delivered |
| UI-FILTER-01 | Compact shared filter toolbar (search + 3 quick filters + "More filters" panel + removable chips) on Reviews, Action items and Reports (spec §2.1–2.4, 2.6–2.7) | spec docs/superpowers/specs/2026-11-13-compact-filter-toolbar-design.md | ✅ Delivered |
| UI-FILTER-02 | Reviews slim number bar replacing the stat cards (spec §2.5) | spec docs/superpowers/specs/2026-11-13-compact-filter-toolbar-design.md | ✅ Delivered |
| UI-FILTER-03 | Shops and Team: add button moved into the existing search/filter row (Shop limit note before Add Shop) (spec §2.8) | spec docs/superpowers/specs/2026-11-13-compact-filter-toolbar-design.md | ✅ Delivered |
| INSIGHT-01 | Daily per-organisation insight snapshot: 8 rule-based insight types (spec §2.4, §2.7), thresholds/minimums, ranking, max 8, no AI | spec docs/superpowers/specs/2026-11-14-insights-book-design.md | ✅ Delivered |
| INSIGHT-02 | Insights page (Org Admin only, sidebar under Customer feedback): dark book with cover, one spread per insight, page turn, chapter tabs, page edges, empty state, phone single-page | spec §2.1–2.3 | ✅ Delivered |
| INSIGHT-03 | Insight links pin the window and filters; Reviews page accepts `tags`, `rating`, `replied` URL params | spec §2.6–2.7 | ✅ Delivered |
| INSIGHT-04 | `get_latest_insights` reader (org-scoped, names resolved at read, stale items dropped) shared with the Dashboard Spotlight | spec §2.8–2.9 | ✅ Delivered |
| DASH-RD-01 | Dashboard "night panels" redesign keeping every existing report: headline band with star meter and trends, sentiment grid, tag tug-of-war, store rating ladder, highlight cards, Your Store | spec docs/superpowers/specs/2026-11-14-dashboard-redesign-design.md | ✅ Delivered |
| DASH-RD-02 | Dashboard Spotlight strip (Org Admin only) fed by the Insights snapshot | spec §2.1 | ✅ Delivered |
| DASH-RD-03 | `/kpis/` previous-period, 6-point trend, oldest awaiting; `/top-performing/` all_stores | spec §2.10 | ✅ Delivered |
| DASH-RD-04 | Dashboard filter bar as a sentence ("Showing all regions, all stores for the last 30 days"): each part a dropdown, changes apply instantly, Reset only when not default, custom range as inline dates; same filters and URL state as today | owner-approved sample B, 2026-11-14 | ✅ Delivered |

## Out of scope (deferred)

- Changing enrichment's behaviour when a model has no price (it currently fails the enrichment) — design §5.1
- Benchmarking shops (low/average/high), client fee tracking, CSV export, charts
- Daily AI-cost rollup table if the Cost Explorer's cold queries exceed budget at scale
