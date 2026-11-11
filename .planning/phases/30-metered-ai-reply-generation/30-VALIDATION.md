---
phase: "30"
slug: "metered-ai-reply-generation"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-11"
---

# Phase 30 — Validation Strategy

> Per-phase validation contract. Requirement → test map: `30-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django + factory-boy (`--strict-markers --ds=config.settings.test`) |
| **Config file** | `pyproject.toml`; root `conftest.py` (pg auto-skip / `REQUIRE_PG`) |
| **Quick run command** | `.venv/bin/pytest apps/credits apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_views.py apps/integrations/openai -x -q --no-cov` |
| **Full suite command** | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` |
| **Postgres command** | `make test-pg` (or throwaway PG per Phase 29 plans) with `REQUIRE_PG=1 -m pg_concurrency` |
| **Extra gates** | `mypy .`, `ruff check . && ruff format --check .`, `makemigrations --check --dry-run`, `spectacular --validate` |
| **Estimated runtime** | ~60 seconds quick run |

---

## Sampling Rate

- **After every task commit:** the task's own test file(s) with `--no-cov` (< 30 s)
- **After every plan wave:** Quick run command + PG `pg_concurrency` run (all marked tests passed, none skipped)
- **Before `/gsd-verify-work`:** Full suite + gates green; post-push `backend-pg` CI green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Requirement | Test file(s) | Type | Status |
|-------------|--------------|------|--------|
| D-14 (CAS + ai_usage_log_id) | `apps/credits/tests/test_append_only.py` | unit | ⬜ pending |
| CCON-01, CCON-03, D-12, D-16 | `apps/credits/tests/test_consumption.py` | unit | ⬜ pending |
| CCON-01, CCON-05, CCON-06, D-18 | `apps/reviews/tests/test_reply_generation_credits.py` | unit | ⬜ pending |
| CCON-02, D-12 | `apps/credits/tests/test_pg_concurrency.py`, `apps/reviews/tests/test_pg_reply_concurrency.py` | pg_concurrency | ⬜ pending |
| CCON-03, CCON-04, CCON-07 | `apps/reviews/tests/test_views.py` | view | ⬜ pending |
| CCON-08, D-15 | `apps/integrations/openai/tests/test_client.py`, `test_guardrails.py` | unit | ⬜ pending |
| CCON-08, D-06 | `apps/credits/tests/test_settings.py` | unit | ⬜ pending |
| CQA-02 | `apps/reviews`, `apps/integrations` suites + `docs/sre/v0.9-credits-rollout.md` | unit + file | ⬜ pending |

*Planner refines this into task IDs.*

---

## Wave 0 Requirements

- [ ] Phase 29 contract re-verification (fail fast if `credit_cost`, `get_shop_credit_balance`, `CreditBalanceView`, `transition_status` absent)
- [ ] New test files listed above; credits-enabled fixture (factory default stays 0)
- [ ] Re-point `TestGenerateReplyEndpoint` patches; update T-20-LK key-set tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` green on PG16 | CCON-02 | Needs push | `gh run view` → `backend-pg` ≥1 passed, 0 skipped |
| UAT generate with an enabled org | CCON-01 | Needs running app | Set allocation via admin/shell per runbook; generate; observe credits fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
