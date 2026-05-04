---
phase: 11
slug: reviews
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-01
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest apps/reviews/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/reviews/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | SYNC-01..10 | unit | `pytest apps/reviews/tests/test_sync_service.py -x -q` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | SYNC-04 | unit | `pytest apps/reviews/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | PROG-08,09 | integration | `pytest apps/reviews/tests/test_consumers.py -x -q` | ✅ partial | ⬜ pending |
| 11-02-02 | 02 | 1 | PROG-10 | unit | `pytest apps/reviews/tests/test_sync_service.py::test_progress_ttls -x` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 2 | REVW-01..09 | integration | `pytest apps/reviews/tests/test_views.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 2 | REVW-14 | query-count | `pytest apps/reviews/tests/test_views.py::test_reviews_list_query_count -x` | ❌ W0 | ⬜ pending |
| 11-04-01 | 04 | 2 | REVW-10..13 | unit | `pytest apps/reviews/tests/test_reply_service.py -x -q` | ❌ W0 | ⬜ pending |
| 11-04-02 | 04 | 2 | REVW-12 | unit | `pytest apps/reviews/tests/test_views.py::test_reply_throttle -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/__init__.py` — ensure test package exists
- [ ] `apps/reviews/tests/factories.py` — `ReviewFactory`, `AuditLogFactory`, `ShopFactory` extension
- [ ] `apps/reviews/tests/test_models.py` — `UniqueConstraint(shop, google_review_id)`, soft-delete, enrichment_status transitions
- [ ] `apps/reviews/tests/test_sync_service.py` — stubs for all SYNC-* tests (initial backfill, upsert, soft-delete, 401 handling, retry/audit, rate bucket, progress TTLs)
- [ ] `apps/reviews/tests/test_reply_service.py` — stubs for REVW-10 (reply posted), REVW-13 (audit log)
- [ ] `apps/reviews/tests/test_selectors.py` — selector tests (list_reviews, query count)
- [ ] `apps/reviews/tests/test_views.py` — API tests: list access (REVW-01), additive filters (REVW-02), query count (REVW-14), reply throttle (REVW-12)
- [ ] `apps/reviews/tests/test_tasks.py` — task dispatch tests: initial backfill dispatched on OAuth (SYNC-01), incremental fan-out (SYNC-02)
- [ ] `apps/reviews/tests/test_consumers.py` — augment existing with: progress event types (PROG-08), reconnect snapshot (PROG-09), staff scope rejection

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Progress Modal opens automatically after OAuth | PROG-01 | Requires live Google OAuth flow | Complete OAuth for a test shop; verify modal appears on Shops page |
| "Run in background" button closes modal, badge appears | PROG-02,03 | End-to-end UI state | Click button during active sync; verify modal closes, badge shows count |
| Top-bar sync badge click opens dropdown with shops | PROG-09 | React widget + Alpine dropdown interaction | Trigger sync; click badge; verify dropdown lists shop with "View progress" link |
| Inline reply composer expand/collapse in DataTable | REVW-09 | UI interaction in React DataTable | Click "Reply" on unreplied row; verify composer expands; click away to collapse |
| Reply posted to Google and confirmed visually | REVW-10 | Requires live Google API | Submit reply in composer; verify success state replaces composer |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
