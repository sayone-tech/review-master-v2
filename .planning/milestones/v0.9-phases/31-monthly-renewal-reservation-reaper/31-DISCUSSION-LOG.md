# Phase 31: Monthly Renewal & Reservation Reaper - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 31-monthly-renewal-reservation-reaper
**Areas discussed:** Zero-remaining lapse, Self-healing cadence, Lapse vs held reservations, Reaper observability

---

## Zero-remaining lapse

| Question | Options | Selected |
|----------|---------|----------|
| Done-marker for 0-remaining balances | lapsed_at on balance / Rescan, no marker / Bounded window | lapsed_at on balance |
| Audit for a 0 lapse | No audit for 0 / Audit with amount 0 | No audit for 0 |
| Lapse payload | Single delta + audit breakdown / Single delta only | Single delta + audit breakdown |

## Self-healing cadence

| Question | Options | Selected |
|----------|---------|----------|
| Missed-run recovery | 1st 00:05 + daily catch-up / Hourly sweep / 1st only | 1st 00:05 + daily catch-up |
| Lookback | All past periods / Cap at 12 months | All past periods |
| Sweep shape | Single task, chunked loop / Fan-out per org | Single task, chunked loop |

## Lapse vs held reservations

| Question | Options | Selected |
|----------|---------|----------|
| After the reaper refunds the last held row | Reaper lapses immediately / Leave to daily sweep | Reaper lapses immediately |
| Refund cannot apply | Stay unlapsed + Sentry error / Force lapse after N days | Stay unlapsed + Sentry error |

## Reaper observability

| Question | Options | Selected |
|----------|---------|----------|
| Signal | WARNING per reap + Sentry if count > 0 / WARNING only / Sentry per reap | WARNING per reap + Sentry if count > 0 |
| Batch and reason | 500/run, "reaped_stale" / Loop until drained | 500/run, "reaped_stale" |
| Config | Settings, env-overridable / Hard-coded constants | Settings, env-overridable |

## Claude's Discretion

- Task names, module split, the reaper skip_locked pre-lock, the lapsed_at index shape, and retry config.

## Deferred Ideas

- Postgres immutability trigger; the 00:30 UTC infra alert (outside the repo).
