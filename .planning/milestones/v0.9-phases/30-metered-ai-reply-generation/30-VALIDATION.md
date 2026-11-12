---
phase: "30"
slug: "metered-ai-reply-generation"
status: validated
nyquist_compliant: true
wave_0_complete: true
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

| Task | Requirement / decisions | Test file(s) | Type | Status |
|------|-------------------------|--------------|------|--------|
| 30-01 T1 (tracer) | CCON-01, CCON-06, CCON-07, CQA-02; D-04, D-07, D-14, D-18, D-19 | `apps/credits/tests/test_append_only.py`, `apps/reviews/tests/test_views.py` (TestGenerateReplyCredits, re-pointed TestGenerateReplyEndpoint) | unit + view (e2e) | ✅ green |
| 30-01 T2 | CCON-03, CCON-05; D-01, D-02, D-08, D-11, D-12, D-16, D-17, D-19 | `apps/credits/tests/test_consumption.py` | unit | ✅ green |
| 30-02 T1 | CCON-05, CCON-06; D-15 | `apps/integrations/openai/tests/test_guardrails.py` | unit | ✅ green |
| 30-02 T2 | CCON-08; D-05, D-06, D-15 | `apps/integrations/openai/tests/test_client.py`, `apps/credits/tests/test_settings.py` | unit | ✅ green |
| 30-03 T1 | CCON-05, CCON-06; D-03, D-04, D-09, D-15, D-17, D-18 | `apps/reviews/tests/test_reply_generation_credits.py`, `test_reply_generation_service.py`, `test_views.py` | unit + view | ✅ green |
| 30-03 T2 | CCON-03, CCON-04, CCON-07; D-08, D-10, D-11, D-12, D-19 | `apps/reviews/tests/test_views.py` (TestReviewCreditCost + 400/402/409) + spectacular | view | ✅ green |
| 30-04 T1 | CCON-02; D-03, D-12, D-16 | `apps/credits/tests/test_pg_concurrency.py`, `apps/reviews/tests/test_pg_reply_concurrency.py` | pg_concurrency | ✅ green |
| 30-04 T2 | CQA-02; D-13 | `docs/sre/v0.9-credits-rollout.md` (file checks) | file | ✅ green |
| 30-04 T3 | phase gate (§27 reviews) | full suite + coverage, mypy, ruff, makemigrations, spectacular, PG | gate | ✅ green |

Sampling continuity: every task carries at least one `<automated>` verify with a `<fails_when>`; no three consecutive tasks lack an automated check.

---

## Wave 0 Requirements

- [x] Phase 29 contract re-verification (fail fast if `credit_cost`, `get_shop_credit_balance`, `CreditBalanceView`, `transition_status` absent)
- [x] New test files listed above; credits-enabled fixture (factory default stays 0)
- [x] Re-point `TestGenerateReplyEndpoint` patches; update T-20-LK key-set tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `backend-pg` green on PG16 | CCON-02 | Needs push | `gh run view` → `backend-pg` ≥1 passed, 0 skipped |
| UAT generate with an enabled org | CCON-01 | Needs running app | Set allocation via admin/shell per runbook; generate; observe credits fields |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** local gates green 2026-11-11 (12 pg_concurrency passed, 0 skipped on throwaway PostgreSQL 14; full suite 1439 passed, 14 skipped, coverage 89.39%). Manual-Only rows above (CI `backend-pg` on PG16, UAT generate) remain open until after push.

## Validation Audit 2026-11-11

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
