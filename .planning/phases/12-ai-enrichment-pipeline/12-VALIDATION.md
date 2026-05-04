---
phase: 12
slug: ai-enrichment-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| **Quick run command** | `pytest apps/integrations/openai/ apps/reviews/tests/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/integrations/openai/ apps/reviews/tests/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01 | 01 | 1 | ENRCH-01 | unit | `pytest apps/integrations/openai/tests/test_client.py -x` | ❌ W0 | ⬜ pending |
| 12-02 | 01 | 1 | ENRCH-08, ENRCH-09, ENRCH-10 | unit | `pytest apps/integrations/openai/tests/test_pricing.py -x` | ❌ W0 | ⬜ pending |
| 12-03 | 02 | 1 | ENRCH-02, ENRCH-03 | unit | `pytest apps/reviews/tests/test_enrichment_service.py -x` | ❌ W0 | ⬜ pending |
| 12-04 | 02 | 1 | ENRCH-04, ENRCH-07, ENRCH-12 | unit | `pytest apps/reviews/tests/test_enrichment_service.py -x` | ❌ W0 | ⬜ pending |
| 12-05 | 03 | 2 | ENRCH-05, ENRCH-14 | unit | `pytest apps/reviews/tests/test_enrichment_service.py::test_failed_review_appears_in_serializer -x` | ❌ W0 | ⬜ pending |
| 12-06 | 03 | 2 | ENRCH-06 | unit | `pytest apps/reviews/tests/test_tasks.py -x` | ✅ | ⬜ pending |
| 12-07 | 04 | 2 | ENRCH-11 | unit | `pytest apps/integrations/openai/tests/test_client.py::test_langsmith_best_effort -x` | ❌ W0 | ⬜ pending |
| 12-08 | 05 | 3 | ENRCH-13 | unit | `pytest apps/reviews/tests/test_management_commands.py -x` | ❌ W0 | ⬜ pending |
| 12-09 | 06 | 5 | ENRCH-02 (sync wiring) | unit | `pytest apps/reviews/tests/test_sync_service.py::test_fetch_and_persist_enqueues_enrichment_for_pending_reviews -x` | ❌ Plan 06 | ⬜ pending |
| 12-10 | 06 | 5 | ENRCH-14 (sync.complete gating) | unit | `pytest apps/reviews/tests/test_sync_service.py::test_fetch_and_persist_does_not_emit_sync_complete -x` | ❌ Plan 06 | ⬜ pending |
| 12-11 | 06 | 5 | ENRCH-14 (enrichment progress emission) | unit | `pytest apps/reviews/tests/test_enrichment_progress.py -x` | ❌ Plan 06 | ⬜ pending |
| 12-12 | 06 | 5 | ENRCH-06 (Beat seed migration) | structural | `python manage.py makemigrations --check --dry-run` | ❌ Plan 06 | ⬜ pending |
| 12-13 | 07 | 2 | ENRCH-14 (ActionItemChip + ReviewTable) | typecheck | `cd frontend && npx tsc --noEmit -p tsconfig.json` | ❌ Plan 07 | ⬜ pending |
| 12-14 | 08 | 2 | ENRCH-14 (ProgressModal + TopbarBell) | typecheck | `cd frontend && npx tsc --noEmit -p tsconfig.json` | ❌ Plan 08 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Note on row 12-05:** This row was previously pointed at `apps/reviews/tests/test_views.py::test_failed_enrichment_visible`, which no plan created. Plan 12-04 creates the equivalent assertion as `apps/reviews/tests/test_enrichment_service.py::test_failed_review_appears_in_serializer` — that test confirms FAILED enrichments still serialize via `ReviewReadSerializer` (ENRCH-05). The row above now points to the actual test.

---

## Wave 0 Requirements

- [ ] `apps/integrations/openai/tests/__init__.py` — create directory structure
- [ ] `apps/integrations/openai/tests/factories.py` — AiPricingFactory, AiUsageLogFactory
- [ ] `apps/integrations/openai/tests/fixtures/enrichment_success.json` — deterministic GPT response fixture
- [ ] `apps/integrations/openai/tests/test_client.py` — stub tests for ENRCH-01, ENRCH-11
- [ ] `apps/integrations/openai/tests/test_parser.py` — stub tests for EnrichmentResult schema, max_five_tags
- [ ] `apps/integrations/openai/tests/test_pricing.py` — stub tests for ENRCH-08, ENRCH-09, ENRCH-10
- [ ] `apps/reviews/tests/test_enrichment_service.py` — stub tests for ENRCH-02, ENRCH-03, ENRCH-04, ENRCH-05, ENRCH-07, ENRCH-12
- [ ] `apps/reviews/tests/test_management_commands.py` — stub tests for ENRCH-13
- [ ] `apps/reviews/management/__init__.py` + `commands/__init__.py` — if not already present
- [ ] `apps/reviews/tests/test_sync_service.py` — stub tests for ENRCH-02 sync wiring (Plan 06)
- [ ] `apps/reviews/tests/test_enrichment_progress.py` — stub tests for sync.enrichment.progress emission (Plan 06)
- [ ] `apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py` — Beat seed for ENRCH-06 (Plan 06)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ProgressModal shows enrichment bar filling in real time after fetch bar completes | ENRCH-14 (UI) | Requires live WebSocket + running Celery worker | 1. Connect OAuth for a shop 2. Watch ProgressModal 3. Verify yellow bar fills then green "AI Analysing" bar follows 4. Confirm "Sync complete" only appears after green bar hits 100% |
| TopbarBell shows "Analysing reviews with AI…" text during enrichment stage | ENRCH-14 (UI) | Requires live enrichment in progress | 1. Dismiss ProgressModal via "Run in background" 2. Verify topbar bell row shows green Loader2 + "Analysing reviews with AI…" 3. Verify bell removes the shop only after `sync.complete` |
| Action item chips render on review card | ENRCH-14 (UI) | Requires enriched data + review list UI | 1. Wait for enrichment to complete 2. Navigate to /admin/org/reviews/ 3. Verify amber Sparkles chips appear on reviews that have extracted_action_items |
| LangSmith traces appear in LangSmith project | ENRCH-11 | Requires live LangSmith API key | 1. Set LANGSMITH_API_KEY + LANGSMITH_PROJECT 2. Run enrichment on one review 3. Check LangSmith dashboard for trace with correct metadata |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
