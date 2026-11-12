# AI Cost & Pricing — Design

**Date:** 2026-11-12 · **Milestone:** v0.10 — AI Cost & Pricing (Superadmin)
**Source specs (binding except where this doc overrides them):**
- `docs/in-progress/Requirements_AI_Cost_Explorer.md` (v1.0) — the dashboard
- `docs/in-progress/Requirements_AI_Pricing_Management.md` (v1.1) — the pricing page, gap detection, LiteLLM sync

This document records the *why*, the decisions made in conversation, and every
correction needed to make the two specs fit the current codebase. Where this
document and a source spec disagree, **this document wins**.

---

## 1. Intent

The Superadmin (platform owner) needs one screen in the ReviewBee dashboard that
shows **how much AI spend each organisation and each shop is generating**, filterable
by date. Today that data exists (`openai_ai_usage_log`, model `AiUsageLog`, which
already stamps an `estimated_cost_usd` on every call) but it is only visible as raw
rows in Django admin. The owner uses the numbers to decide when a client's price
needs adjusting — that decision is made by the owner, off-platform; the dashboard
only needs to show the spend clearly.

The pricing-management half exists to keep those numbers **correct**: the cost on
each log row is computed from the `AiPricing` table at log time, and today that
table can only be edited in Django admin with no history discipline, no gap
alerting and no way to track OpenAI price changes.

**Priority:** the Cost Explorer is the headline and ships first. Pricing management
follows.

## 2. Goals, non-goals, anti-goals

**Goals**
- Superadmin sees total AI cost, calls, and tokens for a date range, broken down by
  organisation → shop, by request type, and by model.
- Superadmin can maintain `AiPricing` safely from the product UI (append-only,
  no backdating), see when a used model has no price, and optionally let a weekly
  LiteLLM sync keep prices current.

**Non-goals** (unchanged from the specs): charts/time series, CSV export, per-call
drill-down, budgets/alerts, forecasting, client billing/invoicing, recording what
clients pay, benchmarking shops against each other ("low/average/high" labelling —
explicitly declined by the owner), non-OpenAI providers, multi-currency, recomputing
historical costs.

**Anti-goals** (would be a failure even if it "works")
- Any Org Admin or Staff user able to see platform cost data — this is Superadmin-only.
- Numbers that don't add up: per-shop / per-type / per-model breakdowns that don't
  sum to the org total, with no explanation.
- Any change that alters an existing `AiUsageLog.estimated_cost_usd`.
- N+1 queries on any list (CLAUDE.md §6 — blocker).

## 3. Delivery order (phases)

| Phase | Name | Covers |
|---|---|---|
| 34 | AI Cost Explorer | Cost Explorer spec in full, with §4 corrections |
| 35 | AI Pricing Page + Gap Detection | Pricing spec §2–5, §7, §8 (manual parts), §9 (non-sync endpoints) |
| 36 | LiteLLM Auto-Sync | Pricing spec §6, sync audit events, sync endpoints, Cost Explorer footer caveat (pricing spec §11) |

Phase 34 has no dependency on 35/36. Phase 36 depends on 35.

---

## 4. Cost Explorer — corrections to the spec

### 4.1 Call statuses are three, not two
`AiUsageLog.Status` is `SUCCESS`, `FAILED`, **`MODERATED`** (a call whose input or
output was blocked by the guardrails). The "Total API Calls" footer shows all three:
"N succeeded · M failed · K moderated".

### 4.2 Which rows count toward cost and tokens — *decided by the owner*
**Decision (owner):** cost and token totals sum **`SUCCESS` rows only**, as the spec
says (AC 19, §7.1). Call counts include all statuses.
Known consequence, accepted: a `MODERATED` reply-generation row carries a real
`estimated_cost_usd` (the OpenAI call was billed before output moderation blocked
it — `reply_generation.py`, "D-29"), so that spend is not in the totals. The
moderated count stays visible in the calls footer.

### 4.3 Shop attribution is not total — add an "Unattributed" row
`AiUsageLog` reaches a shop only via the nullable `review` FK (`on_delete=SET_NULL`).
A row loses its shop when its review is hard-deleted (e.g. a shop deletion cascading
to its reviews). Without handling this, spec AC 22 ("per-shop sums match the per-org
total") fails.
**Decision:** the shops table includes a final **"Unattributed"** row (only when
non-zero) aggregating that org's rows with `review_id IS NULL`. It is excluded from
the "Active Shops" count and is not clickable. AC 22 then holds by construction.

### 4.4 API path follows the existing superadmin convention
Existing superadmin APIs live under `/api/v1/superadmin/...` (see
`apps/credits/api_urls.py`). Replace the spec's `/api/v1/admin/ai-cost/...` with
`/api/v1/superadmin/ai-cost/...` (same sub-paths). Page routes stay as specified:
`/admin/ai-cost/` and `/admin/ai-cost/organisations/{org_id}/` — matching the
existing `/admin/organisations/` page route.

### 4.5 Roles
There is no "Manager" role. Roles are `SUPERADMIN`, `ORG_ADMIN`, `STAFF_ADMIN`. All
non-superadmin roles get 403 on pages and APIs (use the existing `IsSuperadmin`
permission from `apps/accounts/permissions.py`).

### 4.6 Module placement — *builder's call recorded here*
No `admin_dashboard` app exists and the spec says not to proliferate apps.
**Decision:** put the work in `apps/integrations/openai/`, which owns `AiUsageLog`
and `AiPricing`:
- `selectors/ai_cost.py` — all aggregations
- `views.py` / `api_urls.py` / `urls.py` — superadmin DRF views + the page shell views
- template under `templates/` following the existing superadmin page pattern
- React island: new entrypoint `frontend/src/entrypoints/ai-cost-explorer.tsx`
  following the Vite-per-widget pattern (see `org-management.tsx`, `dashboard.tsx`)
- Sidebar: add "AI Cost" (and in Phase 35 "AI Pricing") to the superadmin branch
  of `templates/partials/sidebar.html`, next to "Organisations".

### 4.7 Request types present today
`request_type` values in the data are `enrichment` and `reply_generation`. The badge
group must render whatever values appear (spec risk table already says this); do not
hard-code a "Moderation" badge — moderation calls are logged under the request type
that triggered them, with `status=MODERATED`.

### 4.8 Throttling
CLAUDE.md §24 forbids endpoints without throttling. Use `ScopedRateThrottle` with a
new scope (e.g. `superadmin_ai_cost_read`), following `apps/credits/views.py`.

### 4.9 Everything else in the Cost Explorer spec stands
Date-range options and UTC anchoring, 365-day cap, KPI cards, sorting, pagination
(10/25/50/100, default 25), exclusion of zero-activity orgs/shops, 10-minute Redis
cache, display formatting, query-count tests, index work verified with
`EXPLAIN ANALYZE`, and the footer caveat.

---

## 5. Pricing Management — corrections to the spec (v1.1)

### 5.1 Fact: what happens today when a model has no price
`AiPricing.objects.get_active()` raises `DoesNotExist` when no active row exists.
- **Enrichment** (`apps/reviews/services/enrichment.py`) does not catch it → the
  enrichment attempt **fails** (it does not silently log $0).
- **Reply generation** catches it, logs `ai_pricing_lookup_failed`, and writes the
  usage row with `estimated_cost_usd = 0`.

Gap detection (spec §7) is still valuable and is built as specified. **This milestone
does not change enrichment's behaviour on missing pricing** — out of scope; noted so
nobody assumes the spec's "$0 silently" description covers enrichment.

Also note: production calls use a single model, `settings.OPENAI_MODEL`, so in
practice there is one active model at a time; the design still handles many.

### 5.2 The auto-sync on/off switch must live in the database
The spec defines `AI_PRICING_AUTO_SYNC_ENABLED` as an env-backed Django setting and
also says a Superadmin button toggles it — env settings cannot be changed at runtime.
**Decision:** add a single-row model in `apps/integrations/openai/models.py`,
e.g. `AiPricingSyncConfig`, holding: `enabled` (default `False`), `last_run_at`,
`last_success_at`, `last_status`, `last_error`. Drop the `AI_PRICING_AUTO_SYNC_ENABLED`
setting. This row also **replaces the Redis key `ai_pricing:last_sync_at`** (durable,
survives Redis flush; the banner reads it from the DB). Other settings in the spec
(source URL, lookback days, tolerance, known-free models, missing-cache TTL) stay as
env settings.

### 5.3 Beat schedule is DB-backed
The project uses `django-celery-beat`'s DatabaseScheduler; schedules are seeded by
data migration (see `apps/credits/migrations/0003_beat_credit_lapse.py`). Seed
`sync_ai_pricing_from_litellm_task` (Monday 09:00 UTC) that way, not via
`CELERY_BEAT_SCHEDULE`. Queue: `default`. Add the route to `CELERY_TASK_ROUTES` and a
row to CLAUDE.md §12.5's Beat table.

### 5.4 Audit logging needs a platform-level home — *builder's call recorded here*
CLAUDE.md §29.4 says prefer `AuditLog` for domain events, but
`AuditLog.organisation` is **non-nullable** and pricing events are platform-wide.
**Decision:** make `AuditLog.organisation` nullable (migration) and write pricing
events with `organisation=None`, `entity_type="ai_pricing"`, `actor` = the
Superadmin (or `None` for sync). The Org Activity Log viewer filters by the caller's
organisation, so null-org rows are never shown to tenants — this must be confirmed by
the `tenant-security-auditor` subagent and covered by a test asserting an Org Admin's
activity log never returns a null-organisation row.
The spec's `performed_by_user_id` maps to `AuditLog.actor`.

### 5.5 API path
As §4.4: `/api/v1/superadmin/ai-pricing/...` instead of `/api/v1/admin/ai-pricing/...`.
Page route `/admin/ai-pricing/` stays. The `{model}` path segment in the history
endpoint must accept model ids containing dots and dashes.

### 5.6 Concurrency on "Add New Price"
The model docstring requires exactly one active row per model. The close-current +
insert in spec §5.2 must lock the current row with `select_for_update()` inside
`transaction.atomic()` (CLAUDE.md §6.12). The same service is reused by the sync.

### 5.7 Price validation
Spec says prices are 0.000001–1000 but cached price "may be 0"; known-free models
may also be priced at all-zeros. **Decision:** all three price fields accept
`0 ≤ price ≤ 1000` with up to 8 decimal places (matches `numeric(12,8)`).

### 5.8 Future-dated prices need a time-aware "active" lookup — *builder's call recorded here*
Today `get_active()` returns the row with `effective_to IS NULL` and ignores
`effective_from`. Once a price can start in the future, that would charge calls at
the future rate the moment it is saved, and deleting a future row would leave the
model with no active price.
**Decisions:**
- `get_active(model, at=None)` becomes a time-window lookup:
  `effective_from <= at < coalesce(effective_to, ∞)`, with `at` defaulting to now.
  `calculate_cost` keeps its signature. Covered by tests for: before, at, and after a
  scheduled switch.
- **At most one pending (future) row per model.** Adding a new price while one is
  pending is rejected with a clear message ("delete the scheduled price first").
- **Deleting a pending row reopens the previous row** (sets its `effective_to` back
  to `NULL`) in the same locked transaction.
- The Current Prices table shows the row active *now*. A pending row is shown as
  "Scheduled: $X from {date}" under it. The sync compares against the row active now.

### 5.9 Who set a price — *builder's call recorded here*
Add `source` (`manual` | `sync` | `seed`) and nullable `created_by` (FK user) to
`AiPricing`. Existing rows backfill as `seed`. The history view shows both, which
covers the spec's "manual vs sync visible in history" without building a separate
Superadmin audit viewer. `AuditLog` rows (§5.4) remain the detailed record, readable
in Django admin. **The Django-admin `AiPricing` editor becomes read-only** so the
append-only rule cannot be bypassed.

### 5.10 Gap detection also checks the configured model — *builder's call recorded here*
When enrichment hits a missing price it fails **before** writing an `AiUsageLog` row
(§5.1). A model used only by enrichment would therefore never appear in a gap query
that only scans the log. **Decision:** the missing-pricing selector also reports
`settings.OPENAI_MODEL` when it has no row active now. Enrichment's own behaviour is
unchanged.

### 5.11 A hand-set price beats the sync — *decided by builder at the owner's request*
The spec's risk table says "manual edit takes precedence", but its Case C would
overwrite a manual price every Monday. **Decision:** if the price active now for a
model has `source = manual`, the sync **does not replace it**. Instead it records the
model in the run summary as `skipped_manual` with both prices (ours vs LiteLLM), and
the sync status banner shows "N hand-set prices differ from LiteLLM" with the list.
To hand a model back to the sync, the Superadmin adds a new price with the LiteLLM
values. A pre-filled "Use LiteLLM price" action on that list is optional polish, not
required. Case A (no price at all) and Case C on `sync`/`seed` rows behave as specified.

### 5.12 Everything else in the pricing spec stands
Append-only rows, no backdating (5 s grace), delete only future-dated rows,
autocomplete ordering with "⚠ No pricing" first, missing-pricing alert bars on both
pages (the Cost Explorer one lands in Phase 35 once the selector exists), known-free
exemption list, 10-minute cached gap query with rate-limited refresh, LiteLLM exact
match only, per-token → per-1M conversion with `Decimal`, Case A/B/C sync behaviour,
fetch failure changes nothing, manual "Sync Now" rate-limited to 1 / 15 min.

---

## 6. Constraints (from CLAUDE.md, apply throughout)

- Services/selectors pattern; thin views; thin Celery task (§5, §12.3).
- Every list endpoint paginated; every endpoint throttled; `CaptureQueriesContext`
  query-count test per endpoint (§6.9, §8, §24).
- Tests never hit the network: mock the LiteLLM fetch (`respx`/`responses`) (§16).
- `drf-spectacular` schema updated (§24 step 11).
- Review with `code-reviewer`, `orm-performance-auditor`, `tenant-security-auditor`
  before PR (§27).
- Requirements registered in `.planning/REQUIREMENTS.md` + `ROADMAP.md` (§24 gate);
  specs move to `docs/completed/` when the milestone ships (§28).

## 7. Left to the builder

- Exact index set on `AiUsageLog` (spec §8.4 suggests two; benchmark and choose).
- Shop-join query shape (join vs. subquery) as long as query counts stay fixed.
- React component structure and client-side routing for the drill-down.
- Exact throttle rates.
- Cache key details beyond the spec's format.
