---
phase: 33
review: 33-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Activity Log filters cannot reach credit rows (entity_type whitelist and shop filter)  [medium]"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Credit audit rows expose internal identifiers and Superadmin identity to Org Admins  [medium]"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Credit columns on `ShopReadSerializer` are null for retrieve / create / update but populated for list  [low]"
  - id: IN-01
    severity: info
    disposition: open
    title: "Staff-only code paths on the Shops page are unreachable  [low]"
  - id: IN-02
    severity: info
    disposition: open
    title: "Buy More modal handles an empty support email poorly  [low]"
  - id: IN-03
    severity: info
    disposition: open
    title: "Minor consistency and coupling issues in the credits widgets  [low]"
  - id: IN-04
    severity: info
    disposition: open
    title: "OpenAPI and docs drift after Phase 33  [low]"
open: 7
total: 7
recorded: 2026-11-11T20:00:00.595Z
---

# Phase 33: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
