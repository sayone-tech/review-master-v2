# Phase 33 — UI Review

**Audited:** 2026-11-12
**Baseline:** 33-UI-SPEC.md (approved 2026-11-11)
**Screenshots:** not captured (no dev server on localhost:3000, 5173 or 8080; port 8080 answered 404 with no app behind it, so a code-only audit)
**Interaction captures:** off (workflow.ui_interaction_capture is false). Every interaction finding below is derived from code, not observed in a browser.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Contract copy is matched almost verbatim. The card prints credit numbers without thousands separators, and the date format deviates from the spec |
| 2. Visuals | 3/4 | Focal points, icon aria-hidden and the progressbar semantics are all present. Layout could not be checked visually, and the four backstop checks are unverified |
| 3. Color | 3/4 | Band mapping and the accent budget are correct. Three contract hex literals are repeated as arbitrary values instead of tokens |
| 4. Typography | 3/4 | New elements stay on 12/14/24 and 400/600. The Staff empty state ships 15px and 13.5px, off the declared scale |
| 5. Spacing | 3/4 | The card, badge, composer line and Buy More link follow the 4px scale. The Staff empty state uses `mt-1.5` (6px), `py-16` and `mt-4` ad hoc |
| 6. Experience Design | 3/4 | State coverage is thorough: loading, error with retry, not enabled, 402 handling, fail-open, stacked-modal Esc. It is unproven at runtime |

**Overall: 18/24**

---

## Top 3 Priority Fixes

1. **Credit numbers are not formatted with thousands separators in the card.** (WARNING) The contract requires `en-US` separators and caps allocations at 10,000. `CreditsCard.tsx` renders `{credits.remaining}`, `/ {credits.total}` and `Monthly {allocated} · Bonus {bonus}` raw, so a full shop shows `10000 / 10000`. The badge and composer use `creditsLabel` or `formatCount`, so the card disagrees with them. Fix: wrap those four values in `formatCount()` from `org-management/creditHint`.
2. **The Staff empty state is outside the typography and spacing contract.** (WARNING) `ShopTable.tsx:155-158` uses `text-[15px]` for the heading and `text-[13.5px]` for the body, which are not in 12/14/18/24, plus `mt-1.5` (6px). This is the only Staff-visible new surface for SCOPE-01. Fix: heading `text-[14px] font-semibold`, or 18px if it should lead. Body `text-[14px]`. Spacing `mt-2`.
3. **Contract hex colours are scattered as arbitrary values, and the date format deviates from the spec.** (WARNING) `#166534`, `#92400E` and `#991B1B` appear as `text-[#...]` in `creditBand.ts:29-31`, `CreditsCard.tsx:107` and `ReplyComposer.tsx:397`. Promote them to `@theme` tokens (for example `green-ink`, `amber-ink`, `red-ink`) so the AA-contrast decision lives in one place. Separately, `formatUtcDate` renders `Sep` where the spec says en-GB (`Sept`). The plan summary documents this as deliberate, but it is an unratified contract deviation. Either amend the UI-SPEC or restore the contract format.

Further issues (minor): the card heading is a programmatic focus target (`tabIndex={-1}`) with no custom focus style, so a visible ring relies on the browser default. The card skeleton is `aria-hidden` with only `aria-busy` on the container, so screen readers get no loading announcement. The load-error banner has no icon, so the colour-only red signal is backed only by text.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)
- **Matches the contract:**
  - Card: `AI Reply Credits`, `Couldn't load credits.` / `Please try again.`, `Retry Loading Credits`, `AI replies aren't enabled for this shop.`, and `{n} credits used · {n} credits available`.
  - Badge: `Not enabled`, `—`, and the `{n} credits remaining this month` tooltip. Tooltip and `aria-label` are identical (`CreditBadge.tsx:36-40`).
  - Composer: `Checking credits…`, `Not enough credits — this reply needs {cost}, you have {remaining}.` (bare numbers via `formatCount`), `Retry Credit Check`, and the 409 copy.
  - Buy More modal: both body variants and the fallback address line.
  - Staff empty state: heading and body strings match.
- **Deviation:** `format.ts:12-20` produces `1 Sep 2026`. The spec says `en-GB`, which gives `Sept`. The implementation avoids `Date` entirely, which is good for UTC safety, but the label differs from the contract.
- **Deviation:** `CreditsCard.tsx:132-148` omits `formatCount` on the big number, the total, and the Monthly/Bonus values. This conflicts with the "numbers use thousands separators" rule.
- **Minor:** the `credits remaining` caption sits on the same baseline as the 24px number. For a one-credit shop it reads `1 / 100 credits remaining`, which is acceptable.
- No generic `Submit` / `OK` labels were introduced by this phase.

### Pillar 2: Visuals (3/4)
- **Focal points follow the contract:**
  - The card's 24px number is the anchor, with the 8px bar supporting it.
  - Badge text and band colour carry the Shops-list signal, with the shop name column still primary.
  - `Contact Admin` is the single yellow control in Buy More.
  - The in-card Buy More is a white secondary button, so the Shop Details footer keeps exactly one yellow control (`ShopDetailsModal.tsx:112-120`).
- **Accessibility details are in place:**
  - Decorative `Coins` and `Mail` icons are `aria-hidden`.
  - The progress bar has `role="progressbar"` with min, max, now and text values.
  - Disabled AI button reasons are announced through `aria-describedby` plus `role="status"`.
- **Not verifiable without a browser:**
  - The 360px wrap checks for the insufficient message and for the `Generate with AI · 3 credits` + `Use template` pair.
  - The visual stacking of Buy More over Shop Details.
  - The tone-pill `· N cr` label width.
- No screenshots were captured, so the score is capped at 3.
- **Minor:** `<h3>` in the card sits inside a modal whose title is the shop name. Heading levels are plausible but unverified in the DOM.

### Pillar 3: Color (3/4)
- **Band mapping is correct and matches the contract table:**
  - `BADGE_BAND_CLASSES` and `BAR_BAND_CLASSES` give green, amber, red, empty (`bg-muted text-white`) and not enabled (`bg-line-soft text-muted`).
  - The band helper uses integer maths with the 25% and 5% boundaries as amber.
  - Yellow is not used on the bar, badge, links or Retry.
- **Hardcoded values:**
  - `#166534` (`creditBand.ts:29`).
  - `#92400E` (`creditBand.ts:30`, `ReplyComposer.tsx:397`).
  - `#991B1B` (`creditBand.ts:31`, `CreditsCard.tsx:107`).
  - Each is sanctioned by the contract, but repeating raw hex invites drift. Only `#166534` was declared as a new colour, while `#92400E` and `#991B1B` are also not tokens.
- The composer's legacy 409/422 error banner uses `text-red` on `bg-red-tint`. That is pre-existing styling and not part of this phase.

### Pillar 4: Typography (3/4)
- **New credit elements comply.**
  - Sizes: 12px (badge, lines, helper text), 14px (title, buttons, body) and 24px (the number).
  - Weights: 400 and 600 only. There is no `font-medium` in `widgets/credits`. The `font-medium` hits in `ShopTable.tsx` (lines 191, 216, 339-363) are legacy pills and pagination, which the contract says to leave alone.
- **Violation:** the Staff empty state uses `text-[15px]` and `text-[13.5px]` (`ShopTable.tsx:155-158`). It is derived from the older empty-state pattern but is a new Phase 33 surface, so it should follow the 4-size contract.
- The Buy More modal body is 14px and the fallback line is 12px, as specified.

### Pillar 5: Spacing (3/4)
- **Card:**
  - Container `p-4`, wrapper `mb-6`, rows `mt-2` / `mt-4`, footer `gap-2 flex-wrap`, bar `h-2`.
  - Standalone buttons are `h-8 px-4`.
- **Badge:** `px-2 py-1`.
- **Composer:**
  - Status line `mb-2` with a 4px/12px flex gap.
  - Buy More link `h-8` in a `justify-between` row.
- **Buy More modal:** `gap-4`, tile `w-12 h-12`, `mt-2` fallback.
- **Off-scale:** the Staff empty state uses `mt-1.5` (6px). Its `py-16` and `mt-4` are plausible but not declared for this surface.
- **Not verifiable without a browser:** the 44px mobile-target exception is declared and accepted, but no mobile layout was seen.

### Pillar 6: Experience Design (3/4)
- **State coverage in code:**
  - Card: loading skeleton, error with `Retry Loading Credits`, not enabled, and populated bands. A request per shop is aborted, and stale outcomes are discarded via the tagged `Outcome`.
  - Composer: five-state machine (`none`/`loading`/`ready`/`not_enabled`/`insufficient`/`load_error`).
    - Fails open on cost-fetch error.
    - Handles 402 by adopting the server's numbers, keeping the draft, and focusing the textarea.
    - Handles 409 with the existing red banner.
    - 422/502 update the shared store.
  - Shops badge: `—` fallback, store wins over row, and the badge is a real `<button>`.
  - Staff: `isOrgAdmin` empty state with no CTA, and the filtered-empty message is kept.
- **Modal stacking:**
  - Buy More is a sibling of Shop Details with `dismissible={buyMoreShop === null}` (`ShopModals.tsx:240`), so one Esc closes only Buy More.
  - Focus on the card heading is deferred with `setTimeout 0`.
- **Gaps:**
  - The Esc and focus-return behaviour was verified only in jsdom, with `getClientRects` stubbed. The real FocusTrap interaction is unproven.
  - The skeleton has no screen-reader text.
  - A card load failure still lets Buy More stay hidden, which is correct. Opening it requires a successful load.
  - Credit rows in the Activity Log appear under "All types" only, so an admin cannot filter to them. This is a deliberate contract limit.
- **Registry audit:** `components.json` is absent (shadcn not initialised), so it was skipped.

---

## Files Audited
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/credits/CreditBadge.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/credits/CreditsCard.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/credits/BuyMoreCreditsModal.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/credits/creditBand.ts
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/credits/format.ts
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/ReplyComposer.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/ShopTable.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/ShopDetailsModal.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/ShopModals.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/audit-log/TypePill.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/audit-log/AuditLogTable.tsx
- /Users/renjith/Documents/Accounts/review-master/frontend/src/entrypoints/shop-management.tsx
- /Users/renjith/Documents/Accounts/review-master/templates/shops/shop_list.html
- /Users/renjith/Documents/Accounts/review-master/templates/reviews/review_list.html
- Phase 33 SUMMARY files 01-07 and 33-UI-SPEC.md
