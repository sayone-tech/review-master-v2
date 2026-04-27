---
phase: 6
slug: org-admin-shell
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/ -x -q --no-header` |
| **Full suite command** | `pytest apps/ --cov=apps --cov-fail-under=85 -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/ -x -q --no-header`
- **After every plan wave:** Run `pytest apps/ --cov=apps --cov-fail-under=85 -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | XMOD-05 | unit | `pytest apps/regions/ apps/shops/ apps/accounts/ -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | XMOD-05 | unit | `pytest apps/accounts/tests/test_models.py -x -q` | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | XMOD-05 | unit | `python manage.py migrate --run-syncdb && python manage.py migrate --check` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | XMOD-05 | unit | `pytest apps/common/tests/ -x -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | XMOD-05 | integration | `pytest apps/common/tests/test_isolation.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | SHEL-01 | unit | `pytest apps/accounts/tests/test_views.py -x -q -k login` | ✅ | ⬜ pending |
| 06-04-01 | 04 | 2 | SHEL-02 SHEL-03 | unit | `pytest apps/organisations/tests/test_views.py -x -q -k dashboard` | ✅ | ⬜ pending |
| 06-05-01 | 05 | 2 | SHEL-04 | unit | `pytest apps/accounts/tests/test_views.py -x -q -k org_profile` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/regions/__init__.py`, `apps/regions/apps.py`, `apps/regions/models.py` — Region model stubs
- [ ] `apps/regions/tests/__init__.py`, `apps/regions/tests/test_models.py` — Region test stubs
- [ ] `apps/shops/__init__.py`, `apps/shops/apps.py`, `apps/shops/models.py` — Shop model stubs
- [ ] `apps/shops/tests/__init__.py`, `apps/shops/tests/test_models.py` — Shop test stubs
- [ ] `apps/common/tests/__init__.py`, `apps/common/tests/conftest.py` — shared fixture infrastructure
- [ ] `apps/common/tests/test_isolation.py` — cross-tenant isolation test stubs
- [ ] `apps/accounts/tests/test_views.py` extended with `org_profile` test stubs

*Existing infrastructure (pytest, factories, accounts/organisations tests) covers the remainder.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sidebar active state yellow highlight on current page | SHEL-01 | Visual CSS state — not testable via pytest | Login as Org Admin, navigate to each of the 6 nav items, confirm yellow highlight on active |
| Zero-regions setup banner disappears after first Region created | SHEL-03 | Requires browser flow across two requests | Create a Region via admin shell stub, refresh dashboard, confirm banner gone |
| django-sequences smoke test passes against live Django 6 test DB | XMOD-05 note | Compatibility check not expressible as a pure unit test | Run `pytest apps/common/tests/test_sequences_smoke.py -x -v` and confirm green |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
