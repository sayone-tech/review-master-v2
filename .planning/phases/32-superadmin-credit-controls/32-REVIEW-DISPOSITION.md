---
phase: 32
review: 32-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "`ensure_balance` seeds from an allocation read outside any lock, so a concurrent 0 -> N edit can leave a stuck zero row"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Shop availability (active shop, non-DELETED org) is checked outside the transaction and org lock"
  - id: WR-03
    severity: warning
    disposition: open
    title: "A stale-period request on an inactive shop returns 409 with a balance snapshot instead of 404"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Bonus POST has no idempotency, and the generic-error path invites a double credit"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Credit shop list is stuck on a 404 when the page index goes out of range"
  - id: IN-01
    severity: info
    disposition: open
    title: "Shop search has no length bound"
  - id: IN-02
    severity: info
    disposition: open
    title: "Deferred hint prints the raw \"keep\" number"
  - id: IN-03
    severity: info
    disposition: open
    title: "Double-submit guard depends on React state"
  - id: IN-04
    severity: info
    disposition: open
    title: "Shops created after an allocation change take the new value this month"
open: 9
total: 9
recorded: 2026-11-11T16:07:33.257Z
---

# Phase 32: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
