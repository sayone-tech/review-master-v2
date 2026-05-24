---
phase: 16
slug: org-admin-shop-creation-conditional-depth-selector
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest apps/shops/tests/ -x -q` |
| **Full suite command** | `pytest --cov=apps --cov-fail-under=85 -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/shops/tests/ -x -q`
- **After every plan wave:** Run `pytest --cov=apps --cov-fail-under=85 -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | SDEP-01 | — | `ChoiceField` rejects invalid `sync_depth` with 400 | unit | `pytest apps/shops/tests/ -x -q -k "sync_depth"` | ✅ | ⬜ pending |
| 16-01-02 | 01 | 1 | SDEP-01 | — | `create_shop()` persists caller-specified `sync_depth` | unit | `pytest apps/shops/tests/test_services.py -x -q -k "sync_depth"` | ✅ | ⬜ pending |
| 16-01-03 | 01 | 1 | SDEP-01 | — | `POST /api/v1/shops/` with `sync_depth=ONE_YEAR` creates shop with that depth | integration | `pytest apps/shops/tests/test_views.py -x -q -k "sync_depth"` | ✅ | ⬜ pending |
| 16-01-04 | 01 | 1 | SDEP-01 | — | `shop_list` view context includes `allow_custom_sync_depth` | integration | `pytest apps/shops/tests/test_views.py -x -q -k "allow_custom"` | ✅ | ⬜ pending |
| 16-02-01 | 02 | 2 | SDEP-01 | — | Dropdown absent from DOM when `allowCustomSyncDepth === false` | manual | Open shop creation modal in browser with org flag disabled | — | ⬜ pending |
| 16-02-02 | 02 | 2 | SDEP-01 | — | Dropdown resets to "Last 2 years" on modal close/reopen | manual | Select "All time" → Cancel → reopen → verify "Last 2 years" selected | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files, config, or fixtures are needed.

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dropdown absent from DOM when org flag is disabled | SDEP-01 | React conditional render — DOM absence not covered by Django unit tests | Open shop creation modal with `allow_custom_sync_depth=False` org; inspect DOM — no `#cs-sync-depth` element should exist |
| Dropdown resets to "Last 2 years" on modal close/reopen | SDEP-01 | React state reset — requires browser interaction | Select "All time" → Cancel → reopen modal → verify select shows "Last 2 years" |
| End-to-end: created shop shows correct depth on shop detail | SDEP-01 | Full user flow — requires browser + real backend | Create shop with "Last 1 year" → navigate to shop detail → verify "Review history" field shows "Last 1 year" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
