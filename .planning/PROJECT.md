# Multi-Tenant Review Management Platform

## What This Is

A multi-tenant SaaS platform for managing organisations, their stores, and Google Business Profile reviews. It supports three user roles — Superadmin, Organisation Admin, and Staff Admin — each with their own dashboard and permissions. Phase 1 delivers the Superadmin module and its supporting invitation flow.

## Core Value

Superadmins can create and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.

## Requirements

### Validated

- [x] Global design system, left sidebar layout, and responsive behaviour — Validated in Phase 01: Foundation
- [x] Superadmin authentication (login, logout, forgot password) — Validated in Phase 02: Authentication
- [x] Organisations list with search, filter by status/type, and pagination — Validated in Phase 03: Organisation Management
- [x] Create, view, edit, enable, disable, and delete organisations — Validated in Phase 03: Organisation Management
- [x] Adjust store allocation per organisation — Validated in Phase 03: Organisation Management

### Active

- [ ] Organisation Admin invitation email flow (send on create, resend)
- [ ] Organisation Admin account activation page (token-gated)
- [ ] Superadmin profile management (name update, password change)

### Out of Scope

- Organisation Admin dashboard and store management — Phase 2
- Staff Admin role and dashboard — Phase 3
- Google Business Profile OAuth connection — Phase 2+
- Review fetching, storage, and analytics — Phase 4
- Billing and subscription — Phase 5
- Notifications module beyond basic email — future

## Context

- Requirements document: `docs/Requirements_Phase1_Superadmin.docx` (v1.0, April 2026)
- Three-role RBAC: SUPERADMIN, ORG_ADMIN, STAFF_ADMIN
- Stack is fully defined: Django 6 + DRF + Django templates + Tailwind CSS + React (for complex interactive components) + PostgreSQL + Redis + Amazon SES
- Brand: Primary Yellow #FACC15, Primary Black #0A0A0A — clean SaaS aesthetic (Linear/Stripe/Vercel style)
- All email via Amazon SES using `django-ses`; local dev uses MailHog
- Invitation tokens via Django's `TimestampSigner`, 48-hour expiry, single-use

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
| Django templates + Tailwind for shell; React only for complex widgets | Reduces frontend complexity; server-rendered pages are simpler to secure and test | Confirmed — Phase 03 OrgManagement widget uses this hybrid pattern |
| Amazon SES via django-ses | Standard for transactional email on GCP-hosted Django apps | Confirmed — send_transactional_email helper wired in Phase 03 |
| Django session auth (not JWT) for Phase 1 | Token auth only needed if a separate client is added | Confirmed — session auth used throughout Phases 1–3 |
| Soft-delete for organisations in Phase 1 | Permanent purge deferred to a scheduled job in a future phase | Confirmed — soft_delete() implemented in Phase 03 |
| Invitation tokens via TimestampSigner | Built-in to Django; no extra dependencies; 48-hour expiry and single-use enforced | Confirmed — InvitationToken model created in Phase 03; full activation flow in Phase 04 |

---
*Last updated: 2026-04-23 — Phase 03 (Organisation Management) complete*
