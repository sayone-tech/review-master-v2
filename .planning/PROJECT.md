# Multi-Tenant Review Management Platform

## What This Is

A multi-tenant SaaS platform for managing organisations, their stores, and Google Business Profile reviews. It supports three user roles — Superadmin, Organisation Admin, and Staff Admin — each with their own dashboard and permissions.

## Current State

**v0.3 shipped 2026-05-05** — Reviews and Action Items module complete. Org Admins and Staff can view, respond to, and action Google Business Profile reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.

**77/77 requirements delivered. 4 milestones shipped.**

### What's shipped (v0.3, Phases 10–13)

- Celery + Celery Beat + Channels infrastructure — `google-sync`, `ai-enrichment`, `default` queues; Flower (dev/staging only); Redis lock helper; retry/backoff utilities
- Google review fetching — initial backfill + 6-hour incremental sync; real-time progress UI via WebSocket (SyncProgressConsumer); TopbarBell indicator with stage awareness (fetching → enriching); reply submission to Google
- AI enrichment pipeline — GPT-4o-mini single-prompt JSON; AiUsageLog + time-versioned AiPricing; LangSmith tracing (best-effort); cost calculator locked at write time; idempotent 3-layer protection; skip for comment-less reviews
- Action Items module — AI promotion from reviews + manual creation; brand/shop scoping; STAFF never sees brand-scope items; status workflow (open → in_progress → resolved/dismissed); assignment with audit log; notes; ACTN-12 ≤5 query budget on list
- Notification bell — HTTP polling (60s interval); CustomEvent bridge for immediate post-sync refresh; unread count + popover; mark-read / mark-all-read; transaction.on_commit dispatch hooks
- Topbar sync indicator — WebSocket-connected per active shop; solid yellow spinner during sync; failure/success badge states; dismiss/clear UX

### What's shipped (v0.2-org-admin, Phases 6–9)

- Org Admin shell — 6-item sidebar, personalised dashboard (welcome card + zero-regions setup banner), profile page (name edit-in-place, password change)
- TenantScopedViewSet + IsOrgScoped — cross-tenant isolation enforced on every Org Admin viewset; CI fixture asserts 403 for cross-tenant access
- Data model foundation — Region, Shop, StaffAccessScope, SequenceCounter; Fernet-encrypted token storage; InvitationToken purpose enum
- Regions — list, create (race-safe auto-ID via django-sequences), edit, delete (blocked with shop count when occupied)
- Shops — list (allocation counter, search, status/region filters, pagination); create via Google OAuth popup (COOP/Safari/Redis-polling handled); Fernet-encrypted refresh tokens; view/edit/activate/deactivate; Reconnect Google
- Team — invite Manager (full-access) or Staff (region+store scoped); edit; enable/disable (immediate session termination); remove (invitations invalidated); resend; self-protection + last-manager API guards
- 6 transactional emails — invitation, resend (org), team invitation, team invitation resent, password reset, activation — all HTML + plain-text via Amazon SES

### What's in production (v1.0, Phases 1–5)

- Superadmin login, logout, forgot-password, session management
- Global design system — left sidebar, topbar, 10+ reusable components, WCAG AA, fully responsive
- Organisation list with search, filter by status/type, pagination
- Create, view, edit, enable, disable, delete organisations (soft-delete)
- Store allocation adjustment per organisation
- Invitation token flow — send on create, resend; atomic invalidate + re-issue
- Org Admin account activation page — token-gated, strength indicator, three token states
- Superadmin profile management — name edit-in-place, password change with strength indicator
- CI pipeline — pre-commit, mypy, pytest ≥85%, migration check, deploy check
- Production security headers — HSTS, CSP, X-Frame-Options, secure cookies, SSL redirect

## Requirements

### Validated

- ✓ Superadmin control plane (organisations, allocation, invitations) — v1.0
- ✓ Org Admin shell with tenant security scaffold — v0.2
- ✓ Regions CRUD with race-safe auto-ID and deletion guard — v0.2
- ✓ Shops with Google OAuth connection, allocation enforcement, Fernet-encrypted tokens — v0.2
- ✓ Team management — invite/edit/enable/disable/remove with self-protection and last-manager guard — v0.2
- ✓ Team invitation acceptance flow with role-based redirect — v0.2
- ✓ N+1-safe query ceilings on all list endpoints — v0.2
- ✓ Celery + Celery Beat + Channels infrastructure (queues, locking, retries, Flower) — v0.3
- ✓ Google review fetching (initial backfill + incremental), real-time WebSocket progress, reply to Google — v0.3
- ✓ AI enrichment pipeline (GPT-4o-mini, AiUsageLog, AiPricing, LangSmith, cost calculator) — v0.3
- ✓ Action Items — AI promotion, manual creation, brand/shop scoping, status workflow, assignment, notes — v0.3
- ✓ Notification bell — HTTP polling, CustomEvent bridge, unread count, mark-read lifecycle — v0.3
- ✓ Topbar sync indicator — WebSocket-per-shop, stage-aware spinner, failure/success states — v0.3

### Active

_(none — v0.4 requirements TBD via `/gsd:new-milestone`)_

### Out of Scope

| Feature | Reason |
| ------- | ------ |
| Staff Admin dashboard | Phase 3 — no review data exists yet |
| Google review fetching and response | Phase 4 |
| Shop hard-delete / freeing allocation slot | Deactivate + future scheduled purge |
| Email address change flow | Requires verification loop; deferred |
| Bulk region / shop actions | Not needed until tenant count grows |
| Region hierarchy beyond one level | Anti-feature for current scope |
| Two-factor authentication | Future security hardening |
| Billing and subscriptions | Phase 5+ |

## Constraints

- **Tech Stack**: Django 6.0+, Python 3.12+, DRF, PostgreSQL 16, Redis 7, Tailwind CSS, React (embedded widgets) — no deviations
- **Architecture**: Domain-driven app layout under `apps/`; services/selectors pattern; no business logic in views or serializers
- **Performance**: P95 API response < 400ms for list endpoints; page load < 2s
- **Security**: HTTPS everywhere, secure cookies, HSTS, CSRF, CSP; secrets in GCP Secret Manager
- **Query policy**: Strict no-N+1; CI must assert fixed query count ceiling on every list endpoint
- **Coverage**: Minimum 85% line coverage on services, selectors, and permissions; enforced in CI

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django templates + Tailwind for shell; React only for complex widgets | Reduces frontend complexity; server-rendered pages are simpler to secure and test | ✓ Confirmed — hybrid pattern used across all org admin pages |
| Amazon SES via django-ses | Standard for transactional email on GCP-hosted Django apps | ✓ Confirmed — 6 email types shipped |
| Django session auth (not JWT) | Token auth only needed if a separate client is added | ✓ Confirmed — session auth used throughout v1.0 and v0.2 |
| Soft-delete for organisations | Permanent purge deferred to a scheduled job | ✓ Confirmed — soft-delete pattern consistent across v1.0 and v0.2 |
| django-sequences for race-safe Region ID generation | select_for_update() fallback ready; smoke test passed Django 6 | ✓ Confirmed — django-sequences compatible; SequenceCounter model exists as fallback |
| GOOGLE_OAUTH-only shop connection (MANUAL removed in gap-closure) | Manual API key flow added complexity without production need | ✓ Confirmed — SHOP-10/19/20 retired; cleaner UX |
| TenantScopedViewSet in apps/common | Cross-cutting concern; used by both ORG_ADMIN and STAFF_ADMIN roles | ✓ Confirmed — enforced on all Org Admin viewsets |
| InvitationToken purpose enum expand-contract (3 steps) | Safe schema migration without downtime | ✓ Steps 1+2 complete (v0.2); step 3 (rename) deferred post-v0.2 |
| Cross-Origin-Opener-Policy scoped to OAuth view only | Global same-origin policy must not change | ✓ Confirmed — per-view header override on OAuth start view |
| StaffAccessScope in apps/accounts | Avoids circular imports with regions/shops apps | ✓ Confirmed |
| Django 6 built-in CSP middleware | Zero new dependencies vs third-party django-csp | ✓ Confirmed — unsafe-inline for Alpine.js + Tailwind; nonce migration deferred |
| Celery tasks are thin wrappers over service functions | Business logic must be testable without a worker | ✓ Confirmed — all Phase 10–13 tasks delegate to service functions |
| Channels surface kept narrow (SyncProgressConsumer only) | Auditable; prevents scope creep into real-time sync of action items / notifications | ✓ Confirmed — grep-verified; NotifBell uses HTTP polling per mandate |
| OpenAI call outside transaction.atomic() | Holding a row lock during a slow HTTP call is an anti-pattern | ✓ Confirmed — three-layer idempotency used instead (Redis lock + status flag + select_for_update) |
| Cost locked at AiUsageLog write time; historical costs never retroactively changed | Predictable billing; AiPricing is time-versioned append-only | ✓ Confirmed — calculate_cost reads active pricing row at call time |
| LangSmith is best-effort (unreachable → OpenAI call still proceeds) | Tracing infra must not block revenue-generating API calls | ✓ Confirmed — LangSmith failures logged at WARNING only |
| sync.complete emitted by enrichment.py (not sync.py), gated by enriched >= fetched | Enrichment service is the final stage; premature complete would truncate action-item promotion | ✓ Confirmed — Phase 12 move; sync.py no longer emits complete |
| transaction.on_commit for all notification dispatch hooks | Signals fire pre-commit — phantom notification rows on rollback | ✓ Confirmed — all dispatch sites use on_commit |
| NotifBell ↔ TopbarBell bridge via CustomEvent (notifications:refresh) | Two separate React roots; no shared store | ✓ Confirmed — TopbarBell dispatches on sync.complete; useNotifications listens and fetches immediately |
| CursorPagination for Reviews list | Reviews table grows large with incremental sync; cursor provides O(1) performance | ✓ Confirmed — PageNumberPagination would degrade on large datasets |
| Partial unique constraint on (source_review, title, scope) WHERE source=AI | Enables idempotent AI promotion via bulk_create(ignore_conflicts=True) | ✓ Confirmed — safe for concurrent enrichment retries |

## Context

- Requirements archives: `.planning/milestones/v1.0-REQUIREMENTS.md`, `.planning/milestones/v0.2-org-admin-REQUIREMENTS.md`
- Three-role RBAC: SUPERADMIN, ORG_ADMIN, STAFF_ADMIN
- Brand: Primary Yellow #FACC15, Primary Black #0A0A0A — clean SaaS aesthetic
- All email via Amazon SES (`django-ses`); local dev uses MailHog
- GBP API production approval from Google is a non-code prerequisite for Shops to go live in production
- Tech debt carried forward: CSP nonce migration deferred; premailer CSS inlining deferred; InvitationToken rename (step 3 of expand-contract) deferred

---

<details>
<summary>v0.2-org-admin milestone (archived)</summary>

**Shipped:** 2026-04-30
**Phases:** 4 (6–9) | **Plans:** 17 | **Requirements:** 57/57
**Files:** 248 changed | **Insertions:** 34,438 | **Timeline:** 3 days

Org Admins can manage their Regions, Shops, and Team from a dedicated dashboard. Google OAuth popup flow with COOP/Safari/Redis-polling fallback. Fernet-encrypted tokens. Full team invite/manage lifecycle with self-protection and last-manager guards.

Full archive: `.planning/milestones/v0.2-org-admin-ROADMAP.md`

</details>

<details>
<summary>v1.0 milestone (archived)</summary>

**Shipped:** 2026-04-27
**Phases:** 5 (1–5) | **Plans:** 24 | **Requirements:** 52/52
**Commits:** 146 | **Files:** 271 | **LOC:** ~50,000

Superadmins can provision and manage organisations, allocate store slots, and control Org Admin access — the foundational control plane every subsequent phase depends on.

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

---
Last updated: 2026-05-05 after v0.3-reviews-and-action-items milestone shipped
