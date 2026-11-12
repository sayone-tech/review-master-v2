# Milestones

## v0.9 AI Reply Credits (Shipped: 2026-11-12)

**Phases completed:** 5 phases (29–33), 23 plans, 45 tasks | PR #54 — 191 commits, 274 files changed, +41,395/−1,790
**Timeline:** 2026-11-11 → 2026-11-12
**Requirements:** 29/29 v1 delivered (CRED, CCON, CREN, CVIS-01..07, CSUP, SCOPE, CQA) plus off-milestone SHOP-22/23
**Closeout type:** override_closeout. Phases 29–33 were verified manually by the user; CI on PR #54 is green (`backend-test`, `backend-pg`, `frontend-test`, `lint-typecheck`).
**Known verification overrides:** 36 newly acknowledged, 0 carried forward from a prior close (see STATE.md Deferred Items). They are the 16 pending UAT scenarios and 5 "human needed" verifications for Phases 29–33, plus 12 debug sessions, UAT/verification gaps, a quick task and a deferred item from earlier milestones.
**Added during verification:** CVIS-06 (AI reply generated + credits-used Activity Log rows), CVIS-07 (Superadmins shown as "ReviewBee Admin"), Activity Log date filter now includes the whole end day, SHOP-22 (Google permission note), SHOP-23 ("N of M credits left").

**Key accomplishments:**
- Lazy per-shop monthly credit balance (`ensure_balance`) with full constraint-backed ledger schema, UTC period seam, and a `backend-pg` CI job that proves the first-use race on real PostgreSQL
- CreditTransaction is append-only in the app layer (QuerySet update/delete/bulk_update and instance delete raise), with a single RESERVED -> COMMITTED/REFUNDED status CAS (`ledger.transition_status`) proven single-winner on real Postgres, plus read-only admin and full DB-invariant tests
- One pure `credit_cost(text)` (0/1/2/3 from settings tiers, code-point length, open top tier) plus never-writing balance selectors (`get_shop_credit_balance`, one-query `annotate_credit_state` via FilteredRelation + Coalesce), closing Phase 29 with the CLAUDE.md section 3 update and the ORM audit
- Closed the two ORM bypasses of the append-only credit ledger: save() now force-inserts new instances (reused-pk rewrite) and QuerySet.bulk_create rejects update_conflicts upserts.
- Reserve (row-locked, guarded F()) -> OpenAI outside any transaction -> commit CAS that links the AiUsageLog row, with refund-in-finally and a single late-commit policy, wired into generate-reply with credits_charged / credits_remaining in the 200 body.
- Moderation blocks now say which stage blocked and which MODERATED AiUsageLog row they wrote, the reply chat call runs on a 30 s / 1-retry `with_options` copy, a timeout is a single traced transient error, and a settings test proves the whole request fits inside the 5-minute reservation TTL.
- Every generate outcome now settles exactly once in the service `finally` (output block and success consume; input block, OpenAI/unexpected failure and interruption refund) with the MODERATED or FAILED usage-log row linked, unpayable or empty requests stop at 400/402/409 with no writes, and a read-only `credit-cost` endpoint on its own throttle returns the price generate will charge.
- Real-PostgreSQL proof that concurrent AI-reply generation never overspends a shop's credits and that a client abort still settles, plus the CQA-02 rollout runbook and the Phase 30 auditor/gate record.
- Daily 00:05 UTC Celery Beat lapse sweep that writes one LAPSED ledger row plus a `shop.credits.lapsed` audit row per past-month balance with credits left, guarded by a `lapsed_at` marker, held-reservation skipping and pk-keyset paging; CREN-02 pinned by tests.
- Celery Beat every-10-minutes reaper that refunds RESERVED credit rows older than the 5-minute TTL through Phase 30's `refund_reservation` CAS (reason `reaped_stale`), then lapses the past-month balances it freed; ids-only logs and Sentry, bounded oldest-first batches, and operator docs for both Phase 31 schedules.
- Four real-PostgreSQL race tests show the reaper never double-refunds or refunds a committed reservation, overlapping sweeps write exactly one LAPSED row per balance, and a month-straddling reservation settles before its balance lapses; all local Phase 31 gates are green.
- Four real-PostgreSQL race tests prove concurrent bonuses, org edits, reservations and first uses stay lossless; they exposed a genuine deadlock (FOR UPDATE on the organisation row against a concurrent balance insert) that is fixed with FOR NO KEY UPDATE, and every local Phase 32 gate is green.
- Role-keyed Staff scoping on the Shops list and retrieve, with one-query virtual credit balances on every row and a credit-contact bootstrap for the Buy More modal.
- Buy More Credits modal that opens a CRLF-safe, fully URL-encoded Contact Admin mailto to platform support, plus the shared D-03 band helper, credit/UTC-date formatters and a shop-keyed balance store.
- Tenant- and Staff-scoped, never-writing, no-store GET /api/v1/shops/{id}/credits/ with a server-owned period label and renewal date, backed by a table-driven SCOPE-01 negative sweep over every credit route.
- ReplyComposer now fetches the server's credit cost, labels the AI button "Generate with AI · N credits", shows the shop's live remaining balance, explains every disabled state inline, and turns a 402 into an in-place state change that keeps the user's draft.
- Shops-page credit path end to end: a CREDITS badge opens Shop Details with a server-fresh AI Reply Credits card (all states), which stacks a sibling Buy More modal with correct Escape ordering, plus store seeding and a defensive Staff empty state.

Full archive: `.planning/milestones/v0.9-ROADMAP.md` · `.planning/milestones/v0.9-REQUIREMENTS.md` · spec `docs/completed/Requirements_Credits_System.md`

---

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
