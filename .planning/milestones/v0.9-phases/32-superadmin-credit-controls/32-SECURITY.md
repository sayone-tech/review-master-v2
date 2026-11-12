---
phase: "32"
slug: "superadmin-credit-controls"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-11"
---

# Phase 32 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Superadmin client → OrganisationViewSet create/PATCH | Only Superadmin may set `monthly_credit_allocation` | allocation int |
| Superadmin client → CreditShopListView / BonusAllocationView | Non-tenant Superadmin endpoints; org/shop derived server-side | org id (URL), shop id, amount, period echo, reason |
| org edit / bonus ↔ request-path credit writers | Concurrent writers on the org row and balance rows (reserve, first-use ensure_balance, refund, lapse) | counters, ledger rows |
| services → AuditLog / logs | No free-text reason or PII in audit payloads or logs | ids, ints, `has_reason` |
| browser → bonus POST | Cross-origin forgery | CSRF token |
| operators → runbook | Allocation changes must go through the UI service, not admin/queryset updates | — |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-32-01 | Elevation of privilege | OrganisationViewSet create/PATCH with allocation | high | mitigate | `IsAuthenticated + IsSuperadmin`; field only on Superadmin serializers; tenant audit: no serializer uses `__all__`/`exclude`, no other write path | closed |
| T-32-02 | Tampering | Mass assignment via `update_organisation` | medium | mitigate | `_UPDATABLE_FIELDS` whitelist; serializer bounds | closed |
| T-32-03 | Tampering | Concurrent org edits computing CRED-06 from a stale old value | high | mitigate | Atomic; old value read under org row lock `select_for_update(of=("self",), no_key=True)` | closed |
| T-32-04 | Tampering | New value saved before materialising | high | mitigate | Materialise helpers run before the field save in the same atomic; tracer + matrix tests | closed |
| T-32-05 | Tampering | Django admin edit bypassing materialisation/audit | medium | mitigate | Field read-only in OrganisationAdmin (D-22); test | closed |
| T-32-06 | Repudiation | Allocation change with no trace | medium | mitigate | One `organisation.credits.set` AuditLog per real change / create > 0 | closed |
| T-32-07 | Denial of service | Org edit holding the org lock while looping per shop | medium | mitigate | Set-based helpers, constant 7/5 queries (ORM audit counted); first-edit-of-month ~1,000-row inserts estimated 100–300 ms — confirm on staging | closed |
| T-32-08 | Information disclosure | Names/emails/free text in audit or logs | low | mitigate | Ids and ints only (tenant audit check 4) | closed |
| T-32-09 | Tampering | Stale Edit form reverting another admin's change | medium | mitigate | EditOrgModal sends the allocation only when changed since open | closed |
| T-32-10 | Repudiation / user error | Hint claiming "immediate" when server defers (D-18) | medium | mitigate | Hint keys on server `current_month_credit_allocation`; backend rule matches (code review confirmed) | closed |
| T-32-11 | Tampering | Client-side validation bypass | low | accept | Server serializer, model validators and DB CHECK enforce 0..10000 | closed |
| T-32-12 | Elevation of privilege | CreditShopListView / BonusAllocationView | high | mitigate | `[IsAuthenticated, IsSuperadmin]`, scoped throttles; 403 tests for Org Admin/Staff/anonymous; real tenant-security-auditor run: no HIGH | closed |
| T-32-13 | Tampering | Organisation spoofing in bonus body | medium | mitigate | No org field accepted; org read from Shop row | closed |
| T-32-14 | Tampering | Stale-period write after UTC rollover | high | mitigate | Period echo compared before any write; 409 path read-only | closed |
| T-32-15 | Tampering | Lost update / overspend under concurrent bonus and reserve | high | mitigate | One atomic: org lock → ensure_balance → balance lock → `F()` increment + ledger + audit; PG concurrent-bonus test | closed |
| T-32-16 | Denial of service | Deadlock between bonus, org edit and reserve | medium | mitigate | Real deadlock found by 32-05 PG races and fixed (`no_key=True` on org row lock); ORM audit: no remaining cycle | closed |
| T-32-17 | Information disclosure | Free-text reason in AuditLog/logs | medium | mitigate | Reason only in `CreditTransaction.note`; AuditLog has `has_reason`. Missing `caplog` test noted by tenant audit | closed |
| T-32-18 | Tampering | Bonus to a deactivated shop / deleted org | low | mitigate | Availability check → 404. **Residual:** check runs outside the lock (review WR-02) and after the period check (review WR-03 / tenant LOW 2: stale period + inactive shop → 409 with balance) | open — below high threshold (non-blocking) |
| T-32-19 | Tampering | Replay / double-submit creating two bonuses | low | accept | Each POST is an intentional additive allocation (D-10). **Note:** review WR-04 — a client retry after a lost post-commit response double-credits; no idempotency key | closed |
| T-32-20 | Denial of service | Hammering list/bonus endpoints | low | mitigate | `superadmin_credits_read` 120/min, `superadmin_credits_write` 30/min | closed |
| T-32-21 | Information disclosure | Unscoped read selectors (T-29-19) | medium | mitigate | Callers verified Superadmin-only by tenant audit. **Gap:** no cross-org list test (tenant MEDIUM 1); Phase 33 must add a scoped variant before Org Admin/Staff reuse (tenant LOW 4) | open — below high threshold (non-blocking) |
| T-32-22 | Tampering | Double-submit creating two bonuses | low | mitigate | Allocate disabled on first click + early return; single-POST test | closed |
| T-32-23 | Tampering | Writing to the wrong month after rollover | medium | mitigate | Period echoed; 409 swaps in server period and requires a fresh click | closed |
| T-32-24 | Information disclosure / XSS | Tenant shop names in the modal | low | mitigate | React text nodes only | closed |
| T-32-25 | Spoofing (CSRF) | Bonus POST from another origin | medium | mitigate | `X-CSRFToken` via shared helper, same-origin credentials; Django CSRF middleware (tenant audit check 6) | closed |
| T-32-26 | Elevation of privilege | UI hiding as the only guard | low | transfer | Server `IsSuperadmin` is authoritative | closed |
| T-32-27 | Tampering | Lost/double bonus under concurrency | high | mitigate | Concurrent-bonus PG test asserts exact sums (20 pg_concurrency passed, 0 skipped on PG14) | closed |
| T-32-28 | Denial of service | Deadlock between org edit, bonus, reserve | high | mitigate | Three PG races with bounded joins; failed before the 32-05 fix, pass after | closed |
| T-32-29 | Tampering | Zero-allocation row after a race with a 0 → N edit | high | mitigate | 6-round two-ordering PG test for bonus vs edit. **Disputed (review WR-01 vs ORM audit):** reviewer flags first-use generate vs 0 → N edit via `ensure_balance`'s unlocked allocation read; ORM audit says `reserve_credits`' read-only pre-check rejects 0 so no zero row is created — routed to the verifier | closed (pending verifier) |
| T-32-30 | Tampering / Repudiation | Operators bypassing CRED-06 via admin/queryset | medium | mitigate | Runbook rewritten to the Superadmin UI / `update_organisation` | closed |
| T-32-31 | Elevation of privilege | Missed authorisation gap | high | mitigate | Real `tenant-security-auditor` + `orm-performance-auditor` + `gsd-code-reviewer` runs 2026-11-11, no HIGH/BLOCKER | closed |
| T-32-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed; frontend deps already pinned | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-32-01 | T-32-11 | Client checks are UX only; three server-side layers enforce range | plan-time decision (32-02 PLAN) | 2026-11-11 |
| AR-32-02 | T-32-19 | Bonuses are intentionally additive (D-10); review WR-04 retry double-credit tracked in 32-REVIEW-DISPOSITION.md | plan-time decision (32-03 PLAN) | 2026-11-11 |
| AR-32-03 | T-32-SC | No new dependencies | plan-time decision | 2026-11-11 |

Other audit follow-ups (not threats): `apps/shops/services/shops.py:32` still takes a full `FOR UPDATE` on the org row — switch to `no_key=True` to avoid blocking credit inserts (ORM LOW); bonus/allocation audit rows show the Superadmin actor to Org Admins in the Activity Log — confirm intended (tenant LOW 3; relevant to Phase 33 CVIS-05).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-11 | 32 | 30 | 2 (low/medium; threats_open: 0) | secure-phase orchestrator (ASVS L1) + tenant-security-auditor + orm-performance-auditor + gsd-code-reviewer |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (no open threat at or above `high`)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-11 (2 non-blocking residuals open; T-32-29 dispute routed to the goal verifier)
