# Phase 33: Credit Visibility & Staff Scoping - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 33-credit-visibility-staff-scoping
**Areas discussed:** Shops-list badge, Composer credit UX, Credits card on Shop Details, Buy More modal & contact

---

## Shops-list badge

| Question | Options | Selected |
|----------|---------|----------|
| Badge click (spec §9.2 vs roadmap SC4 conflict) | Open Shop Details card / Open Buy More directly / Depends on balance | Open Shop Details card |
| Zero states | "Not enabled" vs "0 credits" / Hide badge when not enabled | "Not enabled" vs "0 credits" |
| Thresholds | Spec bands, shared / Separate rules | Spec bands, shared |
| Badge text | "35 credits" + tooltip / "35 / 100" | "35 credits" + tooltip |

## Composer credit UX

| Question | Options | Selected |
|----------|---------|----------|
| Remaining placement | Muted line above composer / Inside the AI button area only | Muted line above composer |
| Re-charge clarity (D-11) | Cost on each tone pill / Reuse replace-draft confirm / Button label only | Cost on each tone pill |
| Disabled reasons | Inline text + Buy More / Tooltip on the disabled button | Inline text + Buy More |
| 402 handling | Switch to disabled state / Error toast + refresh | Switch to disabled state |

## Credits card on Shop Details

| Question | Options | Selected |
|----------|---------|----------|
| Placement | Top, above the detail rows / Bottom, after the detail rows | Top |
| Staff view | Same card for both / Staff: remaining only | Same card for both |
| Not enabled | Explain + Buy More / Explain only / Hide the card | Explain + Buy More |
| Freshness | Fetch on open only / Poll while open | Fetch on open only |

## Buy More modal & contact

| Question | Options | Selected |
|----------|---------|----------|
| Recipient | Platform support, all roles / Staff → their Org Admin | Platform support, all roles |
| Pre-fill | Subject + body / Subject only / Plain mailto | Subject + body |
| No-shop context | Org only / You decide | Org only |
| 24h promise | Soften it / Keep '24 hours' | Soften it |

**User's choice:** recommended option in every case.

## Claude's Discretion

- Exact copy/layout/tokens (defer to `/gsd-ui-phase 33`)
- 409 in-flight composer message
- Badge → Shop Details open mechanics

## Deferred Ideas

- Staff credit requests routed to their Org Admin (rejected; CVIS-04 change)
- Polling the credits card (rejected)
- Real checkout flow (future)
