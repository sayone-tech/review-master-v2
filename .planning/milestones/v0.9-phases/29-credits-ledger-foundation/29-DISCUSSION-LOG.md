# Phase 29: Credits Ledger Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-11
**Phase:** 29-credits-ledger-foundation
**Areas discussed:** Ledger schema & FKs, Append-only enforcement, Cost function edges, Balance read contract

---

## Ledger schema & FKs

| Question | Options | Selected |
|----------|---------|----------|
| Forward columns | Full schema now / Minimal now, add later / You decide | Full schema now |
| on_delete | PROTECT shop/balance, SET_NULL rest / CASCADE from shop | PROTECT shop/balance, SET_NULL rest |
| Lazy-allocation actor | System (actor=None) / Triggering user | System (actor=None) |
| Bonus note | Optional note column / No note | Optional note column |

## Append-only enforcement

| Question | Options | Selected |
|----------|---------|----------|
| Enforcement depth | App layer + DB CHECKs / Also a Postgres trigger | App layer + DB CHECKs |
| Status transitions | RESERVED→COMMITTED/REFUNDED only / Also COMMITTED→REFUNDED | RESERVED→COMMITTED/REFUNDED only |
| Ledger uniques | Partial uniques INITIAL + LAPSED (+ RESERVED index) / INITIAL only now | Partial uniques INITIAL + LAPSED |

## Cost function edges

| Question | Options | Selected |
|----------|---------|----------|
| Zero length | Return 0 / Raise ValueError | Return 0 |
| Length unit | Python len() code points / Grapheme clusters | Code points |
| Tier config | List of (max_len, cost), last None / Env-overridable ints | List of tuples, last None |

## Balance read contract

| Question | Options | Selected |
|----------|---------|----------|
| Read shape | Frozen dataclass / Plain dict | Frozen dataclass |
| No-row value | Org's live allocation / Always 0 | Org's live allocation |
| Inactive shops | Compute normally / Return null | Compute normally |
| PG CI shape | Separate job, -m pg_concurrency / Whole suite on Postgres | Separate job |

## Claude's Discretion

- Module names inside apps/credits, enum storage, FilteredRelation vs Subquery, ensure_balance lock mechanics.

## Deferred Ideas

- Postgres immutability trigger; COMMITTED→REFUNDED goodwill refunds; PROTECT handling for future hard-delete / Phase 28 reset.
