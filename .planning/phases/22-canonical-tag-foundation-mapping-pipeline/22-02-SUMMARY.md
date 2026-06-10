---
phase: 22-canonical-tag-foundation-mapping-pipeline
plan: "02"
subsystem: config
tags: [settings, celery, canonical-tags, enrichment, config-only]
dependency_graph:
  requires: []
  provides:
    - "settings.CANONICAL_VOCAB_INJECT_LIMIT (int, default 200)"
    - "settings.ENRICHMENT_RATE_LIMIT (str, default '125/m')"
  affects:
    - "config/settings/base.py"
    - ".env.example"
tech_stack:
  added: []
  patterns:
    - "env.int() / env() helper — same idiom as surrounding enrichment settings block"
key_files:
  modified:
    - path: "config/settings/base.py"
      role: "Two new env-configurable settings added after the enrichment block"
    - path: ".env.example"
      role: "Both variables documented with explanatory comments"
decisions:
  - "D-06 caveat made explicit in both settings comment and .env.example: ENRICHMENT_RATE_LIMIT is per-worker, not global; global throttling deferred to Phase 23"
  - "D-02 default 200 used for CANONICAL_VOCAB_INJECT_LIMIT as specified in 22-CONTEXT.md"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-10"
  tasks_completed: 2
  files_modified: 2
---

# Phase 22 Plan 02: Enrichment Config Settings Summary

Config-only plan adding two env-configurable Django settings consumed by the canonical tag pipeline: `CANONICAL_VOCAB_INJECT_LIMIT` (top-N vocabulary cap for D-02) and `ENRICHMENT_RATE_LIMIT` (per-worker Celery rate for QUEUE-02/D-06), both documented in `.env.example`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add CANONICAL_VOCAB_INJECT_LIMIT and ENRICHMENT_RATE_LIMIT to base.py | 97ddf18 | config/settings/base.py |
| 2 | Document both variables in .env.example | 3b0cfd2 | .env.example |

## Verification Results

- Django settings resolve correctly under `config.settings.test`:
  - `CANONICAL_VOCAB_INJECT_LIMIT == 200` (int)
  - `ENRICHMENT_RATE_LIMIT == "125/m"` (valid Celery rate format)
- `.env.example` contains `CANONICAL_VOCAB_INJECT_LIMIT=200` and `ENRICHMENT_RATE_LIMIT=125/m`
- All pre-commit hooks passed (ruff, mypy, bandit, gitleaks, missing-migrations)

## Decisions Made

- **Default 200 for CANONICAL_VOCAB_INJECT_LIMIT**: Per D-02 and 22-CONTEXT.md Open Question 3 resolution — 200 tags is a practical upper bound that prevents prompt-token runaway while accommodating large org vocabularies.
- **Default "125/m" for ENRICHMENT_RATE_LIMIT**: Per D-06 — this is a per-worker rate, derived from ~500/min total target ÷ ~4 expected workers. Comment makes explicit that true global throttling (Redis token bucket) is deferred to Phase 23.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. This is a config-only plan; no data-rendering code was added.

## Threat Flags

None. Only non-secret integer/rate-string defaults were added to `.env.example`. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `config/settings/base.py` exists and contains both settings: PASSED
- `.env.example` contains both env var lines: PASSED
- Commit 97ddf18 exists: PASSED
- Commit 3b0cfd2 exists: PASSED
