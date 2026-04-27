# Multi-Tenant Review Management Platform

## What This Is

A multi-tenant SaaS platform for managing organisations, their stores, and Google Business Profile reviews. It supports three user roles — Superadmin, Organisation Admin, and Staff Admin — each with their own dashboard and permissions.

## Current State

**v1.0 shipped 2026-04-27** — Superadmin module complete.
**Phase 6 complete 2026-04-27** — Org Admin shell, tenant security scaffold, and full v0.2 data model foundation.

The foundational control plane is live and the Org Admin shell is now functional: Org Admins can log in, navigate the 6-item sidebar, see a personalised dashboard with zero-regions setup guidance, and manage their profile. The multi-tenant security scaffold (`IsOrgAdmin`, `IsOrgScoped`, `TenantScopedViewSet`) protects all future Phase 7-9 endpoints from cross-tenant leakage.

### What's in production (v1.0)

- Superadmin login, logout, forgot-password, session management
- Global design system — left sidebar, topbar, 10+ reusable components, WCAG AA, fully responsive
- Organisation list with search, filter by status/type, pagination
- Create, view, edit, enable, disable, delete organisations (soft-delete)
- Store allocation adjustment per organisation
- Invitation token flow — send on create, resend; atomic invalidate + re-issue
- Org Admin account activation page — token-gated, strength indicator, three token states
- Superadmin profile management — name edit-in-place, password change with strength indicator
- 4 transactional emails (invitation, resend, password reset, activation) via Amazon SES
- CI pipeline — pre-commit, mypy, pytest ≥85%, migration check, deploy check
- Production security headers — HSTS, CSP, X-Frame-Options, secure cookies, SSL redirect

## Current Milestone: v0.2-org-admin — Organisation Admin Module

**Goal:** Organisation Admins can manage their Shops, Regions, and Team from a dedicated dashboard — the operational layer built on top of the Superadmin control plane.

**Target features:**
- Org Admin shell — sidebar (Dashboard, Shops, Regions, Team, Profile, Logout), dashboard placeholder with welcome + setup banner, profile page reuse
- Regions module — list, create (with auto-ID generation), edit, delete (blocked when shops assigned)
- Shops module — list (allocation counter, search/filter/pagination), create via OAuth or manual Place ID, view/edit, activate/deactivate, API key management, Google reconnect
- Team module — invite (Manager full-access / Staff scoped by region+store), edit, enable/disable, remove, resend invitation; self-protection + last-manager rules
- Team invitation email and acceptance flow (reusing Phase 1 token infrastructure)
- Data model additions: Region, Shop, StaffAccessScope; User updates (invited_by_id, invited_at, accepted_at); OrganisationInvitation → UserInvitation with purpose enum

**Source:** `docs/Requirements_Phase2_OrgAdmin.docx` (v1.0, April 2026)

Likely candidates:
- Organisation Admin dashboard and store management (Phase 2 in original scope)
- Staff Admin role and dashboard
- Google Business Profile OAuth connection per store

## Constraints

- **Tech Stack**: Django 6.0+, Python 3.12+, DRF, PostgreSQL 16, Redis 7, Tailwind CSS, React (embedded widgets) — no deviations
- **Architecture**: Domain-driven app layout under `apps/`; services/selectors pattern; no business logic in views or serializers
- **Performance**: P95 API response < 400ms for list endpoints at 1,000 organisations; page load < 2s
- **Security**: HTTPS everywhere, secure cookies, HSTS, CSRF, CSP; secrets in GCP Secret Manager
- **Query policy**: Strict no-N+1; CI must assert fixed query count ceiling on every list endpoint
- **Coverage**: Minimum 85% line coverage on services, selectors, and permissions; enforced in CI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django templates + Tailwind for shell; React only for complex widgets | Reduces frontend complexity; server-rendered pages are simpler to secure and test | Confirmed — OrgManagement and Profile widgets use this hybrid pattern |
| Amazon SES via django-ses | Standard for transactional email on GCP-hosted Django apps | Confirmed — send_transactional_email helper wired in Phase 03 |
| Django session auth (not JWT) for Phase 1 | Token auth only needed if a separate client is added | Confirmed — session auth used throughout v1.0 |
| Soft-delete for organisations | Permanent purge deferred to a scheduled job in a future phase | Confirmed — delete_organisation() soft-deletes; no hard-delete in v1.0 |
| Invitation tokens via TimestampSigner | Built-in to Django; no extra dependencies; 48-hour expiry and single-use enforced | Confirmed — full activation flow shipped in Phase 04 |
| Django 6 built-in CSP middleware | Zero new dependencies vs third-party django-csp | Confirmed — CSP uses unsafe-inline for Alpine.js + Tailwind; nonce migration deferred |

## Context

- Requirements archive: `.planning/milestones/v1.0-REQUIREMENTS.md`
- Three-role RBAC: SUPERADMIN, ORG_ADMIN, STAFF_ADMIN
- Brand: Primary Yellow #FACC15, Primary Black #0A0A0A — clean SaaS aesthetic
- All email via Amazon SES (`django-ses`); local dev uses MailHog
- Tech debt accepted at v1.0: 20 non-critical items (browser UAT deferred, premailer CSS inlining deferred, ORG_ADMIN /admin/organisations/ UX gap)

---

<details>
<summary>v1.0 milestone (archived)</summary>

**Shipped:** 2026-04-27
**Phases:** 5 | **Plans:** 24 | **Requirements:** 52/52
**Commits:** 146 | **Files:** 271 | **LOC:** ~50,000

Core value: Superadmins can provision and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

---
*Last updated: 2026-04-27 — Phase 6 complete*
