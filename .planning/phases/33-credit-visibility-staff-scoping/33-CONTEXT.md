# Phase 33: Credit Visibility & Staff Scoping - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admins and Staff can see a shop's AI reply credits **before** they generate: an "AI Reply Credits" card on Shop Details, a credits badge on every Shops-list row, and the cost + remaining credits in the reply composer (with distinct disabled states and 402 handling). A placeholder **Buy More Credits** modal (mailto only, no payment) is reachable from those surfaces. Org Admins see credit events in the Activity Log; Staff do not. Staff only ever see credits — and Shops-list rows — for shops in their StaffAccessScope (SCOPE-01), proven by negative tests.

Requirements: CVIS-01, CVIS-02, CVIS-03, CVIS-04, CVIS-05, SCOPE-01. Superadmin credit controls are Phase 32, not here.

</domain>

<decisions>
## Implementation Decisions

### Shops-list credits badge (CVIS-02)
- **D-01:** Clicking a badge **opens the Shop Details modal with the credits card visible** (spec §9.2). Roadmap SC4's "Buy More opens from the Shops-list badge" is satisfied **via the card's Buy More link** (badge → card → Buy More), not by the badge opening Buy More directly. The planner should note this as a clarification of SC4's wording.
- **D-02:** Zero states are distinguished by **text, not colour alone**: an org with 0 monthly credits shows a muted grey **"Not enabled"** badge; a shop that has used everything shows **"0 credits"** in dark grey.
- **D-03:** Colour bands follow the spec and are **shared by the badge and the Shop Details progress bar** via one helper: green when remaining > 25% of total, amber 5–25%, red < 5%, dark grey at 0 (the card's "used 75% / 95%" boundaries are the same thresholds). Total = allocated + bonus.
- **D-04:** Badge text is **"{n} credits"** ("1 credit" singular) with tooltip and aria-label **"{n} credits remaining this month"**.

### Reply composer (CVIS-03)
- **D-05:** A muted line **above the composer** reads "This shop has {n} credits remaining this month." (spec §9.4), updated from `credits_remaining` after every generate.
- **D-06:** Because every generate charges, including tone switches and regenerates (Phase 30 D-11), **once a draft exists each tone pill shows its cost** (e.g. "Friendly · 2 cr"). No extra confirm step beyond the composer's existing replace-draft confirm.
- **D-07:** Disabled reasons are shown as **inline text, not tooltip-only**:
  - Not enabled: "AI replies aren't enabled for this shop." — **no** Buy More link here (D-12 covers the card).
  - Not enough credits: "Not enough credits — this reply needs {cost}, you have {remaining}." with a **Buy More Credits link directly beneath the composer** (spec §9.4).
- **D-08:** A **402 from generate switches the composer to the matching disabled state** using the 402 body (`reason`, remaining) — no generic error toast — and **keeps any draft text the user typed**.
- Carried (not re-decided): AI button hidden for star-only reviews; label and aria-label "Generate with AI · {N} credits"; tone pills disabled while generating; cost always from the server (`credit-cost` endpoint) — roadmap SC3 / Phase 30 D-10.

### Shop Details credits card (CVIS-01)
- **D-09:** The card sits **at the top of `ShopDetailsModal`, above the existing detail rows**, so a badge click (D-01) shows it without scrolling.
- **D-10:** **Org Admin and Staff see the same card**, including the "Monthly {allocated} · Bonus {bonus}" breakdown (Staff seeing their own shop's numbers was accepted in Phase 30). No role branching in the component.
- **D-11:** The card **fetches fresh on every modal open** (endpoint sends `Cache-Control: no-store`); **no polling**. The composer refreshes its own number after generate.
- **D-12:** **"Not enabled" (total 0)**: the card shows "AI replies aren't enabled for this shop.", **no progress bar** (no divide-by-zero), and a **Buy More Credits** link so users can ask for the feature to be turned on.
- Carried: remaining / total, colour-coded bar (D-03), "{used} credits used · {available} credits available", "Renews {date} (UTC)" from server `renews_on`, period label from server `period_label`; a shop with no activity this month shows its full allocation (virtual balance, never writes) — roadmap SC1.

### Buy More Credits modal (CVIS-04)
- **D-13:** **Contact Admin mails `REVIEWBEE_SUPPORT_EMAIL` for every role** (platform support is the only party that can add credits). No per-org admin routing.
- **D-14:** The mailto **pre-fills subject and body**: subject "Credit request — {Org} / {Shop}"; body lists org, shop, month, current remaining / total, and a blank line for the amount needed. **No review text** (CLAUDE.md §22). URL-encode all values.
- **D-15:** The modal component takes **optional shop context**; without a shop it references the **org only** (subject "Credit request — {Org}", shop lines omitted).
- **D-16:** **Soften the spec's SLA**: replace "Credits are added within 24 hours of request." with wording like "Your administrator will add credits as soon as possible." (exact copy for `/gsd-ui-phase 33`).
- Carried: title "Buy More Credits", mail icon, primary "Contact Admin" + secondary "Close", focus trap, ARIA labels, ESC / backdrop close, no payment flow — roadmap SC4 / spec §9.5.

### Staff scoping (SCOPE-01) — decided at plan-phase, 2026-11-11
- **D-17:** **Shop retrieve is Staff-scoped too.** `GET /api/v1/shops/{id}/` returns 404 for a Staff user whose StaffAccessScope does not include the shop (same rule as the list and the credits GET). This goes slightly beyond the roadmap wording on purpose, because it closes the same leak.
- **D-18:** **The Shops page stays Org-Admin-only** (`@org_admin_required` and the sidebar are unchanged). SCOPE-01 is enforced at the API (`GET /api/v1/shops/`, credit endpoints), and Staff see credits in the reply composer. The UI-SPEC's Staff "No shops assigned" empty state is built defensively behind a role prop but cannot be reached yet.

### Carried forward (locked by earlier phases / roadmap — do not re-decide)
- Server is the source of truth for cost, remaining, `is_enabled`, `period_label`, `renews_on`; dates render with `timeZone: "UTC"` (ROADMAP notes).
- Backend shape (ROADMAP notes): shop credits GET returning the virtual balance, never writes, `Cache-Control: no-store`; `list_shops(with_credits=True)` as one annotation (fixed query count for 1 vs 20 shops), serializer fields default `None`; one shared `get_accessible_shop_for_credits` selector; Activity Log selector change.
- SCOPE-01 resolves research option (b): **`list_shops` gains real Staff scoping** — a deliberate behaviour change (Staff stop seeing out-of-scope shops).
- CVIS-05: Org Admin sees `shop.credits.*` and `organisation.credits.set` in the Activity Log; Staff do not (event filtering, not hiding the whole log — exact mechanism is the planner's, research-flagged in ROADMAP).
- Frontend: balance store keyed by `shop_id`, refreshed after generate; `api.ts` gets a 402 branch.
- Phase 30 contracts: generate returns `{draft, credits_charged, credits_remaining}`; 402 `reason` distinguishes not-enabled vs insufficient (D-08/D-09); 409 for a duplicate in-flight generate (D-12).
- Mandatory `tenant-security-auditor` + `orm-performance-auditor` (CLAUDE.md §27).
- At milestone close: confirm the CQA-02 deploy note still matches, and move the spec `docs/in-progress/` → `docs/completed/` (CLAUDE.md §28).

### Claude's Discretion
- Exact copy, layout, icon and colour tokens — defer to `/gsd-ui-phase 33` (roadmap: run it first).
- 409 (generation already in progress) message in the composer — reuse the existing composer error pattern.
- How Shop Details is opened from the badge (same modal component, focus moved to the card heading).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — CVIS-01..05, SCOPE-01, and the "Spec reconciliations" line (§9.3 shop-switcher badge + AC 33 struck; no click-confirmation step; cost on the button label)
- `.planning/ROADMAP.md` § Phase 33 — goal, success criteria 1–5, implementation notes (backend endpoints, `list_shops` scoping behaviour change, frontend UTC/402/store rules, auditors, milestone-close tasks)

### Product spec
- `docs/in-progress/Requirements_Credits_System.md` §9.1 (Shop Details card), §9.2 (Shops-list badge + thresholds), §9.4 (reply screen), §9.5 (Buy More popup — SLA wording softened by D-16), §5.2 (button cost label); §9.3 struck by reconciliation

### Prior phase context
- `.planning/phases/30-metered-ai-reply-generation/30-CONTEXT.md` — D-08 (402 reason), D-09 (response bodies), D-10 (credit-cost endpoint), D-11 (every generate charges), D-12 (409 in-flight)
- `.planning/phases/29-credits-ledger-foundation/29-0{1,3}-SUMMARY.md` — `get_shop_credit_balance` / `annotate_credit_state` (virtual balance, never writes)
- `.planning/phases/32-superadmin-credit-controls/32-CONTEXT.md` — Superadmin endpoints that SCOPE-01's negative tests must cover (Staff → 403)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` — label/value `Row` layout; the credits card goes above the rows (D-09).
- `frontend/src/widgets/shop-management/ShopTable.tsx` — gains the badge column (D-01..D-04).
- `frontend/src/widgets/review-management/ReplyComposer.tsx` — existing tone pills and replace-draft confirm (D-06); `review-management/api.ts` gains the 402 branch.
- `frontend/src/widgets/modal/Modal.tsx` (+ `ConfirmModal.tsx`) — shell for the Buy More modal (focus trap / ESC / backdrop to verify against CVIS-04).
- `frontend/src/widgets/audit-log/*` — Activity Log widget (CVIS-05 is a selector change; check whether the UI needs a type pill for credit events).
- `apps/credits/selectors/balances.py` — `get_shop_credit_balance`, `annotate_credit_state` (one-query annotation for the Shops list).

### Established Patterns
- `apps/shops/selectors/shops.py::list_shops` — currently not Staff-scoped; SCOPE-01 adds scoping.
- `apps/reviews/selectors/reviews.py::get_accessible_shop_ids` — existing StaffAccessScope expansion (shop + region scopes); reuse for the shared `get_accessible_shop_for_credits` selector.
- `apps/common/selectors/audit_logs.py` — `list_audit_logs_for_org` / `list_audit_logs_for_staff`; CVIS-05 excludes credit events from the Staff selector.

### Integration Points
- `GET /api/v1/reviews/{id}/credit-cost/` (Phase 30) drives the composer; new shop credits GET drives the card; `list_shops(with_credits=True)` drives the badge.

</code_context>

<specifics>
## Specific Ideas

- Badge: "35 credits" / "1 credit" / "0 credits" / "Not enabled"; tooltip "35 credits remaining this month".
- Composer: "This shop has 35 credits remaining this month."; tone pill "Friendly · 2 cr"; "Not enough credits — this reply needs 3, you have 1."
- Buy More mailto subject: "Credit request — {Org} / {Shop}".

</specifics>

<deferred>
## Deferred Ideas

- Routing Staff's credit requests to their own Org Admin instead of platform support — rejected for now (D-13); would change CVIS-04.
- Live polling of the credits card — rejected (D-11).
- Real purchase/checkout flow — future (spec §9.5; the modal is the swap point).

</deferred>

---

*Phase: 33-credit-visibility-staff-scoping*
*Context gathered: 2026-11-11*
