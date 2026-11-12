# Phase 36 — LiteLLM Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An opt-in weekly sync that keeps `AiPricing` current from LiteLLM's public price JSON — adding prices for used-but-unpriced models, updating changed prices, never overriding a hand-set price — with a status banner, an on/off switch and a "Sync Now" button on the AI Pricing page, and a sync-status caveat on the AI Cost Explorer.

**Architecture:** A DB singleton `AiPricingSyncConfig` holds the switch and last-run state. A small LiteLLM client (`httpx`) fetches and converts prices. `services/pricing_sync.py` runs the sync under a Redis lock and writes every price change through Phase 35's `add_price` (so the append-only rules, row locks and audit apply unchanged). A thin Celery task runs it weekly from a DB-seeded Beat schedule. Thin superadmin APIs expose status / toggle / trigger; the React pricing widget gains a `SyncBanner`.

**Tech Stack:** Django 6 + DRF, Celery + django-celery-beat, httpx (already a dependency; tests use `httpx.MockTransport` — no new dependency), django-redis, React + TypeScript + Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md` §5.2, §5.3, §5.10 (guard 3), §5.11 (authoritative) + `docs/completed/Requirements_AI_Pricing_Management.md` v1.1 §6, §8, §9, §11, §12.5. Requirements SYNC-01..04 (+ GAP-03 sync clause) in `.planning/REQUIREMENTS.md`.

**Branch:** `feat/v0.10-ai-cost-pricing` (same PR as Phases 34–35).

## Global Constraints

- Superadmin only; API prefix `/api/v1/superadmin/ai-pricing/sync/`; `IsAuthenticated` + `IsSuperadmin`; throttles: status uses `superadmin_ai_pricing_read`, toggle uses `superadmin_ai_pricing_write`, trigger is **1 per 15 minutes per user**.
- Sync is **off by default**; the switch lives in the database (`AiPricingSyncConfig.enabled`), never in an env setting.
- Source URL `AI_PRICING_SYNC_SOURCE_URL` default `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`; HTTPS GET, **15 s timeout**; tolerance `AI_PRICING_SYNC_TOLERANCE_USD_PER_1M` default `0.000001` (Decimal).
- **Models checked** = models in `AiUsageLog` within `AI_PRICING_LOOKBACK_DAYS` (90) **∪ `settings.OPENAI_MODEL`**. Never add prices for other models. **Exact key match only** — no fuzzy matching.
- **Conversion:** per-1M = `Decimal(str(per_token)) * Decimal(1_000_000)`, quantized to 8 dp. Missing `cache_read_input_token_cost` → `0`. Missing `input_cost_per_token` or `output_cost_per_token` → model is "unpriced" (skipped, WARNING log).
- **Per model:** not in LiteLLM → `unpriced`; no price active now → **Case A** add (`source="sync"`, audit `ai_pricing.added_from_sync`); active price within tolerance on all three fields → **Case B** unchanged; differs and active row `source="manual"` → **skipped_manual** (record ours vs LiteLLM, change nothing); differs otherwise → **Case C** add (`source="sync"`, audit `ai_pricing.updated_from_sync`); a scheduled price exists → **skipped_scheduled**. New rows start at the sync's `now`.
- All price writes go through `services.pricing_management.add_price` (actor `None`). Never touch `AiUsageLog`. Never delete prices.
- **Fetch / parse failure** → no pricing change; config `last_status="failed"`, `last_error` set; audit `ai_pricing.sync_failed`; WARNING log.
- **Success** → config `last_status="success"`, `last_success_at`, `last_summary`; audit `ai_pricing.sync_completed` with counts. Audit rows: `organisation=None`, `entity_type="ai_pricing"`, `entity_id="sync"` for run-level events, the pricing row id for per-price events.
- Toggle writes audit `ai_pricing.sync_enabled` / `ai_pricing.sync_disabled` with the actor.
- **Overdue** = enabled and (`last_success_at` is null or older than 14 days).
- Concurrency: one sync at a time — `distributed_lock("lock:ai_pricing:sync", timeout=300)`, non-blocking; a second concurrent run returns `skipped_locked`.
- Beat: `sync_ai_pricing_from_litellm_task`, Monday 09:00 UTC, queue `default`, seeded by data migration (django-celery-beat DB scheduler). The scheduled run does nothing when disabled; "Sync Now" runs even when disabled.
- Missing-pricing caches are invalidated after any sync that changed prices (Phase 35 `services.pricing_cache`).
- Tests never hit the network.

## Review Focus

1. **A Superadmin hand-set a contract price; LiteLLM differs** → the sync leaves it alone every week and the banner lists it. → Task 3.
2. **LiteLLM is down, slow, returns HTML, or the JSON shape changed** → nothing changes, the banner turns amber with the error, the next run retries. → Tasks 2, 3.
3. **The switch is off and Monday arrives** → nothing is fetched or written; "Sync Now" still works. → Tasks 3, 4.
4. **Two Superadmins press "Sync Now" together, or it overlaps the Monday run** → one run proceeds, the other reports it was skipped; never duplicate prices. → Task 3.
5. **A scheduled price is pending for a model whose LiteLLM price changed** → the sync skips it rather than failing the whole run. → Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `apps/integrations/openai/models.py` + `migrations/0006_ai_pricing_sync_config.py` | `AiPricingSyncConfig` singleton |
| `apps/integrations/openai/litellm.py` (create) | Fetch + parse + convert LiteLLM JSON |
| `apps/integrations/openai/services/pricing_management.py` (modify) | `add_price(..., audit_action=...)` |
| `apps/integrations/openai/services/pricing_sync.py` (create) | `run_pricing_sync`, `set_sync_enabled` |
| `apps/integrations/openai/selectors/pricing_sync.py` (create) | `get_sync_status` |
| `apps/integrations/openai/tasks.py` (create) + `migrations/0007_beat_ai_pricing_sync.py` | Celery task + Beat seed |
| `config/settings/base.py` (modify) | sync settings, route, throttle |
| `apps/integrations/openai/pricing_views.py`, `serializers.py`, `api_urls.py` (modify) | status / toggle / trigger |
| `frontend/src/widgets/ai-pricing/{SyncBanner.tsx, api.ts, types.ts, MissingPricingAlert.tsx, AiPricingWidget.tsx}`, `frontend/src/widgets/ai-cost/AiCostWidget.tsx` | UI |

---

### Task 1: Sync config singleton + toggle service

**Files:**
- Modify: `apps/integrations/openai/models.py`
- Create: `apps/integrations/openai/migrations/0006_ai_pricing_sync_config.py` (makemigrations + a RunPython that creates row pk=1), `apps/integrations/openai/services/pricing_sync.py` (toggle only for now), `apps/integrations/openai/selectors/pricing_sync.py`
- Test: `apps/integrations/openai/tests/test_pricing_sync_config.py`

**Interfaces:**
- Produces:
  - `class AiPricingSyncConfig(models.Model)`: `class Status(TextChoices): NEVER="never"; SUCCESS="success"; FAILED="failed"`; fields `enabled=BooleanField(default=False)`, `last_run_at=DateTimeField(null=True, blank=True)`, `last_success_at=DateTimeField(null=True, blank=True)`, `last_status=CharField(max_length=10, choices=Status.choices, default=Status.NEVER)`, `last_error=TextField(blank=True)`, `last_summary=JSONField(default=dict, blank=True)`, `updated_at=DateTimeField(auto_now=True)`; `db_table="openai_ai_pricing_sync_config"`; `CheckConstraint(condition=Q(pk=1), name="ai_pricing_sync_config_singleton")`; classmethod `load() -> AiPricingSyncConfig` (`get_or_create(pk=1)`). No indexes (single row).
  - `def set_sync_enabled(*, enabled: bool, actor: User) -> AiPricingSyncConfig` — `select_for_update` the row; no-op (no audit) if unchanged; else save + audit `ai_pricing.sync_enabled`/`ai_pricing.sync_disabled` (`entity_id="sync"`, before/after `{"enabled": …}`).
  - `class SyncStatus(TypedDict): enabled: bool; last_run_at: datetime | None; last_success_at: datetime | None; last_status: str; last_error: str; overdue: bool; summary: dict[str, Any]; next_run_at: datetime | None`
  - `def get_sync_status(*, now: datetime | None = None) -> SyncStatus` — `next_run_at` = next Monday 09:00 UTC after `now` when enabled, else `None`; `overdue` per Global Constraints.

- [ ] **Step 1: Write the failing tests** — `load()` creates once and returns the same row; a second row with pk=2 violates the constraint; `set_sync_enabled(True)` → enabled + one audit `ai_pricing.sync_enabled` with organisation None and actor; same value again → no new audit; `get_sync_status` overdue cases (disabled → False; enabled + never succeeded → True; enabled + success 13 days ago → False; 15 days → True); `next_run_at` on a Monday 08:00 → same day 09:00, on Monday 09:00 → next Monday 09:00.
- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_pricing_sync_config.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** Verify the migration both ways on dev Postgres (`docker compose exec -T web python manage.py migrate openai` / `migrate openai 0005` / forward).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): sync config singleton and toggle service`

---

### Task 2: LiteLLM client

**Files:**
- Create: `apps/integrations/openai/litellm.py`
- Modify: `config/settings/base.py` (`AI_PRICING_SYNC_SOURCE_URL`, `AI_PRICING_SYNC_TOLERANCE_USD_PER_1M` — env-backed; tolerance read as a string and converted to `Decimal`)
- Test: `apps/integrations/openai/tests/test_litellm.py`

**Interfaces:**
- Produces:
  - `class LiteLLMFetchError(Exception)` (message is safe to show a Superadmin; never includes response bodies longer than 200 chars).
  - `@dataclass(frozen=True) class LiteLLMPrice: input_per_1m: Decimal; output_per_1m: Decimal; cached_per_1m: Decimal`
  - `@dataclass(frozen=True) class LiteLLMCatalog: prices: dict[str, LiteLLMPrice]; unusable: frozenset[str]` (`unusable` = keys present but missing input or output cost)
  - `def fetch_litellm_catalog(*, url: str | None = None, timeout: float = 15.0, transport: httpx.BaseTransport | None = None) -> LiteLLMCatalog` — raises `LiteLLMFetchError` on network error, timeout, non-200, non-JSON, or a top-level value that isn't an object. Entries that aren't objects are ignored. `transport` exists for tests (`httpx.MockTransport`).
  - `def to_per_1m(value: object) -> Decimal` — `Decimal(str(value)) * Decimal(1_000_000)` quantized to `Decimal("0.00000001")`; raises `ValueError` for non-numeric / negative.

- [ ] **Step 1: Write the failing tests**

```python
def test_converts_per_token_to_per_1m():
    assert to_per_1m(0.00000015) == Decimal("0.15000000")
    assert to_per_1m("0.0000006") == Decimal("0.60000000")

def test_parses_catalog_with_cached_default_zero(): ...      # entry without cache_read_input_token_cost → cached 0
def test_entry_missing_output_cost_is_unusable(): ...        # in .unusable, not in .prices
def test_non_object_entries_ignored(): ...                    # "sample_spec": "text" skipped
@pytest.mark.parametrize("response", [500 status, HTML body, JSON list, timeout, connect error])
def test_fetch_failures_raise_fetch_error(response): ...     # httpx.MockTransport raising / returning each
def test_uses_configured_url_and_timeout(settings): ...       # MockTransport asserts request URL; timeout passed
```

- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): LiteLLM price catalog client`

---

### Task 3: Sync service

**Files:**
- Modify: `apps/integrations/openai/services/pricing_management.py` (add `audit_action: str = "ai_pricing.added"` keyword to `add_price`, used for the audit row's `action`), `apps/integrations/openai/services/pricing_sync.py`
- Test: `apps/integrations/openai/tests/test_pricing_sync.py`

**Interfaces:**
- Consumes: Task 1 config, Task 2 client, Phase 35 `add_price` + `ScheduledPriceExistsError` / `PricingError`, `services.pricing_cache` invalidation, `selectors.pricing` recent-usage helper (reuse; don't duplicate the query), `apps.common.locks.distributed_lock`.
- Produces:
  - `class SyncOutcome(StrEnum): COMPLETED="completed"; FAILED="failed"; SKIPPED_DISABLED="skipped_disabled"; SKIPPED_LOCKED="skipped_locked"`
  - `@dataclass class SyncSummary: outcome: SyncOutcome; added: list[str]; updated: list[str]; unchanged: list[str]; skipped_manual: list[dict]; skipped_scheduled: list[str]; unpriced: list[str]; errored: list[str]; error: str = ""` with `def as_json(self) -> dict` (Decimals as 8-dp strings). `skipped_manual` items: `{"model", "ours": {input, output, cached}, "litellm": {input, output, cached}}`.
  - `def run_pricing_sync(*, force: bool = False, now: datetime | None = None, transport: httpx.BaseTransport | None = None) -> SyncSummary`

Algorithm:
```
if not force and not config.enabled: return SyncSummary(SKIPPED_DISABLED)   # no writes, no fetch
with distributed_lock("lock:ai_pricing:sync", timeout=300) as acquired:
    if not acquired: return SyncSummary(SKIPPED_LOCKED)
    config.last_run_at = now; save
    try catalog = fetch_litellm_catalog(transport=transport)
    except LiteLLMFetchError as e: mark failed (last_status, last_error=str(e)), audit ai_pricing.sync_failed {"error": str(e)}, log WARNING, return FAILED
    for model in sorted(recent_usage_models ∪ {OPENAI_MODEL}):
        per-model try/except Exception → errored (log exception, continue)
        apply Case A / B / C / skipped_manual / skipped_scheduled / unpriced per Global Constraints
    mark success (last_status, last_success_at=now, last_error="", last_summary=summary.as_json())
    audit ai_pricing.sync_completed {counts + skipped_manual + unpriced}
    if added or updated: on_commit(invalidate pricing caches)
    return summary
```
Each `add_price` call runs in its own transaction (it is `@transaction.atomic`), so one model's failure never rolls back another's.

- [ ] **Step 1: Write the failing tests** (catalog via `httpx.MockTransport`; `distributed_lock` patched in one test to yield False)

```python
def test_disabled_scheduled_run_does_nothing(db): ...                    # Review Focus 3: no fetch (transport asserts not called), no config change
def test_force_runs_even_when_disabled(db): ...
def test_case_a_adds_price_for_unpriced_used_model(db): ...              # source sync, audit added_from_sync, effective_from == now
def test_case_b_within_tolerance_unchanged(db): ...
def test_case_c_updates_sync_or_seed_price(db): ...                      # old closed at now, audit updated_from_sync
def test_manual_price_never_overridden(db):                               # Review Focus 1
    ...  # manual row differs → unchanged rows, summary.skipped_manual has ours/litellm, run twice → still unchanged
def test_scheduled_price_pending_is_skipped_not_fatal(db): ...           # Review Focus 5; other models still processed
def test_model_not_in_litellm_is_unpriced(db): ...
def test_unusable_entry_is_unpriced(db): ...
def test_configured_model_included_without_usage(db, settings): ...
def test_models_not_used_are_never_added(db): ...
def test_fetch_failure_changes_nothing_and_records_error(db): ...        # Review Focus 2: no AiPricing rows changed; last_status failed; audit sync_failed
def test_concurrent_run_skipped_when_locked(db): ...                     # Review Focus 4
def test_second_run_is_idempotent(db): ...                               # run twice → second run all unchanged, no new rows
def test_completed_run_records_summary_and_audit(db): ...
def test_per_model_error_isolated(db): ...                               # patch add_price to raise for one model → errored, others applied
def test_never_touches_usage_log(db): ...
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_pricing_sync.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run** `uv run pytest apps/integrations/openai -q` — Expected: PASS (Phase 35 `add_price` tests unaffected by the new keyword).
- [ ] **Step 5: Commit** `feat(ai-pricing): LiteLLM pricing sync service`

---

### Task 4: Celery task + weekly Beat schedule

**Files:**
- Create: `apps/integrations/openai/tasks.py`, `apps/integrations/openai/migrations/0007_beat_ai_pricing_sync.py` (mirror `apps/credits/migrations/0003_beat_credit_lapse.py`)
- Modify: `config/settings/base.py` (`CELERY_TASK_ROUTES["apps.integrations.openai.tasks.sync_ai_pricing_from_litellm_task"] = {"queue": "default"}`)
- Test: `apps/integrations/openai/tests/test_pricing_sync_task.py`

**Interfaces:**
- Produces: `@shared_task def sync_ai_pricing_from_litellm_task(force: bool = False) -> dict` — thin wrapper returning `run_pricing_sync(force=force).as_json()`; logs one INFO line with counts. **No autoretry** (fetch failures are handled and recorded inside the service; the next weekly run retries) — document this in the docstring like `apps/credits/tasks.py`.
- Beat seed: `CrontabSchedule(minute="0", hour="9", day_of_week="1", day_of_month="*", month_of_year="*", timezone="UTC")`; `PeriodicTask(name="ai_pricing_sync_from_litellm", task="apps.integrations.openai.tasks.sync_ai_pricing_from_litellm_task", queue="default", enabled=True, kwargs="{}")`; reverse deletes the PeriodicTask by name.

- [ ] **Step 1: Write the failing tests** — task (eager) with sync disabled returns `outcome == "skipped_disabled"`; with `force=True` calls the service with `force=True` (patch the service); route present in `CELERY_TASK_ROUTES`; the migration's seed function creates exactly one PeriodicTask with the crontab above and is idempotent when run twice; reverse removes it.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** — Expected: PASS; migrate forward/back on dev Postgres.
- [ ] **Step 5: Commit** `feat(ai-pricing): weekly LiteLLM sync task and beat schedule`

---

### Task 5: Sync APIs

**Files:**
- Modify: `apps/integrations/openai/pricing_views.py`, `serializers.py`, `api_urls.py`, `config/settings/base.py` (throttle rate `superadmin_ai_pricing_sync_trigger`)
- Test: `apps/integrations/openai/tests/test_pricing_sync_views.py`

**Interfaces:**
- Consumes: Task 1 `get_sync_status`, `set_sync_enabled`; Task 4 task.
- Produces:
  - `GET /api/v1/superadmin/ai-pricing/sync/status/` → `{enabled, last_run_at, last_success_at, last_status, last_error, overdue, next_run_at, summary: {added, updated, unchanged, skipped_manual: [{model, ours: {input, output, cached}, litellm: {…}}], skipped_scheduled, unpriced, errored}}` (summary keys always present; empty lists when never run) — name `superadmin-ai-pricing-sync-status`.
  - `POST /api/v1/superadmin/ai-pricing/sync/toggle/` body `{enabled: bool}` → 200 status payload — name `superadmin-ai-pricing-sync-toggle`.
  - `POST /api/v1/superadmin/ai-pricing/sync/trigger/` → 202 `{queued: true}`; enqueues `sync_ai_pricing_from_litellm_task.delay(force=True)` via `transaction.on_commit` — name `superadmin-ai-pricing-sync-trigger`. Throttle: a `SimpleRateThrottle` subclass `SyncTriggerThrottle` keyed per user with rate `"1/15m"` (override `parse_rate` to accept a numeric multiplier on the period: `"1/15m"` → 1 request per 900 s). 429 body is DRF's default.

- [ ] **Step 1: Write the failing tests** — 403 org admin/staff + 401/403 anonymous on all three; CSRF enforced on toggle/trigger (`APIClient(enforce_csrf_checks=True)` + `force_login`); status shape for never-run and after a completed run; toggle on/off returns new state and writes one audit row each; toggle 400 on missing/non-bool `enabled`; trigger 202 and the task is enqueued once on commit (patch `.delay`); second trigger within 15 min → 429, after 15 min (patch time) → 202; `parse_rate("1/15m") == (1, 900)`; query ceilings (status ≤ 3, toggle ≤ 6).
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** `uv run pytest apps/integrations/openai -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): sync status, toggle and trigger endpoints`

---

### Task 6: Sync banner, alert note, Cost Explorer caveat

**Files:**
- Create: `frontend/src/widgets/ai-pricing/SyncBanner.tsx` + test
- Modify: `frontend/src/widgets/ai-pricing/{api.ts, types.ts, AiPricingWidget.tsx, MissingPricingAlert.tsx}` + tests, `frontend/src/widgets/ai-cost/AiCostWidget.tsx` (+ its footer test)

**Interfaces:**
- Consumes: Task 5 contracts.
- Produces: `api.ts` `fetchSyncStatus()`, `toggleSync(enabled)`, `triggerSync()`; `SyncBanner({ onChanged })`.

Copy (exact, PM §6.2, §6.4, §6.5, §7.3, §11; design §5.11):
- Off (grey): "Automatic pricing sync is off. Prices update only when you add them manually." + button "Enable sync".
- On (green): "Automatic pricing sync is on. Last synced: {MMM D, YYYY} at {HH:MM} UTC." (or "Not synced yet." when never succeeded) + button "Disable sync".
- Failed or overdue (amber): failed → "Last sync failed {MMM D, YYYY}. Click to view details."; overdue without failure → "No successful sync in over 14 days. Click to view details." Clicking opens a small modal showing `last_error` (or "No error recorded.") and the last run time.
- Always: secondary button "Sync Now". On 202 show "Sync started. Refresh in a minute to see results." and refetch status after 30 s; on 429 show "Sync Now can be used once every 15 minutes."
- When `summary.skipped_manual` is non-empty: "{N} hand-set price(s) differ from LiteLLM" with a list "`{model}`: ours ${in}/${out}/${cached} · LiteLLM ${in}/${out}/${cached}" (6 dp) and a per-row button "Use LiteLLM price" that opens the Add New Price modal pre-filled with the LiteLLM values and model.
- Enable/Disable asks for confirmation with the existing ConfirmModal: "Turn on automatic pricing sync? Prices for models you use will update every Monday 09:00 UTC. Hand-set prices are never changed." / "Turn off automatic pricing sync?".
- `MissingPricingAlert` (pricing variant): when sync is enabled, add "Next weekly sync (Mon 09:00 UTC) will fetch pricing from LiteLLM automatically for models it covers."
- Cost Explorer footer becomes: "Based on configured pricing; sync status: {synced N days ago | synced today | sync off | sync failed}. Actual OpenAI invoice is authoritative." (falls back to the Phase 34 caveat if the status request fails).

- [ ] **Step 1: Write the failing tests** — each banner state renders its exact copy; toggle opens confirm then calls `toggleSync`; Sync Now 202 and 429 messages; details modal shows `last_error`; skipped-manual list and "Use LiteLLM price" pre-fills the modal; alert note only when enabled; Cost Explorer footer variants and fallback.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** `cd frontend && npx vitest run && npm run build` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): sync banner, sync note and cost explorer sync caveat`

---

### Task 7: Milestone close-out

**Files:**
- Modify: `CLAUDE.md` §3 tree (`litellm.py`, `services/pricing_sync.py`, `selectors/pricing_sync.py`, `tasks.py`), §12.2 route line, §12.5 Beat table row (`sync_ai_pricing_from_litellm_task` | `default` | Weekly, Monday 09:00 UTC — opt-in LiteLLM price sync, does nothing unless enabled (v0.10/Phase 36)), §14.4 one line on the sync rule (never overrides `source=manual`), §28 references if any; `.planning/ROADMAP.md` (tick Phase 36; mark v0.10 shipped-pending-merge in the milestone list); `.planning/REQUIREMENTS.md` (mark all v0.10 requirements delivered).
- Move: `Requirements_AI_Cost_Explorer.md` and `Requirements_AI_Pricing_Management.md` from `docs/in-progress/` → `docs/completed/` (done); update every reference (a grep for the old in-progress path over `.planning`, `docs` and `CLAUDE.md` must return nothing afterwards).

- [ ] **Step 1:** Controller runs `code-reviewer`, `orm-performance-auditor`, `tenant-security-auditor` on the Phase 36 diff; apply accepted findings.
- [ ] **Step 2:** `uv run pre-commit run --all-files`, full `uv run pytest`, `uv run python manage.py makemigrations --check --dry-run`, `cd frontend && npx vitest run && npm run build` — all pass.
- [ ] **Step 3:** Commit `docs(v0.10): close out phase 36 and milestone v0.10`.
