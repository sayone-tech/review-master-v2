---
phase: 22
slug: canonical-tag-foundation-mapping-pipeline
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `22-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (CLAUDE.md §16) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest apps/reviews/tests/test_enrichment_service.py apps/integrations/openai/tests/test_parser.py -x` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~quick <15s · full ~minutes |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run `pytest apps/reviews apps/integrations/openai`
- **Before `/gsd-verify-work`:** Full suite must be green (`pytest --cov=apps --cov-fail-under=85`)
- **Max feedback latency:** ~15 seconds (quick path)

---

## Per-Task Verification Map

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|-------------|----------|-----------|-------------------|-------------|
| CTAG-01 | `OrgCanonicalTag` created with org FK + polarity_type, unique `(org,label)` | unit | `pytest apps/reviews/tests/test_models.py -k canonical` | ❌ W0 |
| CTAG-02 | `ReviewTag.canonical_tag` FK populated post-enrichment | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k canonical_fk` | ❌ W0 |
| CTAG-03/05 | Prompt injects capped vocab; canonical English-only instruction present | unit | `pytest apps/integrations/openai/tests/test_prompts.py -k vocab` | ❌ W0 (file exists) |
| CTAG-04 | `Tag` schema parses `canonical` + nullable `polarity_type` | unit | `pytest apps/integrations/openai/tests/test_parser.py -k canonical` | ❌ W0 (file exists) |
| CTAG-06 | Mapping inside atomic block; rollback on failure | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k atomic` | ❌ W0 |
| CTAG-07 | Exactly one `AiUsageLog` row per enrich | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k usage_log` | ✅ extend |
| CTAG-08 | Pre-phase null `canonical_tag` rows stay valid | unit/migration | `pytest apps/reviews/tests/test_models.py -k null_canonical` | ❌ W0 |
| QUEUE-02 | `enrich_review_task` carries per-worker `rate_limit` from setting | unit | `pytest apps/reviews/tests/test_tasks.py -k rate_limit` | ❌ W0 (file exists) |
| — | Query-count ceiling for enrich hot path (no N+1) | perf | `pytest apps/reviews/tests/test_enrichment_service.py -k query_count` | ❌ W0 |
| — | Idempotency: re-enrich → no dup canonical, no miscount | integration | `pytest apps/reviews/tests/test_enrichment_service.py -k idempot` | ✅ extend |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/factories.py` — add `OrgCanonicalTagFactory`
- [ ] `apps/integrations/openai/tests/fixtures/` — add `canonical` + `polarity_type` to a tag fixture (or new fixture) so parser tests reflect the new schema
- [ ] Extend `apps/integrations/openai/tests/test_parser.py` — canonical normalization + nullable `polarity_type` parse cases
- [ ] Extend `apps/integrations/openai/tests/test_prompts.py` — vocab injection + `ENRICHMENT_PROMPT_VERSION` bump assertion
- [ ] New canonical-mapping cases in `apps/reviews/tests/test_enrichment_service.py` (FK populate, atomic rollback, query-count, idempotency)
- [ ] `apps/reviews/tests/test_tasks.py` — assert `enrich_review_task` carries `rate_limit`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real GPT returns sensible canonical mappings across business types | CTAG-03/04 | Needs live model judgement; tests mock OpenAI | Spot-check enrichment on a few real reviews in staging after deploy |

*All structural behaviors have automated verification; only model-quality is manual.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
