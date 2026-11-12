# AI Pricing Management — Superadmin

**Version 1.1 · November 2026**

> Implementation notes and corrections against the current codebase live in
> `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md` — where the
> two disagree, the design doc wins.

## 1. Document Overview

This document specifies a Superadmin interface for managing the `openai_ai_pricing` table (Django model: `AiPricing`) that drives cost calculation on every AI call logged by ReviewBee. It also specifies an optional weekly auto-sync that pulls current OpenAI model prices from the LiteLLM community-maintained JSON, and an always-on gap-detection mechanism that flags any model logged in `AiUsageLog` without a corresponding pricing row.

This feature closes a gap in the AI Cost Explorer: without a way to maintain pricing accurately, the dashboard's cost figures drift from what OpenAI actually bills. With manual edit + optional auto-sync + gap detection, ReviewBee can keep its internal cost tracking within pennies of OpenAI's invoices and never silently lose cost visibility when a new model is deployed.

### 1.1 Context

The `AiPricing` table already exists in production with the schema shown below, matching the CLAUDE.md §14.3 specification:

| Column | Type | Purpose |
|---|---|---|
| id | int8 | PK |
| model | varchar(100) | Exact model identifier, e.g. `gpt-4o-mini-2024-07-18` |
| input_token_price_per_1m | numeric(12,8) | USD per 1 million input tokens |
| output_token_price_per_1m | numeric(12,8) | USD per 1 million output tokens |
| cached_token_price_per_1m | numeric(12,8) | USD per 1 million cached input tokens |
| effective_from | timestamptz | When this pricing starts applying |
| effective_to | timestamptz (nullable) | When this pricing stops applying; `NULL` means current |

Rows are **time-versioned and immutable** by convention (§14.4 of CLAUDE.md): a new rate requires a new row, not an edit of an existing one. This convention is preserved — the Superadmin UI enforces it in software.

### 1.2 Scope

- Superadmin-only page listing current and historical pricing per model
- "Add New Price" flow for one model, with autocomplete that surfaces missing-pricing models at the top
- No editing of historical rows (immutability enforced)
- Optional: delete a mistakenly-added future-dated row that hasn't become active yet
- Weekly automated sync from LiteLLM's pricing JSON, feature-flagged and OFF by default
- Automated creation of pricing rows for logged models that don't yet have pricing (via the sync task when enabled)
- Always-on gap detection: flag any model logged in `AiUsageLog` without a current pricing row via a banner on the AI Cost Explorer
- Audit log entries on every pricing change (manual, automated sync, or sync-added-missing)

### 1.3 Out of Scope

- A UI for editing cost-calculation logic itself (that's code)
- Historical re-computation — changing a pricing row never retroactively alters past `AiUsageLog.estimated_cost_usd` values
- Price alerts or budget warnings (future, if useful)
- Pricing for non-OpenAI providers — this table is named `openai_ai_pricing` for a reason; add new providers via a separate table and feature
- Multi-currency — all prices in USD
- Manual override of a specific `AiUsageLog` row's cost

### 1.4 Dependencies

- Existing `AiPricing` table (schema above — already shipped)
- Celery + Celery Beat for the weekly sync task
- Existing Superadmin role and authentication
- AI Cost Explorer page exists to host the missing-pricing banner (or will be shipped together)

## 2. Access

| Role | Access |
|---|---|
| Superadmin | Full read/write |
| All other roles | 403 Forbidden |

Route: `/admin/ai-pricing/`

Sidebar entry under the Superadmin shell: **AI Pricing** (icon: `DollarSign` or `Receipt` from Lucide)

## 3. Page Structure

Top to bottom:

1. Page header: "AI Pricing" with subtitle "Current and historical token rates for OpenAI models"
2. **Missing-pricing alert bar** (visible only when any model is logged without pricing — see §7)
3. Auto-sync status banner (only when auto-sync is enabled — see §6.4)
4. "Add New Price" button (top-right, primary yellow)
5. Current Prices table — one row per model that has an active pricing row
6. History section — expandable per model, shows all past pricing rows

## 4. Current Prices Table

Shows the active `AiPricing` row for each model (where `effective_to IS NULL`).

Columns:

| Column | Content |
|---|---|
| Model | Model identifier, bold. Below: small text "Active since {date}" |
| Input (per 1M tokens) | `$0.150000` with 6 decimal places visible |
| Output (per 1M tokens) | `$0.600000` |
| Cached Input (per 1M) | `$0.075000` |
| Effective From | Date in `YYYY-MM-DD` |
| Actions | Three-dot menu: "Add new price for this model" · "View history" |

Sort: alphabetical by model name.

Empty state: "No pricing configured. Add pricing for at least one model to enable cost tracking." with an "Add New Price" CTA.

## 5. Add New Price Flow

Triggered by:
- The main "Add New Price" button
- "Add new price for this model" in a row's action menu
- Clicking a specific model in the missing-pricing alert (pre-fills the Model field)

Modal: **Add New Price**

Fields:

| Field | Type | Required | Validation |
|---|---|---|---|
| Model | Text input + autocomplete | Yes | 1–100 chars |
| Input price (USD per 1M tokens) | Decimal | Yes | 0.000001 to 1000.00000000 |
| Output price (USD per 1M tokens) | Decimal | Yes | Same range |
| Cached input price (USD per 1M tokens) | Decimal | Yes | Same range; may be 0 if cached pricing not applicable |
| Effective from | Date-time picker | Yes | Must be ≥ current time (no backdating) |

Buttons: Cancel + Save (primary yellow).

### 5.1 Model Autocomplete Behavior

The Model input is an autocomplete pulling from distinct `AiUsageLog.model` values. The suggestion list orders entries as:

1. **Models with no current pricing row** (sorted by most recent `AiUsageLog.created_at` first) — displayed with a small red `⚠ No pricing` label on the right
2. Then all other distinct models sorted alphabetically
3. Free-text entry is also accepted (in case a Superadmin is adding pricing for a model not yet logged)

This surfaces gaps immediately: as soon as a Superadmin opens "Add New Price," any logged-but-unpriced models are at the top of the list.

### 5.2 Save Behavior

On save, inside a single transaction:

1. If a current row exists for this model (where `effective_to IS NULL`), set its `effective_to` to the new row's `effective_from` value (closes the previous rate at the moment the new one begins)
2. Insert the new row with `effective_to = NULL`
3. Write an audit log entry: `ai_pricing.added`

### 5.3 Backdating Is Not Allowed

`effective_from` must be in the future (or equal to "now" within a small grace window — e.g., 5 seconds). This prevents retroactive rewrites of historical cost calculations.

If Superadmin wants to correct a mis-entered price that's been active for days, they add a new row with `effective_from = now()`. The incorrectly-priced historical `AiUsageLog` rows keep their mis-computed cost (an audit footnote, not a bug).

### 5.4 Deleting a Future-Dated Row

A future-dated pricing row (where `effective_from > now()`) can be deleted — it hasn't taken effect yet, so no `AiUsageLog` rows reference it.

Active or past rows cannot be deleted. The UI shows a disabled delete button with tooltip: "This pricing is in effect or has been in effect — can't delete."

## 6. Weekly Auto-Sync from LiteLLM

### 6.1 Rationale

OpenAI does not publish a public pricing API. Their pricing page is HTML and brittle to scrape. The LiteLLM open-source project maintains a comprehensive, Apache 2.0-licensed JSON file of model pricing that is updated within hours or days of provider price changes:

```
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
```

This file is used in production by Langfuse, Helicone, and many other platforms. It covers all major OpenAI models by their exact identifiers.

### 6.2 Feature Flag

Auto-sync is **feature-flagged and OFF by default**. Enabling it is a deliberate Superadmin choice.

Setting: `AI_PRICING_AUTO_SYNC_ENABLED = bool, default False`.

The current state is visible on the AI Pricing page as a status banner at the top:

- Off: grey banner — "Automatic pricing sync is off. Prices update only when you add them manually. [Enable sync]"
- On: green banner — "Automatic pricing sync is on. Last synced: Nov 10, 2026 at 09:00 UTC. [Disable sync]"

Clicking Enable / Disable toggles the setting via a Superadmin-only API endpoint. Changes write to the audit log.

### 6.3 Sync Task Behavior

Celery Beat task `sync_ai_pricing_from_litellm_task` runs weekly (Monday 09:00 UTC by default, configurable).

Flow:

1. Skip if `AI_PRICING_AUTO_SYNC_ENABLED` is False — do nothing
2. Fetch the LiteLLM JSON (HTTPS, 15-second timeout)
3. On fetch failure (network, non-200, malformed JSON): log a WARNING, write `ai_pricing.sync_failed` audit entry, exit — do NOT alter any pricing
4. Compute the set of models to check: all distinct `AiUsageLog.model` values logged in the last 90 days
5. For each such model:
   - Look up its entry in the LiteLLM JSON
   - If **not found in LiteLLM**: log INFO, record the model in the sync result's `unpriced_models` list for Superadmin follow-up, and skip
   - Convert LiteLLM's per-token prices to per-1M-token prices (LiteLLM uses per-token; our table uses per-1M)
   - Look up the current `AiPricing` row for this model
   - **Case A — no current `AiPricing` row exists for this model**: INSERT a new row with LiteLLM's prices and `effective_from = now()`. Write audit log entry `ai_pricing.added_from_sync`. This closes the gap where a newly-deployed model had no pricing and was logging $0 cost.
   - **Case B — current row exists and prices match within tolerance**: do nothing
   - **Case C — current row exists and prices differ by more than $0.000001 per 1M tokens on any field**: INSERT a new row with LiteLLM's prices and close the previous row by setting its `effective_to = now()` (same transaction). Write audit log entry `ai_pricing.updated_from_sync`
6. Write a summary audit log entry: `ai_pricing.sync_completed` with details — models updated, models added (Case A), models unchanged, models missing from LiteLLM
7. Update a Redis key `ai_pricing:last_sync_at` with the current timestamp for display in the banner

### 6.4 Sync Status Banner Details

When enabled, the banner shows:

- Last successful sync time (read from `ai_pricing:last_sync_at`)
- If the last sync failed or is overdue (> 14 days since last success), the banner becomes amber: "Last sync failed Nov 10, 2026. Click to view details." Clicking opens a small modal with the error message from the audit log.

### 6.5 Manual "Sync Now" Trigger

A secondary button "Sync Now" appears next to the Enable/Disable toggle (whether auto-sync is on or off). Clicking it enqueues the same task immediately. Useful for a Superadmin who just updated LiteLLM's JSON via a PR, or just wants to verify the sync works.

Rate-limited server-side: 1 manual sync per 15 minutes per Superadmin.

### 6.6 What the Sync Does and Does Not Do

Does:
- Create new pricing rows for logged models that lack any pricing (Case A above)
- Update pricing when LiteLLM's current rate differs from your stored rate (Case C)
- Flag models logged in `AiUsageLog` that aren't in LiteLLM (so Superadmin knows to add manually)

Does NOT:
- Add pricing for models never seen in `AiUsageLog` (avoids polluting the table with pricing for models you don't use)
- Delete old `AiPricing` rows
- Alter historical `AiUsageLog.estimated_cost_usd` values — re-pricing is forward-only
- Retroactively match OpenAI's billing for past calls

## 7. Missing-Pricing Gap Detection (Always-On)

A model being logged in `AiUsageLog` without a current `AiPricing` row is a silent failure mode: the `estimated_cost_usd` column stores $0 (or NULL) for those calls, and the AI Cost Explorer under-reports spend. Gap detection surfaces this immediately.

This detection runs always — it does not depend on the auto-sync feature flag.

### 7.1 Detection Query

A single SQL query (wrapped in a selector `apps/integrations/openai/selectors/pricing.py::list_missing_pricing_models`):

```sql
SELECT DISTINCT u.model
FROM openai_ai_usage_log u
LEFT JOIN openai_ai_pricing p
  ON p.model = u.model
  AND p.effective_to IS NULL
WHERE p.model IS NULL
  AND u.created_at > NOW() - INTERVAL '90 days'
```

Returns the list of models logged in the last 90 days that have no active pricing row.

Cached in Redis for 10 minutes (key: `ai_pricing:missing_models`) to keep the banner cheap to render on every page load.

### 7.2 Known-Free Models Exemption

OpenAI's Moderation API and similar free-tier APIs log to `AiUsageLog` but legitimately have no cost. To prevent them from perpetually appearing in the missing-pricing alert:

- Settings list: `AI_PRICING_KNOWN_FREE_MODELS = [...]` — defaults to `["omni-moderation-latest", "text-moderation-latest", "text-moderation-stable"]`
- Models in this list are excluded from the missing-pricing detection

Alternatively, Superadmin can add an explicit `AiPricing` row with all-zero prices for these models to cover the same case. Both approaches work; the settings list is maintenance-free.

### 7.3 Missing-Pricing Alert Bar — AI Pricing Page

Rendered at the top of the AI Pricing page (§3 step 2). Only shown when the detection query returns a non-empty list.

Visual: amber background, warning icon, text:

> ⚠ **N models are logged without pricing.** These calls show $0 in cost totals until pricing is added.
>
> Missing: `gpt-4o-2026-10-xx`, `o1-mini-2026-09-xx`
>
> [Add pricing for gpt-4o-2026-10-xx →] [Add pricing for o1-mini-2026-09-xx →]

Each "Add pricing for X" button opens the Add New Price modal (§5) with the Model field pre-filled.

If auto-sync is enabled and LiteLLM covers these models, a note is added: "Next weekly sync (Mon 09:00 UTC) will fetch pricing from LiteLLM automatically for models it covers."

### 7.4 Missing-Pricing Alert Bar — AI Cost Explorer Page

The same alert is rendered on the AI Cost Explorer page (cross-reference to that doc), so Superadmin sees the gap in the context where it matters most — the cost dashboard.

Clicking the alert on the Cost Explorer navigates to the AI Pricing page.

### 7.5 "Check for Missing Pricing" Manual Trigger

A secondary action on the AI Pricing page: "Refresh missing-pricing check." Flushes the Redis cache and re-runs the detection query. Useful after a Superadmin has added pricing rows and wants to confirm the gap is closed.

Rate-limited to 1 per 60 seconds per Superadmin.

## 8. Audit Log Additions

New audit action types:

- `ai_pricing.added` — manual Superadmin addition
- `ai_pricing.deleted` — future-dated row deleted by Superadmin
- `ai_pricing.sync_enabled` / `ai_pricing.sync_disabled` — feature-flag toggled
- `ai_pricing.sync_completed` — successful weekly sync (payload: counts of added, updated, unchanged, missing-from-litellm models)
- `ai_pricing.sync_failed` — failed weekly sync (payload includes error)
- `ai_pricing.added_from_sync` — new pricing row created by the sync for a model that had no prior pricing (Case A in §6.3)
- `ai_pricing.updated_from_sync` — existing pricing updated by the sync due to price change (Case C in §6.3)

Each entry includes `performed_by_user_id` for manual actions, and `NULL` for automated syncs.

## 9. API Endpoints

All Superadmin-only. 403 for any other role.

| Method + Path | Purpose |
|---|---|
| `GET /api/v1/admin/ai-pricing/` | List current pricing rows (one per model where `effective_to IS NULL`) |
| `GET /api/v1/admin/ai-pricing/{model}/history/` | Full history for one model |
| `POST /api/v1/admin/ai-pricing/` | Add a new pricing row (§5.2) |
| `DELETE /api/v1/admin/ai-pricing/{id}/` | Delete a future-dated row (§5.4) |
| `GET /api/v1/admin/ai-pricing/missing/` | List models logged without current pricing (for the alert bar); respects known-free exemptions |
| `POST /api/v1/admin/ai-pricing/missing/refresh/` | Flush the missing-pricing cache and recompute (rate-limited) |
| `GET /api/v1/admin/ai-pricing/sync/status/` | Returns `enabled`, `last_sync_at`, `last_sync_status`, `last_sync_error` |
| `POST /api/v1/admin/ai-pricing/sync/toggle/` | Body: `{enabled: bool}`; enables or disables auto-sync |
| `POST /api/v1/admin/ai-pricing/sync/trigger/` | Manual sync trigger (rate-limited 1 per 15 min per user) |

## 10. Technical Design

### 10.1 Module Layout

Add to the existing admin or integrations app:

- `apps/integrations/openai/services/pricing_management.py` — add_pricing, close_current, delete_future
- `apps/integrations/openai/services/pricing_sync.py` — LiteLLM fetch + diff + apply + missing-model creation
- `apps/integrations/openai/services/pricing_gap_detection.py` — missing-pricing query, cache, exemption logic
- `apps/integrations/openai/tasks.py` — add `sync_ai_pricing_from_litellm_task`
- `apps/integrations/openai/selectors/pricing.py` — list current, list history, get by model, list_missing_pricing_models

### 10.2 Settings Additions

```python
# config/settings/base.py

AI_PRICING_AUTO_SYNC_ENABLED = env.bool("AI_PRICING_AUTO_SYNC_ENABLED", default=False)
AI_PRICING_SYNC_SOURCE_URL = env(
    "AI_PRICING_SYNC_SOURCE_URL",
    default="https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)
AI_PRICING_SYNC_LOOKBACK_DAYS = env.int("AI_PRICING_SYNC_LOOKBACK_DAYS", default=90)
AI_PRICING_SYNC_TOLERANCE_USD_PER_1M = env.float(
    "AI_PRICING_SYNC_TOLERANCE_USD_PER_1M", default=0.000001
)
AI_PRICING_KNOWN_FREE_MODELS = env.list(
    "AI_PRICING_KNOWN_FREE_MODELS",
    default=["omni-moderation-latest", "text-moderation-latest", "text-moderation-stable"]
)
AI_PRICING_MISSING_CACHE_TTL_SECONDS = env.int(
    "AI_PRICING_MISSING_CACHE_TTL_SECONDS", default=600
)
```

The source URL is configurable so Superadmin can point to a mirror or a self-hosted copy if GitHub becomes blocked or LiteLLM changes format.

### 10.3 Celery Beat Schedule

```python
CELERY_BEAT_SCHEDULE = {
    # ...existing schedules...
    "sync_ai_pricing_from_litellm": {
        "task": "apps.integrations.openai.tasks.sync_ai_pricing_from_litellm_task",
        "schedule": crontab(day_of_week="monday", hour=9, minute=0),  # Monday 09:00 UTC
    },
}
```

### 10.4 LiteLLM JSON Format Handling

LiteLLM's JSON uses per-token prices as decimal fractions:

```json
{
  "gpt-4o-mini": {
    "max_tokens": 16384,
    "input_cost_per_token": 0.00000015,
    "output_cost_per_token": 0.0000006,
    "cache_read_input_token_cost": 0.000000075,
    ...
  },
  "gpt-4o-mini-2024-07-18": {
    ...
  }
}
```

Conversion to our per-1M format:

```python
input_per_1m = Decimal(str(litellm_entry["input_cost_per_token"])) * Decimal(1_000_000)
```

Edge cases to handle:

- Missing `cache_read_input_token_cost` key → default to `0` (model doesn't offer cached pricing)
- Missing `input_cost_per_token` or `output_cost_per_token` → skip this model, log WARNING, add to `unpriced_models`
- Exact model match preferred; if your logged model is `gpt-4o-mini-2024-07-18` and LiteLLM has that exact key, use it. Do NOT fuzzy-match.

### 10.5 Idempotency of Sync

The sync task is idempotent: running it twice back-to-back has no effect the second time, because prices match after the first run. Safe to retry on transient failures.

### 10.6 Gap Detection Performance

The missing-pricing query runs on every AI Pricing and AI Cost Explorer page load (read from Redis cache most of the time). Query cost:

- Scans `AiUsageLog` last-90-days window (indexed on `created_at`)
- LEFT JOIN with `AiPricing` on (model, effective_to IS NULL)
- Cached for 10 minutes

Add a supporting index if needed: `(model) INCLUDE (created_at)` on `AiUsageLog` — benchmark first; the existing `(organisation_id, created_at)` may be sufficient.

## 11. Updated Cost-Drift Risk (Reference Back to AI Cost Explorer)

The AI Cost Explorer document's Risk §10 included:

> **Cost does not match what OpenAI actually charged us** — `AiUsageLog.estimated_cost_usd` is computed from `AiPricing` at log time — can drift from OpenAI's actual invoice.

With this feature in place, the risk is mitigated as follows:

- Manual edit UI gives Superadmin a direct way to correct pricing when OpenAI changes rates
- Weekly LiteLLM auto-sync (when enabled) keeps pricing current within ~7 days of OpenAI changes, and auto-creates pricing rows for newly-deployed models
- Always-on missing-pricing banner catches gaps immediately, regardless of auto-sync state
- Residual gaps: promotional rates, custom contract pricing, batch discounts — these still cause drift and can only be reconciled against the actual OpenAI invoice

The caveat on the Cost Explorer page becomes: *"Based on configured pricing; sync status: {synced 3 days ago | sync off}. Actual OpenAI invoice is authoritative."*

## 12. Acceptance Criteria

### 12.1 Access

1. Only Superadmin can access `/admin/ai-pricing/` — other roles return 403
2. All API endpoints return 403 for non-Superadmin requests
3. Sidebar entry visible only for Superadmin

### 12.2 Current Prices View

4. Table lists one row per model with an active `AiPricing` row (`effective_to IS NULL`)
5. All four price fields displayed with correct precision (6 decimal places)
6. Empty state renders when no `AiPricing` rows exist

### 12.3 Add New Price Flow

7. Form validates all fields; prices must be positive decimals
8. `effective_from` in the past is rejected (except within 5-second grace window)
9. On save, the previous current row for this model gets its `effective_to` set to the new row's `effective_from`
10. New row is inserted with `effective_to = NULL`
11. Both the UPDATE and INSERT happen in a single transaction
12. Audit log entry `ai_pricing.added` is written
13. The model autocomplete surfaces models with no current pricing at the top of the list, each with a `⚠ No pricing` label
14. Free-text model entry is accepted (for models not yet in `AiUsageLog`)
15. Clicking an "Add pricing for X" button in the missing-pricing alert opens the modal with the Model field pre-filled

### 12.4 History View

16. For each model, history shows all past and future `AiPricing` rows in chronological order
17. Current row (where `effective_to IS NULL`) is visually distinguished
18. Future-dated rows have a delete action; past and current rows do not

### 12.5 Auto-Sync Feature

19. Auto-sync defaults OFF; Superadmin must explicitly enable
20. Toggle action writes audit log entry and updates the setting
21. Weekly Beat task does nothing when flag is OFF
22. When ON, task fetches LiteLLM JSON, filters to models used in the last 90 days
23. For each model in the filtered set, if no current `AiPricing` row exists AND LiteLLM has the model, a new row is inserted and `ai_pricing.added_from_sync` is logged
24. For each model with a current row, if LiteLLM differs beyond tolerance, a new row is inserted and the previous closed; `ai_pricing.updated_from_sync` is logged
25. Fetch failures log WARNING and write `ai_pricing.sync_failed` — no pricing changes made
26. Models not found in LiteLLM are skipped with INFO log and included in the sync summary's `unpriced_models` list
27. Sync status banner shows last sync time correctly
28. Overdue (>14 days without successful sync) banner is amber with error details
29. Manual "Sync Now" button enqueues the task immediately; rate-limited to 1 per 15 minutes per Superadmin

### 12.6 Missing-Pricing Gap Detection

30. The missing-pricing query returns distinct models logged in the last 90 days that lack a current `AiPricing` row
31. Models listed in `AI_PRICING_KNOWN_FREE_MODELS` are excluded from the missing-pricing results
32. The alert bar on the AI Pricing page is only rendered when the missing list is non-empty
33. The alert bar on the AI Cost Explorer page shows the same missing list and links to the AI Pricing page
34. Each "Add pricing for X" button in the alert pre-fills the Model field in the Add New Price modal
35. "Refresh missing-pricing check" button flushes the cache and re-runs the query, rate-limited to 1 per 60 seconds per Superadmin
36. The missing-pricing cache TTL is 10 minutes (configurable via settings)

### 12.7 Cross-cutting

37. All endpoints have `CaptureQueriesContext` tests asserting query count ceilings
38. Historical `AiUsageLog.estimated_cost_usd` values are NEVER altered by this feature
39. All audit log event types listed in §8 are written and queryable
40. The pricing sync service has unit tests covering: successful sync, LiteLLM unreachable, malformed JSON, model not in LiteLLM, price identical (no-op), price changed (new row created), model with no prior pricing (Case A — new row created)
41. The gap detection service has unit tests covering: all models priced (empty result), some missing (list returned), known-free models excluded, 90-day window boundary

## 13. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LiteLLM JSON format changes and sync breaks | Fetch failure logs WARNING and skips — no silent corruption. Monthly sanity check during Superadmin review. Alternative source URL is configurable. |
| LiteLLM stale (price actually changed but JSON not updated yet) | Manual override always available. Manual edit takes precedence. Not worse than status quo (no sync). |
| Superadmin backdates a price accidentally | `effective_from` must be ≥ now with 5s grace. UI confirmation on save shows the exact timestamp being recorded. |
| Sync adds pricing for a model that doesn't match our logged model identifier exactly | Only exact-match, no fuzzy matching. Cached pricing defaults to 0 when missing. Manual review of first few syncs recommended before trusting unattended runs. |
| Auto-sync accidentally changes pricing during peak traffic | New rows have `effective_from = now()` so inflight calls at that exact moment are rare and self-contained. Credit cost in the Credits System is based on review comment length, not live pricing — decoupled by design. |
| Superadmin confused by why auto-sync changed a price | Every sync-induced change writes a detailed audit log entry with before/after values and the source (sync vs manual). History view surfaces this. |
| New OpenAI model deployed silently and logs $0 cost unnoticed | Always-on gap detection surfaces this immediately on both the AI Pricing and Cost Explorer pages. Auto-sync (if enabled) fills the gap automatically on next run. |
| Free-tier models (Moderation API) perpetually in the missing-pricing alert | Settings-based exemption list excludes known-free models from the alert. Superadmin can also add explicit zero-cost `AiPricing` rows. |
| Price drift between weekly syncs | Weekly cadence is a trade-off (avoids hammering GitHub, acceptable staleness). Configurable via `CELERY_BEAT_SCHEDULE` if a tighter cadence is needed later. |
