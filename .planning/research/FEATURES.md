# Feature Research

**Domain:** Per-shop monthly usage-credit / quota system for a single AI feature (reply drafting) in a multi-tenant B2B SaaS
**Milestone:** v0.9 AI Reply Credits (subsequent milestone; only NEW features covered)
**Researched:** 2026-11-11
**Confidence:** MEDIUM overall. Industry-convention findings are from vendor blogs and developer write-ups (conventions, not standards). Dependency and gap findings are HIGH because they were verified against the live code (`ReplyComposer.tsx`, `reply_generation.py`, `reviews/views.py`) and the binding spec.

## How credit/quota systems for AI features typically behave

Consistent patterns across the sources (schematic, stigg, solvimon, flexprice, Lovable docs, and similar):

- **Append-only ledger plus a balance row.** Every event (allocation, bonus, consumption, expiry, refund) is an immutable entry; the balance is derived or cached. The spec's `CreditTransaction` and `ShopCreditBalance` match this shape.
- **Reserve, commit or release.** Hold credits before the expensive side effect, commit on success, release on failure. The conditional write (`WHERE remaining >= n`) or `SELECT FOR UPDATE` guards concurrency. The spec's two-phase pattern is the accepted approach.
- **Cost before the click, balance always visible.** The consistent UX guidance is to show per-action cost on the trigger, keep the balance visible, and never let a generic "low on credits" message stand in for numbers. User complaints (the Figma forum, for example) centre on unclear per-action cost and unclear remaining balance.
- **Empty state is an actionable state.** At zero balance the feature stays discoverable but disabled, with an explanation and a next step (upgrade or top-up). Here the next step is the "Buy More Credits" contact placeholder.
- **Low-balance warning around 80% consumed.** This is convention, not a benchmark. The spec's colour bands (amber from 75%, red above 95%) are in line with it.
- **Failures are never billed.** Provider errors release the hold. Charging on user discard or edit is normal ("the call was billed"). The spec and the locked decisions follow this.
- **Expiry or lapse with a visible reset date.** Use-it-or-lose-it monthly allocations are common when the user is told up front. The spec covers this with the "Renews on" line and the lapse messaging.
- **Admin grants are ledgered, with a reason.** Bonus or top-up entries carry actor and reason. Matches the spec.

## Feature Landscape

### Table Stakes (users expect these)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `Organisation.monthly_credit_allocation` on Create/Edit Org (0-10,000, next-month effect) | Superadmin must be able to set the budget | LOW | Extends existing org create/edit serializer, service and form. Write `organisation.credits.set` AuditLog with before/after. Show the current value on org detail as well (spec only mentions the forms). |
| `ShopCreditBalance` (lazy per UTC month) + `CreditTransaction` ledger | Core ledger and balance | MEDIUM | New `apps/credits`. `UNIQUE(shop, year, month)` and `get_or_create` race-safe. The read path must NOT create rows (see Gap 2). |
| Tiered cost function (1/2/3) in one pure function, thresholds in settings | Predictable pricing; displayed cost must equal charged cost | LOW | Spec §4.3 and §13.1 conflict on location. PROJECT.md decision is `apps/credits/services/credit_cost.py`. Count `len(comment.strip())` (Gap 5). |
| Reserve, OpenAI outside txn, commit or refund | Prevents over-spend under concurrency and never bills for failures | HIGH | Highest-risk item. Wraps the existing `generate_reply_draft`. Needs guarded status transitions (Gap 9) and the moderation-stage distinction (Gap 8). |
| 402 on insufficient credits, 400 on empty-comment review | Server-side enforcement; the UI is advisory only | LOW | Throttle and serializer validation must run BEFORE the reserve (DRF throttling already runs first). Return a machine-readable body (`code`, `required`, `remaining`). |
| AI button hidden for star-only reviews | A useless action is not offered | LOW | `ReplyComposer.tsx` has a single "Generate with AI" toggle button. Drive visibility from a server-computed field. |
| Cost on the button label | Cost before the click (locked: replaces the §5.4 confirmation) | LOW | See Gap 4: the existing UI is a two-step flow (toggle, then tone pills). |
| "X credits remaining" in the composer | Balance always visible | LOW | Fetch once per shop per composer-open and update from the generate response. |
| Insufficient and zero states: disabled button, explanation, "Buy More Credits" | Actionable empty state | LOW | See Gap 1 for the distinct copy needed for "not enabled" versus "used up". |
| Shop Details "AI Reply Credits" card (remaining/total, bar, used, renews-on) | Balance visible to all roles with shop access | MEDIUM | New card in `ShopDetailsModal.tsx`. The bar must not be colour-only (add text). Handle total = 0. |
| Shops-list credit badge (colour-coded) | At-a-glance health across shops | MEDIUM | Needs an annotated `remaining_credits` in the list selector (single subquery, no N+1) with a virtual fallback to org allocation when no row exists. A new query-count test is mandatory. |
| "Buy More Credits" placeholder modal (mailto `REVIEWBEE_SUPPORT_EMAIL`) | Dead-end avoidance; the future payment hook | LOW | Reusable component with focus trap, ESC and backdrop dismissal. Mounted from the card, the badge and the composer. |
| Superadmin "Allocate Bonus Credits" modal (current month only) | The only lever to grant credits mid-month | MEDIUM | Must lazily create the row if absent. Show a before/after preview (see Differentiators). Superadmin-only at the API and UI. |
| Monthly lapse task (00:05 UTC on the 1st, idempotent) | The "unused credits lapse" promise | MEDIUM | `default` queue, thin task. Idempotency key is "no existing LAPSED transaction for that balance". |
| Stale-RESERVED reaper (10 min cadence, 5 min TTL) | Crash safety for the two-phase pattern | MEDIUM | Guarded `UPDATE ... WHERE status=RESERVED`. Must refund to the ORIGINAL balance row, not the current month's. |
| AuditLog rows for every credit event | Traceability (spec §3.4) | LOW | Reuse `apps/common` `AuditLog` (CLAUDE.md §29.4). One row per generation is acceptable at a 10/min/user ceiling. |
| Permission matrix: Staff only sees credits for shops in their `StaffAccessScope`; non-Superadmin denied on superadmin endpoints | Tenant isolation (highest-risk surface in this repo) | MEDIUM | Needs `tenant-security-auditor`. Cross-tenant checks on the balance, history and generate endpoints. |

### Differentiators (competitive advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Generate response returns `credits_charged` and `credits_remaining` | Exact toast ("2 credits used, 33 remaining") with no refetch; avoids stale display | LOW | Small response-shape extension to the existing endpoint. Also include `credits_charged` in the 422 moderation body (Gap 8). |
| Embed `ai_credit_cost` (or `ai_eligible`) in the review list payload | Avoids one `/cost/` call per visible row (an N+1 over HTTP) and keeps the label instant | LOW | Computed from `comment` with no extra query. The spec's `/cost/` endpoint is still built (it is in the requirements) but the UI should not depend on it per row. |
| Before/after preview in the bonus modal ("Remaining will become 55") | Prevents fat-finger grants, since the ledger is immutable and the spec has no reversal | LOW | Client-side arithmetic from the already-fetched balance. |
| Low-balance emphasis in the composer (amber text at <=25% remaining) | Matches the 80% convention; costs almost nothing | LOW | Reuse the badge thresholds. No email or push (out of scope). |
| Read-only Django admin for `ShopCreditBalance` / `CreditTransaction` | Satisfies spec §8.3 ("investigate via Django admin") instead of building reporting | LOW | Preferable to building a history UI. |
| One-line copy "Credits are used even if you discard the draft" near the button | Honest-pricing transparency; avoids support tickets | LOW | Spec §5.5 asks for a first-use tooltip. A static helper line is simpler and accessible. |

### Anti-Features (commonly requested, often problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Click-confirmation step ("This will use X credits. Continue?") | Accident prevention (spec §5.4) | Locked out. Adds friction. The existing flow already has a second deliberate click (tone pill) before spend. | Cost on the label and on the tone-pill row. |
| "Don't ask again this session" state | Goes with the confirmation | Dead once confirmation is cut | None |
| Credit rollover, per-user credits, inter-shop transfer | Common asks | Spec out-of-scope. Rollover contradicts the lapse model and the ledger invariants. | Superadmin bonus for the current month |
| Reversal or negative bonus adjustment | Fixes mistaken grants | Not in the spec. Breaks the "immutable ledger, positive bonus" invariant and invites audit complexity. | Preview step; Django admin for genuine corrections |
| Pre-creating balance rows for every shop each month | Simpler reads | Wasteful, and creates rows for shops that never use AI (spec §7.1 chose lazy). | Virtual balance in selectors when no row exists |
| Credit-history UI / analytics widget | Looks like "usage visibility" | Spec out-of-scope. The `/credits/history/` endpoint has no UI consumer in this milestone. | Audit log plus Django admin. Build the endpoint only if it is cheap. |
| Overage / negative balance / auto-reload / email low-balance alerts | Standard in billing products | There is no payments flow. Negative balances break the hard-cap model. | Hard cap with 402 |
| Credits for enrichment, dashboards and other AI features | Natural extension | Enrichment is a system-driven spend and must never block sync. Spec scope is reply generation only. | Keep enrichment off the ledger |
| WebSocket or polling balance sync | "Live" balance | Violates the Channels scope discipline (CLAUDE.md §13.2). | Refresh on composer open, on generate response, and on 402 |
| Shop-switcher badge (§9.3, AC 33) | Spec item | No switcher exists. Deferred. Remove AC 33 from the requirements. | Revisit if a switcher is built |

## Spec gaps and recommended resolutions

These are the items the roadmap and requirements should decide explicitly. Ordered by impact.

1. **Rollout dark-launch (HIGH impact).** `monthly_credit_allocation` defaults to 0 and the spec treats 0 as "feature disabled". AI reply generation has been shipped since Phase 19, so on deploy every existing org immediately loses it. Resolve with either a data migration that backfills existing orgs to a business-chosen default, or an explicit pre-deploy runbook step ("Superadmin sets allocations first"). Put this in the requirements as an explicit item.

2. **No balance row yet.** The spec only addresses creation at first consumption. Reads (shop card, shops list, composer, bonus modal) must NOT write. Selectors return a virtual balance: `allocated = org.monthly_credit_allocation`, `bonus = 0`, `consumed = 0`, `period = current UTC month`. The shops list uses `Coalesce(balance subquery, org allocation)`. Add this as acceptance criteria and a query-count test. Related: lazy creation at 0 allocation should not write a row or a zero `INITIAL_ALLOCATION` transaction (return 402 first). Lazy creation SHOULD write the INITIAL transaction and `shop.credits.allocated` audit for non-zero rows.

3. **Mid-month allocation change is inconsistent for shops without a row.** Spec §7.3 and AC 16 say the new value applies next month. But a shop with no row yet will lazily pick up the NEW allocation, whereas a shop that already used AI keeps the old one. Either accept and document ("takes effect next month for shops that already have a balance; others pick it up on first use"), or snapshot. Recommend accepting and putting accurate helper text on the edit form. Snapshotting adds effective-dating complexity for little value.

4. **Cost label versus the real UI flow.** `ReplyComposer.tsx` is a two-step flow. The header "Generate with AI" is a toggle that opens tone pills (Professional/Friendly), and spend happens on the pill click (the "Replace your draft?" confirm state already exists when a draft is present). The spec's yellow button with sub-caption does not exist. Recommended: the cost in the toggle label (`Generate with AI (2 credits)`), a short "Uses 2 credits" note in the pill group, and the existing small border-button styling. The `aria-label="Generate reply with AI"` overrides the visible text, so update it to include the cost (label-in-name, WCAG). A disabled state must also close the pill group and set `aria-disabled`/tooltip text that is reachable by keyboard (a native `disabled` button gives no tooltip on focus; consider `aria-disabled` plus a visible helper line).

5. **Comment length definition.** The spec says "1+ character" and "zero-length". Use `len(comment.strip())` consistently (whitespace-only is empty, and it is what moderation and the prompt effectively see). Server is authoritative: JS `.length` counts UTF-16 units, Python counts code points, so emoji-heavy reviews can differ on the 100/500 boundary. Therefore the UI must use the server-supplied cost, never recompute it client-side. The 4000-char input cap makes the top tier unaffected.

6. **Allocation 0 versus exhausted (copy and behaviour).** Spec §5.3 treats both as "insufficient". For allocation 0 and no bonus, an Org Admin cannot fix anything by buying credits. Recommended: keep the button visible but disabled in both cases (unlike star-only, which is hidden, because discoverability and the Buy More path matter). Use distinct copy ("AI replies aren't enabled for this shop. Contact ReviewBee admin." versus "Not enough credits (needs 2, 1 remaining)."). Return `code: "insufficient_credits"` plus `reason: "not_enabled" | "exhausted"`, `required`, `remaining`. "Enabled" means `allocated + bonus > 0`, because a bonus can enable a single 0-allocation shop. Card and badge for total 0: show "Not enabled" and a dark-gray badge, with no divide-by-zero in the bar.

7. **Stale balance and 402 handling.** Another user can spend between display and click. The composer needs a 402 branch (existing code only maps 422 and 429) that updates local remaining from the response body and shows an actionable message. The cost label must also re-render when remaining changes after a generation.

8. **Moderation refund split needs a stage signal (verified in code).** Locked decision: refund on input-moderation block, consume on output-moderation block. `ContentModeratedException` is raised at two sites in `guardrails.py` (lines ~292 input and ~338 output) with only a message string to distinguish them, and the view returns an identical 422. Add a `stage` attribute (input/output) to the exception, branch the refund in the credits wrapper, and have the 422 body say whether a credit was charged ("1 credit was used"). Otherwise users are charged with no explanation.

9. **Reserve/commit/reaper races.** (a) The reaper TTL is 5 min; make the OpenAI client timeout comfortably shorter, and make commit and refund guarded transitions (`UPDATE ... WHERE status='RESERVED'`) so a reaped reservation is never also committed. (b) Refund must target the transaction's own `shop_credit_balance`, not "current month" (a reservation can straddle UTC midnight). (c) Lapse should skip or tolerate balance rows with in-flight RESERVED transactions, since a later refund would otherwise return credits to an already-lapsed row. (d) The commit/refund must run in `finally`; the client's `AbortController` aborts the fetch but not the server work, and a disconnect on ASGI must not skip settlement. Invariant to test: `consumed_credits == sum(non-REFUNDED CONSUMPTION debits)` per balance.

10. **Linking to `AiUsageLog` requires a service refactor (verified in code).** Spec requires CONSUMPTION to carry `ai_usage_log_id`. `generate_reply_draft(review, tone) -> str` currently creates its logs internally (SUCCESS, FAILED, and MODERATED via guardrails) and returns only text. Return the usage-log id (or a small result object), or the commit step cannot link it. Still exactly one `AiUsageLog` row per call (spec AC 38).

11. **Throttle and ordering.** Locked at 10/min (spec says 30). Order: auth and scope, serializer validation (tone), throttle (already pre-action in DRF), empty-comment 400, then reserve. A throttled or invalid request must never create a RESERVED row.

12. **Org Admin "view allocation" has no home.** Spec §2 gives Org Admin a read-only view of the org allocation, but no org-settings page exists for Org Admin. Satisfy it on the Shop Details credits card ("Monthly allocation 100 + bonus 20"). Staff see only remaining/total for accessible shops.

13. **Audit-log visibility (§2, AC 25) versus the existing Activity Log (v0.7).** Org Admin sees credit events org-wide; Staff must NOT. The Activity Log is Staff-scoped by action/shop today, so `shop.credits.*` and `organisation.credits.set` must be excluded from Staff queries, and consumed events may add volume (the type filter exists). Needs a deliberate selector change plus a Staff negative test. This was not verified in depth, so treat it as phase-specific research.

14. **Reviews-page credits (§1.1) versus §9.** §1.1 promises credits on the Reviews page, but §9 only specifies the composer. The Reviews list spans shops. Recommend the composer only (per §9.4). Defer any page-level display.

15. **Timezone display.** "Renews Dec 1" in the user's timezone can read Nov 30 for the Americas. Display "Renews Dec 1 (UTC)" or the exact local time; the boundary is UTC.

16. **Ledger conventions.** Define sign conventions (`credits_delta` negative for consumption, `consumed_credits` increments), the `status` field for non-consumption rows (default COMMITTED), and that REFUNDED consumption nets to zero. State these once in the requirements to keep tests unambiguous.

17. **Minor.** Superadmin hitting generate-reply ("Not applicable") should be a clean 403, not a crash. Deactivated or disconnected shops still hold balances; the lapse and badge should tolerate them. The `/credits/history/` endpoint has no UI consumer, so defer or build it as a bare selector. AC 33 (switcher popup) must be struck from the requirements.

## Feature Dependencies

```
Organisation.monthly_credit_allocation (field + form + audit)
    └──feeds──> Lazy ShopCreditBalance creation / virtual balance selector
                    ├──required by──> Credits read API (GET /shops/{id}/credits/)
                    │       ├──> Shop Details credits card
                    │       ├──> Shops-list badge (annotated list selector)
                    │       └──> Composer "X remaining"
                    ├──required by──> Bonus allocation (Superadmin modal + endpoint)
                    └──required by──> Consumption (reserve -> OpenAI -> commit/refund)

credit_cost.py (pure function)
    ├──required by──> Consumption service
    ├──required by──> Review list `ai_credit_cost` field and /cost/ endpoint
    └──required by──> Cost label on button

Consumption service
    ├──requires──> generate_reply_draft refactor (return usage-log id; moderation `stage`)
    ├──requires──> CreditTransaction status enum (RESERVED/COMMITTED/REFUNDED)
    ├──enables──> Reaper task
    └──enables──> Composer 402/updated-balance handling

Lapse task ──requires──> ShopCreditBalance + CreditTransaction (LAPSED)
Buy More modal ──independent──> mounted from card, badge, composer (no backend)
Activity Log scoping change ──requires──> AuditLog rows for credit events
Rollout migration/runbook ──must precede──> enabling the 402 gate in production
```

### Dependency Notes

- **Consumption requires the `reply_generation.py` refactor:** the existing service writes its own `AiUsageLog` rows and exposes only text; linking and the stage-aware refund need changes there.
- **UI cards and badge require the virtual-balance selector first:** otherwise they render empty or wrong for shops that have not used AI this month.
- **The 402 gate must not ship before the rollout step:** otherwise existing orgs lose a shipped feature (Gap 1).
- **Composer changes depend on the `ReviewReadSerializer` additions:** `ai_credit_cost` and eligibility. A new field is cheap but touches the list query-count test.
- **Lapse and reaper are independent of the UI** and can be built after the core ledger and consumption.

## MVP Definition

### Launch With (v0.9)

- [ ] Allocation field on Org Create/Edit with audit — the lever for everything else
- [ ] Balance and ledger models, virtual balance selector, lazy creation — the foundation
- [ ] Cost function, the consumption wrapper with reserve/commit/refund, 402/400, moderation-stage refund split — the spending cap
- [ ] Composer: hidden for star-only, cost label, remaining text, disabled and zero states, 402 handling, Buy More link
- [ ] Shop Details card, Shops-list badge, Buy More modal, Superadmin bonus modal
- [ ] Lapse and reaper Beat tasks, AuditLog events, Staff-excluded Activity Log scoping
- [ ] Rollout step (backfill or runbook) — required for a safe deploy

### Add After Validation (v0.9.x)

- [ ] Credits history endpoint or UI — when a consumer or support need appears
- [ ] Reviews-page credit indicator — when users ask for it
- [ ] Superadmin usage report — spec §8.3 defers it

### Future Consideration (v1.0+)

- [ ] Real payment and checkout in place of the Buy More placeholder (spec: within about 2 months)
- [ ] Shop-switcher badge (needs a switcher)
- [ ] Credits for other AI features, rollover, overage, alerts

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Consumption with reserve/commit/refund | HIGH | HIGH | P1 |
| Allocation field + ledger/balance models | HIGH | MEDIUM | P1 |
| Rollout backfill/runbook | HIGH | LOW | P1 |
| Composer cost label, remaining, empty/zero/402 states | HIGH | MEDIUM | P1 |
| Shop Details card + Shops-list badge | HIGH | MEDIUM | P1 |
| Bonus allocation modal | MEDIUM | MEDIUM | P1 |
| Lapse and reaper tasks | HIGH | MEDIUM | P1 |
| Buy More placeholder modal | MEDIUM | LOW | P1 |
| Moderation-stage refund split | HIGH | LOW | P1 |
| Response carries `credits_charged`/`remaining`; list carries `ai_credit_cost` | MEDIUM | LOW | P2 |
| Bonus-modal before/after preview | MEDIUM | LOW | P2 |
| Activity Log Staff scoping for credit events | MEDIUM | MEDIUM | P1 (security) |
| Read-only Django admin for ledger | MEDIUM | LOW | P2 |
| Credits history endpoint | LOW | LOW | P3 |

**Priority key:** P1 = must have for launch; P2 = should have, add when possible; P3 = nice to have, future.

## Competitor / Analogue Feature Analysis

Generic AI-credit products (not review-tool competitors) are the relevant analogues here. Based on vendor docs and posts, not hands-on testing.

| Feature | Typical AI-credit SaaS (e.g. Lovable, Schematic-style) | ReviewBee v0.9 approach |
|---------|--------------------------------------------------------|--------------------------|
| Cost shown before action | Cost label on the trigger, updated as inputs change | Cost on the toggle label and tone-pill row, server-computed |
| Out-of-credits | Disabled action plus upgrade or top-up path | Disabled plus contact-admin modal (placeholder) |
| Low-balance warning | About 80% consumed | Colour bands at 75% and 95% used, no emails |
| Failed requests | Released or refunded | Refund on OpenAI failure and input block; consume on output block |
| Overage / auto-reload | Common | Anti-feature here (hard cap) |
| Monthly expiry | Common with a visible reset date | Lapse, "Renews on ... (UTC)" |

## Sources

- Spec: `/Users/renjith/Documents/Accounts/review-master/docs/completed/Requirements_Credits_System.md` (HIGH, binding)
- Project decisions: `/Users/renjith/Documents/Accounts/review-master/.planning/PROJECT.md` (HIGH)
- Live code verified: `frontend/src/widgets/review-management/ReplyComposer.tsx` (two-step toggle then tone-pill flow, 422/429 handling only), `apps/reviews/services/reply_generation.py` (returns str, writes logs internally), `apps/reviews/views.py` (identical 422 for both moderation stages), `apps/integrations/openai/guardrails.py` (two raise sites) (HIGH)
- [Schematic: AI credit system](https://schematichq.com/blog/ai-credit-system) and [credit ledger docs](https://docs.schematichq.com/use-cases/credit-ledger) (MEDIUM, vendor)
- [Stigg: credits enforced in the request path](https://www.stigg.io/blog-posts/credits-are-a-financial-system-we-built-it-for-you-enforced-in-the-request-path) (MEDIUM, vendor)
- [Towards AI: AI credit pricing UX, show the cost before the click](https://pub.towardsai.net/ai-credit-pricing-ux-show-the-cost-before-the-click-ce25489465c7) (LOW-MEDIUM, personal write-up)
- [Lovable docs: out of credits](https://docs.lovable.dev/introduction/out-of-credits) (MEDIUM)
- [Figma forum: credit system causes frustration](https://forum.figma.com/report-a-problem-6/credit-system-causes-frustration-55167) (LOW, anecdotal user feedback on unclear cost and balance)

---
*Feature research for: per-shop monthly AI reply credits (v0.9)*
*Researched: 2026-11-11*
