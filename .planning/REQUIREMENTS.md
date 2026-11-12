# Requirements — v0.10 AI Cost & Pricing (Superadmin)

**Planned via:** superpowers brainstorming → writing-plans (not the GSD flow).
**Design (authoritative where it differs from the specs):** `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md`
**Specs:** `docs/in-progress/Requirements_AI_Cost_Explorer.md` (CE §n) · `docs/in-progress/Requirements_AI_Pricing_Management.md` (PM §n)

Acceptance criteria are the numbered criteria in each spec's Acceptance Criteria
section, as amended by the design doc.

## Phase 34 — AI Cost Explorer

| ID | Requirement | Acceptance |
|---|---|---|
| COST-01 | Superadmin-only page `/admin/ai-cost/` + sidebar entry; all APIs under `/api/v1/superadmin/ai-cost/` return 403 for other roles | CE AC 1–3; design §4.4–4.5 |
| COST-02 | Date-range filter (this month default, last month, 7/30/90 d, custom ≤365 d), UTC-anchored, persists across drill-down | CE AC 10–13 |
| COST-03 | Platform KPI cards: cost, calls (success/failed/moderated split), input tokens, output tokens | CE AC 4; design §4.1–4.2 |
| COST-04 | Organisations table: active orgs only, sortable, paginated, request-type cost badges | CE AC 5–9 |
| COST-05 | Org drill-down: scoped KPIs, shops table with "Unattributed" row, cost-by-model table | CE AC 14–18; design §4.3 |
| COST-06 | Data correctness: cost/tokens from SUCCESS only, calls from all statuses; type/shop/model breakdowns sum to org total | CE AC 19–23 as amended by design §4.2–4.3 |
| COST-07 | Performance: fixed query-count tests per endpoint, index migration verified with EXPLAIN ANALYZE, 10-min cache, throttled endpoints | CE AC 24–27; design §4.8 |

## Phase 35 — AI Pricing Page + Gap Detection

| ID | Requirement | Acceptance |
|---|---|---|
| PRICE-01 | Superadmin-only page `/admin/ai-pricing/` + sidebar entry; APIs under `/api/v1/superadmin/ai-pricing/` | PM AC 1–3 |
| PRICE-02 | Current prices table (one active row per model, 6-dp display, empty state) | PM AC 4–6 |
| PRICE-03 | Add New Price: validation (0–1000), no backdating (5 s grace), locked close-current + insert in one transaction, audit entry | PM AC 7–12; design §5.6–5.7 |
| PRICE-04 | Model autocomplete with unpriced models first + free-text entry + pre-fill from alert | PM AC 13–15 |
| PRICE-05 | History view per model with source + who set it; delete only future-dated rows (reopens previous); at most one scheduled price per model; time-aware active-price lookup | PM AC 16–18; design §5.8–5.9 |
| PRICE-06 | Platform-level audit events in `AuditLog` (nullable organisation), never visible to tenants | PM §8, AC 39; design §5.4 |
| GAP-01 | Missing-pricing detection (90-day window + configured `OPENAI_MODEL`, known-free exemption, 10-min cache, rate-limited refresh) | PM AC 30–31, 35–36, 41; design §5.10 |
| GAP-02 | Missing-pricing alert bar on AI Pricing and AI Cost Explorer pages | PM AC 32–34 |

## Phase 36 — LiteLLM Auto-Sync

| ID | Requirement | Acceptance |
|---|---|---|
| SYNC-01 | DB-backed sync config (off by default), toggle endpoint + audit | PM AC 19–20; design §5.2 |
| SYNC-02 | Weekly Beat task (DB-seeded, Mon 09:00 UTC) with Case A/B/C behaviour, exact match, failure changes nothing; never overwrites a hand-set price | PM AC 21–26, 40; design §5.3, §5.11 |
| SYNC-03 | Sync status banner (green/grey/amber overdue), manual "Sync Now" rate-limited 1/15 min | PM AC 27–29 |
| SYNC-04 | Cost Explorer footer caveat shows sync status | PM §11 |

## Cross-cutting

| ID | Requirement | Acceptance |
|---|---|---|
| XCUT-01 | Historical `AiUsageLog.estimated_cost_usd` never altered | PM AC 38 |
| XCUT-02 | Query-count tests on every endpoint; OpenAPI schema updated | PM AC 37; CLAUDE.md §24 |

## Out of scope (deferred)

- Changing enrichment's behaviour when a model has no price (it currently fails the enrichment) — design §5.1
- Benchmarking shops (low/average/high), client fee tracking, CSV export, charts
