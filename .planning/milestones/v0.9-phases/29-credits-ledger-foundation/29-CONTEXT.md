# Phase 29: Credits Ledger Foundation - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the `apps/credits` bounded context that every later v0.9 phase builds on:

- `ShopCreditBalance`: one row per shop per UTC month, created lazily. Uniqueness and `0 <= consumed <= allocated + bonus` are DB-enforced.
- `CreditTransaction`: the append-only ledger.
- `Organisation.monthly_credit_allocation`: its own migration, NOT NULL default 0, CHECK 0–10,000.
- `periods.current_period()`: the time seam.
- `allocation.ensure_balance()`: `get_or_create` in its own atomic block.
- One pure tiered cost function.
- Read selectors (single-shop virtual balance and the `annotate_credit_state` list annotation) that never write.
- Read-only Django admin.
- A Postgres CI job with a registered `pg_concurrency` marker and the first-use race test.

Requirements: CRED-02, CRED-03, CRED-04, CRED-05, CQA-01.

**Not in this phase:**
- Reserve/commit/refund wiring and the 402 response (Phase 30)
- Lapse and reaper Beat jobs (Phase 31)
- The Superadmin allocation UI/audit and the CRED-06 materialise-on-edit rule (Phase 32)
- Any UI and the Staff scoping work (Phase 33)

</domain>

<decisions>
## Implementation Decisions

### Already closed upstream (do not re-litigate)
- BigAutoField PKs, not UUIDs.
- Cost is computed from `Review.comment`, trimmed (not `review.text`).
- Consumption `credits_delta` is **negative**. Headline "used" reads `balance.consumed_credits`, never `SUM(history)`.
- No backfill. Rollout is a deploy note (CQA-02, Phase 30), and orgs are enabled through CRED-06 (Phase 32).
- On lazy creation with allocation 0, write the balance row but **no** zero-amount INITIAL transaction and no audit row.

### Ledger schema & FKs
- **D-01:** Create the **full** `CreditTransaction` schema in Phase 29, including the nullable forward columns later phases need:
  - `review` FK
  - `actor` FK (user)
  - `ai_usage_log` FK → `openai.AiUsageLog` (direction is tx → usage log, never the reverse)
  - `note`

  Phases 30/31 then add code only, with no ledger-table migrations. — **Reversibility:** costly — dropping or reshaping columns later means migrations on a growing, append-only table.
- **D-02:** FK delete rules:
  - `ShopCreditBalance.shop`: **PROTECT**
  - `CreditTransaction.shop_credit_balance`: **PROTECT**
  - `review`, `actor`, `ai_usage_log`: **SET_NULL**

  Ledger history must never disappear. Shops are only soft-deactivated today (`Shop.is_active`), so PROTECT doesn't block any existing flow. Note for the future: an org/shop hard-delete or data reset (deferred Phase 28) will need to handle these PROTECT FKs explicitly. — **Reversibility:** one-way — changing on_delete later needs a migration and changes audit-retention guarantees.
- **D-03:** Lazy-creation events are **system events**. The INITIAL_ALLOCATION ledger row and the `shop.credits.allocated` AuditLog row use `actor=None`, following the Phase 24 polarity-job convention.
- **D-04:** `note` is an optional nullable short text column (≤255) for BONUS_ALLOCATION reasons. Phase 32's bonus modal may use it.

### Append-only enforcement
- **D-05:** Enforce append-only in the **app layer plus DB CHECKs**, with no Postgres trigger:
  - `save()` on an existing row rejects any change other than `status`.
  - `delete()` raises.
  - A custom QuerySet blocks `update()` and `delete()`, except through the named status-transition service functions.
  - Django admin is read-only for both models (no add/change/delete permissions).
  - Value invariants are DB `CheckConstraint`s, so SQLite and Postgres behave the same.
- **D-06:** Allowed status transitions are **RESERVED → COMMITTED** and **RESERVED → REFUNDED** only.
  - Only CONSUMPTION rows are created as RESERVED.
  - INITIAL_ALLOCATION, BONUS_ALLOCATION and LAPSED rows are created COMMITTED and are final.
  - Each transition is a CAS: `filter(pk=..., status=RESERVED).update(status=...)`. Success is judged by the affected-row count. COMMITTED → REFUNDED is **not** allowed.
- **D-07:** Ledger DB constraints and indexes added in Phase 29:
  - Partial `UniqueConstraint(balance) WHERE type=INITIAL_ALLOCATION`
  - Partial `UniqueConstraint(balance) WHERE type=LAPSED` (Phase 31's lapse depends on it)
  - Partial index on `(status, created_at) WHERE status=RESERVED` (for the Phase 31 reaper)

  This sits alongside the balance's `UniqueConstraint(shop, year, month)` and the `CHECK (consumed >= 0 AND consumed <= allocated + bonus)` / non-negative CHECKs. — **Reversibility:** costly — each constraint has its own migration and later phases rely on it.

### Cost function
- **D-08:** `credit_cost(text) -> int` is a pure, total function. For empty or whitespace-only input (trimmed length 0) it **returns 0** and does not raise. 0 means "not chargeable": Phase 30 returns 400 before reserving, and the UI hides the AI button.
- **D-09:** Length is `len(comment.strip())` in **Python code points**, with no new dependency. The UI never recomputes cost; it always uses the server-supplied value. The emoji boundary test documents that one emoji code point counts as 1.
- **D-10:** `REVIEWBEE_CREDIT_TIERS` is a list of `(max_len, cost)` tuples whose last `max_len` is `None` (an open-ended top tier). Default: `[(100, 1), (500, 2), (None, 3)]`. A settings test asserts the list is ascending, ends with `None`, and has positive costs. Boundary tests cover 0, 1, 100, 101, 500, 501, 10000, 10001, emoji, and whitespace-only.

### Balance read contract
- **D-11:** The single-shop virtual-balance selector returns a **frozen dataclass**, e.g. `CreditBalanceView(shop_id, year, month, allocated, bonus, consumed, remaining, is_enabled, is_materialized, renews_on)`.
  - `is_enabled = (allocated + bonus) > 0`.
  - `is_materialized` says whether a row exists.
  - The selector never writes. Phases 32/33 serialize it.
- **D-12:** A shop with no current-month row reports the **organisation's live `monthly_credit_allocation`** as allocated/remaining (CRED-05), with bonus=0 and consumed=0. `annotate_credit_state` uses the same `Coalesce` fallback (FilteredRelation or Subquery; both are N+1-safe). Phase 32's CRED-06 materialise-on-edit keeps this correct across N→M changes.
- **D-13:** Inactive (soft-deactivated) shops are **computed normally**. Selectors don't filter on `is_active`, the UI decides what to display, and lapse still covers their rows.

### Postgres CI (CQA-01)
- **D-14:** Add a **separate** `backend-pg` CI job:
  - `services: postgres:16`, using a new `config.settings.test_pg`.
  - Runs `pytest -m pg_concurrency` only.
  - Register `pg_concurrency` in `pyproject.toml` markers, because `--strict-markers` is on.
  - Marked tests auto-skip when the DB vendor isn't Postgres, so the existing SQLite job and its 85% coverage gate are unchanged.
  - Add `make test-pg` for local runs against the docker-compose `db`.
  - Race tests use `django_db(transaction=True)`, `threading.Barrier`, and `connections.close_all()` in `finally`.
  - Phase 29 ships the first-use race test: N concurrent first uses produce one balance row and one INITIAL row.

### Claude's Discretion
- Exact module and file names inside `apps/credits` (follow the ARCHITECTURE.md layout: `services/periods.py`, `services/credit_cost.py`, `services/allocation.py`, `selectors/balances.py`).
- Enum storage (TextChoices) and column names, as long as the semantics above hold.
- Whether to use FilteredRelation or Subquery for `annotate_credit_state`, decided by a query-count test.
- Exactly how `ensure_balance` handles the lock: `get_or_create` in its own atomic, then INITIAL tx + audit only when `created`. Do not use `select_related` with `select_for_update`; use `of=("self",)`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & requirements
- `docs/completed/Requirements_Credits_System.md`: binding spec v1.0. Read it together with the reconciliations in REQUIREMENTS.md line 7.
- `.planning/REQUIREMENTS.md`: CRED-02..05 and CQA-01 (Phase 29), and CRED-06/CQA-02 (the context behind the rollout decisions).
- `.planning/ROADMAP.md` § "Phase 29: Credits Ledger Foundation": success criteria and the enablers list.
- `.planning/PROJECT.md` § "Key v0.9 decisions"

### Research
- `.planning/research/SUMMARY.md`: cross-cutting items #1 (Postgres CI) and #5 (Coalesce fallback), and the reconciled settle/lazy-create choices.
- `.planning/research/ARCHITECTURE.md`: `apps/credits` layout and dependency direction (credits imports nothing from shops/reviews/organisations; string FKs).
- `.planning/research/PITFALLS.md`: SQLite false assurance, the first-use race, ledger semantics.
- `.planning/research/STACK.md`: Django 6.0.2 constraint syntax (`CheckConstraint(condition=...)`, partial `UniqueConstraint`, `FilteredRelation`).

### Project conventions
- `CLAUDE.md` §3 (add `apps/credits` to the app list), §5 (services/selectors), §6 (N+1, indexes, query-count tests, `select_for_update`), §16 (testing), §19 (CI), §27 (run `orm-performance-auditor` on models/constraints/migrations), §29.4 (AuditLog usage).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/common/models.py::AuditLog`: fields organisation, nullable actor, entity_type, entity_id, action, before_data, after_data. Use it for `shop.credits.allocated`.
- `apps/reviews/services/reclassify.py::_flip_and_audit`: the analog for a system-actor (`actor=None`) audit write inside an atomic block.
- `apps/reviews/services/finalise.py::_refresh_review_counts`: the analog for a single grouped aggregate with a query-count test.
- `apps/organisations/services/organisations.py::_UPDATABLE_FIELDS`: whitelist. Phase 32 adds `monthly_credit_allocation`; Phase 29 only adds the field and migration.

### Established Patterns
- `config/settings/test.py` re-declares `INSTALLED_APPS` and uses SQLite `:memory:`, so `apps.credits` must go in **both** `base.py` and `test.py`.
- `pyproject.toml` pytest `addopts` includes `--strict-markers`, so `pg_concurrency` must be registered.
- `.github/workflows/ci.yml` has `frontend-test`, `lint-typecheck` and `backend-test` jobs. Add `backend-pg` next to them.
- Shops are soft-deactivated (`apps/shops/services/shops.py` toggles `is_active`) and never hard-deleted in services.
- Read-only admin precedent: `readonly_fields` in `apps/action_items/admin.py`. Credits admin should also deny add/change/delete.

### Integration Points
- `apps/organisations/models.py::Organisation`: add `monthly_credit_allocation` (own migration).
- `openai.AiUsageLog`: the target of the nullable `ai_usage_log` FK (SET_NULL).
- `reviews.Review`: the target of the nullable `review` FK (SET_NULL).

</code_context>

<specifics>
## Specific Ideas

- One emoji counts as 1 credit-length unit. Document this in the boundary test rather than treating it as a bug.
- The invariant `consumed_credits == SUM(-delta) WHERE type=CONSUMPTION AND status IN (RESERVED, COMMITTED)` should be expressible as a test helper now. Phase 30 will exercise it.

</specifics>

<deferred>
## Deferred Ideas

- A Postgres trigger enforcing ledger immutability at the DB level was considered and rejected for now (it can't be tested on SQLite). Revisit if a non-ORM write path ever appears.
- COMMITTED → REFUNDED (goodwill refunds after commit) is out of scope and would need its own requirement.
- Handling PROTECT FKs during a future org/shop hard-delete or the deferred Phase 28 data reset.

</deferred>

---

*Phase: 29-credits-ledger-foundation*
*Context gathered: 2026-11-11*
