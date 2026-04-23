# Roadmap: Multi-Tenant Review Management Platform

## Overview

This roadmap delivers the Superadmin module — the foundational control plane for the multi-tenant review management platform. Starting from a blank repo, it builds upward: project scaffolding and design system first, then authentication, then the full organisation management CRUD surface, then the invitation and account activation flow, and finally superadmin profile management with CI/CD hardening. Every phase delivers a coherent, independently verifiable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Project scaffolding, data models, design system shell, and Docker dev environment (completed 2026-04-22)
- [ ] **Phase 2: Authentication** - Superadmin login, logout, password reset, and session management
- [ ] **Phase 3: Organisation Management** - Full CRUD control plane: list, create, view, edit, enable/disable, delete, store allocation
- [ ] **Phase 4: Invitation and Activation** - Invitation token flow, Org Admin account activation page, and all transactional emails
- [ ] **Phase 5: Profile and Hardening** - Superadmin profile management, CI/CD pipeline, observability, and security hardening

## Phase Details

### Phase 1: Foundation
**Goal**: The project is runnable locally and has all data models, migrations, and design system primitives in place — ready for auth and feature work
**Depends on**: Nothing (first phase)
**Requirements**: DSYS-01, DSYS-02, DSYS-03, DSYS-04, DSYS-05, DSYS-06, DSYS-07, DSYS-08
**Success Criteria** (what must be TRUE):
  1. `docker-compose up` brings up a working Django dev environment (web, db, redis, mailhog) with no errors
  2. All data models (User with role enum, Organisation with soft-delete, InvitationToken) exist with migrations applied and are reversible
  3. The base layout shell (fixed left sidebar, top bar, main content area) renders correctly on desktop, tablet, and mobile with the correct brand colours
  4. The full reusable component set (buttons, form inputs, modals, toasts, data tables, badges, empty states, loading skeletons) is present and visually correct
  5. Keyboard navigation, visible focus states, ARIA labels, and WCAG AA contrast requirements are met across all base components
**Plans**: 5 plans
- [ ] 01-01-PLAN.md — Project scaffolding: pyproject.toml, config/ settings package, apps/common foundation, pre-commit + test infrastructure
- [ ] 01-02-PLAN.md — Data models: User (role enum), Organisation (soft-delete status), InvitationToken with reversible migrations
- [ ] 01-03-PLAN.md — Docker dev environment + Vite/Tailwind v4/TypeScript/Alpine.js frontend toolchain + Django base.html shell
- [ ] 01-04-PLAN.md — Sidebar + topbar partials (responsive 240px/64px/drawer) + reusable template components (buttons, fields, badges, toasts, empty state, skeletons, filter bar, pagination)
- [ ] 01-05-PLAN.md — React widgets (Modal, ConfirmModal, DataTable) + /__ui__/ showcase page + WCAG AA human-verify checkpoint

### Phase 2: Authentication
**Goal**: Superadmin can securely log in, log out, and recover their password — every authenticated page is behind this gate
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05
**Success Criteria** (what must be TRUE):
  1. Superadmin can log in with email and password at /login and is redirected to the organisations list
  2. Superadmin can log out from any page and their server-side session is immediately invalidated
  3. Superadmin can request a password reset email via "Forgot password?" and receive it within 60 seconds
  4. Superadmin can reset their password via the emailed link (which expires after 1 hour and becomes invalid after single use)
  5. Superadmin's authenticated session persists after a browser refresh without re-login
**Plans**: 3 plans
- [ ] 02-01-PLAN.md — Auth/session/throttle settings, LoginRateThrottle class, and failing test scaffold covering AUTH-01..AUTH-05
- [ ] 02-02-PLAN.md — auth_base + login templates, CustomAuthenticationForm/CustomLoginView with rate limit + remember-me, and URL rewiring (remove Phase-1 logout_stub)
- [ ] 02-03-PLAN.md — Password-reset views (custom confirm with flash), four reset-flow templates (including strength indicator), and email templates (HTML + text + subject)

### Phase 3: Organisation Management
**Goal**: Superadmin can fully manage the organisation roster — list, create, view, edit, enable, disable, delete, and adjust store allocations — with the invitation email sent automatically on create
**Depends on**: Phase 2
**Requirements**: ORGL-01, ORGL-02, ORGL-03, ORGL-04, ORGL-05, ORGL-06, ORGL-07, ORGL-08, CORG-01, CORG-02, CORG-03, CORG-04, VORG-01, VORG-02, VORG-03, EORG-01, EORG-02, EORG-03, ENBL-01, ENBL-02, DORG-01, DORG-02, STOR-01, STOR-02, STOR-03
**Success Criteria** (what must be TRUE):
  1. Superadmin lands on /admin/organisations after login and sees a paginated table of organisations with correct columns, search, status filter, and type filter all working
  2. Superadmin can create an organisation via a modal, receive a success toast confirming the invitation email was sent, and see the new row appear in the list immediately
  3. Superadmin can view full organisation details (including Org Admin activation status and last invitation timestamp) and edit all fields except email
  4. Superadmin can enable or disable an organisation via a confirmed popup and the status badge updates in the list without a page reload
  5. Superadmin can soft-delete an organisation (after typing its name to confirm) and adjust a store allocation with inline validation preventing values below current usage
**Plans**: TBD

### Phase 4: Invitation and Activation
**Goal**: Org Admin recipients can accept invitations and activate their accounts via a secure, time-limited token link — and Superadmins can resend invitations when needed
**Depends on**: Phase 3
**Requirements**: INVT-01, INVT-02, ACTV-01, ACTV-02, ACTV-03, ACTV-04, ACTV-05, EMAL-01, EMAL-02, EMAL-03, EMAL-04
**Success Criteria** (what must be TRUE):
  1. An invitation recipient clicking the link in the email lands on /invite/accept/<token>/ with the correct welcome message, pre-filled email, and a working activation form
  2. Completing the activation form creates the Org Admin user, marks the token as used, updates the organisation's activation status to Active, and logs the user in
  3. An invalid, expired, or already-used token shows the correct full-page error message instead of the form
  4. Superadmin can resend an invitation from the row actions menu or details modal — the previous token is invalidated and a new email arrives with the replacement notice
  5. All transactional emails (invitation, resend, password reset) render correctly in Gmail, Outlook, and Apple Mail with inlined CSS, max 600px width, and a plain-text fallback
**Plans**: TBD

### Phase 5: Profile and Hardening
**Goal**: Superadmin can manage their own profile, and the project is production-ready with CI/CD, observability, security headers, and 85%+ test coverage enforced
**Depends on**: Phase 4
**Requirements**: PROF-01, PROF-02
**Success Criteria** (what must be TRUE):
  1. Superadmin can update their full name from /admin/profile and see a success toast
  2. Superadmin can change their password (providing current password, new password with strength indicator, and confirmation) and see a success toast
  3. GitHub Actions CI pipeline runs pre-commit, mypy, pytest (85%+ coverage), migration check, and deploy check on every PR with no manual steps
  4. Every list endpoint has a CI-enforced query-count ceiling test that passes regardless of result size

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 5/5 | Complete   | 2026-04-22 |
| 2. Authentication | 1/3 | In Progress|  |
| 3. Organisation Management | 0/TBD | Not started | - |
| 4. Invitation and Activation | 0/TBD | Not started | - |
| 5. Profile and Hardening | 0/TBD | Not started | - |
