---
phase: 22-canonical-tag-foundation-mapping-pipeline
verified: 2026-06-10T09:10:00Z
status: passed
score: 9/9 REQs verified (CTAG-01..08, QUEUE-02 — all automated-testable)
overrides_applied: 0
verification_method: inline (orchestrator) — background subagent dispatch was unreliable in this environment; all checks run directly against the codebase + full test suite
gaps: []
deferred:
  - id: review_count-increment
    note: "ROADMAP Success Criterion #1 says new canonical labels are 're-used (with review_count incremented) on subsequent matches'. Implemented per locked decision D-03 (derive-on-read): review_count stays 0 in the enrichment hot path and is NEVER incremented there, to avoid double-counting on re-enrichment. Actual count derivation is Phase 23 scope (finalising/dedup/backfill). Intentional deviation, not an execution gap."
  - id: global-rate-limit
    note: "ROADMAP Success Criterion #4 says the Celery rate limit is 'global ... that holds across all workers (~500/min)'. Implemented per locked decision D-06 as Celery's native rate_limit, which is PER WORKER INSTANCE (default ENRICHMENT_RATE_LIMIT='125/m'). True global throttling is explicitly deferred to Phase 23 (QUEUE-01 / queue split). Documented in tasks.py docstring and 22-06-SUMMARY. Intentional deviation."
human_verification: []
---

# Phase 22 — Canonical Tag Foundation & Mapping Pipeline — VERIFICATION

**Goal:** Each organisation accrues a self-organising per-org canonical tag
vocabulary, built and evolved entirely inside the existing single GPT enrichment
call — no extra API call, no vector DB, no per-call cost regression.

**Verdict: PASSED.** All 6 plans complete with SUMMARYs; all 9 requirement IDs
implemented with code + test evidence; full `apps/` suite green; pre-commit
(ruff, mypy --strict, bandit, missing-migrations) passed on every commit. Two
ROADMAP success-criteria sub-clauses are intentionally deferred to Phase 23 per
locked decisions D-03 and D-06 (see `deferred` above).

## Requirement traceability

| REQ | Met | Evidence |
|-----|-----|----------|
| CTAG-01 | ✓ | `OrgCanonicalTag` model (Title-Case label, `polarity_type`, `review_count`, org FK) — `apps/reviews/models.py:128`; new rows created in pipeline — `enrichment.py` bulk_create. |
| CTAG-02 | ✓ | Unique `(organisation, label)` constraint `uniq_orgcanonicaltag_org_label`; nullable `ReviewTag.canonical_tag` FK (`on_delete=SET_NULL`) populated in `_persist_success`. |
| CTAG-03 | ✓ | `get_org_vocabulary` selector (top-N by `-review_count`, capped by `CANONICAL_VOCAB_INJECT_LIMIT`) injected into the single prompt — `prompts.py:_build_canonical_vocab_block`; `ENRICHMENT_PROMPT_VERSION = 4`. |
| CTAG-04 | ✓ | Map-or-propose instruction block in the enrichment prompt; `Tag.canonical` + nullable `polarity_type` in parser schema. |
| CTAG-05 | ✓ | Prompt requires English canonical labels; 22-03 `normalize_canonical` validator enforces Title-Case ≤3 words server-side. |
| CTAG-06 | ✓ | Canonical lookup/insert folded into the existing `_persist_success` `transaction.atomic()`; batch SELECT + `bulk_create(ignore_conflicts=True)` + re-SELECT; FK set on each `ReviewTag`. Atomic-rollback test confirms unwind. |
| CTAG-07 | ✓ | Exactly one `AiUsageLog.objects.create` per enrichment call; no extra OpenAI call. `test_canonical_usage_log_is_exactly_one`. |
| CTAG-08 | ✓ | Migration `0011_orgcanonicaltag_reviewtag_canonical_tag.py` adds model + FK with **zero** `RunPython` (no backfill); pre-existing rows keep `canonical_tag = NULL`. |
| QUEUE-02 | ✓ | `enrich_review_task` carries `rate_limit=settings.ENRICHMENT_RATE_LIMIT` — `tasks.py:176` (per-worker; global deferred to Phase 23, see deferred). |

## Success-criteria assessment

1. **Self-organising canonical vocabulary inside the atomic block** — ✓ (create-new / reuse-existing). *Sub-clause "review_count incremented" deferred per D-03 — see deferred.*
2. **Every ReviewTag gets `canonical_tag` populated, org via `review.organisation_id`** — ✓.
3. **Org vocabulary injected into the single prompt; map-or-propose in the same call; English output** — ✓.
4. **Exactly one AiUsageLog row; configurable Celery rate limit** — ✓ for the one-row + configurable-limit clauses. *"Global across all workers" deferred per D-06 — see deferred.*
5. **Backward compatible, non-backfilling migration; pre-phase reviews valid with null `canonical_tag`** — ✓.

## Test evidence
- Full suite: `DJANGO_SETTINGS_MODULE=config.settings.test pytest apps/` → **all pass, 0 failures**.
- Targeted: `test_models` (OrgCanonicalTag), `test_parser` (Tag schema), `test_prompts` (vocab injection/version 4), `test_enrichment_service` (canonical FK, atomic rollback, idempotency, one-AiUsageLog, query-count no-N+1), `test_tasks` (rate_limit).
- No-N+1: `test_canonical_query_count_is_fixed_regardless_of_tag_count` — identical query count for 2 vs 5 tags.
- `mypy --strict` clean on touched modules; `grep review_count apps/reviews/services/enrichment.py` → comment only (never written in hot path, D-03).

## Notes
Plans 22-04 and 22-05 were executed inline by the orchestrator after background
worktree executors were denied an un-allow-listed Bash command (worktree
HEAD-check `git symbolic-ref`/`git reset`); 22-03 and 22-06 edits were rescued
from their worktrees and committed. No scope change resulted.
