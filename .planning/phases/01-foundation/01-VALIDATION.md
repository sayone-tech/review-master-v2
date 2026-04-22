---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django |
| **Config file** | pyproject.toml |
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
| 1-01-01 | 01 | 0 | DSYS-01 | smoke | `docker-compose up -d && docker-compose exec web python manage.py check` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | DSYS-01 | smoke | `docker-compose exec web python manage.py migrate --check` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | DSYS-02 | unit | `pytest apps/accounts/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | DSYS-02 | unit | `pytest apps/organisations/tests/test_models.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | DSYS-03 | unit | `pytest apps/accounts/tests/test_models.py::test_invitation_token -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 2 | DSYS-04 | visual/manual | N/A — layout render | N/A | ⬜ pending |
| 1-05-01 | 05 | 3 | DSYS-05 | visual/manual | N/A — component library | N/A | ⬜ pending |
| 1-06-01 | 06 | 3 | DSYS-06 | visual/manual | N/A — accessibility | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/tests/__init__.py` — test package stub
- [ ] `apps/accounts/tests/factories.py` — UserFactory stub
- [ ] `apps/organisations/tests/__init__.py` — test package stub
- [ ] `apps/organisations/tests/factories.py` — OrganisationFactory stub
- [ ] `conftest.py` (root) — pytest-django settings fixture
- [ ] `pytest` + `pytest-django` + `factory-boy` installed in pyproject.toml

*Wave 0 installs test infrastructure so all subsequent waves can run automated checks.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Base layout renders on desktop/tablet/mobile | DSYS-04 | Browser visual check required | Open `docker-compose up`, navigate to `/`, verify sidebar + topbar + content area at 1440px, 768px, 375px |
| Full component library renders correctly | DSYS-05 | Visual/interactive check | Navigate to component showcase page, verify buttons/forms/modals/tables/toasts/badges/skeletons |
| Keyboard navigation & ARIA | DSYS-06 | A11y manual audit | Tab through all components, verify focus indicators visible, screen reader ARIA labels present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
