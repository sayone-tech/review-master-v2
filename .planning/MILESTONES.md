# Milestones

## v0.2-org-admin Org Admin Module (Shipped: 2026-04-30)

**Phases completed:** 4 phases (6–9), 17 plans | 248 files changed, 34,438 insertions
**Timeline:** 2026-04-27 → 2026-04-30 (3 days)
**Requirements:** 57/57 (3 retired — SHOP-10/19/20 scope-reduced)
**Tests:** 438 passing

**Key accomplishments:**

- Org Admin shell — 6-item sidebar, personalised welcome dashboard, profile reuse; TenantScopedViewSet + IsOrgScoped security base enforced on all subsequent viewsets; full v0.2 data model migrations (Region, Shop, StaffAccessScope, InvitationToken purpose enum)
- Regions module — full Django backend + React widget; race-safe auto-ID generation (django-sequences); deletion blocked when shops assigned; all 11 RGN requirements verified
- Shops module — Google OAuth popup flow with COOP/Safari/Redis-polling fallback; Fernet-encrypted refresh tokens; allocation enforcement with select_for_update(); searchable Google listing picker; GOOGLE_OAUTH-only connection (MANUAL removed after gap-closure)
- Team module — invite Manager (full-access) and Staff (region+store scoped) members; enable/disable with immediate session termination; remove with invitation invalidation; self-protection + last-manager API guards; 5 production email templates (invitation + resend, HTML + plain-text)
- Team invitation acceptance — token-gated (`/invite/accept/{token}/`), purpose-branched activation, auto-login, role-appropriate redirect (Manager → /admin/org/dashboard, Staff → welcome page)
- Cross-module integrity — deactivated shops excluded from Staff scope selectors (XMOD-03); shop allocation counter transactional under concurrent sessions; N+1-safe query ceilings on all 4 list endpoints

---
