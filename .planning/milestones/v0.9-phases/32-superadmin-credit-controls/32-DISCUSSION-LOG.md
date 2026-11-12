# Phase 32: Superadmin Credit Controls - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 32-superadmin-credit-controls
**Areas discussed:** Mid-month change UX, Credits modal shop list, Bonus allocation flow, Where allocation is shown

---

## Mid-month change UX

| Option | Description | Selected |
|--------|-------------|----------|
| Live inline hint | Hint under the field updates as they type (0→N "immediately"; N→M "takes effect Dec 1, shops keep N") | ✓ |
| Confirm dialog on save | Confirmation step spelling out when the change applies | |
| Static helper text only | Spec helper text only, rule not surfaced dynamically | |

| Option (N → 0) | Description | Selected |
|--------|-------------|----------|
| Same N→M rule | Shops keep N this month, 0 from next month | ✓ |
| 0 takes effect immediately | Kill switch; would change CRED-06 | |

| Option (disabled org) | Description | Selected |
|--------|-------------|----------|
| Editable, no special rule | Allocation is just a field | ✓ |
| Read-only while disabled | Must re-enable first | |

| Option (create default) | Description | Selected |
|--------|-------------|----------|
| Default 0 | Matches CRED-01 and deploy note | ✓ |
| Pre-fill a suggested value | Would change CRED-01 | |

**User's choice:** all recommended options.

---

## Credits modal shop list

| Question | Options | Selected |
|----------|---------|----------|
| Which shops | Active only / All, deactivated marked / All, all actionable | Active only |
| Row columns | Remaining + breakdown / Remaining / total only | Remaining + breakdown |
| Scale | Search + paginated / Search, single scroll list | Search + paginated |
| Pick shop | Click row → bonus form / Dropdown above a form | Click row → bonus form |

**User's choice:** all recommended options.

---

## Bonus allocation flow

| Question | Options | Selected |
|----------|---------|----------|
| Confirm step | Live preview, one click / Review screen, then confirm | Live preview, one click |
| Big amounts | No extra guard / Warn above a threshold / Cap cumulative bonus per month | No extra guard |
| After save | Back to list, row updated / Close the modal | Back to list, row updated |
| Month 409 | Explain + refresh balances / Generic error, close | Explain + refresh balances |

**User's choice:** all recommended options.

---

## Where allocation is shown

| Question | Options | Selected |
|----------|---------|----------|
| Org table | "Credits/shop" column / No column | "Credits/shop" column |
| View modal | Yes, with next-month note / Yes, value only / No | Yes, with next-month note |
| Modal header | Allocation + month only / Add org totals | Allocation + month only |
| Action label | "Manage credits" / "Allocate bonus credits" / You decide | "Manage credits" |

**User's choice:** all recommended options.

---

## Claude's Discretion

- Exact copy, layout, empty states and toast styling (defer to `/gsd-ui-phase 32`)
- Shop-list page size and search semantics
- API shape and how the View modal's "pending change" note is derived (read-only)

## Deferred Ideas

- Org-level aggregate credit totals / usage reporting (spec §8.3 future scope)
- Immediate N → 0 kill switch (rejected; would change CRED-06)
- Cumulative monthly bonus cap / large-amount warning (rejected)
