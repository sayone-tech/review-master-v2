---
phase: 13
slug: action-items-and-notifications
status: signed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
signed_off: 2026-05-03
signed_off_by: planner
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Approved by planner on 2026-05-03 after revision-mode pass that addressed
> blocking issues B1–B4 and recommendations R1–R5.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-django |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest apps/action_items/ apps/notifications/ -x -q` |
| **Full suite command** | `pytest apps/ -q --tb=short` |
| **Frontend type-check** | `cd frontend && npx tsc --noEmit -p .` |
| **Frontend bundle**     | `cd frontend && npx vite build` |
| **Estimated runtime**   | ~30 seconds (backend) + ~20 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run `pytest apps/action_items/ apps/notifications/ -x -q` (backend tasks) or `cd frontend && npx tsc --noEmit -p .` (frontend tasks).
- **After every plan wave:** Run `pytest apps/ -q --tb=short` and `cd frontend && npx vite build`.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan / Task | Wave | Requirement(s) | Test Type | Automated Command | Status |
|---------|-------------|------|----------------|-----------|-------------------|--------|
| 13-01-T1 | 13-01 Task 1 — ActionItem + ActionItemNote + AuditLog models | 1 | ACTN-01, ACTN-04 | unit | `pytest apps/action_items/tests/test_models.py -x -q` | ⬜ pending |
| 13-01-T2 | 13-01 Task 2 — factories + admin | 1 | ACTN-01 | unit | `pytest apps/action_items/tests/test_models.py -x -q` | ⬜ pending |
| 13-02-T1 | 13-02 Task 1 — Notification model + factories + admin | 1 | NOTF-01, NOTF-02 | unit | `pytest apps/notifications/tests/test_models.py -x -q` | ⬜ pending |
| 13-03-T1 | 13-03 Task 1 — selectors + BrandScopeGuard permission | 2 | ACTN-02, ACTN-12 | unit + query-count | `pytest apps/action_items/tests/test_selectors.py -x -q` | ⬜ pending |
| 13-03-T2 | 13-03 Task 2 — lifecycle service (create/transition/assign/note/promote) + AuditLog | 2 | ACTN-02, ACTN-08 | unit | `pytest apps/action_items/tests/test_services.py -x -q` | ⬜ pending |
| 13-04-T1 | 13-04 Task 1 — Serializers + FilterSet + ViewSet + URLs (consolidated wiring per B2 Option A) | 3 | ACTN-04, ACTN-05, ACTN-09 | smoke | `python manage.py check` | ⬜ pending |
| 13-04-T2 | 13-04 Task 2 — View tests inc. ACTN-12 ≤5-query gate | 3 | ACTN-02, ACTN-04, ACTN-05, ACTN-07–10, ACTN-12 | integration + query-count | `pytest apps/action_items/tests/test_views.py -x -q` | ⬜ pending |
| 13-05-T1 | 13-05 Task 1 — dispatch_notification + enrichment on_commit + sync.py new_review (R4/R5) | 3 | ACTN-01, NOTF-01, NOTF-02, NOTF-05 | integration | `pytest apps/notifications/tests/test_dispatch.py apps/action_items/tests/test_services.py -x -q` | ⬜ pending |
| 13-05-T2 | 13-05 Task 2 — NotificationViewSet + bell endpoint | 3 | NOTF-03, NOTF-04 | integration + query-count | `pytest apps/notifications/tests/test_views.py -x -q` | ⬜ pending |
| 13-06-T1 | 13-06 Task 1 — types + api + useActionItems + Vite (registers BOTH 13-06 and 13-08 entries) + entrypoint | 4 | ACTN-02, ACTN-04 | type-check | `cd frontend && npx tsc --noEmit -p .` | ⬜ pending |
| 13-06-T2 | 13-06 Task 2 — Filters + Table + Widget + status submenu | 4 | ACTN-03, ACTN-08 | type-check + bundle | `cd frontend && npx tsc --noEmit -p . && npx vite build` | ⬜ pending |
| 13-07-T1 | 13-07 Task 1 — ActionItemModal (3 tabs) + DetailsTab inline (R1) | 4 | ACTN-06, ACTN-07, ACTN-10, ACTN-11 | type-check | `cd frontend && npx tsc --noEmit -p .` | ⬜ pending |
| 13-07-T2 | 13-07 Task 2 — CreateModal + Chip upgrade + has_action_items annotation (B3 REVW-14 gate) | 4 | ACTN-09, ACTN-13, REVW-08 | type-check + bundle + query-count | `cd frontend && npx tsc --noEmit -p . && npx vite build && pytest apps/reviews/tests/ -k "test_query_count" -x -q` | ⬜ pending |
| 13-08-T1 | 13-08 Task 1 — types + api + useNotifications hook (R3 inlined helper) | 4 | NOTF-01, NOTF-02, NOTF-04 | type-check | `cd frontend && npx tsc --noEmit -p .` | ⬜ pending |
| 13-08-T2 | 13-08 Task 2 — NotifBell component + topbar mount | 4 | NOTF-01, NOTF-02, NOTF-03, NOTF-05 | type-check + bundle | `cd frontend && npx tsc --noEmit -p . && npx vite build` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave map (revised after B2-residual + W1 wave fix):** W1 = {13-01, 13-02} · W2 = {13-03} · W3 = {13-04, 13-05} · W4 = {13-06, 13-07, 13-08}.

*Within-wave sequencing in W4:* 13-07 has `depends_on: ["13-06"]` and 13-08 has `depends_on: ["13-05"]`. Within W4, executors must honour `depends_on` ordering: 13-06 runs first, then 13-07 (which modifies `ActionItemManagementWidget.tsx` after 13-06 creates it). 13-08 is independent of 13-06/13-07 within W4 and can run parallel to either, since `frontend/vite.config.ts` is owned exclusively by 13-06 and `templates/partials/topbar.html` is owned exclusively by 13-08.
**Same-wave file conflicts (post-B2-residual + W1 fix):** none.
- W3 ({13-04, 13-05}): `config/urls.py` is owned by 13-04 (uses lazy string `include("apps.notifications.urls")` so 13-04 can land before 13-05). `apps/notifications/urls.py` is owned outright by 13-05 — 13-04 does NOT touch it.
- W4 ({13-06, 13-07, 13-08}): `frontend/vite.config.ts` is owned exclusively by 13-06 (registers BOTH `action-items-management` and `notif-bell` entries upfront; 13-08 does NOT modify the file). `ActionItemManagementWidget.tsx` is created by 13-06 and modified by 13-07 — sequenced via `depends_on: ["13-06"]` on 13-07. `templates/partials/topbar.html` is owned exclusively by 13-08.

---

## Wave 0 Requirements

All Wave 0 scaffolding is delivered as part of Plans 13-01 and 13-02 (the model plans in Wave 1). The MISSING-test pattern does not apply because every test referenced in the verification map has its file created in the same plan that introduces the behaviour.

- [x] `apps/action_items/__init__.py` — created in 13-01
- [x] `apps/action_items/apps.py` — created in 13-01
- [x] `apps/action_items/tests/__init__.py` — created in 13-01
- [x] `apps/action_items/tests/factories.py` — created in 13-01 Task 2
- [x] `apps/action_items/tests/test_models.py` — created in 13-01 Task 1 (ACTN-01)
- [x] `apps/action_items/tests/test_services.py` — created in 13-03 Task 2 (ACTN-02, ACTN-08)
- [x] `apps/action_items/tests/test_selectors.py` — created in 13-03 Task 1 (ACTN-12 query-count)
- [x] `apps/action_items/tests/test_views.py` — created in 13-04 Task 2 (ACTN-04..ACTN-10, ACTN-12)
- [x] `apps/notifications/__init__.py` — created in 13-02
- [x] `apps/notifications/apps.py` — created in 13-02
- [x] `apps/notifications/tests/__init__.py` — created in 13-02
- [x] `apps/notifications/tests/factories.py` — created in 13-02
- [x] `apps/notifications/tests/test_dispatch.py` — created in 13-05 Task 1 (NOTF-05, R4 sync wiring)
- [x] `apps/notifications/tests/test_views.py` — created in 13-05 Task 2 (NOTF-03, NOTF-04)

No `<verify><automated>MISSING — Wave 0 must create …</automated></verify>` placeholders remain in any plan.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Notification bell popover renders and dismisses | NOTF-03 | Browser DOM interaction (popover, outside-click) | Open `/admin/org/action-items/`, verify bell icon shows count, click to open popover with ≤10 items, click item to navigate and mark read |
| Staff user cannot see brand-scoped items via UI | ACTN-06 | Role-dependent UI rendering (Layer 3 — UI hide of scope filter and Brand option in CreateModal) | Log in as Staff, navigate to action items, confirm no brand-scope filter UI and no brand items in list; open create modal — Brand option absent |
| Action item creation modal flow | ACTN-03 | Multi-step form interaction | As Org Admin, click "Create", fill all fields, submit, verify item appears in list with correct data |
| Status transition audit trail | ACTN-08 | UI + database consistency | Transition item to each status, verify audit log entries in detail modal |
| New review notification end-to-end | NOTF-02 | Requires running Google sync against a fixture | Trigger `python manage.py runscript run_sync_for_shop --shop-id=…` (or seed via shell) to insert a new review row; within 60 s the bell badge increments by one per eligible recipient |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are covered by Wave 0 scaffolding (no MISSING placeholders)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags in any verify command
- [x] Feedback latency < 30 s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved by planner on 2026-05-03 (post-revision pass addressing B1–B4 + R1–R5).
