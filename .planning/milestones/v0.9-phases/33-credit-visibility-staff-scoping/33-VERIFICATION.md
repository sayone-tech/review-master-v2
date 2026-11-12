---
phase: 33-credit-visibility-staff-scoping
verified: 2026-11-12T01:45:00Z
status: human_needed
score: 6/6 must-haves verified
covered_files:
  - ".planning/phases/33-credit-visibility-staff-scoping/33-01-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-01-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-02-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-02-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-03-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-03-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-04-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-04-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-05-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-05-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-06-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-06-SUMMARY.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-07-PLAN.md"
  - ".planning/phases/33-credit-visibility-staff-scoping/33-07-SUMMARY.md"
  - "apps/common/selectors/audit_logs.py"
  - "apps/common/serializers.py"
  - "apps/credits/api_urls.py"
  - "apps/credits/serializers.py"
  - "apps/credits/services/periods.py"
  - "apps/credits/tests/test_phase33_flow.py"
  - "apps/credits/tests/test_scope_sweep.py"
  - "apps/credits/tests/test_shop_credits_view.py"
  - "apps/credits/views.py"
  - "apps/reviews/views.py"
  - "apps/shops/selectors/shops.py"
  - "apps/shops/serializers.py"
  - "apps/shops/views.py"
  - "config/settings/base.py"
  - "frontend/src/entrypoints/shop-management.tsx"
  - "frontend/src/widgets/audit-log/AuditLogTable.tsx"
  - "frontend/src/widgets/audit-log/TypePill.tsx"
  - "frontend/src/widgets/audit-log/types.ts"
  - "frontend/src/widgets/credits/BuyMoreCreditsModal.tsx"
  - "frontend/src/widgets/credits/CreditBadge.tsx"
  - "frontend/src/widgets/credits/CreditsCard.tsx"
  - "frontend/src/widgets/credits/contact.ts"
  - "frontend/src/widgets/credits/creditBand.ts"
  - "frontend/src/widgets/credits/creditsApi.ts"
  - "frontend/src/widgets/credits/creditsStore.ts"
  - "frontend/src/widgets/credits/format.ts"
  - "frontend/src/widgets/credits/mailto.ts"
  - "frontend/src/widgets/review-management/ReplyComposer.tsx"
  - "frontend/src/widgets/review-management/api.ts"
  - "frontend/src/widgets/shop-management/ShopDetailsModal.tsx"
  - "frontend/src/widgets/shop-management/ShopModals.tsx"
  - "frontend/src/widgets/shop-management/ShopTable.tsx"
  - "frontend/src/widgets/shop-management/types.ts"
  - "frontend/src/widgets/shop-management/useShops.ts"
  - "templates/reviews/review_list.html"
  - "templates/shops/shop_list.html"
covered_digest: "v4:sha256:74921e9d8c188202871c69b783338180cf8e62f02f7d92d9ba82297eeb21d8bc"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Credit colour bands in a real browser (Shop Details card progress bar, Shops-list CREDITS badge, composer status line)"
    expected: "green above 25%, amber 5-25%, red below 5%, dark grey for 0 credits, muted grey for Not enabled; every state also reads as text, and contrast is acceptable"
    why_human: "Band thresholds are unit-tested in creditBand.test.ts, but the rendered Tailwind colours and contrast cannot be judged by grep or jsdom"
  - test: "Contact Admin mailto opens the default mail client with the right content"
    expected: "Clicking Contact Admin from the card, the Shops-list badge and the composer opens a draft addressed to REVIEWBEE_SUPPORT_EMAIL with subject 'Credit request — {Org} / {Shop}' and the shop/month/balance lines, with no review text"
    why_human: "mailto handoff to an OS mail client cannot be exercised in jsdom; only the generated URL is tested"
  - test: "Reply composer layout at 360px width"
    expected: "Credit status line, 'Generate with AI · N credits' button, tone pills and Buy More Credits link wrap without overflow or clipped text"
    why_human: "Responsive layout needs a real viewport"
  - test: "Two-Escape ordering for Buy More over Shop Details"
    expected: "Opening Buy More from the card, then pressing Escape once closes only Buy More; a second Escape closes Shop Details; focus returns sensibly and the focus trap holds in both"
    why_human: "Stacked focus-trap and keydown ordering is covered with jsdom stubs (Element.getClientRects stubbed); real browser focus behaviour is unproven"
  - test: "Screen-reader announcement of composer credit state changes (loading, ready, not enabled, insufficient, after a 402)"
    expected: "The role=status line announces the new state without a duplicate or missing announcement, and focus lands on the textarea after a 402"
    why_human: "aria-live behaviour needs assistive technology"
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  status: human_needed
---

# Phase 33: Credit Visibility & Staff Scoping Verification Report

**Phase Goal:** Before they generate, Org Admins and Staff can see how many AI reply credits a shop has and what a reply will cost, on Shop Details, the Shops list, and in the reply composer. Staff only ever see credits for shops in their scope.
**Verified:** 2026-11-12T01:45:00Z
**Status:** human_needed
**Re-verification:** No - initial verification

All code-level must-haves are verified against the actual codebase. Status is `human_needed` only because five items need a real browser, mail client or screen reader (listed above and below). No gaps were found.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Shop Details shows an "AI Reply Credits" card: remaining / total, colour-coded bar, used and available, org allocation and bonus, "Renews {date} (UTC)", "Not enabled" state at total 0, Buy More link; a shop with no activity shows its full allocation | VERIFIED | `CreditsCard.tsx` renders every element: `remaining / total`, `role=progressbar` with `BAR_BAND_CLASSES[band]`, `{used} used · {available} available`, `Monthly {allocated} · Bonus {bonus}`, `Renews {renews} (UTC)`, a `not_enabled` branch with no bar, and Buy More buttons in both branches. It is mounted in `ShopDetailsModal.tsx` and fetches `GET /api/v1/shops/{id}/credits/` on every mount. Backend `get_shop_credit_balance` returns the live org allocation for a shop with no row (virtual balance, no writes); `test_shop_credits_view.py` asserts this. |
| 2 | Every Shops list row shows a colour-coded credits badge that also uses text; list query count is the same for 1 shop or 20 | VERIFIED | `CreditBadge.tsx` renders text ("N credits" / "Not enabled") plus band class, title and aria-label, in a CREDITS column in `ShopTable.tsx`. `list_shops(with_credits=True)` uses `annotate_credit_state` (one FilteredRelation LEFT JOIN + Coalesce, no per-row query). `test_list_query_count_is_equal_for_1_and_20_shops_when_credits_enabled` passes. |
| 3 | Composer: AI button hidden for star-only reviews; label and aria-label "Generate with AI · N credits" with remaining shown; disabled with distinct not-enabled vs not-enough messages; tone pills disabled while generating; 402 updates the composer, no generic error | VERIFIED | `ReplyComposer.tsx`: button rendered only when `hasReviewText`; `aiButtonLabel` is used for both `aria-label` and text; single derived `creditState` drives the status line ("This shop has N remaining", "AI replies aren't enabled for this shop.", "Not enough credits - this reply needs X, you have Y."); `disabled={aiButtonDisabled}`; pills `disabled={generatingTone !== null}`; `readInsufficientCredits` branch adopts the server's numbers, keeps the draft, shows no banner. Cost only comes from `getCreditCost` or the 402 body. 21 composer tests pass. |
| 4 | Buy More Credits modal opens from the card, Shops-list badge and composer; Contact Admin mailto to `REVIEWBEE_SUPPORT_EMAIL`; focus trap, ARIA labels, ESC/backdrop close; no payment flow | VERIFIED | `BuyMoreCreditsModal.tsx` is built on the shared `Modal` (focus-trap-react, `role=dialog`, `aria-modal`, `aria-label`, Escape and backdrop close). Opened from `CreditsCard` (via `ShopModals`), from the badge (`shop:open-credits` event opens Shop Details focused on the card, which hosts the modal trigger) and from the composer's insufficient state. `mailto.ts` URL-encodes, strips CR/LF and takes no review data. `REVIEWBEE_SUPPORT_EMAIL` exists in `config/settings/base.py:253` and reaches both pages through the `credit-contact` json_script. No payment UI. See Warnings: the composer offers Buy More only in the insufficient state, by design (D-07). |
| 5a | Org Admins see `shop.credits.*` and `organisation.credits.set` events in the Activity Log; Staff do not | VERIFIED | `list_audit_logs_for_org` filters `AUDIT_ENTITY_FILTER \| CREDIT_AUDIT_FILTER` and annotates `shop_name` (gated on `entity_type="shop"`, org-bounded, text-compared). `AUDIT_ENTITY_FILTER` and the Staff selector are unchanged, so credit rows never reach Staff. Frontend adds the Credits pill and seven labels. Selector and API tests (incl. Staff exclusion with PK collisions) pass. |
| 5b | Shops list and every credit endpoint return only shops in a Staff user's StaffAccessScope; negative tests prove cross-org, out-of-scope Staff and Staff-on-Superadmin calls are refused | VERIFIED | `restrict_to_staff_scope` keys off `role == STAFF_ADMIN` (never id-list truthiness), so a Staff user with zero scope rows gets an empty list. It is applied in `list_shops`, in `ShopViewSet.get_queryset` (retrieve 404, D-17) and, via `get_accessible_shop_for_credits`, in `ShopCreditsView`. `test_scope_sweep.py` is table-driven over every route in `apps/credits/api_urls.py` with a guard test that fails if a route has no row; rows include Staff in/out of scope, other-org admin, Superadmin and anonymous, and Staff against the Superadmin endpoints, each asserting nothing is written. |

**Score:** 6/6 truths verified (roadmap SC5 split into 5a and 5b); 0 present-but-behavior-unverified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/shops/selectors/shops.py` | role-keyed Staff scoping, credit annotation, single credits gate | VERIFIED | `restrict_to_staff_scope`, `list_shops(with_credits, period)`, `get_accessible_shop_for_credits`; wired in `views.py` list/retrieve and `credits/views.py` |
| `apps/credits/views.py` + `api_urls.py` | `ShopCreditsView` at `shops/<int:shop_id>/credits/` | VERIFIED | `IsOrgScoped`, throttle scope `shop_credits` (120/minute, in settings), `Cache-Control: no-store`, uniform 404 `shop_not_found`, read-only |
| `apps/common/selectors/audit_logs.py` | Org-only credit filter + shop name | VERIFIED | `CREDIT_AUDIT_FILTER`, `_shop_name_annotation` |
| `apps/shops/serializers.py` | credits_* fields | VERIFIED | four fields, null on un-annotated rows (see WR-03) |
| `frontend/src/widgets/credits/*` | card, badge, modal, band helper, store, mailto, api, format | VERIFIED | all substantive and imported by the shop and review widgets |
| `ReplyComposer.tsx`, `review-management/api.ts` | credit-aware composer, `getCreditCost`, 402 parsing | VERIFIED | state machine confirmed in code |
| `templates/shops/shop_list.html`, `templates/reviews/review_list.html` | `credit-contact` bootstrap | VERIFIED | `json_script` present in both; views supply `credit_contact` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ShopTable` badge | `ShopModals` | `shop:open-credits` window event | WIRED | listener sets selected shop and `focusCredits` |
| `ShopDetailsModal` | `CreditsCard` | direct mount with `key={shop.id}` | WIRED | `onBuyMore` lifts to `ShopModals` sibling `BuyMoreCreditsModal` |
| `CreditsCard` | `/api/v1/shops/{id}/credits/` | `getShopCredits` | WIRED | route resolves to `ShopCreditsView` |
| `ReplyComposer` | credit-cost and generate-reply | `getCreditCost`, `generateReply`, `readInsufficientCredits` | WIRED | store updated by `setShopCredits` after each |
| Shops list and card/composer | one balance | module store `creditsStore` via `useSyncExternalStore` | WIRED | list rows seed the store; card and composer write it |
| `ShopViewSet` / `ShopCreditsView` / `list_shops` | one Staff rule | `restrict_to_staff_scope` | WIRED | list, retrieve and credits GET cannot disagree |
| Org audit selector | Activity Log UI | `shop_name` on `AuditLogReadSerializer` | WIRED | `AuditLogTable` renders "Credits used - {shop}" |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `CreditsCard` | `credits` | `GET shops/{id}/credits/` -> `get_shop_credit_balance` (ShopCreditBalance row or live org allocation) | Yes | FLOWING |
| `CreditBadge` | `remaining`, `total` | `ShopReadSerializer` fields from `annotate_credit_state` (list) and the store | Yes | FLOWING |
| `ReplyComposer` | `cost`, `credits` | Phase 30 credit-cost endpoint and 402 body; store | Yes | FLOWING |
| Activity Log credit rows | `shop_name`, `after_data` | `AuditLog` rows written by Phase 29-32 services | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 33 backend tests (scope sweep, credits view, walk-through, shops selectors/views, audit log, reviews views) | `.venv/bin/pytest <8 files> --no-cov -q` | all passed (0 failures) | PASS |
| Phase 33 frontend tests | `npx vitest run src/widgets/credits src/widgets/shop-management src/widgets/review-management src/widgets/audit-log` | 16 files, 183 tests passed | PASS |
| Types | `npx tsc --noEmit` | no output (clean) | PASS |
| Lint | `.venv/bin/ruff check apps/credits apps/shops apps/common` | All checks passed | PASS |

The full suite figures (1650 backend / 349 frontend) come from 33-07-SUMMARY and the orchestrator's note; this verifier re-ran only the phase-scoped subsets above, not the full suite.

### Probe Execution

SKIPPED - the phase declares no probes.

### Requirements Coverage

All six IDs appear in plan frontmatter (33-01: SCOPE-01, CVIS-02, CVIS-04; 33-02: CVIS-05; 33-03: CVIS-04, CVIS-01, CVIS-02; 33-04: CVIS-01, SCOPE-01; 33-05: CVIS-03, CVIS-04; 33-06 and 33-07 cover the rest). REQUIREMENTS.md maps exactly these six IDs to Phase 33 and marks them Complete; there are no orphaned requirements.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CVIS-01 | 33-03, 33-04, 33-06 | Shop Details AI Reply Credits card | SATISFIED | Truth 1 |
| CVIS-02 | 33-01, 33-03, 33-06 | Shops-list badge, fixed query count | SATISFIED | Truth 2 |
| CVIS-03 | 33-05 | Composer cost label and states, 402 handling | SATISFIED | Truth 3 |
| CVIS-04 | 33-01, 33-03, 33-05, 33-06 | Buy More modal, mailto, accessible, no payment | SATISFIED | Truth 4 |
| CVIS-05 | 33-02 | Org-only credit events in Activity Log | SATISFIED | Truth 5a |
| SCOPE-01 | 33-01, 33-04 | Staff scoping on Shops list and credit endpoints, negative tests | SATISFIED | Truth 5b |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/widgets/shop-management/ShopTable.tsx` | 136 | `TODO: fetch full region list from API` | Info | Pre-existing; not in the phase diff, and not a debt marker (TBD/FIXME/XXX). No debt markers were introduced by this phase. |

No stubs, hollow props or static-return data sources were found in the phase's non-test files.

### Warnings (non-blocking, carried from 33-REVIEW.md and my own reading)

These do not fail a must-have and do not change the status. They are recorded so they are not lost.

1. **WR-01 (medium, open in 33-REVIEW-DISPOSITION.md):** `AuditLogFilterSet` was not extended. `?entity_type=shop|organisation` returns 400, and filtering the log by shop drops that shop's `shop.credits.*` rows. Org Admins can see credit events in the default list (CVIS-05 as written is met) but cannot isolate or filter them. Confirmed by reading the review; `apps/common/filters.py` is not in the phase diff.
2. **WR-02 (medium, open):** Credit audit rows pass `after_data` through verbatim to Org Admins (internal ids such as `ai_usage_log_id`, `transaction_id`, internal `reason`) and expose Superadmin actor names. The Superadmin-name visibility was an accepted decision (research open question 2, pinned by test and recorded in 33-07); the internal-identifier exposure was not separately decided. 33-SECURITY.md reports threats_open 0, so this is a recommendation, not a failed threat.
3. **WR-03 / IN-01..IN-04 (low):** credit fields are null on retrieve/create/update responses (list-only); Staff paths on the Shops page are unreachable (see next item); empty support-email handling in the modal; minor coupling and OpenAPI/doc drift.
4. **Staff and the Shops page (deliberate, D-18):** `shop_list` is `@org_admin_required`, so Staff never reach the Shops page, Shop Details or the Shops badge in the UI. They see credits only in the reply composer. SCOPE-01 is enforced at the API (list, retrieve, credits GET), which is what the success criterion tests. The goal sentence reads as if Staff see credits on all three surfaces; the recorded decision narrows that for now. Worth a conscious product acknowledgement, not a gap.
5. **Review gap noted in 33-07:** the four section-27 reviews were walked inline because the Agent tool was unavailable; no independent subagent pass has happened. 33-07 recommends one before the PR.
6. **Composer Buy More link** appears only in the insufficient state; the not-enabled state deliberately has none (D-07), consistent with the UI spec and with the card, which does offer it for not-enabled.

### Human Verification Required

### 1. Credit colour bands in a real browser

**Test:** View Shop Details, the Shops list and a composer for shops at roughly 80%, 20%, 3%, 0 and "not enabled".
**Expected:** green, amber, red, dark grey and muted grey respectively, each also readable as text, with acceptable contrast.
**Why human:** Band logic is unit-tested; rendered colour and contrast are not.

### 2. Contact Admin mailto

**Test:** Click Contact Admin from the card, the Shops-list badge path and the composer.
**Expected:** the mail client opens a draft to `REVIEWBEE_SUPPORT_EMAIL` with the encoded subject and shop/month/balance body, and no review text.
**Why human:** OS mail handoff cannot be tested in jsdom.

### 3. Composer at 360px

**Test:** Open a composer on a 360px viewport in each credit state.
**Expected:** no overflow or clipping of the status line, button label, tone pills or Buy More link.
**Why human:** needs a real viewport.

### 4. Two-Escape modal ordering

**Test:** Open Shop Details, open Buy More from the card, press Escape twice.
**Expected:** first Escape closes Buy More only; second closes Shop Details; focus is trapped and restored correctly each time.
**Why human:** jsdom stubs layout for focus-trap; real focus ordering is unproven.

### 5. Screen-reader announcements

**Test:** Walk the composer through loading, ready, not-enabled, insufficient and a 402 with a screen reader.
**Expected:** each state change is announced once via the status line and focus lands on the textarea after a 402.
**Why human:** needs assistive technology.

### Gaps Summary

No gaps. Every roadmap success criterion and every requirement ID is backed by code that exists, is substantive, is wired, and carries real data, and the phase-scoped backend and frontend tests, `tsc` and `ruff` all pass in this verifier's own runs. The status is `human_needed` solely because of the five browser, mail-client and assistive-technology checks above. Open review items WR-01 and WR-02 are worth triaging before the milestone ships, and the Staff-sees-credits-only-in-composer decision (D-18) should be acknowledged.

---

_Verified: 2026-11-12T01:45:00Z_
_Verifier: Claude (gsd-verifier)_
