---
phase: "31"
slug: "monthly-renewal-reservation-reaper"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-11"
---

# Phase 31 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Celery Beat → lapse sweep / reaper tasks | System jobs with no request user; every write must derive tenant ids from locked rows | balance / transaction ids |
| sweep / reaper ↔ request-path settlement | Concurrent writers on the same balance and reservation rows (lapse vs refund vs late commit vs reserve) | credit counters, ledger status |
| tasks → AuditLog / logs / Sentry | Review text is PII and must not leave the system path | ids, ints, reason codes |
| migrations → production schema / Beat tables | Schema change on a hot table; Beat seeds share schedule rows with other tasks | DDL, PeriodicTask rows |
| operators → runbook procedures | Manual reaper/lapse runs on live credit data | ids |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-31-01 | Tampering | `lapse_balance` under overlapping sweeps | high | mitigate | `select_for_update(skip_locked=True)`, `lapsed_at IS NULL` re-checked under lock, guarded marker update, partial unique `credit_tx_one_lapse_per_balance`; PG overlapping-sweep test (16/16 on PG14); confirmed by code review + ORM audit | closed |
| T-31-02 | Tampering | Lapse forced over an unsettled reservation | high | mitigate | RESERVED check inside the lock → `skipped_held` (D-07); month-straddle tests; lock-order analysis (ORM audit §3) shows in-flight refund/commit still reads RESERVED → skip | closed |
| T-31-03 | Tampering | Direct `lapse_balance` on current/future month | medium | mitigate | Past-period predicate in the locked query; guard tests | closed |
| T-31-04 | Tampering / Info disclosure | Cross-tenant audit/ledger write by system sweep | medium | mitigate | org/shop/entity ids copied from the locked balance row; two-organisation test; confirmed by code review | closed |
| T-31-05 | Tampering | Late commit re-deducting on a lapsed balance | medium | mitigate | `_settle_lost_race` reads `lapsed_at` (D-01); marker-only test. **Residual (review WR-01 / ORM audit LOW):** the re-deduct and `reserve_credits` balance UPDATEs re-check the period but not `lapsed_at IS NULL`; a lapse committing in the microsecond gap could let credits be both lapsed and spent | open — below high threshold (non-blocking) |
| T-31-06 | Denial of service | Sweep looping forever / aborting on one bad row | medium | mitigate | pk keyset pagination, per-balance try/except with errored count, `SoftTimeLimitExceeded` re-raised; tests | closed |
| T-31-07 | Information disclosure | Review text in lapse logs/audit | low | mitigate | Lapse path never reads reviews; ids/ints only | closed |
| T-31-08 | Repudiation | Lapse with no trace | low | mitigate | `shop.credits.lapsed` AuditLog for every non-zero lapse; `lapsed_at` for zero-remaining (D-02) | closed |
| T-31-09 | Tampering | Reserve / late re-deduct straddling midnight vs sweep | low | accept | Sweep runs at 00:05 UTC; stray reservation refunded by reaper; late commit on past period is a free draft | closed |
| T-31-10 | Tampering | Overlapping reapers double-refunding | high | mitigate | Every refund via `refund_reservation` status CAS in its own atomic; PG overlapping-reapers test | closed |
| T-31-11 | Tampering | Reaper refunding an already-committed reservation | high | mitigate | Same CAS (committed row matches 0 rows → skipped); PG reaper-vs-late-commit test (5/5 split each of 3 runs, no double refund) | closed |
| T-31-12 | Tampering | Failing refund leaving partial state / rolling back a batch | medium | mitigate | No outer atomic; `RuntimeError` rolls back only its own CAS; balance stays unlapsed (D-09); unit test | closed |
| T-31-13 | Information disclosure | Review text in logs/Sentry/audit | medium | mitigate | Ids and ints only; SECRET sentinel test across caplog, Sentry args, AuditLog JSON | closed |
| T-31-14 | Denial of service | Poison row re-alerting every 10 min / head-of-queue starvation | low | accept | D-09 visibility intended; starvation needs ≥500 poison rows; runbook procedure. Review WR-02 recommends keyset paging + one aggregated Sentry event per run (tracked in 31-REVIEW-DISPOSITION.md) | closed |
| T-31-15 | Denial of service | Reaper refunding a live request | low | mitigate | 5-min TTL vs ~190 s worst-case request (Phase 30 settings test); late commit follows the lost-race policy | closed |
| T-31-16 | Information disclosure | Runbook leaking secrets/review text | low | mitigate | Ids-only examples; credential-shape grep | closed |
| T-31-17 | Tampering | Double refund / double lapse only under real concurrency | high | mitigate | 4 PG race tests (16 pg_concurrency passed, 0 skipped, 3 runs on PG14); `REQUIRE_PG` fails a skipped run. CI on PG16 pending (human item) | closed |
| T-31-18 | Denial of service | Deadlock between lapse lock and refund CAS → balance UPDATE | medium | mitigate | Real `orm-performance-auditor` run 2026-11-11: no cycle — every path takes the balance last or only inserts new rows; lapse never waits on a transaction row; skip-locked never blocks | closed |
| T-31-19 | Tampering / Info disclosure | Regression in org derivation or ids-only logging | medium | mitigate | Real `gsd-code-reviewer` (tenant attribution in scope) + `orm-performance-auditor` runs 2026-11-11, no blockers; cross-tenant reaper attribution test added in 31-03 | closed |
| T-31-20 | Repudiation | Missed lapse run unnoticed | low | transfer | "Lapse not complete by 00:30 UTC" alert owned by the deployment owner (runbook handoff); daily sweep self-heals within 24 h | closed |
| T-31-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed in this phase | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-31-01 | T-31-09 | Sweep runs 5 min after the boundary vs a millisecond ensure/lock gap; reaper and free-draft policy absorb strays | plan-time decision (31-01 PLAN) | 2026-11-11 |
| AR-31-02 | T-31-14 | Repeated Sentry error is the intended D-09 visibility; quarantine column is new schema (out of scope) | plan-time decision (31-02 PLAN, D-09) | 2026-11-11 |
| AR-31-03 | T-31-SC | No new dependencies | plan-time decision | 2026-11-11 |

Open non-blocking: T-31-05 residual (add `lapsed_at__isnull=True` to the `reserve_credits` lock query and the late-commit re-deduct UPDATE; review WR-01 / ORM audit LOW). Other audit items (not threats): WR-03 unvalidated batch/chunk settings (0 silently disables), loop-level query-count tests for reaper/sweep, `lock_timeout` on the deploy migrate.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-11 | 21 | 20 | 1 (medium; threats_open: 0) | secure-phase orchestrator (ASVS L1) + gsd-code-reviewer + orm-performance-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (no open threat at or above `high`)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-11 (1 medium residual open below the blocking threshold)
