---
phase: 20
slug: ai-guardrails
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source-of-truth: 20-RESEARCH.md `## Validation Architecture` (which maps D-01..D-33 to concrete pytest commands).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-django (existing — per CLAUDE.md §16) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest apps/integrations/openai/tests/test_guardrails.py apps/reviews/tests/test_enrichment_service.py apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_views.py apps/reviews/tests/test_tasks.py -x` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~30s quick; ~3-5min full |

---

## Sampling Rate

- **After every task commit:** Run quick command (above)
- **After every plan wave:** Run full suite + `pre-commit run --all-files`
- **Before `/gsd:verify-work`:** Full suite green + `python manage.py makemigrations --check --dry-run` clean
- **Max feedback latency:** 30 seconds for the per-task quick command

---

## Per-Task Verification Map

The planner will fill this in per-task. Each task in PLAN.md must reference one or more of these test files and a concrete pytest `-k` filter. Decisions → tests:

| Decision | Test file | Test focus |
|---|---|---|
| D-01, D-04, D-23, D-30 | `test_guardrails.py` | `moderate_input` calls API, blocks only on underscore high-severity keys |
| D-03, D-21 | `test_guardrails.py` | truncates to `OPENAI_REVIEW_TEXT_MAX_CHARS`, appends `…[truncated]` |
| D-07, D-08, D-22 | `test_guardrails.py` | `moderate_output` blocks flagged, then 300-word sentence truncation |
| D-14, D-15 | `test_enrichment_service.py`, `test_reply_generation_service.py` | call sequence: input → OpenAI → (output for reply) |
| D-16, D-26, D-32 | `test_views.py` | `ContentModeratedException` → HTTP 422 with canonical detail; inherits OpenAIError |
| D-20, D-28, D-29 | `test_enrichment_service.py`, `test_reply_generation_service.py` | input-mod row tokens=0; output-mod row real tokens + `error_code="output_moderated"` |
| D-24 | `test_guardrails.py` | fail-open with 1 retry; both fail → log ERROR + proceed |
| D-25, D-31 | `test_tasks.py` | retry queryset excludes `enrichment_error_code="content_moderated"` |
| D-33 | `test_guardrails.py` | `AiUsageLog` row written from inside `guardrails.py`, outside atomic() |

---

## Wave 0 Requirements

- [ ] **NEW** `apps/integrations/openai/tests/test_guardrails.py` — entire test file (does not exist today)
- [ ] Extend `apps/reviews/tests/test_enrichment_service.py` — add `class TestEnrichReviewModeration` for D-14, D-20, D-28, D-29 input path
- [ ] Extend `apps/reviews/tests/test_reply_generation_service.py` — add `class TestGenerateReplyDraftModeration` for D-15 input + D-07 output paths
- [ ] Extend `apps/reviews/tests/test_views.py` — add `test_generate_reply_returns_422_on_content_moderated`
- [ ] Extend `apps/reviews/tests/test_tasks.py` — add `test_retry_failed_enrichments_excludes_moderated`

No new framework install. Existing `unittest.mock.patch` convention applies (per RESEARCH.md §"Mock convention").

---

## Manual-Only Verifications

| Behavior | Decision | Why Manual | Test Instructions |
|----------|---|------------|-------------------|
| Frontend renders 422 `detail` verbatim | D-26, D-27 | Phase 19 React component is out of scope; no React test runner change | In dev: trigger a flagged review via shell, click "Generate with AI" in browser, confirm canonical D-26 copy appears under the textarea |
| Sentry captures `ai.moderation.errored` at ERROR | D-24 | Sentry integration is environmental | Verify in staging by temporarily forcing `_call_moderation_api` to raise; check Sentry receives the event with `entity_type/entity_id` tags |

---

## Validation Sign-Off

- [ ] Every plan task has an `<automated>` verify command or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all five test files listed above
- [ ] No watch-mode flags (`-f`, `--watch`) in any task verify command
- [ ] Feedback latency < 30s for the quick command
- [ ] `nyquist_compliant: true` set in frontmatter once all checks pass

**Approval:** pending — set when plan-checker confirms coverage
