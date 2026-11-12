# Requirements: v0.9 AI Reply Credits

**Defined:** 2026-11-11
**Core Value:** Org Admins and Staff can view, respond to, and action Google reviews — and AI reply spend is capped by a visible per-shop monthly credit budget that Superadmin controls.
**Source spec:** `docs/in-progress/Requirements_Credits_System.md` (v1.0, Nov 2026), reconciled against the live codebase in `.planning/research/SUMMARY.md`.

**Spec reconciliations (binding):** "Manager" = Org Admin · `review.text` → `Review.comment` (trimmed) · spec's `replies.py` → `apps/reviews/services/reply_generation.py` · UUID PKs → BigAutoField · generate-reply throttle stays 10/min (not 30) · no click-confirmation step (§5.4 dropped) — cost on the button label · §9.3 shop-switcher badge + AC 33 struck (no switcher exists) · bonus UI lives on the Superadmin org row with a shop picker (Superadmin has no Shop Details screen) · §7.3 refined by CRED-06.

## v1 Requirements

### Foundation & Ledger (CRED)

- [x] **CRED-01**: Superadmin can set an organisation's monthly credits per shop (integer 0–10,000, default 0) on Create and Edit Organisation; the value persists (whitelisted in `update_organisation`) and every change writes an `organisation.credits.set` AuditLog row
- [ ] **CRED-02**: Each shop has one credit balance per UTC calendar month (allocated / bonus / consumed), created lazily on first use; the DB enforces uniqueness on `(shop, year, month)` and `0 <= consumed <= allocated + bonus`
- [x] **CRED-03**: Every credit event is recorded in an append-only ledger (`INITIAL_ALLOCATION | BONUS_ALLOCATION | CONSUMPTION | LAPSED`, status `RESERVED | COMMITTED | REFUNDED`); no update/delete path exists and status is the only permitted mutation, via named service functions; Django admin is read-only
- [ ] **CRED-04**: Credit cost is 1 / 2 / 3 for trimmed comment length 1–100 / 101–500 / 501+, computed by one pure function with thresholds in settings and an open-ended top tier; unit tests cover 0, 1, 100, 101, 500, 501, 10000, 10001, emoji, and whitespace-only
- [ ] **CRED-05**: Reading a balance never creates a row; a shop with no row for the current month reports its full organisation allocation (not 0)
- [x] **CRED-06**: Changing an organisation's allocation from 0 → N takes effect immediately for the current month; any other change (N → M) takes effect from the next month, and current-month balances keep the previous value

### Consumption (CCON)

- [x] **CCON-01**: Org Admin, or Staff for shops in their scope, generating an AI reply is charged the review's credit cost via reserve (short row-locked transaction) → OpenAI call outside any transaction → commit
- [x] **CCON-02**: Concurrent generate requests on the same shop can never spend beyond the shop's remaining credits (proven by a Postgres concurrency test)
- [x] **CCON-03**: When remaining credits are below the cost, generate returns 402 with `reason` (`not_enabled` | `exhausted`), `required`, and `remaining`, and no reservation is created
- [x] **CCON-04**: Generate returns 400 for a review whose comment is empty or whitespace-only, before any reservation
- [x] **CCON-05**: Credits are refunded when the OpenAI call fails or input moderation blocks the review, and consumed when output moderation blocks the draft; each outcome writes a `shop.credits.consumed` or `shop.credits.refunded` AuditLog row
- [x] **CCON-06**: Each consumption ledger row links to the single AiUsageLog row of its OpenAI call; a generate request still writes exactly one AiUsageLog row
- [x] **CCON-07**: The generate response includes `credits_charged` and `credits_remaining`, and a cost endpoint returns the credit cost for a given review
- [x] **CCON-08**: The reply-path OpenAI call uses an explicit timeout well below the reservation TTL; the existing 10/min generate-reply throttle is unchanged

### Renewal & Reaper (CREN)

- [x] **CREN-01**: A Celery Beat job at 00:05 UTC on the 1st lapses unused credits for every past-month balance not yet lapsed — idempotent on re-run and self-healing after a missed run — writing a LAPSED ledger row and a `shop.credits.lapsed` AuditLog row per shop
- [x] **CREN-02**: Each new month every shop starts from the organisation's monthly allocation; bonus credits never carry over
- [x] **CREN-03**: A Celery Beat job every 10 minutes refunds RESERVED transactions older than the reservation TTL, and can never double-refund or refund an already-committed transaction

### Visibility (CVIS)

- [x] **CVIS-01**: Shop Details shows an "AI Reply Credits" card: remaining / total, colour-coded progress bar, used and available counts, org allocation and bonus, "Renews {date} (UTC)", a "Not enabled" state when total is 0, and a Buy More Credits link
- [x] **CVIS-02**: Each Shops list row shows a colour-coded credits badge, with a fixed query count regardless of the number of shops
- [x] **CVIS-03**: In the reply composer the AI button is hidden for star-only reviews, its label and aria-label show the cost ("Generate with AI (requires N credits)"), the credit status sits under the button, remaining credits are shown, the button is disabled with distinct "not enabled" vs "not enough credits" messaging, tone pills are disabled while generating, and a 402 response is handled
- [x] **CVIS-04**: A "Buy More Credits" modal opens from the credits card, Shops-list badge, and composer; it shows a Contact Admin mailto to `REVIEWBEE_SUPPORT_EMAIL`, is accessible (focus trap, ARIA labels, ESC/backdrop close), and has no payment flow
- [x] **CVIS-05**: Org Admin sees `shop.credits.*` and `organisation.credits.set` events in the Activity Log; Staff do not
- [ ] **CVIS-06**: Every successful AI reply generation writes an `ai_reply_generated` AuditLog row on the review (`after_data`: tone only; no credit numbers, no AI usage log id), shown in the Activity Log as "AI reply generated (Professional)" under the Replies type. Org Admin and Staff (for reviews in their shops) see it; Staff never see credit numbers (CVIS-05 holds). For Org Admin the `shop.credits.consumed` / `refunded` / `late_commit` rows show the credit count and review ("Credits used: 2 — {shop} · Review #{id}"), the Type filter offers "Credits" (Org Admin only), and the shop filter keeps that shop's credit rows

### Superadmin Controls (CSUP)

- [x] **CSUP-01**: Superadmin can open a credits action on any organisation row, see that org's shops with current balances, select a shop, and allocate bonus credits for the current month (1–10,000, optional reason) with a before/after preview; each allocation writes a BONUS_ALLOCATION ledger row and a `shop.credits.bonus_allocated` AuditLog row
- [x] **CSUP-02**: Superadmin credit endpoints return 403 to non-Superadmins; Org Admin and Staff cannot change the allocation or allocate bonus credits

### Staff Scoping (SCOPE)

- [x] **SCOPE-01**: The Shops list and every credit endpoint return only shops within a Staff user's StaffAccessScope; negative tests cover cross-org access, out-of-scope Staff, and Staff calling Superadmin endpoints

### Quality & Rollout (CQA)

- [ ] **CQA-01**: A Postgres CI job runs `pg_concurrency`-marked tests covering the first-use race, N threads vs K credits, and reaper vs late commit
- [x] **CQA-02**: Existing Phase 19/20 generate-reply tests and factories are updated for credits, and a deploy note documents that organisations start at 0 credits until Superadmin sets an allocation (production org enabled via CRED-06)

## Off-Milestone Requirements

Small changes outside the v0.9 credits scope, captured here so nothing ships untraced (CLAUDE.md §24).

### Shop Connection (SHOP)

- [ ] **SHOP-22**: The Google connect button (Create Shop → Connect step, and the Reconnect Google modal) shows a permission note directly above it, before Google's consent screen. The note explains that Google only offers the one broad "manage your Business Profile" permission, and lists the app's actual use: read reviews and the location list; post, edit or delete replies only when the user chooses to. It states that the app never changes business details, hours, photos or ownership. It must not claim the app never deletes anything, because users can delete their own replies (`apps/reviews/services/replies.py`). No "Learn more" link until a help page exists.
- [ ] **SHOP-23**: When the reply composer shows no credit warning (ready state), the line under the Generate with AI button shows remaining of total, e.g. "18 of 20 credits left this month", so users see the shop's monthly budget. `GET /api/v1/reviews/{id}/credit-cost/` gains an additive `total` field (allocated + bonus for the current month, read from the same virtual balance, no extra query, same Staff scoping). If `total` is missing the composer falls back to "This shop has N credits remaining this month."

## Future Requirements

Deferred — tracked but not in the v0.9 roadmap.

- **CFUT-01**: Credit transaction history UI and endpoint for Org Admin
- **CFUT-02**: Superadmin credit usage report per organisation per month
- **CFUT-03**: Shop-switcher credit badge (spec §9.3 / AC 33) — once a global shop switcher exists
- **CFUT-04**: Real payment flow replacing the Buy More placeholder
- **RESET-01..03**: Superadmin data reset + re-sync (carried from v0.8 Phase 28 — deferred pre-launch)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Credit rollover across months | Spec §1.2 — unused credits lapse |
| Per-user credit allocation | Credits are per-shop |
| Credit transfer between shops | Spec §1.2 |
| Email / push credit alerts | In-app visibility only |
| Credits for other AI features (enrichment, summaries) | Scope is reply generation only |
| Per-organisation cost formulas | One formula for all |
| Click-confirmation before generating | User decision — cost shown on button label instead |
| WebSocket balance updates | CLAUDE.md §13.2 — Channels surface stays narrow |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRED-01 | Phase 32 | Complete |
| CRED-02 | Phase 29 | Gaps Found |
| CRED-03 | Phase 29 | Complete |
| CRED-04 | Phase 29 | Gaps Found |
| CRED-05 | Phase 29 | Gaps Found |
| CRED-06 | Phase 32 | Complete |
| CCON-01 | Phase 30 | Complete |
| CCON-02 | Phase 30 | Complete |
| CCON-03 | Phase 30 | Complete |
| CCON-04 | Phase 30 | Complete |
| CCON-05 | Phase 30 | Complete |
| CCON-06 | Phase 30 | Complete |
| CCON-07 | Phase 30 | Complete |
| CCON-08 | Phase 30 | Complete |
| CREN-01 | Phase 31 | Complete |
| CREN-02 | Phase 31 | Complete |
| CREN-03 | Phase 31 | Complete |
| CVIS-01 | Phase 33 | Complete |
| CVIS-02 | Phase 33 | Complete |
| CVIS-03 | Phase 33 | Complete |
| CVIS-04 | Phase 33 | Complete |
| CVIS-05 | Phase 33 | Complete |
| CVIS-06 | Phase 33 (gap, 2026-11-12) | Pending |
| CSUP-01 | Phase 32 | Complete |
| CSUP-02 | Phase 32 | Complete |
| SCOPE-01 | Phase 33 | Complete |
| CQA-01 | Phase 29 | Gaps Found |
| CQA-02 | Phase 30 | Complete |
| SHOP-22 | Off-milestone (quick change) | Pending |
| SHOP-23 | Off-milestone (quick change) | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28 ✓
- Unmapped: 0
- Per phase: Phase 29 → 5 · Phase 30 → 9 · Phase 31 → 3 · Phase 32 → 4 · Phase 33 → 7
- Off-milestone: 2 (SHOP-22, SHOP-23, not counted in the v1 total)
- Note: CQA-01 is delivered in Phase 29 (Postgres CI job + `pg_concurrency` marker + first-use race test); the N-threads-vs-K-credits test (CCON-02, Phase 30) and the reaper-vs-late-commit test (CREN-03, Phase 31) are added to the same job.

---
*Requirements defined: 2026-11-11*
*Last updated: 2026-11-11 after v0.9 roadmap creation (traceability filled, Phases 29–33)*
