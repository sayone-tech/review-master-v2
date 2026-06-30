# Milestones

## v0.8 Canonical Tag System (Shipped: 2026-06-30)

**Phases completed:** 6 phases (22–27), 20 plans | merged via PR #38 — 187 files changed, +31,150/−659
**Timeline:** 2026-06-10 → 2026-06-30
**Requirements:** 29/29 delivered (RESET-01..03 deferred pre-launch)
**Phase 28 (Superadmin Data Reset):** deferred — no production deployment yet; carried forward, not cancelled.

**Key accomplishments:**

- Self-organising per-org canonical tag vocabulary built inside the *existing* single GPT enrichment call — no extra API call, no vector DB; `ReviewTag.canonical_tag` FK with label held FK-only (O(1) rename); exactly one `AiUsageLog` row per review.
- Visible four-step initial sync (Fetch → Build Tag Vocabulary → AI Enrichment → Finalising) with a sequential 50-review vocabulary seed, via the single `SyncProgressConsumer` (no new consumer); split `ai-enrichment-high`/`-low` + `tag-merge` Celery queues.
- Self-maintaining polarity — GPT-assigned at creation; weekly DB-only Beat job flips `always_*` → `mixed` past the 15% / 30-day threshold, each flip audited.
- Org Admin tag curation — sortable/query-bounded Tags page with inline rename and per-org-locked merge (HTTP-polled `TagMergeJob` progress + rollback); dashboard polarity split for `mixed` tags.
- Trustworthy sync progress — snapshot-poll fallback + org-scoped GET endpoint so the modal self-heals on missed WebSocket events; finalise completion-gating so Finalising fires when bulk enrichment actually completes and is visible.

Full archive: `.planning/milestones/v0.8-ROADMAP.md` · `.planning/milestones/v0.8-REQUIREMENTS.md`

---

## v0.3 Reviews and Action Items (Shipped: 2026-05-05)

**Phases completed:** 13 phases, 78 plans, 42 tasks

**Key accomplishments:**

- (none recorded)

---

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
