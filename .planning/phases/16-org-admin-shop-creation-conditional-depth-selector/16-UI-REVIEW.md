---
phase: 16
slug: org-admin-shop-creation-conditional-depth-selector
date_audited: 2026-05-24
overall: 23/24
copywriting: 4/4
visuals: 4/4
color: 4/4
typography: 4/4
spacing: 4/4
experience_design: 3/4
status: clean
---

# Phase 16 — UI Review

**Audited:** 2026-05-24
**Baseline:** 16-UI-SPEC.md (approved 2026-05-15)
**Screenshots:** not captured (retroactive code-only audit; no dev server)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Label, helper text, and three option strings are verbatim matches to UI-SPEC §"Copywriting Contract" |
| 2. Visuals | 4/4 | Field structure mirrors the Region select; same wrapper, same select, no decorative drift |
| 3. Color | 4/4 | Uses `inputCls`/`labelCls` unchanged — no accent (yellow) leakage onto the form control, accent reserved for "Add Shop" CTA |
| 4. Typography | 4/4 | Label 12px semibold uppercase, body 13.5px, helper 12px muted — all on the declared scale, no new sizes |
| 5. Spacing | 4/4 | Inherits `space-y-4` from the Step 3 form; helper text uses `mt-1` matching the error-text pattern |
| 6. Experience Design | 3/4 | Solid defaults, correct reset, conditional DOM-absent render — but `SYNC_DEPTH_LABELS` was added to `types.ts` then never used (DRY drift), and no info affordance beyond helper text |

**Overall: 23/24**

---

## Top 3 Priority Fixes

1. **[INFO] Unused `SYNC_DEPTH_LABELS` constant in `types.ts`** — `frontend/src/widgets/shop-management/types.ts:11-15` exports a `Record<SyncDepth, string>` with the option labels, but `CreateShopModal.tsx:483-485` hardcodes the same strings as `<option>` children. Either use the constant to render options (`{(Object.keys(SYNC_DEPTH_LABELS) as SyncDepth[]).map(k => <option key={k} value={k}>{SYNC_DEPTH_LABELS[k]}</option>)}`) or drop the export. Current state means a future label change has two places to update.
2. **[INFO] Helper text uses HTML entity `&#39;` instead of a Unicode apostrophe** — `CreateShopModal.tsx:474` reads `this shop&#39;s` to satisfy `react/no-unescaped-entities`. The UI-SPEC §"Copywriting Contract" cites a straight apostrophe. Rendered output is identical, but a plain string literal in JSX (`{"this shop's initial..."}`) reads more cleanly and matches the contract source-of-truth verbatim.
3. **[INFO] No "no shops yet, custom depth disabled" affordance** — when `allow_custom_sync_depth=false`, the selector is silently absent (correct per spec). Org Admins who hear about the feature from Superadmin and don't see it have no in-product breadcrumb. Out of contract for Phase 16, but worth tracking for a future phase: a one-line note in the shop list or settings page explaining that depth control is a Superadmin-enabled feature.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

UI-SPEC §"Copywriting Contract" locks five strings; all five render correctly:

- Label "Review History" — `CreateShopModal.tsx:471` ✓
- Helper "Sets how far back this shop's initial review sync will go." — `CreateShopModal.tsx:474` ✓ (rendered via `&#39;` entity — see fix #2)
- "Last 1 year" / "Last 2 years" / "All time" — `CreateShopModal.tsx:483-485` ✓
- No error/empty/destructive copy — correct, the field is always pre-populated and has no validation surface (UI-SPEC §"Field Structure", bullet 6)

No generic labels, no "Submit"/"OK" drift. Helper text terminology matches the existing `Shop.SyncDepth` model semantics — "Review History" is consistent with the Phase 15 shop-detail field name ("Review history").

### Pillar 2: Visuals (4/4)

Field markup is a near-clone of the Region select (`CreateShopModal.tsx:443-466`), which UI-SPEC §"Field Structure" explicitly designates as the copy template. Differences from Region are exactly the three allowed by spec:

- Different `htmlFor`/`id` (`cs-sync-depth` vs `cs-region`) ✓
- Different label text ✓
- No error-state branch (`inputCls` only, never `inputErrorCls`) ✓
- Plus the additional helper text `<p>` (UI-SPEC §"Field Structure" key contract point 3)

Sibling-modal consistency: `ShopModals.tsx` only passes the new prop through (line 198); no other modal was disturbed. `EditShopModal` and `ShopDetailsModal` are untouched, matching UI-SPEC §"What Is NOT Changing".

### Pillar 3: Color (4/4)

- `inputCls` (`CreateShopModal.tsx:9-10`) uses `bg-white`, `border-line`, `focus:ring-black/[0.06]`, `focus:border-ink` — black-tone focus ring, **not** the yellow accent. Matches UI-SPEC §"Color".
- `labelCls` uses `text-subtle` (#A1A1AA). Matches.
- Helper text uses `text-muted` (#71717A). Matches the "Supplementary semantic colors" row.
- No hardcoded hex inside the new block. The only inline hex usage in the file (`#DC2626`, `#71717A`, `#F0FDF4`, `#FAFAFA`, etc.) is in pre-Phase-16 code (steps 1 and 2, error texts) and outside Phase 16's scope.
- Yellow accent appears only on the "Add Shop" footer button (`CreateShopModal.tsx:218`) — Phase 16 added no accent usage.

### Pillar 4: Typography (4/4)

| Role | UI-SPEC | Shipped | File:Line |
|---|---|---|---|
| Label | 12px / 600 / uppercase | `text-[12px] font-semibold ... uppercase` | CreateShopModal.tsx:13 (`labelCls`) |
| Helper | 12px / 400 | `text-[12px] text-muted` | CreateShopModal.tsx:473 |
| Input/option | 13.5px / 400 | `text-[13.5px]` | CreateShopModal.tsx:10 (`inputCls`) |

No new sizes, no new weights, no arbitrary text-* classes. Helper text font weight is implicit `normal` (matches spec's 400).

### Pillar 5: Spacing (4/4)

- The new `<div>` is a child of the Step 3 `<form class="space-y-4">` (line 385), giving it 16px vertical rhythm with neighbouring fields automatically — no per-field margin override needed. Matches UI-SPEC §"Spacing Scale" md=16px.
- Helper text margin `mt-1` (4px) — matches the "Exceptions" row in UI-SPEC §"Spacing Scale" and the existing error-text pattern at line 437.
- Label margin `mb-1` from `labelCls` — matches.
- No arbitrary spacing (e.g. `mt-[7px]`) introduced. No `space-y-*` override applied to the new wrapper that would break the parent rhythm.

### Pillar 6: Experience Design (3/4)

Strong points:
- Conditional DOM-absent render (`CreateShopModal.tsx:468`) — not `display:none`, not `disabled`, not `aria-hidden`. Matches UI-SPEC §"Conditional Render Rule".
- Default `TWO_YEARS` (`CreateShopModal.tsx:61`) — matches UI-SPEC §"State Initialization".
- `reset()` restores `TWO_YEARS` on close/reopen (`CreateShopModal.tsx:102`) — prevents stale state, matches the documented pitfall.
- Native `<select>` provides keyboard navigation (arrow keys, type-ahead, Enter) for free — no custom keyboard handling needed.
- `aria-label="Review History"` + `<label htmlFor>` association — redundant accessible name, matches the Region pattern.
- Payload always includes `sync_depth` (`CreateShopModal.tsx:155`) — matches D-05 (option 1 from UI-SPEC §"Payload Field").

Score deductions:
- **DRY drift**: `SYNC_DEPTH_LABELS` constant added to `types.ts:11-15` is dead code. The labels are hardcoded inline (`CreateShopModal.tsx:483-485`). A future copy edit (e.g. "Past year" replacing "Last 1 year") has two places to update. UI-SPEC's example also hardcodes the options, so this is permitted by contract — but the export is unused and should either be applied or removed.
- **No info affordance**: when `allow_custom_sync_depth=false`, the Org Admin has zero in-product breadcrumb that this control even exists. The phase is intentionally scoped to "absent when disabled", so this is out of contract — but worth noting for future discoverability.
- **No fetch/save indicator** specific to this field — N/A, since the field is part of the larger form's "Add Shop" submit. The footer button's `Saving…` state covers it.

Edge cases checked:
- Modal opened → field rendered (flag is read at mount, won't change mid-modal) ✓
- Pick "Last 1 year" → Cancel → reopen → resets to "Last 2 years" ✓ (via `reset()` in the `!open` effect, line 113-116)
- Backend accepts `sync_depth` even when org flag is false (D-05) — so a stale React state with the flag flipped server-side would still produce a 201; safe-fail direction.

---

## Registry Safety

`components.json` absent — project does not use shadcn or third-party registries. UI-SPEC §"Registry Safety" confirms: no blocks used, no safety gate required. **Skipped.**

---

## Files Audited

- `frontend/src/widgets/shop-management/CreateShopModal.tsx` — primary surface (lines 38, 47, 61, 102, 155, 468-488)
- `frontend/src/widgets/shop-management/ShopModals.tsx` — prop threading (lines 64, 72, 198)
- `frontend/src/widgets/shop-management/types.ts` — type contract (lines 9-15, 59)
- `frontend/src/entrypoints/shop-management.tsx` — bootstrap read (lines 38-40, 71)
- `templates/shops/shop_list.html` — `json_script` bootstrap tag (line 31)
- `.planning/phases/16-org-admin-shop-creation-conditional-depth-selector/16-UI-SPEC.md` — design contract
- `.planning/phases/16-org-admin-shop-creation-conditional-depth-selector/16-01-SUMMARY.md`, `16-02-SUMMARY.md` — execution provenance

---

## UI REVIEW COMPLETE

Phase 16 is a textbook example of a tightly-scoped UI delta that lands clean against its contract. The conditional Review History select reuses the Region select's `labelCls`/`inputCls`/structure with the three allowed differences (id, label, no error branch, plus helper text), uses no new tokens, no new colors, no new spacing values, and adds zero accent leakage. The DOM-absent conditional, default-`TWO_YEARS` state, and `reset()` hook all match the spec. The single point worth tracking is the unused `SYNC_DEPTH_LABELS` constant in `types.ts` — it's harmless today but it's two-source-of-truth waiting to drift. Overall score 23/24, status clean — ship as-is and queue the DRY cleanup as an info-level follow-up.
