---
phase: 25
slug: org-admin-tag-management-dashboard-polarity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source test map: `25-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `--ds=config.settings.test` |
| **Quick run command** | `pytest apps/reviews/tests/ apps/dashboard/tests/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85 -q` |
| **Estimated runtime** | ~60 seconds (quick), full suite longer |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/reviews/tests/ apps/dashboard/tests/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85 -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> Task IDs are assigned at planning time. Rows below are keyed by requirement and
> map each phase behavior to its automated proof. The planner/executor fills
> Task ID / Plan / Wave columns as tasks are created.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | TMGT-01 | T-25-AC1 | Staff GET `/admin/org/tags/` → redirect (no access) | unit | `pytest apps/reviews/tests/test_views.py::test_tags_page_staff_redirected -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-01 | — | ORG_ADMIN GET `/admin/org/tags/` → 200 | unit | `pytest apps/reviews/tests/test_views.py::test_tags_page_org_admin_ok -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-02 | — | canonical tags list query count ≤ 3 (fixed ceiling) | unit | `pytest apps/reviews/tests/test_views.py::test_canonical_tags_list_query_count -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-02 | — | ordering by column works | unit | `pytest apps/reviews/tests/test_views.py::test_canonical_tags_ordering -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-03 | T-25-AC5 | rename updates only `OrgCanonicalTag.label` (O(1), no ReviewTag fan-out) | unit | `pytest apps/reviews/tests/test_services.py::test_rename_updates_canonical_tag_label -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-03 | T-25-AC5 | rename rejects case-insensitive duplicate (`label__iexact`) | unit | `pytest apps/reviews/tests/test_services.py::test_rename_rejects_iexact_duplicate -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-03 | — | rename applies Title-Case normalization | unit | `pytest apps/reviews/tests/test_services.py::test_rename_title_case -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-04 | T-25-AC3 | merge endpoint returns 409 when an active job exists | unit | `pytest apps/reviews/tests/test_views.py::test_merge_409_when_active_job -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-05 | — | merge FK re-point is a single bulk UPDATE (no N+1) | unit | `pytest apps/reviews/tests/test_services.py::test_merge_bulk_update_no_n_plus_one -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-05 | T-25-AC3 | merge `transaction.atomic` rolls back on failure (no half-merge) | unit | `pytest apps/reviews/tests/test_services.py::test_merge_rollback_on_error -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-05 | T-25-AC1 | cross-org scoping: org A cannot merge org B tags | unit | `pytest apps/reviews/tests/test_services.py::test_merge_cross_org_blocked -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-05 | — | `dispatch_notification` called on SUCCESS | unit | `pytest apps/reviews/tests/test_services.py::test_merge_dispatches_notification -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-06 | T-25-AC1 | poll endpoint returns active job for the caller's org only | unit | `pytest apps/reviews/tests/test_views.py::test_tag_merge_job_active_endpoint -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TMGT-06 | — | dismiss endpoint marks job dismissed | unit | `pytest apps/reviews/tests/test_views.py::test_tag_merge_job_dismiss -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TDASH-01 | — | tag polarity endpoint returns stacked pos/neg counts for mixed tags | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_basic -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TDASH-02 | — | aggregation excludes ReviewTag rows with null `canonical_tag` | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_excludes_null_canonical -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TDASH-02 | — | tag polarity query count ≤ 2 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_tag_polarity_query_count -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/reviews/tests/factories.py` — add `TagMergeJobFactory` (model not yet created) + ensure `OrgCanonicalTagFactory`/`ReviewTagFactory` cover polarity_type
- [ ] `apps/reviews/tests/test_services.py` — stubs for rename + merge service tests (TMGT-03, TMGT-05)
- [ ] `apps/reviews/tests/test_views.py` — stubs for canonical-tag viewset + tag-merge-job endpoint tests (TMGT-01, TMGT-02, TMGT-04, TMGT-06)
- [ ] `apps/dashboard/tests/test_aggregations.py` — stubs for tag polarity tests (TDASH-01, TDASH-02), extend existing file
- [ ] No new `conftest.py` needed — existing `apps/dashboard/tests/conftest.py` provides org/shop fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Merge in-progress bar polls, survives page reload, shows completion toast | TMGT-06 | Live UI polling + reload behavior is integration/visual, not unit-testable in isolation | Trigger a merge in the Tags page; observe the in-progress bar; reload the page mid-merge → bar re-appears from the job poll; on completion → toast |
| Dashboard mixed-tag stacked bar renders pos/neg split visually | TDASH-01 | Recharts visual rendering | Open dashboard with a `mixed` canonical tag that has both polarities; confirm the stacked bar splits |
| Tags nav item hidden for Staff in sidebar | TMGT-01 | Template rendering (the API 403 IS unit-tested; sidebar hide is belt-and-braces) | Log in as Staff → Tags item absent from sidebar |

*The authoritative defense (API 403 / redirect, cross-org block) is automated above; these manual checks cover the UI belt-and-braces layer.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
