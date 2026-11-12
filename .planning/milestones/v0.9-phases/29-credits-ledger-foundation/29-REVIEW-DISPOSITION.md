---
phase: 29
review: 29-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Append-only guard bypassable by saving a hand-built instance with an existing pk"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`bulk_create(update_conflicts=True)` is an unguarded rewrite path"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Virtual balance for a past period reports today's allocation"
  - id: IN-01
    severity: info
    disposition: open
    title: "Dead positional-args branch in `save()`"
  - id: IN-02
    severity: info
    disposition: open
    title: "Status-transition lookup relies on enum name == value"
  - id: IN-03
    severity: info
    disposition: open
    title: "`credit_cost` does not validate tiers at runtime"
  - id: IN-04
    severity: info
    disposition: open
    title: "Allocation read outside the transaction in `ensure_balance`"
  - id: IN-05
    severity: info
    disposition: open
    title: "Denormalised `shop`/`organisation` on `CreditTransaction` unconstrained"
  - id: IN-06
    severity: info
    disposition: open
    title: "Inconsistent import discipline for credits → shops"
open: 7
total: 9
recorded: 2026-11-11T12:13:50.890Z
---

# Phase 29: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | 29-04 (d866fe0) |
| WR-02 | warning | fixed | 29-04 (e848817) |
| WR-03 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
