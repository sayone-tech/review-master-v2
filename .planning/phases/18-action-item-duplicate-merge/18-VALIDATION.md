---
phase: 18
slug: action-item-duplicate-merge
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 + pytest-django 4.9.0 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest apps/action_items/ -x -q` |
| **Full suite command** | `uv run pytest apps/action_items/ --cov=apps/action_items --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest apps/action_items/ -x -q`
- **After every plan wave:** Run `uv run pytest apps/action_items/ --cov=apps/action_items --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| canonical FK on ActionItem model | 18-01 | 1 | D-01 | unit | `uv run pytest apps/action_items/tests/test_models.py -x -q` | ⬜ pending |
| SET_NULL cascade on canonical delete | 18-01 | 1 | D-02 | unit | `uv run pytest apps/action_items/tests/test_models.py -x -q` | ⬜ pending |
| merge_action_items() service function | 18-02 | 2 | D-14/D-15 | unit | `uv run pytest apps/action_items/tests/test_services.py -x -q` | ⬜ pending |
| D-03 read-only guards on lifecycle mutators | 18-02 | 2 | D-03 | unit | `uv run pytest apps/action_items/tests/test_services.py -x -q` | ⬜ pending |
| D-05/06/08/09 merge validation rules | 18-02 | 2 | D-05/06/08/09 | unit | `uv run pytest apps/action_items/tests/test_services.py -x -q` | ⬜ pending |
| list_action_items hides merged duplicates + annotates count | 18-02 | 2 | D-10/D-11 | unit | `uv run pytest apps/action_items/tests/test_selectors.py -x -q` | ⬜ pending |
| get_action_item prefetches duplicates | 18-02 | 2 | D-12 | unit | `uv run pytest apps/action_items/tests/test_selectors.py -x -q` | ⬜ pending |
| POST /merge/ endpoint (Org Admin) | 18-02 | 2 | D-16 | integration | `uv run pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| POST /merge/ returns 403 for Staff | 18-02 | 2 | D-16 | integration | `uv run pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| PATCH/status on merged duplicate returns 400 | 18-02 | 2 | D-17 | integration | `uv run pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| List query-count gate with duplicate_count annotation | 18-02 | 2 | D-10/11 | performance | `uv run pytest apps/action_items/tests/test_selectors.py -x -q` | ⬜ pending |
| list serializer exposes duplicate_count + frontend types | 18-02 | 2 | D-11 | integration | `uv run pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| detail serializer includes nested duplicates | 18-02 | 2 | D-12 | integration | `uv run pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| Frontend list multi-select + toolbar + MergeModal | 18-03 | 3 | D-18 | manual | `npx tsc --noEmit` (in frontend/) | ⬜ pending |
| Frontend detail "Mark as duplicate of…" + DuplicatePickerModal | 18-04 | 3 | D-19 | manual | `npx tsc --noEmit` (in frontend/) | ⬜ pending |
| Frontend "Also reported in" section | 18-04 | 3 | D-13 | manual | `npx tsc --noEmit` (in frontend/) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All test cases listed above are new (❌). Test files exist — extend existing ones:

- [ ] `apps/action_items/tests/test_models.py` — add D-01 (canonical field), D-02 (SET_NULL cascade) tests
- [ ] `apps/action_items/tests/test_services.py` — add D-03 guards, D-05/06/08/09 validation, merge happy-path, audit-log test
- [ ] `apps/action_items/tests/test_selectors.py` — add D-10/11/12 tests + query-count gate
- [ ] `apps/action_items/tests/test_views.py` — add D-16 endpoint tests (Org Admin + Staff 403) + D-17 400 responses

*No new test files needed — all new tests extend existing test modules.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| List view: checkboxes appear, "Merge duplicates" toolbar button shows when ≥2 checked | D-18 | React UI interaction | Open action items list as Org Admin; select 2+ AI items; verify toolbar button appears |
| MergeModal: radio picks primary, confirmation text correct, merge completes | D-18 | React UI interaction | With 2+ items selected, click "Merge duplicates"; pick primary; verify confirmation text; confirm; verify one item remains |
| "+N" badge appears on canonical after merge | D-11 | React UI rendering | After merge, find the canonical in the list; verify "+N" badge shows on its row |
| Detail view: "Also reported in" section shows merged items | D-13 | React UI rendering | Open canonical's detail; verify "Also reported in" section lists duplicates with shop, date, rating |
| "Mark as duplicate of…" button opens search picker | D-19 | React UI interaction | Open any AI action item's detail as Org Admin; click "Mark as duplicate of…"; verify search-as-you-type picker opens |
| DuplicatePickerModal: search filters correctly, selection + confirm merges | D-19/D-20 | React UI interaction | Search for another item; select it; confirm; verify both items now show canonical/duplicate relationship |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
