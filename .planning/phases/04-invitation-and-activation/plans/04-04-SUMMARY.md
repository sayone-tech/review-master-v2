---
plan: 04-04
slug: resend-invitation-backend
status: complete
completed: 2026-04-23
---

# Plan 04-04 — Resend Invitation Backend — SUMMARY

## Commits

| Hash | Description |
|------|-------------|
| 794ce48 | test(accounts): RED stubs for resend_invitation service (task 1) |
| 4897403 | feat(organisations): resend_invitation @action + endpoint tests (INVT-01,02) |

## Deliverables

**Task 1 — resend_invitation service:**
- `apps/organisations/services/organisations.py` — `resend_invitation()` with `@transaction.atomic`, invalidates old tokens (`update(is_used=True)` — preserves audit trail), creates fresh token, sends email with `is_resend=True`, returns raw token. Accepts `resent_by` arg for future audit-log integration.

**Task 2 — DRF @action endpoint:**
- `apps/organisations/views.py` — `resend_invitation` `@action(detail=True, methods=["post"])` on `OrganisationViewSet`; Superadmin-only (`IsSuperadmin` guard), returns `{"detail": "Invitation resent."}`, URL: `/api/v1/organisations/<id>/resend-invitation/`

## Tests

| Scope | Count |
|-------|-------|
| resend_invitation service (test_services.py) | 8 |
| resend-invitation endpoint (test_views.py) | 8 |
| **Total new** | **16** |

All 149 tests pass (accounts + organisations suites).

## Requirements Covered

INVT-01 (new token created, old invalidated), INVT-02 (Superadmin-only endpoint, 403 for Org Admin)
