---
phase: 17
slug: tag-rework-reviewtag-model-and-filter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-21
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest apps/reviews/tests/ apps/integrations/openai/tests/ -x -q` |
| **Full suite command** | `pytest apps/ -x -q --reuse-db` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/reviews/tests/ apps/integrations/openai/tests/ -x -q`
- **After every plan wave:** Run `pytest apps/ -x -q --reuse-db`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| ReviewTag model + migration | 17-01 | 1 | TAG-01 | unit | `pytest apps/reviews/tests/test_models.py -x -q` | ⬜ pending |
| Remove Review.tags JSONField | 17-01 | 1 | TAG-01 | unit | `pytest apps/reviews/tests/test_models.py -x -q` | ⬜ pending |
| Enrichment writes ReviewTag rows | 17-02 | 2 | TAG-02 | unit | `pytest apps/reviews/tests/test_enrichment_service.py -x -q` | ⬜ pending |
| ReviewReadSerializer exposes tags | 17-02 | 2 | TAG-01/02 | integration | `pytest apps/reviews/tests/test_views.py -x -q` | ⬜ pending |
| GET /api/v1/reviews/tags/ endpoint | 17-03 | 2 | TAG-03 | integration | `pytest apps/reviews/tests/test_views.py -x -q` | ⬜ pending |
| Tags filter backend | 17-03 | 2 | TAG-03 | integration | `pytest apps/reviews/tests/test_views.py -x -q` | ⬜ pending |
| Frontend TagsFilter component | 17-04 | 3 | TAG-03 | manual | `npm run build` exits 0 | ⬜ pending |
| Clickable tag chips | 17-04 | 3 | TAG-03 | manual | `npm run build` exits 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/factories.py` — add `ReviewTagFactory`, remove `tags` from `ReviewFactory`
- [ ] `apps/reviews/tests/test_models.py` — stub `test_review_tag_model` for TAG-01

*Existing pytest infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tags dropdown opens, search filters client-side, chips appear selected | TAG-03 | React UI interaction | Open reviews page, click Tags dropdown, type a label, verify filtered list |
| Clicking tag chip in table row adds to active filter | TAG-03 | React UI interaction | Click a chip on a review row, verify tag appears in active filter |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
