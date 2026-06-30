---
phase: 24
slug: polarity-auto-reclassification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-11
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from the "## Validation Architecture" section of 24-RESEARCH.md.

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

> Populated during planning/execution. No GPT calls in this phase — pure DB.
> Key coverage areas (from 24-RESEARCH.md Validation Architecture):

| Area | Requirement | Test Type | Automated Command (target) | Status |
|------|-------------|-----------|----------------------------|--------|
| Flip always_positive → mixed when negative ÷ all > threshold | POL-02 | unit/service | `pytest apps/reviews/tests/test_polarity_reclassify.py -k flip -q` | ⬜ pending |
| No flip below min-sample (e.g. 4 reviews, 1 opposite) | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k min_sample -q` | ⬜ pending |
| Boundary: exactly at threshold does NOT flip (> not ≥) | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k boundary -q` | ⬜ pending |
| Already-mixed tags skipped (one-way, sticky) | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k skip_mixed -q` | ⬜ pending |
| Neutral counts in denominator only (dilutes ratio) | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k neutral -q` | ⬜ pending |
| Soft-deleted reviews excluded from window | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k soft_delete -q` | ⬜ pending |
| Window measured by Review.review_create_time | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k window -q` | ⬜ pending |
| Multi-tenant isolation: org A flip never reads/writes org B | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k tenant -q` | ⬜ pending |
| Idempotency: second run same week is a no-op | POL-02 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k idempotent -q` | ⬜ pending |
| No-N+1: query count fixed regardless of tag/org count | POL-02 | query-count | `pytest apps/reviews/tests/test_polarity_reclassify.py -k query_count -q` | ⬜ pending |
| AuditLog row written (entity_type/action/before/after) | POL-03 | unit | `pytest apps/reviews/tests/test_polarity_reclassify.py -k audit -q` | ⬜ pending |
| Beat schedule seeded (weekly PeriodicTask exists) | POL-02 | migration | `pytest apps/reviews/tests/test_polarity_reclassify.py -k beat -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/test_polarity_reclassify.py` — new test module for the reclassification service + task + AuditLog + query-count

*Existing infrastructure (pytest-django, factories incl. OrgCanonicalTagFactory/ReviewTagFactory, CaptureQueriesContext, AuditLog) covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| (none — POL-03 tag-list visibility is deferred to Phase 25; reclassification events are auto-asserted via AuditLog) | — | — | — |

*All Phase 24 behaviors have automated verification (no UI in this phase).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
