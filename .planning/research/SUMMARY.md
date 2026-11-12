# Project Research Summary

**Project:** ReviewBee (review-master), milestone v0.9 AI Reply Credits
**Domain:** Per-shop monthly usage-credit ledger gating one AI feature (reply drafting) in a multi-tenant Django/DRF/Celery/React SaaS
**Researched:** 2026-11-11
**Confidence:** HIGH (codebase-verified); MEDIUM on client-disconnect behaviour under Daphne and on Beat missed-run semantics

## Executive Summary

v0.9 is a leaf bounded context (`apps/credits`) bolted onto a shipped feature: AI reply generation (Phase 19) becomes metered. The expert pattern is an append-only ledger plus a per-shop-per-UTC-month balance row with a two-phase **reserve → fulfil → commit-or-refund** flow: the reserve is a short row-locked transaction, the OpenAI call runs with no lock held, and settlement is a compare-and-swap on `status=RESERVED` so commit, refund and the reaper are mutually exclusive. Research found **no new dependency is needed** (Django 6.0.2, Celery 5.6.3, django-celery-beat 2.9.0, the existing React widget kit cover everything); the hard parts are concurrency semantics, failure windows, and integration seams in existing code, not libraries.

The recommended approach is one orchestrator, `generate_reply_with_credits`, in `apps/reviews/services/reply_generation.py` (not the view, not `replies.py`, not inside `generate_reply_draft`), with the DB as the safety net: unique `(shop, year, month)`, `CHECK (consumed <= allocated + bonus)`, `CHECK >= 0`, and partial unique indexes making INITIAL and LAPSED once-per-balance. Lapse is a self-healing catch-up sweep (all past periods lacking a LAPSED row), not "previous month only". List badges use one `FilteredRelation`/Subquery annotation with a `Coalesce` fallback to the org allocation because balance rows are lazy.

The main risks are not in the credits app itself but cross-cutting: tests run on SQLite (false assurance on locking); the OpenAI client has no explicit timeout (SDK default 600s) so the 5-minute reaper TTL can refund in-flight calls; `ContentModeratedException` has no stage and `generate_reply_draft` returns no usage-log id; the shops list has no Staff scoping; no Superadmin shop UI exists to host "Allocate Bonus"; and the default allocation of 0 would **disable a shipped feature for every existing org on deploy**. The roadmap must treat each as an explicit requirement, not an implementation detail.

## Key Findings

### Recommended Stack

Zero new runtime, dev, or frontend dependencies. Do not bundle a Django/Celery/DRF upgrade. See STACK.md.

**Core technologies (all existing, new usage):**
- Django ORM 6.0.2: `F()` atomic updates, `select_for_update`, `CheckConstraint(condition=...)`, partial `UniqueConstraint`, `FilteredRelation` — SQL verified against the pinned version.
- PostgreSQL 16: row locks and CHECK constraints are the correctness backstop; concurrency tests MUST run here.
- Celery Beat via `django-celery-beat` seed migration (copy `reviews/0013` / `0016`): monthly lapse `5 0 1 * *` UTC and `*/10` reaper, both on `default`; explicit `timezone="UTC"`.
- DRF 3.17.1 + drf-spectacular: 402 as explicit response / `APIException` subclass; document 400/402/422/502.
- stdlib `datetime` + one `current_period()` seam (`apps/credits/services/periods.py`): no dateutil, no freezegun.
- Existing `Modal` + `focus-trap-react`, react-query, lucide, Tailwind for Buy More and Bonus modals.

**Required config changes:** `REVIEWBEE_CREDIT_TIERS` (open-ended last tier), `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`, `REVIEWBEE_SUPPORT_EMAIL`; add `apps.credits` to `INSTALLED_APPS` in **base and test.py** (test.py re-declares the list); explicit reply-path OpenAI timeout.

### Expected Features

**Must have (table stakes, all P1):**
- `Organisation.monthly_credit_allocation` (0–10,000) on org create/edit with `organisation.credits.set` audit, whitelisted in `_UPDATABLE_FIELDS`
- `ShopCreditBalance` + `CreditTransaction` ledger, lazy row creation, virtual balance on reads (reads never write)
- Tiered cost 1/2/3 from one pure function, `len(comment.strip())`, server-authoritative
- Reserve/commit/refund wired into `generate_reply`; 402 (with `reason: not_enabled | exhausted`, `required`, `remaining`) and 400 on empty comment; moderation-stage refund split
- Composer: AI button hidden for star-only, cost on label, remaining text, disabled/zero/402 states, Buy More modal
- Shop Details credits card, Shops-list badge (N+1-safe, not-enabled state for total 0), Superadmin bonus modal
- Monthly lapse + stale-reservation reaper; AuditLog rows for every event; Staff-excluded Activity Log scoping
- Rollout step (backfill or runbook) so the 402 gate doesn't break existing orgs

**Should have (P2):** generate response carries `credits_charged` / `credits_remaining`; review list carries `ai_credit_cost`; before/after preview in bonus modal; read-only Django admin for ledger; static "credits are used even if you discard" helper line.

**Defer:** credits history UI (endpoint only if cheap), Reviews-page credit indicator, Superadmin usage report, real payments, shop-switcher badge (strike AC 33), rollover/overage/alerts, credits for other AI features, any WebSocket for balances (violates CLAUDE.md §13.2).

### Architecture Approach

`apps/credits` owns models, `periods`, `credit_cost`, `allocation` (lazy ensure + bonus), `consumption` (reserve/commit/refund), `lapse`, selectors, tasks, views. Dependency direction is strict: credits models/selectors use string FKs and import nothing from shops/reviews/organisations; `shops.selectors → credits.selectors`; `reviews.services → credits.services`; credits never imports reviews (the orchestrator passes plain IDs/ints). The FK runs `CreditTransaction → openai.AiUsageLog` (never reverse).

**Major components:**
1. `credits.services.consumption` + `allocation` — reserve (short atomic), settle via CAS on `status=RESERVED`, always via `tx.shop_credit_balance_id`, never a computed period.
2. `reviews.services.reply_generation.generate_reply_with_credits` — orchestrator; exception ordering in the view puts 402/400 before the catch-all `except Exception → 502`.
3. `credits.services.lapse` + `tasks` — per-balance `lapse_balance()` in its own atomic, chunked, skips balances with RESERVED rows.
4. `credits.selectors.balances` — `annotate_credit_state` (opt-in `with_credits=True` on `list_shops`) and single-shop virtual-balance selector.
5. Superadmin non-tenant endpoints (new) for shop credits and bonus allocation.

### Critical Pitfalls

1. **SQLite test settings hide every locking bug** — `select_for_update` no-op, threads can't share `:memory:`. Add Postgres CI job + `pg_concurrency` marker (register it; `--strict-markers` is on); test state-machine transitions deterministically on SQLite, true races only on Postgres.
2. **Reaper TTL vs OpenAI timeout** — `client.py` sets no timeout (SDK default 600s, verified). Use `_get_client().with_options(timeout=30, max_retries=1)` on the reply path only; keep TTL ≥ 2× worst case; reaper uses `skip_locked`; effective refund latency is TTL + up to 10 min.
3. **Double refund / late commit / month-boundary stranding** — every status change is a conditional UPDATE `WHERE status=RESERVED`; `consumed_credits` moves only via `F()`; lapse skips balances with RESERVED rows and reaper re-lapses past-period balances after refunding; late-commit policy: return the draft, attempt one conditional re-deduct, log AuditLog + Sentry.
4. **Moderation stage + usage-log plumbing** — add `stage` (and `usage_log_id`) to `ContentModeratedException` at both raise sites in `guardrails.py`; make `generate_reply_draft` a thin wrapper over `_generate_reply_draft_with_log -> (str, usage_log_id)`; 422 body says whether a credit was charged.
5. **Tenant leakage** — `list_shops`/`ShopViewSet` have no Staff scoping (adding credit fields leaks out-of-scope balances → violates AC 28); `TenantScopedViewSet` returns `none()` for Superadmin; Staff must not reach history or `shop.credits.*` Activity Log events.
6. **Rollout dark-launch** — default 0 means "disabled"; every existing org loses AI replies on deploy.

## Cross-Cutting Items the Roadmap Must Handle

| # | Item | Resolution | Owner |
|---|------|------------|-------|
| 1 | **Postgres CI for concurrency** (test settings are SQLite) | Add `config.settings.test_pg` + CI job with `services: postgres:16`; register `pg_concurrency` marker; `django_db(transaction=True)`, `threading.Barrier`, `connections.close_all()` in `finally`. Required tests: first-use race (one row, one INITIAL), N threads vs K credits (exactly K succeed), reaper vs late commit. Must land BEFORE consumption is called verified. | Phase 29 |
| 2 | **OpenAI timeout vs reservation TTL** | Reply-path `with_options(timeout=30, max_retries=1)` (don't touch shared defaults used by enrichment); settings sanity test `TTL >= 2 × timeout × (retries+1)`; verify LangSmith wrapper still traces. | Phase 30 |
| 3 | **`ContentModeratedException` stage + AiUsageLog id plumbing** | `stage` + `usage_log_id` kwargs (optional — enrichment unaffected); `_persist_moderated_log` returns pk; wrapper-returning-tuple pattern; test matrix: input-block refund, output-block commit-with-link, OpenAI failure refund, success. Exactly one AiUsageLog row per call (AC 38). Mandatory `ai-enrichment-specialist` review. | Phase 30 |
| 4 | **Lapse idempotency + catch-up** | Partial unique index on `(balance) WHERE type=LAPSED`; select `period < current AND NOT EXISTS LAPSED`; per-balance atomic; chunked; skip RESERVED; reaper re-lapses; `PeriodicTask.update_or_create` by name; monitor "not completed by 00:30 UTC". Tests: double run, outage across a boundary, midnight-straddling reservation. | Phase 31 |
| 5 | **Lazy-row Coalesce fallback** | Every list/detail read falls back to `organisation.monthly_credit_allocation`; reads never write; lazy create at allocation 0 writes balance row but no zero-delta INITIAL tx. Regression test: untouched shop shows full allocation, not 0/red. | Phase 32 |
| 6 | **Staff scoping gap in shops list** | Decide: (a) null credit fields for out-of-scope shops for Staff (recommended, surgical) or (b) fix `list_shops` scoping globally under a separate requirement. One shared `get_accessible_shop_for_credits` selector for every credit endpoint. History endpoint Org Admin/Superadmin only. Negative tests: cross-org, out-of-scope Staff, Staff→history, Org Admin→bonus. Run `tenant-security-auditor`. | Phase 32 |
| 7 | **Missing Superadmin shop UI for bonus** | Spec's "Shop Details (Superadmin)" screen doesn't exist (Superadmin has no tenant org; React surface is organisations-only). Build non-tenant endpoints `GET /api/v1/superadmin/organisations/{org_id}/shops/credits/` (paginated) + `POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/` (`IsAuthenticated & IsSuperadmin`, not `TenantScopedViewSet`, throttle scope), plus an org-row action in `org-management` opening a shops-and-balances modal. Largest scope risk; needs UI-SPEC first. Bonus: F() update, `ensure_balance()`, request echoes displayed period (409 on mismatch), org derived server-side, amount 1–10,000. | Phase 33 |
| 8 | **Rollout / dark-launch** | Default 0 must not silently kill a shipped feature. Require ONE of: data migration backfilling existing orgs to a business-chosen default, or a pre-deploy runbook gate. Update existing Phase 19/20 `generate_reply` tests and org factories (they'll 402). | Decide 29 → ship 30 → verify 34 |
| 9 | **Mid-month allocation change vs lazy creation** | FEATURES (accept + document) vs PITFALLS (materialise) conflict. Recommendation: honour AC 16 by materialising current-month balance rows with the OLD value inside the org-edit atomic, but treat a first-time 0 → N change as effective immediately. Emit `organisation.credits.set` only on actual change. Needs explicit product decision. | Decide 29 → build 33 |

## Implications for Roadmap

Suggested phase structure (Phases 29+). Six phases; do not merge Phase 30 with any UI phase. Phases 31 and 32 are independent and can run in parallel.

### Phase 29: Foundation (test infra, schema, cost function)
**Rationale:** Everything depends on schema; nothing in consumption can be called verified without Postgres CI.
**Delivers:** Postgres CI job + marker + `now`/`current_period()` seam; `Organisation.monthly_credit_allocation` (separate migration, NOT NULL default 0, CHECK 0–10,000, whitelist, audit); `apps/credits` app (models with all constraints, indexes incl. partial `(status, created_at) WHERE RESERVED`, PROTECT/SET_NULL FKs, read-only admin); `periods.py`; `credit_cost.py` with open-ended tier + boundary tests (0,1,100,101,500,501,10000,10001, emoji, whitespace); settings; `apps.credits` in base AND test.py.
**Decisions to close here:** rollout default/backfill (#8), mid-month policy (#9), bigint vs UUID PKs (recommend bigint), ledger sign conventions, `review.comment` not `review.text`.

### Phase 30: Consumption core
**Rationale:** Highest-risk, race-sensitive path; UI must build on a verified contract.
**Delivers:** `allocation.ensure_balance` (`get_or_create` in own atomic → INITIAL tx + audit only when `created` → `select_for_update(of=("self",))`, no `select_related`); `consumption.py` reserve/commit/refund with CAS; `InsufficientCreditsError`/`EmptyCommentError`; guardrails `stage`/`usage_log_id`; `_generate_reply_draft_with_log`; `generate_reply_with_credits`; view mapping (402/400 before 502 catch-all), `cost` `@action` on `ReviewViewSet`, response `credits_charged`/`credits_remaining`; reply-path OpenAI timeout; `assert not connection.in_atomic_block` guard; rollout backfill migration; updated existing tests/factories; `shop.credits.refunded` audit action.
**Order of operations in the view:** auth/scope → tone validation → throttle (10/min) → empty-comment 400 → reserve (last).

### Phase 31: Beat jobs (lapse + reaper)
**Rationale:** Needs models and `refund_reservation`; no UI dependency.
**Delivers:** `lapse.py` self-healing sweep, `reap_stale_reserved_transactions_task` (`skip_locked`, bounded batch, per-row atomic, WARNING log without review text), seed migration, `CELERY_TASK_ROUTES`, CLAUDE.md §12.5 update.

### Phase 32: Read API and visibility plumbing
**Rationale:** Provides the data three UI surfaces consume; the security-sensitive scoping work.
**Delivers:** `annotate_credit_state` (FilteredRelation or Subquery — either N+1-safe), `list_shops(with_credits=True)`, serializer fields with `default=None`, shop credits GET (virtual balance, never writes, `Cache-Control: no-store`), optional bare history selector, `ai_credit_cost` on review list, Activity Log selector change (Org Admin sees `shop.credits.*`, Staff does not), `period_label`/`renews_on` from server. Query-count tests (1 vs 20 shops).
**Mandatory:** `tenant-security-auditor` + `orm-performance-auditor`.

### Phase 33: Superadmin controls
**Rationale:** Depends on `allocation.py`; contains the biggest scope risk.
**Delivers:** bonus service + Superadmin endpoints (#7), org-form field in Create/Edit React modals, org-row shops-and-balances modal, mid-month materialise-on-edit (#9), before/after preview.
**Prerequisite:** `/gsd-ui-phase` for the Superadmin surface.

### Phase 34: Frontend and rollout verification
**Rationale:** Last, so it consumes stable contracts.
**Delivers:** Shop Details credits card + Shops-list badge (text not colour-only, total-0 "Not enabled" state, no divide-by-zero); composer: hidden for star-only, cost in toggle label and `aria-label`, "Uses N credits" note, tone pills disabled while generating (no abort-and-restart), 402 branch in `api.ts`, balance store keyed by `shop_id` + refresh event; Buy More modal; dates rendered with `timeZone: "UTC"` ("Renews Dec 1 (UTC)"); deploy-order check for #8.

### Phase Ordering Rationale

- Postgres CI and constraints first — they convert "we think it's race-safe" into "the DB enforces it".
- Consumption before everything else — UI, lapse and reaper all depend on settle semantics and on `tx.shop_credit_balance_id` addressing.
- Lapse/reaper and read API are independent; run in parallel.
- Superadmin controls after read API so the shops-and-balances surface reuses the same selectors.
- Rollout decided in 29, shipped with the gate in 30, verified last; the 402 gate must never reach production before the backfill/runbook is done.

### Research Flags

Needs deeper research or a spike during planning:
- **Phase 30:** client-disconnect behaviour under Daphne for sync DRF views (does settlement run in `finally` after abort?); `with_options` timeout vs LangSmith wrapper; late-commit policy with product owner.
- **Phase 32:** Activity Log Staff-scoping change not verified in depth; Staff-scope option (a) vs (b).
- **Phase 33:** Superadmin shop-credits surface has no precedent; needs UI-SPEC + scope decision.
- **Phase 29 (discuss):** rollout default and mid-month policy are product decisions.

Standard patterns (skip research-phase): Phase 31 (copy Beat seed), Phase 29 models/cost function, Phase 34 modals.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every capability mapped to an installed, version-verified component; SQL compiled on Django 6.0.2. Beat missed-run catch-up MEDIUM, mitigated by self-healing sweep. |
| Features | MEDIUM | Industry conventions from vendor blogs; gap findings HIGH (verified against live code + spec). |
| Architecture | HIGH | Every integration point read from live code. |
| Pitfalls | HIGH | Codebase-specific findings verified at cited paths; Daphne client-abort MEDIUM. |

**Overall confidence:** HIGH

### Gaps to Address

- **Research disagreements reconciled:**
  - Settle mechanism: use CAS `filter(status=RESERVED).update(...)` (works on both engines) over `select_for_update` on the tx row.
  - Lazy creation: `get_or_create` in its own atomic (not `bulk_create(ignore_conflicts=True)`, which can't say who won).
  - List annotation: FilteredRelation (single JOIN) unless profiling says otherwise.
  - OpenAI default timeout: 600s on `openai==2.33.0` — confirmed.
  - Mid-month change policy (#9): needs product decision.
- **Spec drifts to record in REQUIREMENTS:** `review.text` → `Review.comment`; spec's `replies.py` → `reply_generation.py`; UUID PKs → bigint; throttle 30/min → locked 10/min; `cost` endpoint is a throttled `@action` on `ReviewViewSet`; strike AC 33; Org Admin allocation view lives on Shop Details card; "Manager" = Org Admin.
- **Ledger semantics:** `credits_delta` negative for consumption; REFUNDED rows keep their delta, so headline "used" comes from `balance.consumed_credits`, never `SUM(history)`; invariant `consumed_credits == SUM(-delta) WHERE CONSUMPTION AND status IN (RESERVED, COMMITTED)` shipped as test + management check; `status` is the single permitted mutation, only via named service functions.
- **Whitespace-only comments:** `strip()` identically in server guard, cost function, UI eligibility; UI uses server-supplied cost.
- **Beat monitoring** (alert if lapse not complete by 00:30 UTC) is infra outside this repo — flag to deployment owner.
- **Inactive shops:** lapse includes them; badge hides them.
- **Housekeeping:** update CLAUDE.md (§3 app list, §12.5 Beat table) and move the spec per §28 on completion.

## Sources

### Primary (HIGH)
- `docs/completed/Requirements_Credits_System.md` (binding spec v1.0), `.planning/PROJECT.md` (locked v0.9 decisions)
- Live code: `reply_generation.py`, `reviews/views.py`, `integrations/openai/{client,guardrails,exceptions,models}.py`, `shops/{views,selectors,serializers}.py`, `common/{viewsets,models}.py`, `common/selectors/audit_logs.py`, `organisations/services/organisations.py`, `reviews/migrations/{0013,0016}`, `config/settings/{base,test}.py`, `.github/workflows/ci.yml`, `ReplyComposer.tsx`
- Installed: Django 6.0.2, Celery 5.6.3, django-celery-beat 2.9.0, `openai==2.33.0` (`DEFAULT_TIMEOUT = 600s`)
- Django 6.0 docs (querysets, constraints); PyPI check 2026-11-11; CLAUDE.md §5, §6, §7.2, §9, §12, §13.2, §14, §22, §24, §27, §29

### Secondary (MEDIUM)
- django-celery-beat docs; Schematic, Stigg, Lovable docs (credit ledger, reserve/commit, empty-state conventions)

### Tertiary (LOW)
- Towards AI and Figma forum posts (UX anecdote on cost visibility)

---
*Research completed: 2026-11-11*
*Ready for roadmap: yes*
