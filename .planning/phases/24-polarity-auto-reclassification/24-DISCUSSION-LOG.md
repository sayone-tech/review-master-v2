# Phase 24: Polarity Auto-Reclassification - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 24-polarity-auto-reclassification
**Areas discussed:** Direction & stickiness, Threshold semantics, POL-03 visibility scope, Reclassification log destination

---

## Direction & stickiness

| Option | Description | Selected |
|--------|-------------|----------|
| One-way only (mixed sticky) | always_* → mixed only; mixed permanent | ✓ (Claude) |
| Two-way with hysteresis | also re-promote mixed → always_* below a lower band | |
| One-way + re-promotion hint | auto-flip one way, log a hint for manual re-promotion | |

**User's choice:** "use the best approach" → Claude chose one-way (matches POL-02 verbatim, idempotent, no flapping). → CONTEXT D-01.

---

## Threshold semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Opposite ÷ all, neutral in denominator, min-sample, configurable | numerator = opposite polarity, denominator = all reviews in window (neutral dilutes), min ≥10, by review_create_time, configurable | ✓ (Claude) |
| Opposite incl. neutral in numerator | treat negative+neutral as "not positive" | |
| Opposite ÷ all, no minimum sample | same ratio, no min-sample guard | |

**User's choice:** "use the best approach" → Claude chose the literal-reading ratio with a min-sample guard. → CONTEXT D-02/D-03/D-04.

---

## POL-03 visibility scope

| Option | Description | Selected |
|--------|-------------|----------|
| Persist + log now; render in Phase 25 | job + AuditLog + admin readonly; page in 25 | |
| Build minimal tag-list visibility now | small throwaway read-only surface this phase | |
| Defer all visibility to Phase 25 | job + logging only; rendering entirely in 25 | ✓ (User) |

**User's choice:** Defer all visibility to Phase 25. POL-03 "events logged" delivered via AuditLog (D-06); "visible on tag list page" carried by Phase 25. → CONTEXT D-07.

---

## Reclassification log destination

| Option | Description | Selected |
|--------|-------------|----------|
| Existing AuditLog (new event type) | reuse Phase 21 AuditLog + Activity Log viewer | ✓ (User) |
| Dedicated TagReclassificationLog model | purpose-built table | |
| Structured logger only | no DB persistence | |

**User's choice:** Existing AuditLog with action="polarity_reclassified", system actor, before/after JSON. → CONTEXT D-06.

---

## Claude's Discretion

Beat cadence + queue; global-task vs per-org fan-out; optional `polarity_reclassified_at` denorm column. All noted under "Claude's Discretion" in CONTEXT.md.

## Deferred Ideas

- Auto re-promotion (mixed → always_*) — manual via Phase 25 or future.
- Rendering polarity_type on the tag list page — Phase 25.
- Dashboard polarity split — Phase 25.
- Per-tag reclassification-history view — optional, reads AuditLog.
