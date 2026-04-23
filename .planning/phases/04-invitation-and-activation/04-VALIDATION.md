---
phase: 4
slug: invitation-and-activation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django + vitest |
| **Config file** | `pyproject.toml` (pytest), `frontend/vitest.config.ts` |
| **Quick run command** | `docker compose exec web pytest apps/accounts/tests/ apps/organisations/tests/ -x -q` |
| **Full suite command** | `docker compose exec web pytest -x -q && docker compose exec vite npm run test -- --run` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose exec web pytest apps/accounts/tests/ apps/organisations/tests/ -x -q`
- **After every plan wave:** Run full suite (pytest + vitest)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | ACTV-01..05 | unit+integration | `pytest apps/accounts/tests/test_views.py -k invite -x -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | INVT-01,02 | unit | `pytest apps/organisations/tests/test_services.py -k resend -x -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | EMAL-01,02,03 | unit | `pytest apps/common/tests/ apps/accounts/tests/ -k email -x -q` | ✅ | ⬜ pending |
| 04-03-01 | 03 | 2 | INVT-01,02 | component | `npm run test -- --run ResendInvitationModal` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/accounts/tests/test_views.py` — stubs for invite_accept view (ACTV-01..05)
- [ ] `apps/organisations/tests/test_services.py` — stubs for resend_invitation service (INVT-01, INVT-02)
- [ ] `frontend/src/widgets/org-management/ResendInvitationModal.test.tsx` — component stub (INVT-01)

*Existing infrastructure (pytest-django, vitest, factories) covers all phase requirements — no new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Email renders in Gmail, Outlook, Apple Mail | EMAL-04 | Cannot automate cross-client rendering | Send test email to a Gmail account; inspect CSS inlining, 600px max-width, plain-text fallback |
| Password strength indicator shows visually | ACTV-02 | Alpine.js DOM interaction | Navigate to /invite/accept/<test-token>/, type a weak password, observe indicator |
| Post-activation redirect to org admin dashboard | ACTV-03 | Requires full browser session | Activate an account via test token, verify redirect URL |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
