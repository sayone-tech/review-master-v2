---
phase: 14
slug: dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest apps/dashboard/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85` |
| **Estimated runtime** | ~30 seconds (quick), ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/dashboard/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | TECH-03 | unit | `pytest apps/reviews/tests/test_models.py::test_review_meta_indexes -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-02 | 01 | 1 | FILT-08 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_out_of_scope_shop -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-03 | 01 | 1 | FILT-09 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_range_too_long -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-04 | 01 | 1 | FILT-10 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_from_after_to -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-05 | 01 | 1 | TECH-02 | unit | `pytest apps/dashboard/tests/test_filters.py::test_filter_hash_differs_by_shop_scope -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-01 | 02 | 1 | TOP-01 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_top_performing_date_only -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-02 | 02 | 1 | TOP-02 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_top_performing_min_reviews -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-03 | 02 | 1 | KPI-03 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_negative_count_ai_sentiment -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-04 | 02 | 1 | SENT-06 | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_sentiment_empty_states -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-05 | 02 | 1 | TECH-04 | unit | `pytest apps/dashboard/tests/test_aggregations.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 14-03-01 | 03 | 1 | FILT-08 | integration | `pytest apps/dashboard/tests/test_views.py::test_out_of_scope_store_returns_403 -x` | ❌ Wave 0 | ⬜ pending |
| 14-03-02 | 03 | 1 | FILT-09 | integration | `pytest apps/dashboard/tests/test_views.py::test_date_range_too_long_returns_400 -x` | ❌ Wave 0 | ⬜ pending |
| 14-03-03 | 03 | 1 | TECH-04 | integration | `pytest apps/dashboard/tests/test_views.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 14-03-04 | 03 | 1 | ERR-01 | unit | `pytest apps/common/tests/test_views.py::test_404_page -x` | ❌ Wave 0 | ⬜ pending |
| 14-03-05 | 03 | 1 | ERR-02 | unit | `pytest apps/common/tests/test_views.py::test_500_page -x` | ❌ Wave 0 | ⬜ pending |
| 14-04-01 | 04 | 2 | TECH-05 | manual | Load `/admin/org/dashboard/` — verify `#dashboard-root` div present and bootstrap JSON tags rendered | N/A | ⬜ pending |
| 14-05-01 | 05 | 2 | FILT-01 | manual | Filter bar renders with region dropdown populated from bootstrap data | N/A | ⬜ pending |
| 14-05-02 | 05 | 2 | FILT-06 | manual | Changing filter updates URL params without page reload | N/A | ⬜ pending |
| 14-06-01 | 06 | 2 | TOP-03 | manual | Bars colored green/amber/red by threshold | N/A | ⬜ pending |
| 14-06-02 | 06 | 2 | TOP-05 | manual | Bar click navigates to reviews page with correct shop+date params | N/A | ⬜ pending |
| 14-07-01 | 07 | 2 | KPI-05 | manual | Each KPI card shows independent skeleton while loading | N/A | ⬜ pending |
| 14-07-02 | 07 | 2 | SENT-04 | manual | Coverage footer appears when enrichment < 100% | N/A | ⬜ pending |
| 14-08-01 | 08 | 3 | ERR-01 | manual | Visiting a 404 URL shows branded page (not Django default) | N/A | ⬜ pending |
| 14-08-02 | 08 | 3 | ERR-02 | manual | Triggering a 500 shows branded page (not Django default) | N/A | ⬜ pending |
| 14-08-03 | 08 | 3 | TECH-06 | manual | Network tab shows 5 parallel API requests on page load | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All of the following must be created before Wave 1 execution begins:

- [ ] `apps/dashboard/__init__.py` — new app package
- [ ] `apps/dashboard/apps.py` — `DashboardConfig` with `name = "apps.dashboard"`
- [ ] `apps/dashboard/tests/__init__.py` — test package
- [ ] `apps/dashboard/tests/test_filters.py` — stubs for FILT-08, FILT-09, FILT-10, TECH-02 (test bodies raise `pytest.fail("not implemented")` until Plan 14-01 fills them)
- [ ] `apps/dashboard/tests/test_aggregations.py` — stubs for TOP-01, TOP-02, TECH-04, KPI-03, SENT-06
- [ ] `apps/dashboard/tests/test_views.py` — stubs for TECH-04 HTTP layer, FILT-08 integration
- [ ] Framework: pytest + pytest-django already configured in `pyproject.toml` — no install needed
- [ ] Migration `apps/reviews/migrations/0006_dashboard_indexes.py` is created in Plan 14-01 (Wave 1), not Wave 0 — Wave 0 only needs the test package stubs

*Wave 0 is complete when all stub test files exist and `pytest apps/dashboard/ -x -q` exits 0 (stubs pass trivially).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Filter bar dropdowns render immediately from bootstrap data | FILT-01, FILT-02 | Browser DOM / React render — no backend assertion | Load `/admin/org/dashboard/`; inspect Region and Store dropdowns — must be populated before any API response arrives |
| URL params updated on filter change | FILT-06 | `history.replaceState` — browser API, not testable with pytest | Open DevTools; change Region filter; verify URL bar shows `?region=N` without page reload |
| Filter state persists within session | FILT-07 | `sessionStorage` — browser API | Set a filter; navigate away; press back; verify filter is restored |
| Bar threshold coloring | TOP-03 | Visual — SVG fill colors not easily asserted in unit tests | Load dashboard with seeded data; verify green/amber/red bars match rating thresholds |
| Bar click navigation | TOP-05 | `window.location.href` — requires browser | Click a bar; verify navigation to `/admin/org/reviews/?store=N&from=...&to=...` with absolute ISO dates |
| Single-shop "Your Store" card | STORE-01 | Requires test user with exactly 1 accessible shop | Log in as a single-store Staff user; verify "Your Store" card renders instead of bar chart |
| Loading skeletons per card | KPI-05 | Network throttling required | In DevTools, throttle to Slow 3G; reload dashboard; verify each KPI card shows independent skeleton |
| Sentiment coverage footer | SENT-04, SENT-05 | Requires seeded data with partial enrichment | Load dashboard with org where some reviews are not enriched; verify coverage footer + spinner (if <50%) |
| 404 branded page | ERR-01 | Requires `DEBUG=False` for `handler404` to fire | With `DEBUG=False`, visit `/admin/org/nonexistent/`; verify branded 404 (logo, yellow CTA) |
| 500 branded page | ERR-02 | Requires triggering a 500 | With `DEBUG=False`, temporarily add a view that raises `Exception`; verify branded 500 |
| 5 parallel API requests | TECH-06 | Network waterfall — browser DevTools | Open Network tab; reload dashboard; verify 5 API requests fire simultaneously (overlapping timelines) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
