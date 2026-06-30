---
phase: 23
slug: four-step-initial-sync-seeding-queue-split
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-10
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from the "## Validation Architecture" section of 23-RESEARCH.md.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (in-memory SQLite test settings) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`DJANGO_SETTINGS_MODULE=config.settings.test`) |
| **Quick run command** | `.venv/bin/pytest apps/reviews -q -p no:warnings` |
| **Full suite command** | `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/pytest apps/ -q -p no:warnings` |
| **Estimated runtime** | ~60–90 seconds (full), ~10s (reviews app) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the touched app(s).
- **After every plan wave:** Run the full suite command.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 90 seconds.

---

## Per-Task Verification Map

> Populated during planning/execution. Every behavior-adding task must carry an
> `<automated>` verify command or a Wave 0 dependency. Key coverage areas
> (from 23-RESEARCH.md Validation Architecture):

| Area | Requirement | Test Type | Automated Command (target) | Status |
|------|-------------|-----------|----------------------------|--------|
| Token-bucket global limiter (acquire/empty/expire) | DSYNC-01, QUEUE-01 | unit | `pytest apps/reviews/tests/test_rate_limit.py -q` | ⬜ pending |
| enrich_review_task routes high vs low via apply_async(queue=) | QUEUE-01 | unit | `pytest apps/reviews/tests/test_tasks.py -k queue -q` | ⬜ pending |
| Sequential seed loop (first N, vocab re-read each iter) | SEED-02 | integration | `pytest apps/reviews/tests/test_sync_service.py -k seed -q` | ⬜ pending |
| Seed loop WAITs on depleted bucket; completes all N (no crash/restart) | SEED-02 | integration | `pytest apps/reviews/tests/test_sync_service.py -k depleted -q` | ⬜ pending |
| Parallel bulk fan-out + finalising trigger | SEED-03 | integration | `pytest apps/reviews/tests/test_sync_service.py -k bulk -q` | ⬜ pending |
| Finalising merge (FK re-point, higher-count winner, no N+1) | SEED-04 | unit + query-count | `pytest apps/reviews/tests/test_finalise.py -q` | ⬜ pending |
| review_count cache refresh (aggregate) | SEED-04 | unit | `pytest apps/reviews/tests/test_finalise.py -k review_count -q` | ⬜ pending |
| 4-step snapshot pass-through + reconnect repaint (step + per-step counters) | SEED-01 | unit + consumer | `pytest apps/reviews/tests/test_consumers.py apps/reviews/tests/test_progress.py -q` | ⬜ pending |
| Daily incremental routes to ai-enrichment-low through pipeline | DSYNC-01 | integration | `pytest apps/reviews/tests/test_tasks.py -k incremental -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/test_rate_limit.py` — token bucket + `_wait_for_openai_token` (Plan 01)
- [ ] `apps/reviews/tests/test_finalise.py` — finalising merge + count refresh (Plan 02)
- [ ] `apps/reviews/tests/test_consumers.py` — reconnect snapshot carries 4-step `step` + per-step counters (Plan 03 Task 4)
- [ ] `apps/reviews/tests/test_progress.py` — write/read snapshot round-trip preserves 4-step keys (Plan 03 Task 4)

*Existing infrastructure (pytest-django, factories, fakeredis/mock patterns, CaptureQueriesContext) covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 4-step progress visually renders (Fetching → Building → AI Enrichment → Finalising) with per-step counts and correct colors | SEED-01 | Visual/UX fidelity per 23-UI-SPEC cannot be asserted by grep | Trigger an initial sync for a store with >50 reviews; watch the ProgressModal advance through all 4 steps |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
