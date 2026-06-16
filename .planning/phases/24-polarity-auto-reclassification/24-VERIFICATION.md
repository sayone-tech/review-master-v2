---
phase: 24-polarity-auto-reclassification
verified: 2026-06-16T05:00:00Z
status: passed
score: 3/3 REQs verified (POL-01, POL-02, POL-03)
overrides_applied: 0
verification_method: inline (orchestrator) — fully automated-testable phase, no UI; verified against the codebase + full test suite
gaps: []
deferred:
  - id: pol-03-tag-list-visibility
    note: "POL-03 has two halves: (a) reclassification events are LOGGED, and (b) the current polarity_type is VISIBLE on the tag list page. Half (a) is fully delivered here (one AuditLog row per flip, surfaced in the Phase 21 Activity Log viewer). Half (b) — the tag-list-page rendering of polarity_type — is intentionally DEFERRED to Phase 25's Org Admin Tags page per locked decision D-07 (the user's explicit choice). Phase 24 guarantees polarity_type is correct + auditable; Phase 25 renders it. Not an execution gap."
human_verification: []
---

# Phase 24 — Polarity Auto-Reclassification — VERIFICATION

**Goal:** Canonical tags carry an accurate, self-maintaining `polarity_type` — a
weekly DB-only job keeps `always_*` vs `mixed` honest without manual curation or
extra GPT calls.

**Verdict: PASSED.** Both plans complete with SUMMARYs; all 3 requirement IDs
implemented with code + test evidence; full `apps/` suite green (incl. a
test-hardening fix for a Phase-23 order-fragility surfaced by this phase);
pre-commit (ruff, mypy --strict, bandit, missing-migrations) passed on every
commit. One ROADMAP success-criterion sub-clause (POL-03 tag-list visibility) is
intentionally deferred to Phase 25 per locked decision D-07 — see `deferred`.

## Requirement traceability

| REQ | Met | Evidence |
|-----|-----|----------|
| POL-01 | ✓ | Already shipped in Phase 22 (GPT assigns `polarity_type` at creation). **Re-confirmed** here by a regression test (`test_polarity_reclassify.py`) asserting fresh `OrgCanonicalTag` rows carry a non-empty `polarity_type`; **no `apps/integrations/openai` import** (prompt/parser untouched, per D-01). |
| POL-02 | ✓ | `run_polarity_reclassification` (`apps/reviews/services/reclassify.py`): single grouped `values("canonical_tag_id","polarity").annotate(Count)` aggregate (no-N+1, query-count test proves fixed count for N=2 vs N=5); flip when opposite÷all `> threshold` (**strict >**) AND `total >= MIN_REVIEWS`; numerator = opposite polarity only, neutral in denominator (D-02); window by `Review.review_create_time`, soft-deleted excluded (D-03); candidate filter `ALWAYS_POSITIVE`/`ALWAYS_NEGATIVE` only → one-way, mixed skipped (D-01); `bulk_update(["polarity_type","polarity_reclassified_at"])` — `review_count` excluded (Phase 22 D-03). Thin `reclassify_polarity_task` Beat wrapper; **no GPT call**. Weekly `CrontabSchedule` Sunday 03:00 UTC seeded via reversible data migration `0013` (D-05, CLAUDE.md §12.5). |
| POL-03 | ✓ (logging) / deferred (visibility) | One `AuditLog` row per flip — `entity_type="canonical_tag"`, `action="polarity_reclassified"`, `actor=None`, `before_data`/`after_data` — written via `bulk_create` inside the same `transaction.atomic()` as the flip (D-06). Appears in the Phase 21 Activity Log viewer. The "visible on tag list page" half is deferred to Phase 25 (D-07 — see `deferred`). |

## Success-criteria assessment
1. **Every new canonical tag assigned a polarity_type at creation** — ✓ (Phase 22; re-confirmed by regression test).
2. **Weekly Beat job flips always_* → mixed at the 15%/30-day threshold, pure DB, no GPT** — ✓.
3. **Reclassification events logged, current polarity_type visible on the tag list page** — ✓ for "logged" (AuditLog). *"visible on the tag list page" deferred to Phase 25 per D-07.*

## Test evidence
- `apps/reviews/tests/test_polarity_reclassify.py` — **14 tests, all green**: flip, boundary (exactly-threshold does NOT flip), min-sample (no flip below 10), already-mixed skip, neutral-in-denominator, soft-delete exclusion, window-by-`review_create_time`, multi-tenant isolation, idempotency (second run = no-op), no-N+1 query count, AuditLog write, Beat schedule seeded, POL-01 re-confirmation.
- Full `apps/` suite: **green** after hardening `test_finalise.py::test_fk_repoint_no_n_plus_one` (a latent Phase-23 Faker-order fragility surfaced by this phase's added test module — fixed with explicit unique ReviewTag labels).
- `mypy --strict` clean on `reclassify.py`; `makemigrations --check` clean.

## Notes
Plans executed via background worktree executors (bypass-permissions active);
both merged cleanly. POL-03's visibility half is the only deferred item, by the
user's explicit D-07 decision — it lands in Phase 25's Tags page.
