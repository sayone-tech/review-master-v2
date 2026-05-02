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
| 12-05 | 03 | 2 | ENRCH-05, ENRCH-14 | integration | `pytest apps/reviews/tests/test_views.py -x -q` | ✅ | ⬜ pending |
| 12-06 | 03 | 2 | ENRCH-06 | unit | `pytest apps/reviews/tests/test_tasks.py -x` | ✅ | ⬜ pending |
| 12-07 | 04 | 2 | ENRCH-11 | unit | `pytest apps/integrations/openai/tests/test_client.py::test_langsmith_best_effort -x` | ❌ W0 | ⬜ pending |
| 12-08 | 05 | 3 | ENRCH-13 | unit | `pytest apps/reviews/tests/test_management_commands.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/integrations/openai/tests/__init__.py` — create directory structure
- [ ] `apps/integrations/openai/tests/factories.py` — AiPricingFactory, AiUsageLogFactory
- [ ] `apps/integrations/openai/tests/fixtures/enrichment_success.json` — deterministic GPT response fixture
- [ ] `apps/integrations/openai/tests/test_client.py` — stub tests for ENRCH-01, ENRCH-11
- [ ] `apps/integrations/openai/tests/test_parser.py` — stub tests for EnrichmentResult schema, max_five_tags
- [ ] `apps/integrations/openai/tests/test_pricing.py` — stub tests for ENRCH-08, ENRCH-09, ENRCH-10
- [ ] `apps/reviews/tests/test_enrichment_service.py` — stub tests for ENRCH-02, ENRCH-03, ENRCH-04, ENRCH-07, ENRCH-12
- [ ] `apps/reviews/tests/test_management_commands.py` — stub tests for ENRCH-13
- [ ] `apps/reviews/management/__init__.py` + `commands/__init__.py` — if not already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ProgressModal shows enrichment bar filling in real time after fetch bar completes | ENRCH-14 (UI) | Requires live WebSocket + running Celery worker | 1. Connect OAuth for a shop 2. Watch ProgressModal 3. Verify yellow bar fills then green "AI Analysing" bar follows 4. Confirm "Sync complete" only appears after green bar hits 100% |
| TopbarBell shows "Analysing with AI…" text during enrichment stage | ENRCH-14 (UI) | Requires live enrichment in progress | 1. Dismiss ProgressModal via "Run in background" 2. Verify topbar bell shows Sparkles icon + "Analysing with AI…" 3. Verify bell disappears only after `sync.complete` |
| Action item chips render on review card | ENRCH-14 (UI) | Requires enriched data + review list UI | 1. Wait for enrichment to complete 2. Navigate to /admin/org/reviews/ 3. Verify action item chips appear on reviews that have extracted_action_items |
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
