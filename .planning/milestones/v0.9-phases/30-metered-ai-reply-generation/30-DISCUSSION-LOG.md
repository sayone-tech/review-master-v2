# Phase 30: Metered AI Reply Generation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 30-metered-ai-reply-generation
**Areas discussed:** Late commit & disconnect, Timeout & TTL values, Error & response contract, Regenerate & double-click

---

## Late commit & disconnect

| Question | Options | Selected |
|----------|---------|----------|
| Reaper refunded before commit | Return draft + one re-deduct / Return draft free / Discard draft, error | Return draft + one re-deduct |
| Client disconnect | Settle as if delivered / Refund on disconnect | Settle as if delivered |
| Other CAS miss | Same as late commit / Raise 500 | Same as late commit |

## Timeout & TTL values

| Question | Options | Selected |
|----------|---------|----------|
| Reply-path timeout | 30s, retries=1 / 20s, retries=0 / 60s, retries=2 | 30s, retries=1 |
| Reservation TTL | 5 min / 15 min | 5 min |
| In-transaction guard | Raise real exception / Plain assert | Raise real exception |

## Error & response contract

| Question | Options | Selected |
|----------|---------|----------|
| 402 reason | allocated+bonus==0 → not_enabled / org allocation==0 → not_enabled | allocated+bonus==0 |
| Error bodies | Include credits_charged + credits_remaining / Only on success | Include on errors |
| Cost endpoint | GET credit-cost @action {cost, remaining, is_enabled} / Cost only | Full @action |

## Regenerate & double-click

| Question | Options | Selected |
|----------|---------|----------|
| Regenerate charging | Every call charges / Free window | Every call charges |
| Double-click | 409 if RESERVED exists for review / Charge both / Idempotency-Key | 409 guard |
| Deploy note | docs/sre runbook + PR / PR only | Runbook + PR |

## Claude's Discretion

- Consumption service naming/exceptions, credit-cost throttle scope, optional partial unique index for D-12, late-commit audit action name, how existing tests get credits.

## Deferred Ideas

- Idempotency-Key header; free regenerate window.
