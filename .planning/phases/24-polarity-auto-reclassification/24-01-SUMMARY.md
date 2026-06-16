---
phase: 24-polarity-auto-reclassification
plan: "01"
subsystem: reviews
tags: [polarity, reclassification, celery, settings, migration, tests, wave-0]
dependency_graph:
  requires:
    - 22-canonical-tag-foundation-mapping-pipeline (OrgCanonicalTag model, PolarityType, ReviewTag)
    - 21-audit-log-viewer (AuditLog model as reclassification log sink)
  provides:
    - POLARITY_RECLASSIFY_* settings consumed by Plan 02 service
    - OrgCanonicalTag.polarity_reclassified_at column consumed by Plan 02 service + Phase 25 tag list
    - reclassify_polarity_task route entry consumed by Plan 02 task registration
    - Wave-0 test scaffold consumed by Plan 02 (turns GREEN when service ships)
  affects:
    - config/settings/base.py (three new settings + one route entry)
    - apps/reviews/models.py (new field on OrgCanonicalTag)
    - apps/reviews/migrations/ (migration 0012)
    - apps/reviews/tests/ (new test module)
tech_stack:
  added: []
  patterns:
    - env.float/env.int for typed configurable settings (analog: SEED_PHASE_SIZE)
    - AddField nullable DateTimeField migration (online-safe, no data backfill)
    - Wave-0 RED test scaffold with bare @pytest.mark.django_db function style
key_files:
  created:
    - apps/reviews/migrations/0012_orgcanonicaltag_polarity_reclassified_at.py
    - apps/reviews/tests/test_polarity_reclassify.py
  modified:
    - config/settings/base.py
    - apps/reviews/models.py
decisions:
  - "Used float(env(...)) fallback for POLARITY_RECLASSIFY_THRESHOLD instead of env.float() — safer cross-version approach per PATTERNS.md A2 note"
  - "Migration 0012 depends only on reviews 0011, single AddField — no data backfill, safe online add (T-24-03 mitigated)"
  - "Test file uses 14 test functions (2 for coverage area a) to fully encode always_positive and always_negative symmetry"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-16T06:16:01Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
  files_created: 2
---

# Phase 24 Plan 01: Foundation — Settings, Schema, Wave-0 Tests Summary

**One-liner:** Three configurable POLARITY_RECLASSIFY_* settings, reclassify_polarity_task Celery route, nullable polarity_reclassified_at column on OrgCanonicalTag (migration 0012), and a 14-test Wave-0 RED scaffold encoding all POL-02/POL-03 behaviours ready to turn GREEN in Plan 02.

## What Was Built

### Task 1: POLARITY_RECLASSIFY_* settings + reclassify_polarity_task route (12ea695)

Added to `config/settings/base.py` immediately after the Phase 23 OPENAI_GLOBAL_RATE_LIMIT block:

- `POLARITY_RECLASSIFY_THRESHOLD` — float default 0.15, read via `float(env(...))` fallback
- `POLARITY_RECLASSIFY_WINDOW_DAYS` — int default 30
- `POLARITY_RECLASSIFY_MIN_REVIEWS` — int default 10

Added route entry in `CELERY_TASK_ROUTES` after `finalize_canonical_tags_task`, routing `reclassify_polarity_task` to the `default` queue (low-frequency, low-concurrency, D-05; not ai-enrichment-* or google-sync or tag-merge).

### Task 2: OrgCanonicalTag.polarity_reclassified_at + migration 0012 (7e9b093)

Added a nullable `DateTimeField(null=True, blank=True)` named `polarity_reclassified_at` to `OrgCanonicalTag` near `polarity_type`. Null means never auto-reclassified; AuditLog remains authoritative. The field provides Phase 25 tag-list display a cheap last-reclassified timestamp without requiring an AuditLog JOIN (per D-07 research recommendation).

Migration `0012_orgcanonicaltag_polarity_reclassified_at.py` is a single `AddField` on `orgcanonicaltag` depending only on `reviews 0011`. No data backfill, no other fields altered, `review_count` untouched (D-03 Phase 22).

### Task 3: Wave-0 failing test module + POL-01 re-confirmation (d356e1c)

Created `apps/reviews/tests/test_polarity_reclassify.py` with 14 `@pytest.mark.django_db` test functions:

| Coverage | Test function |
|----------|---------------|
| (a) flip always_positive → mixed | `test_flip_always_positive_to_mixed_when_threshold_exceeded` |
| (a) flip always_negative → mixed | `test_flip_always_negative_to_mixed_when_threshold_exceeded` |
| (b) no flip below MIN_REVIEWS | `test_no_flip_below_min_reviews` |
| (c) boundary exactly 0.15 no flip | `test_boundary_exactly_threshold_does_not_flip` |
| (d) mixed tags skipped, no log | `test_mixed_tags_are_skipped_no_audit_log` |
| (e) neutral in denominator only | `test_neutral_reviews_in_denominator_only` |
| (e) neutral never triggers flip | `test_neutral_reviews_never_trigger_flip_even_when_majority` |
| (f) soft-deleted excluded | `test_soft_deleted_reviews_excluded` |
| (g) window by review_create_time | `test_reviews_older_than_window_excluded` |
| (h) multi-tenant isolation | `test_multi_tenant_isolation` |
| (i) idempotency | `test_idempotency_second_run_changes_nothing` |
| (j) no-N+1 query count | `test_query_count_is_fixed_regardless_of_tag_count` |
| (k) AuditLog row per flip | `test_audit_log_written_on_flip` |
| POL-01 | `test_pol01_reconfirm_new_tag_has_non_empty_polarity_type` |

RED state confirmed: module fails at collection with `ModuleNotFoundError: No module named 'apps.reviews.services.reclassify'` — expected Wave-0 state. No `apps.integrations.openai` import anywhere in file. No GPT/Redis/WebSocket mocks.

## Deviations from Plan

### Auto-fixed Issues

None.

### Minor Adjustments

**1. [Rule 1 - Stylistic] Used `float(env(...))` instead of `env.float()`**
- **Found during:** Task 1 implementation
- **Context:** PATTERNS.md Assumption A2 notes `env.float()` may not exist in all django-environ versions. The fallback `float(env("POLARITY_RECLASSIFY_THRESHOLD", default="0.15"))` is explicitly listed as the safe approach.
- **Fix:** Used the fallback form to avoid a potential boot-time AttributeError
- **Files modified:** `config/settings/base.py`

**2. [Ruff auto-fix] Import reformat in test file**
- **Found during:** Task 3 pre-commit hook
- **Context:** Ruff reformatted a multi-line import to the canonical parenthesized form
- **Fix:** Auto-applied by ruff-check hook, re-staged and re-committed
- **Files modified:** `apps/reviews/tests/test_polarity_reclassify.py`

## Known Stubs

None. This plan delivers config + schema + test scaffolding only. The service (`apps.reviews.services.reclassify`) is deliberately absent — that is the Wave-0 RED contract. No data flows to UI from this plan.

## Threat Flags

None. No new network endpoints, no auth paths, no file access. Single nullable AddField migration (T-24-03 mitigated by online-safe nullable add).

## Self-Check: PASSED

Files exist:
- [x] `config/settings/base.py` (modified)
- [x] `apps/reviews/models.py` (modified)
- [x] `apps/reviews/migrations/0012_orgcanonicaltag_polarity_reclassified_at.py` (created)
- [x] `apps/reviews/tests/test_polarity_reclassify.py` (created)

Commits exist:
- [x] `12ea695` — feat(24-01): settings + route
- [x] `7e9b093` — feat(24-01): model + migration
- [x] `d356e1c` — test(24-01): Wave-0 failing test scaffold
