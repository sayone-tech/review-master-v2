# Research Summary — v0.8 Canonical Tag System

> This milestone is driven by a **frozen spec**: `docs/ReviewBee_Canonical_Tag_Requirements_v1.0.md` (v1.0, Final). No open-ended domain research was needed. This summary captures the **codebase reconciliation** of that spec against the live schema — the authoritative grounding for roadmapping. Prior (v0.4-era) dimension files in this directory are stale.

## The problem

Reviews are enriched independently, so GPT emits semantically-equivalent but textually-different tags ("good service", "Good Customer Service", "great staff" → all "Staff & Service"). This breaks tag-based analytics. A hardcoded global tag list is unviable (restaurants vs electronics vs salons differ). Solution: a **self-organising, per-org canonical vocabulary**, folded into the existing single GPT enrichment call — no extra API calls, no vector DB.

## Reconciliation verdicts (spec assumption → reality)

| # | Spec assumption | Verdict | Reality / evidence |
|---|---|---|---|
| 1 | Tags are a JSONB `tags` column on `Review`; `canonical_tag_id` already present | **CONTRADICTED** | Tags are the **relational `ReviewTag` model** (`apps/reviews/models.py:128`), `related_name="tags"`, unique `(review,label,polarity)`. The JSONField was dropped in migration `0008`. **No `canonical_tag_id` exists anywhere.** |
| 2 | Single combined GPT call + `EnrichmentResult` Pydantic schema | **CONFIRMED** | `apps/integrations/openai/parser.py:16`; persisted via delete-then-`bulk_create` of `ReviewTag` in `apps/reviews/services/enrichment.py:104` inside `transaction.atomic()`. |
| 3 | Current queues `google-sync`/`ai-enrichment`/`default` | **CONFIRMED** | `config/settings/base.py` routes + `CELERY_QUEUE_NAMES`. New `-high`/`-low`/`tag-merge` queues do not exist. |
| 4 | `SyncProgressConsumer` exists; spec wants a new WS consumer for merge | **CONFIRMED + GOVERNANCE CONFLICT** | Sole consumer at `apps/reviews/consumers.py:23`; emits `sync.fetch.progress`, `sync.enrichment.progress`, `sync.complete`, `sync.error`. CLAUDE.md §13.2 forbids new consumers without a §13 amendment + sign-off. |
| 5 | Superadmin full data wipe + per-store sync-status reset | **NOT FOUND (net-new)** | Only `delete_organisation` soft-delete exists. No hard wipe, no `superadmin` app (logic lives in `organisations`). No per-shop `sync_status`/`last_synced_at` DB field — sync state is Redis (`sync:progress:{shop_id}`) + `Shop.connection_status`. |
| 6 | Initial-backfill + incremental sync tasks | **CONFIRMED** | `initial_backfill_task` / `sync_shop_reviews_task` / `enqueue_incremental_syncs_task` in `apps/reviews/tasks.py`; both call `fetch_and_persist_reviews` in `services/sync.py`. |
| 7 | Models + org FK paths | **CONFIRMED** | `Review`/`AiUsageLog`/`ActionItem` have direct `organisation` FK. **`ReviewTag` has NO org FK** — reaches org via `review.organisation`. |

## Tag-storage ground truth (the crux)

Tags are stored **relationally** as `ReviewTag` rows, not JSON, and **`canonical_tag_id` does not exist**. So "adding canonical mapping" means:
- New **`OrgCanonicalTag`** model — direct `organisation` FK, `label` (Title Case, ≤3 words), `polarity_type` enum, `review_count`, timestamps; unique on `(organisation, label)`.
- New **nullable `canonical_tag` FK on `ReviewTag`** (not on `Review`).
- Pydantic `Tag` (`parser.py:16`) gains `canonical` + `polarity_type`; prompt (`prompts.py`) injects the org vocabulary.
- The post-enrichment lookup/insert goes **inside the existing `transaction.atomic()`** in `enrichment.py:104` (the `ReviewTag` write step), resolving org via `review.organisation_id` (already `select_related`).

## Net-new vs modify

**Net-new:** `OrgCanonicalTag` model + migration; `canonical_tag` FK + migration on `ReviewTag`; weekly reclassification Beat job; `tag-merge` Celery task + service + queue; merge status endpoint (HTTP-polled); Org Admin Tags page + endpoints; Superadmin data-reset service + view + permission; seed-phase (sequential first-50) orchestration.

**Modify:** `parser.py` (schema), `prompts.py` (vocab injection + English-only rule), `enrichment.py:104` (canonical lookup/insert), `settings/base.py` (queue split + global rate limit), `SyncProgressConsumer`/sync UI (2-step → 4-step), worker deploy `-Q` args + queue-depth metric publisher.

## Milestone decisions (locked)

- **Tag-merge progress → HTTP polling** (not a new WebSocket consumer). Keeps the Channels surface narrow per §13.2; matches the existing notification-bell polling pattern. No CLAUDE.md amendment needed.
- **Superadmin data reset → hard wipe**, accepted as a deliberate one-time **pre-production** exception to the §11 soft-delete/audit rule (app not yet in production). The "reset sync status" step maps to clearing the Redis snapshot + `Shop.connection_status`, then re-running `initial_backfill_task`.

## Constraints to honour (from CLAUDE.md)

- One `AiUsageLog` row per OpenAI call — canonicalisation is folded into the existing single call, so this is unchanged. **Never** add a separate GPT call for mapping.
- Three-layer idempotency already wraps `enrich_review` (Redis lock `lock:enrich:review:{id}`, `select_for_update`, status short-circuit). Canonical inserts must stay inside the existing atomic block. The new `tag-merge` task needs its own lock (e.g. `lock:tag_merge:org:{org_id}`).
- Tenant scoping: `OrgCanonicalTag` carries a direct `organisation` FK; every Org/Staff queryset filters by it. Rename/merge endpoints enforce org ownership.
- No-N+1 + query-count tests on the Tags list endpoint; cost impact (≈150–300 extra prompt tokens/review) tracked via `AiUsageLog`.

## Open risks

- Where the `canonical_tag` FK lives (`ReviewTag` row-level vs a distinct-label join) — row-level on `ReviewTag` is simplest and recommended.
- Hard wipe contradicts §11 "never hard-delete reviews" — acceptable pre-production only; must not become the production pattern.
- Queue split touches deploy config in multiple places (routes, `CELERY_QUEUE_NAMES`, worker `-Q`, queue-depth metric).
