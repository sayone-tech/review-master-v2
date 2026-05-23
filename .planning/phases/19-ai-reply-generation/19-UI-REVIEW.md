---
phase: 19
slug: ai-reply-generation
date_audited: 2026-05-24
overall: 23/24
copywriting: 3/4
visuals: 4/4
color: 4/4
typography: 4/4
spacing: 4/4
experience_design: 4/4
status: issues_found
---

# Phase 19 — UI Review: AI Reply Generation

**Audited:** 2026-05-24
**Baseline:** 19-UI-SPEC.md (approved design contract)
**Screenshots:** not captured (no dev server) — code-only audit against shipped `ReplyComposer.tsx`

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Rate-limit copy diverges from spec — adds a dynamic "in N seconds" variant not declared in §Copywriting Contract |
| 2. Visuals | 4/4 | Sparkles + Loader2 icons, button hierarchy, depressed-bg state all match anatomy spec |
| 3. Color | 4/4 | All tokens (line, line-soft, amber, amber-tint, red, red-tint, faint, muted, ink) used per §Color per-element map; yellow accent preserved for Submit only |
| 4. Typography | 4/4 | Only `text-[12px]` font-semibold on new elements; `text-[14px]` on inherited textarea/error containers — matches §Typography |
| 5. Spacing | 4/4 | `px-2 py-1`, `gap-1`, `gap-2`, `mb-2`, `mt-2` — fully 4px-grid compliant; "Use template" non-grid `px-2.5` left intact per spec carve-out |
| 6. Experience Design | 4/4 | AbortController race-safety, focus management on success/error/cancel, two-variant pill row (empty vs non-empty), aria-busy/expanded all present |

**Overall: 23/24**

---

## Top 3 Priority Fixes

1. **Rate-limit copy diverges from spec — WARNING.** `ReplyComposer.tsx:103-107` renders `"You've reached the AI generation limit. Please try again in ${e.retryAfterSeconds} seconds."` when `retryAfterSeconds` is present. The §Copywriting Contract declares exactly one string for 429: `"You've reached the AI generation limit. Please wait a moment."` This is a substantive (and arguably better) UX addition, but it was never approved in the contract and was not flagged in the spec exception list. **Fix:** either (a) update 19-UI-SPEC.md §Copywriting Contract to authorise the dynamic variant and re-sign-off, or (b) drop the dynamic branch and use the contract string verbatim. Recommend (a).

2. **Generator button hover-when-open is a no-op — INFO.** `ReplyComposer.tsx:310` writes `${generatorOpen ? "bg-line-soft hover:bg-line-soft" : "bg-white hover:bg-line-soft"}`. When the generator is open, the button is `bg-line-soft` and the hover state is also `bg-line-soft` — visually the user gets no hover feedback while the panel is expanded. Spec §Color allows this (both idle-open bg and hover-open bg are `line-soft`), so this is compliant but worth confirming intentional. **Fix (optional):** consider a 1-shade-darker hover such as `hover:bg-line` for the open state to keep affordance parity with closed state. Not required by spec.

3. **`text-subtle` on "Your reply" label is undeclared — INFO.** `ReplyComposer.tsx:298` uses `text-subtle` on the section label, but §Typography lists this row as "(Pre-existing) Section label" and §Color does not include a `subtle` row in the new per-element map. Since this is pre-existing and the spec explicitly says "not changed", this is compliant — flagged only because a reader of the spec alone wouldn't be able to reconstruct the label colour. **Fix:** add a one-line note in §Color saying "pre-existing `text-subtle` on the YOUR REPLY label is unchanged".

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

Compared each string against §Copywriting Contract row-by-row:

| Spec String | Shipped Location | Match |
|---|---|---|
| `Generate with AI` | `ReplyComposer.tsx:313` | exact |
| `Professional` / `Friendly` | `ReplyComposer.tsx:365` (label = `tone === "professional" ? "Professional" : "Friendly"`) | exact |
| `Professional…` / `Friendly…` (U+2026) | `ReplyComposer.tsx:380` (`{label}…`) | exact — single Unicode ellipsis character |
| `Replace your draft with AI reply?` | `ReplyComposer.tsx:360` | exact |
| `Cancel` | `ReplyComposer.tsx:405` | exact |
| `AI generation failed. Please try again or write your reply manually.` | `ReplyComposer.tsx:101` | exact |
| `You've reached the AI generation limit. Please wait a moment.` | `ReplyComposer.tsx:106` | exact — but only reached when `retryAfterSeconds` is null/zero |
| **NEW (undeclared):** `You've reached the AI generation limit. Please try again in N seconds.` | `ReplyComposer.tsx:104` | **divergence — not in contract** |
| All `aria-label` variants | `:306, :366-368, :403` | exact |

**Score 3/4** because the spec is an enumerated allowlist and the shipped code adds a string. Quality of the addition is high; the gate failure is process, not UX.

### Pillar 2: Visuals (4/4)

- Sparkles `size={12}` icon on generator button (`:312`) — matches §Component Anatomy #2.
- Loader2 `size={12}` with `animate-spin` and `text-amber` on loading pill (`:379`) — matches §Component Anatomy #5 exactly.
- `aria-hidden="true"` on both icons (`:312, :379`).
- No new visual primitives introduced; existing pill/button vocabulary is reused.
- Button hierarchy preserved: Submit (yellow primary) > Discard (white secondary) > Generate/Template (white tertiary) > tone pills (white quaternary).

### Pillar 3: Color (4/4)

Per-element token check (`:310-314, :377, :392, :402, :430`):

| Element | Spec | Shipped | Match |
|---|---|---|---|
| Generate button idle | `bg-white border-line text-ink hover:bg-line-soft` | `:310` `bg-white hover:bg-line-soft border-line text-ink` | exact |
| Generate button open | `bg-line-soft hover:bg-line-soft` | `:310` | exact |
| Tone pill idle | `bg-white border-line text-ink hover:bg-amber-tint hover:text-amber hover:border-amber` | `:392` | exact |
| Tone pill loading | `bg-line-soft text-faint border-line` | `:377` | exact |
| Tone pill disabled-inactive | `disabled:opacity-50 disabled:hover:bg-white` (i.e., neutralised hover) | `:392` `disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-ink disabled:hover:border-line` | exact |
| Spinner Loader2 | `text-amber` | `:379` | exact |
| Cancel button | `text-muted hover:text-ink` | `:402` | exact |
| Confirmation prompt | `text-muted` | `:360` | exact |
| Error row | `border-l-4 border-red bg-red-tint text-red` | `:430` | exact (inherited) |

Accent yellow remains exclusive to Submit (`:448`). No yellow leaked onto AI controls.

### Pillar 4: Typography (4/4)

`grep` of font sizes on new elements:
- `text-[12px]` on generator button, both tone pills (idle + loading), confirmation prompt, Cancel button — matches §Typography "Label / button (12px / 600)".
- `font-semibold` on all new buttons and confirmation prompt — matches §Typography weight.
- `text-[14px]` only appears on the inherited error container at `:430` (which the spec explicitly carves out as inherited).
- No `font-medium`, no `text-[13px]`, no `text-[15px]` on new elements. (The pre-existing "Use template" `font-medium` at `:320` is left untouched per spec.)

### Pillar 5: Spacing (4/4)

New-element spacing classes:
- Generator button: `px-2 py-1 gap-1` — 8/4/4 px, 4px-grid.
- Tone pills (both states): `px-2 py-1 gap-1` — 4px-grid.
- Pill group container: `gap-2 mb-2` and `flex-wrap` when non-empty — matches §Component Anatomy #3 and #6.
- Outer toolbar wrapper: `flex items-center gap-2` (`:302`) — matches §Component Anatomy #1.
- Error row: `mt-2 px-4 py-2` (inherited) — 4px-grid.

No arbitrary `[Npx]` spacing introduced. The pre-existing `px-2.5` on Use-template (`:320`) is untouched, as required by the spec carve-out.

### Pillar 6: Experience Design (4/4)

State machine implementation vs §Interaction State Machine:

- **idle → expanded-empty / expanded-nonempty:** `handleToggleGenerator` (`:66-72`) and the JSX branches at `:359` (confirmation prompt only when `comment.trim() !== ""`). Both branches verified.
- **expanded → loading:** `handleGenerate(tone)` (`:80-116`) sets `generatingTone`, both pills receive `disabled={generatingTone !== null}` (`:389`).
- **loading → success:** `setComment(draft); setGeneratorOpen(false); setGeneratingTone(null); document.getElementById(...).focus()` (`:91-94`) — focus returns to textarea per spec.
- **loading → error:** `setErrorMessage(message); generatorButtonRef.current?.focus()` (`:109-110`) — focus returns to generator button per spec.
- **Cancel:** `handleCancelGenerator` (`:74-78`) closes generator and refocuses generator button — matches spec.
- **Race-safety:** AbortController plumbing (`:37, :44-49, :82-84, :89-90, :97-98, :111-114`) cancels in-flight requests on tone re-click and on unmount. This exceeds spec (spec doesn't mention abort) and is correct defensive UX.
- **A11y:** `aria-expanded` (`:307`), `aria-controls` (`:308`), `aria-busy` on loading pill (`:375, :390`), `aria-label` rotation on loading (`:376, :391`), `role="group"` on container (`:356`), `role="alert"` on error (`:429`) — all match §Accessibility Contract.
- **Keyboard:** All interactive elements are `<button type="button">`; tab order is document order — matches spec.

**Open question (not a defect):** Does the tone picker remember selection across reviews? Per spec there is no persistence requirement — each composer is per-row and remounts. Behaviour is correct.

---

## Registry Safety

Registry audit not applicable — `components.json` not present, no shadcn registries used per §Registry Safety table. No new npm packages introduced. lucide-react (`Sparkles`, `Loader2`) was already a dependency.

---

## Files Audited

- `frontend/src/widgets/review-management/ReplyComposer.tsx` (primary surface, 457 lines)
- `frontend/tailwind.config.js` (verified `amber`, `amber-tint`, `line-soft`, `red-tint`, `faint` tokens exist)
- `.planning/phases/19-ai-reply-generation/19-UI-SPEC.md` (audit baseline)
- `.planning/phases/19-ai-reply-generation/19-CONTEXT.md` (locked decisions, referenced for rate-limit copy authority)

---

## UI REVIEW COMPLETE

Phase 19's ReplyComposer ships at 23/24 — a near-perfect implementation of the approved design contract. Color tokens, spacing scale, typography ladder, icon usage, state machine, focus management, ARIA wiring, and race-safe AbortController plumbing all match 19-UI-SPEC.md verbatim, with the AbortController treatment exceeding the spec. The one substantive divergence is in Copywriting: the shipped code adds a dynamic 429 error variant ("…try again in N seconds") that the spec's exact-string Copywriting Contract does not authorise. The addition is a UX win but a process miss — the fix is to update §Copywriting Contract to permit the variant, or drop it. Two minor INFO-level notes (no hover affordance on the open-state generator button; `text-subtle` on the section label not enumerated in §Color) are compliant with the spec as written and surface only as documentation tidy-ups.
