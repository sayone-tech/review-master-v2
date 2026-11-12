---
phase: "29"
slug: "credits-ledger-foundation"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-11"
---

# Phase 29 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| internal caller → `ensure_balance` | Later phases pass a `shop_id`; the service must not trust a caller-supplied organisation or allocation | shop id (internal) |
| DB constraints ↔ concurrent workers | Concurrent first uses race on one (shop, month); only the DB unique index decides the winner | balance rows |
| CI runner → throwaway Postgres | Test-only service container with fixed throwaway credentials | none (ephemeral test data) |
| Django admin / API → `Organisation.monthly_credit_allocation` | New field must not become API-writable before Phase 32 | allocation integer |
| application code → ledger table | Any ORM path (QuerySet bulk ops, instance save/delete) could rewrite settled history | ledger rows |
| Django admin (staff/superuser) → ledger + balance | Investigation surface that must not become an edit surface | ids, counts, optional note |
| concurrent settlers (Phase 30 commit vs Phase 31 reaper) → one RESERVED row | Two writers race to settle the same reservation | status column |
| settings → pricing | Tier config controls what every reply costs | tier table |
| server price → UI / Phase 30 charge | Price shown and price charged must come from one function | cost integer |
| selector callers (Phase 32/33 endpoints) → balance reads | Selectors are unscoped primitives; endpoints add tenant/Staff scope | balance figures |
| read path → balance table | Reads must not materialise rows (CRED-06 semantics) | none |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-29-01 | Tampering | `ensure_balance` first-use race | high | mitigate | `credit_balance_shop_period_uniq` + partial unique `credit_tx_one_initial_per_balance` (`apps/credits/models.py`); 8-thread pg_concurrency test | closed |
| T-29-02 | Tampering | ShopCreditBalance invariants | high | mitigate | CHECKs `credit_balance_nonneg` / `_no_overspend` / `_month_range`; proven in `test_models.py` | closed |
| T-29-03 | Information disclosure | `shop.credits.allocated` AuditLog `after_data` | medium | mitigate | after_data restricted to period + `allocated_credits`; exact key-set test | closed |
| T-29-04 | Elevation of privilege | Mass assignment of `monthly_credit_allocation` | medium | mitigate | Field referenced only in model, credits services/selectors; organisations serializers/services/admin untouched (explicit `fields` lists) | closed |
| T-29-05 | Spoofing | Wrong organisation on a balance | medium | mitigate | Org derived from Shop row inside `ensure_balance`; test asserts `balance.organisation == shop.organisation` | closed |
| T-29-06 | Repudiation | backend-pg green with zero tests | high | mitigate | `REQUIRE_PG=1` collection hook exits 3 off-PG (`conftest.py`, verified); `-rs` in `ci.yml` | closed |
| T-29-07 | Information disclosure | CI Postgres credentials in `ci.yml` | low | accept | Throwaway `app/app` creds for ephemeral container | closed |
| T-29-08 | Tampering | Out-of-range org allocation | medium | mitigate | DB CHECK `org_monthly_credit_allocation_range` (0..10000) + validators | closed |
| T-29-09 | Denial of service | PROTECT FKs block org/shop hard-delete | low | accept | D-02 decision; deferred Phase 28 reset must handle PROTECT | closed |
| T-29-10 | Tampering | CreditTransaction ORM write paths | high | mitigate | `CreditTransactionQuerySet` raises `AppendOnlyViolation` on update/delete/bulk_update; instance delete raises (`managers.py`, `test_append_only.py`) | closed |
| T-29-11 | Tampering / Repudiation | Django admin for credit models | high | mitigate | add/change/delete permissions False; `test_admin.py` asserts 403 | closed |
| T-29-12 | Tampering | Status transitions | high | mitigate | `ALLOWED_STATUS_TRANSITIONS` + single conditional UPDATE (`services/ledger.py`); 8-thread CAS race test | closed |
| T-29-13 | Tampering | Raw SQL / `_raw_delete` | medium | accept | D-05: PG trigger rejected (untestable on SQLite); revisit if a non-ORM write path appears | closed |
| T-29-14 | Repudiation | Ledger rows lost on related deletes | medium | mitigate | SET_NULL review/actor/ai_usage_log; PROTECT balance/shop/org; `test_models.py` | closed |
| T-29-15 | Tampering | Wrong-sign deltas / non-consumption RESERVED | medium | mitigate | CHECKs `credit_tx_delta_sign`, `credit_tx_only_consumption_reserved` with named-constraint tests | closed |
| T-29-16 | Information disclosure | Admin exposing ledger rows to staff | low | accept | Requires is_staff + view perm; no review text in rows | closed |
| T-29-17 | Tampering | Duplicate / client-side cost computation | medium | mitigate | `credit_cost` sole reader of tiers setting; `test_settings.py` single-source scan | closed |
| T-29-18 | Tampering | Misconfigured tiers | medium | mitigate | D-10 settings shape test; `credit_cost` total over input | closed |
| T-29-19 | Information disclosure | Cross-org balance reads via unscoped selectors | medium | transfer | No endpoint ships in Phase 29; tenant/StaffAccessScope enforcement transferred to Phase 32/33 endpoints (tenant-security-auditor mandatory) | closed |
| T-29-20 | Tampering | Read path creating balance rows | high | mitigate | Never-writes tests (row counts + no INSERT/UPDATE/DELETE in captured SQL) in `test_selectors.py` | closed |
| T-29-21 | Denial of service | N+1 on Shops-list credit annotation | medium | mitigate | Single `FilteredRelation` LEFT JOIN + Coalesce (`selectors/balances.py`); 1-query tests for 2 and 20 shops | closed |
| T-29-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed in this phase | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-29-01 | T-29-07 | Ephemeral CI service container with throwaway credentials; no real data | plan-time decision (29-01 PLAN) | 2026-11-11 |
| AR-29-02 | T-29-09 | D-02: PROTECT FKs intentional; shops are soft-deactivated only; Phase 28 reset must handle PROTECT | user decision D-02 (29-CONTEXT) | 2026-11-11 |
| AR-29-03 | T-29-13 | D-05: no PG trigger (untestable on SQLite); ORM-level append-only guard only | user decision D-05 (29-CONTEXT) | 2026-11-11 |
| AR-29-04 | T-29-16 | Admin is read-only and gated by is_staff + view permission; rows carry no review text | plan-time decision (29-02 PLAN) | 2026-11-11 |
| AR-29-05 | T-29-SC | No new dependencies installed | plan-time decision | 2026-11-11 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-11 | 22 | 22 | 0 | secure-phase orchestrator (ASVS L1 grep-depth short-circuit; register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-11
