---
phase: 30
review: 30-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "Failed commit/settle reported as \"charged 0\" while credits stay held"
  - id: WR-02
    severity: warning
    disposition: open
    title: "LangSmith fallback can call OpenAI a second time (double billing) and escapes the timeout budget"
  - id: WR-03
    severity: warning
    disposition: open
    title: "TTL/timeout invariant only enforced for default values"
  - id: WR-04
    severity: warning
    disposition: open
    title: "One-RESERVED-per-review guard leaks at a UTC month boundary"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Unmetered `generate_reply_draft` remains a public entry point"
  - id: IN-01
    severity: info
    disposition: open
    title: "`credit_cost` throttle (120/min) can be exceeded by the UI's own usage"
  - id: IN-02
    severity: info
    disposition: open
    title: "Runbook understates 409 duration and worst-case budget"
  - id: IN-03
    severity: info
    disposition: open
    title: "Runbook operator snippets have gaps"
  - id: IN-04
    severity: info
    disposition: open
    title: "Stale docstrings and duplicated except branch"
  - id: IN-05
    severity: info
    disposition: open
    title: "`CreditTransaction.save` breaks a positional `force_insert`"
open: 10
total: 10
recorded: 2026-11-11T13:46:27.857Z
---

# Phase 30: Code Review Disposition

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
| IN-05 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
