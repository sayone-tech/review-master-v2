---
phase: "33"
slug: "credit-visibility-staff-scoping"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-12"
---

# Phase 33 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Staff browser / JWT client -> GET /api/v1/shops/ and /api/v1/shops/{id}/ | Visible shop set must be limited to StaffAccessScope | Shop details, credit annotations (tenant-confidential) |
| StaffAccessScope rows -> region expansion | `get_accessible_shop_ids` region expansion is not organisation-bounded | Shop ids |
| Django template -> `credit-contact` json_script bootstrap | Admin-editable organisation name rendered into Shops and Reviews pages | Organisation name, support address (low) |
| Staff / Org Admin -> GET /api/v1/audit-logs/ | Role decides which events (credit rows) are returned | Audit events, actor names (medium) |
| AuditLog.entity_id (untyped CharField) -> Shop lookup | Id may collide across entity types or name another tenant's shop | Shop name |
| Org/shop names -> mailto URL | Untrusted text becomes URL parameters for the OS mail client | Names, credit numbers |
| Org Admin / Staff -> GET /api/v1/shops/{id}/credits/ | Attacker-controlled path id (IDOR surface); Superadmin must not read tenant balances | Balance numbers (tenant-confidential) |
| Browser / proxy caches -> balance response | Per-user balance must not be stored or replayed | Balance numbers |
| Reviews page composer -> credit-cost / generate-reply | Server enforces scope and spend; client only displays | Cost, remaining |
| Two React roots -> shared credits store | Client-side consistency only | Balance numbers |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-33-01 | Information disclosure | `list_shops` Staff branch | high | mitigate | `restrict_to_staff_scope` keys off `role == STAFF_ADMIN` (apps/shops/selectors/shops.py:21); empty-scope test in apps/shops/tests/test_selectors.py | closed |
| T-33-02 | Information disclosure | Foreign-org region in Staff scope | high | mitigate | Org filter before Staff filter in `list_shops` (shops.py:40-41), `get_accessible_shop_for_credits` (shops.py:64-67), `ShopViewSet.get_queryset` (apps/shops/views.py:175-180) | closed |
| T-33-03 | Information disclosure | Staff retrieve of out-of-scope shop | medium | mitigate | D-17 `get_queryset` override -> 404 (apps/shops/views.py:175) | closed |
| T-33-04 | Information disclosure | Credit numbers of out-of-scope shops | high | mitigate | Staff filter applied before `annotate_credit_state` (shops.py:41,53) | closed |
| T-33-05 | Denial of service | Shops list N+1 | medium | mitigate | Single FilteredRelation annotation; 1-vs-20 CaptureQueriesContext tests in apps/shops/tests | closed |
| T-33-06 | Tampering / XSS | Org name in credit-contact bootstrap | medium | mitigate | `json_script` in templates/shops/shop_list.html:32; `</script>` org-name test apps/shops/tests/test_views.py:1165 | closed |
| T-33-07 | Information disclosure | Credit audit rows reaching Staff | high | mitigate | `CREDIT_AUDIT_FILTER` used only in `list_audit_logs_for_org` (apps/common/selectors/audit_logs.py:40,80); Staff selector untouched | closed |
| T-33-08 | Information disclosure | `shop_name` naming another tenant's shop | high | mitigate | `When(entity_type="shop")` + `organisation_id=OuterRef("organisation_id")` + text compare (audit_logs.py:58-64) | closed |
| T-33-09 | Denial of service | Non-numeric entity_id cast / per-row lookups | medium | mitigate | `Cast(pk, CharField)` compared to entity_id (audit_logs.py:59); single correlated Subquery; query-count test; PostgreSQL run in 33-07 | closed |
| T-33-10 | Information disclosure | Superadmin names visible to Org Admins | low | accept | See Accepted Risks AR-33-01 | closed |
| T-33-11 | Information disclosure | Review/reason text in credit after_data | low | accept | See Accepted Risks AR-33-02 | closed |
| T-33-12 | Tampering | mailto parameter / line injection | medium | mitigate | CR/LF replaced and `encodeURIComponent` (frontend/src/widgets/credits/mailto.ts:17,61-62); hostile-name tests in mailto.test.ts | closed |
| T-33-13 | Information disclosure | Review text in mailto | medium | mitigate | `buildCreditRequestMailto` signature takes no review data; prohibition test | closed |
| T-33-14 | Spoofing | Misleading purchase flow / SLA | low | mitigate | No form controls; tests assert no inputs and no "24 hours" (BuyMoreCreditsModal.test.tsx:207-213) | closed |
| T-33-15 | Tampering | NaN/null credits_remaining in store | low | mitigate | `Number.isFinite` guard (creditsStore.ts:36) | closed |
| T-33-16 | Information disclosure | IDOR on /shops/{id}/credits/ | high | mitigate | `get_accessible_shop_for_credits` -> 404 before any balance read (apps/credits/views.py:171-181); scope sweep test_scope_sweep.py | closed |
| T-33-17 | Information disclosure | 403 vs 404 existence probing | low | mitigate | Uniform 404 `shop_not_found` body (credits/views.py:177-181) | closed |
| T-33-18 | Elevation of privilege | Superadmin / org-less user reading tenant credits | medium | mitigate | `IsOrgScoped` (credits/views.py:156); 403 test test_shop_credits_view.py:289 | closed |
| T-33-19 | Tampering | Read materialising a balance row | high | mitigate | View calls only read-only `get_shop_credit_balance` (credits/views.py:183); row-count assertions in tests | closed |
| T-33-20 | Information disclosure | Cached balance served to another user | medium | mitigate | `Cache-Control: no-store` (credits/views.py:185); asserted test_shop_credits_view.py:94 | closed |
| T-33-21 | Denial of service | Hammering the card read | low | mitigate | `ScopedRateThrottle` `shop_credits` 120/minute (config/settings/base.py:441); 429 test | closed |
| T-33-22 | Tampering | Client cost diverging from server charge | medium | mitigate | Cost from credit-cost / 402 body only (ReplyComposer.tsx:173); server 402 remains authority | closed |
| T-33-23 | Information disclosure | Review comment in composer mailto | medium | mitigate | Composer passes only shop name + numbers; `SECRET-REVIEW-TEXT` test (ReplyComposer.test.tsx:140) | closed |
| T-33-24 | Tampering / XSS | Org name in Reviews bootstrap | medium | mitigate | `json_script` in templates/reviews/review_list.html:10; bootstrap test apps/reviews/tests/test_views.py | closed |
| T-33-25 | Information disclosure | Staff seeing other shop balance via composer | low | accept | See Accepted Risks AR-33-03 | closed |
| T-33-26 | Information disclosure | Stale numbers after fast shop switch | low | mitigate | AbortController + shopId guard (frontend/src/widgets/credits/CreditsCard.tsx:33-52) | closed |
| T-33-27 | Denial of service | Divide-by-zero at total 0 | low | mitigate | `creditBarPercent` returns 0 when total <= 0 (creditBand.ts:22-23) | closed |
| T-33-28 | Tampering | Double Escape closing both modals | low | mitigate | Sibling Buy More modal + `dismissible` on ShopDetailsModal (ShopDetailsModal.tsx:19,58,74); two-Escape test | closed |
| T-33-29 | Information disclosure | Badge colour as sole state carrier | low | mitigate | Text + title + aria-label (CreditBadge.tsx:45); CreditBadge.test.tsx | closed |
| T-33-30 | Elevation of privilege / Info disclosure | Missed scoping gap across phase | high | mitigate | Whole-phase walk-through apps/credits/tests/test_phase33_flow.py; scope sweep + route guard; tenant-security review dispositions in 33-07-SUMMARY (run inline, not as subagent) | closed |
| T-33-31 | Denial of service | Query regressions / PostgreSQL-only failures | medium | mitigate | 85 tests green on throwaway PostgreSQL (33-07-SUMMARY); 1-vs-20 query tests | closed |
| T-33-32 | Repudiation / operational | Staff list behaviour change surprises | low | mitigate | "Phase 33 behaviour changes" in docs/sre/v0.9-credits-rollout.md | closed |
| T-33-SC | Tampering | npm/pip/cargo installs | low | accept | See Accepted Risks AR-33-04 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-33-01 | T-33-10 | Org Admins seeing which Superadmin changed their credits is expected (research open question 2); Staff dropdown excludes Superadmin; pinned by `test_actor_dropdown_includes_superadmin_for_org_admin_not_for_staff` | Plan-time decision (33-02), confirmed 33-07 | 2026-11-12 |
| AR-33-02 | T-33-11 | Credit audit writers store ids and counters only (`has_reason` boolean); serializer omits before_data | Plan-time decision (33-02) | 2026-11-12 |
| AR-33-03 | T-33-25 | credit-cost endpoint already Staff-scoped (Phase 30, re-asserted by 33-04 sweep); composer only shows numbers for reviews the Staff user can open | Plan-time decision (33-05) | 2026-11-12 |
| AR-33-04 | T-33-SC | No packages installed in any Phase 33 plan | Plan-time decision (all plans) | 2026-11-12 |

Follow-ups recorded in 33-07-SUMMARY (pre-existing, outside SCOPE-01, not phase threats): `ReviewTargetViewSet` list/history not Staff-scoped (low-medium, same-tenant); `allocation_status` / `has_regions` org aggregates visible to Staff (low).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-12 | 33 | 33 | 0 | gsd-secure-phase (L1 grep verification, orchestrator short-circuit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-12
