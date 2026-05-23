# Phase 20 — UI Review

**Audited:** 2026-05-24
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for this phase) + Phase 20 design decisions (D-26, D-27) from 20-CONTEXT.md
**Screenshots:** Not captured (no dev server detected on ports 3000, 8080; port 5173 returned 302 redirect only)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Generic fallback string fires for HTTP 422 — canonical D-26 copy never reaches the user |
| 2. Visuals | 3/4 | Error banner is appropriately styled; generator overlay UX is clear |
| 3. Color | 3/4 | No hardcoded hex values; one font-medium violation co-occurs with an off-spec spacing class |
| 4. Typography | 2/4 | 4 distinct arbitrary px sizes in use including off-spec 11.5px; font-medium violation on line 320 |
| 5. Spacing | 2/4 | px-2.5 (10px, not on 4px grid) and mt-0.5 (2px, not on 4px grid) present in rendered paths |
| 6. Experience Design | 2/4 | HTTP 422 catch gap means moderated-content state is indistinguishable from a transient failure |

**Overall: 14/24**

---

## Top 3 Priority Fixes

1. **HTTP 422 not handled in `handleGenerate` catch block** — Users whose review text is moderated by the AI guardrail see the generic fallback "AI generation failed. Please try again or write your reply manually." instead of the D-26 canonical message "AI reply isn't available for this review. Please write your reply manually." This actively misleads users into retrying an action that will never succeed, because the backend intentionally never retries moderated content (D-25/D-27). Fix: add `else if (e instanceof ApiError && e.status === 422) { message = "AI reply isn't available for this review. Please write your reply manually."; }` in the catch block at `ReplyComposer.tsx` line 102 area, reading `(e.data as {code?: string}).code === "content_moderated"` to be precise.

2. **`font-medium` violation on the "Use template" button (line 320)** — The design system allows only `font-normal` (400) and `font-semibold` (600). `font-medium` (500) is an off-spec weight that creates visual inconsistency between the "Use template" button and the adjacent "Generate with AI" button which correctly uses `font-semibold`. Fix: change `font-medium` to `font-semibold` on line 320 to match the Generate button.

3. **`px-2.5` (10px) and `text-[11.5px]` are off the 4px spacing/type grid** — `px-2.5` on the "Use template" button (line 320) is 10px, not a 4px-multiple. `text-[11.5px]` on the template preview subtitle (line 341) is not a standard size (should be `text-[12px]` to match the established secondary text size). Both are in the template picker dropdown, which is always visible when templates exist. Fix: change `px-2.5` to `px-2` (8px) on line 320 and `text-[11.5px]` to `text-[12px]` on line 341.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**BLOCKER — D-26 canonical copy never reaches the user for HTTP 422 responses.**

The backend (`apps/reviews/views.py` line 277–292, per 20-07-SUMMARY.md) returns:
```json
{"code": "content_moderated", "detail": "AI reply isn't available for this review. Please write your reply manually."}
```
with HTTP 422 when `ContentModeratedException` is raised.

The frontend `handleGenerate` catch block (`ReplyComposer.tsx` lines 95–115) handles only `status === 429`. All other status codes, including 422, fall through to the static default at line 101:
```
"AI generation failed. Please try again or write your reply manually."
```
The `e.data.detail` field from the 422 body is never read. The canonical D-26 string exists in the backend but is invisible in the UI.

**Impact:** Users with moderated reviews are told to "try again" — but the backend will never succeed because D-25 intentionally excludes those reviews from retry. This is functionally misleading copy.

**WARNING — Generic "Failed to post reply. Please try again." on line 126** is acceptable for submit failures but on the low end of specificity. The 409 and 502 cases correctly surface specific messages; the bare fallback covers the remaining transient errors adequately.

**Positive findings:**
- D-27 is correctly implemented: "Generate with AI" button is unconditionally enabled (no disabled state based on enrichment_status).
- 429 rate-limit copy on lines 103–107 is contextual and actionable.
- Delete confirmation copy ("Delete this reply?" with "Confirm" / "Cancel") is clear.
- "Discard Reply" label is more specific than generic "Cancel".

---

### Pillar 2: Visuals (3/4)

**WARNING — No visual affordance differentiates "AI unavailable for this review" from a transient error.**

Because the 422 case falls through to the generic error, the error banner (`role="alert"`, border-l-4 border-red, line 430) will show the wrong message but otherwise render correctly. If the 422 copy were fixed, the same banner would render the D-26 message. There is no design contract for a distinct visual treatment of moderated content (D-26 says "frontend renders this string verbatim"), so the banner itself is the correct component — it just contains the wrong string.

**Positive findings:**
- Error banner is semantically marked with `role="alert"` (line 429) for screen-reader announcement.
- The generator overlay uses `role="group"` with a dynamic `aria-label` (lines 356–357) that correctly updates based on whether a draft exists.
- Spinner (`Loader2 animate-spin`) appears on the active tone button during generation, not globally — which correctly preserves the Cancel button's visibility.
- `CheckCircle` icon on the replied state is `aria-hidden` (line 182) — correct decorative-icon treatment.
- `Sparkles` icon on the "Generate with AI" button is `aria-hidden` (line 312) and the button has an explicit `aria-label` (line 306).
- Visual hierarchy between the review header section and composer section is maintained through `bg-line-soft` banding.

---

### Pillar 3: Color (3/4)

**WARNING — No hardcoded hex values found (PASS). No `bg-primary`/`text-primary` accent overuse (PASS).**

Color tokens used are semantic: `text-ink`, `text-muted`, `text-subtle`, `text-faint`, `text-red`, `text-green`, `text-amber`, `bg-white`, `bg-line-soft`, `bg-yellow`, `border-line`, `border-red`, `bg-red-tint`, `bg-amber-tint`.

**WARNING — `focus:ring-black/[0.06]` at line 412** uses a Tailwind opacity modifier on a raw color name (`black`) rather than a semantic token. This is a minor violation — it is functionally correct but bypasses the semantic token system for focus ring color. Should be `focus:ring-ink/[0.06]` if `ink` is the semantic alias for black.

The amber/yellow AI accent is correctly scoped to the Sparkles spinner, Generate button hover states, and the Submit Reply primary action — not overused across decorative elements.

---

### Pillar 4: Typography (2/4)

**WARNING — 4 distinct arbitrary pixel sizes in a single component exceeds the 2-size secondary cap.**

Sizes found in `ReplyComposer.tsx`:
| Size | Usage count | Assessment |
|------|------------|------------|
| `text-[14px]` | 9 occurrences | Primary text — acceptable |
| `text-[12px]` | 20 occurrences | Secondary/label text — acceptable |
| `text-[13px]` | 1 occurrence (line 340, template name) | Off-spec — should be `text-[12px]` or `text-[14px]` |
| `text-[11.5px]` | 1 occurrence (line 341, template preview) | Off-spec — half-pixel value is not a valid grid step |

**BLOCKER (typography) — `font-medium` at line 320.**

The "Use template" button uses `font-medium` (weight 500). The design system allows only `font-normal` (400) and `font-semibold` (600). The adjacent "Generate with AI" button correctly uses `font-semibold`. This creates an inconsistency where the two sibling toolbar buttons have different visual weights.

**WARNING — `tracking-[0.05em]` at line 298** (the "Your reply" label). Arbitrary tracking values are off the design system's spacing scale. The intent is to style the uppercase label — using a Tailwind preset like `tracking-wide` (0.025em) or `tracking-wider` (0.05em = `tracking-wider` which is a Tailwind preset) would be on-spec. `tracking-[0.05em]` is equivalent to `tracking-wider`; prefer the named utility.

---

### Pillar 5: Spacing (2/4)

The design system specifies a 4px base grid. All spacing values must be multiples of 4px. Violations found:

| Class | Pixel value | Location | Verdict |
|-------|------------|----------|---------|
| `px-2.5` | 10px | Line 320 ("Use template" button) | VIOLATION — 10px is not on the 4px grid |
| `mt-0.5` | 2px | Lines 182, 189, 341 | VIOLATION — 2px is not on the 4px grid |
| `gap-1.5` | 6px | Not found in this file | n/a |

**`mt-0.5` appears in three places:**
- Line 182: `mt-0.5` on the CheckCircle icon in the replied view (visual micro-alignment)
- Line 189: `mt-0.5` on the "by {name}" byline text
- Line 341: `mt-0.5` on the template preview text

The `mt-0.5` pattern is a habitual workaround for tight vertical rhythm. The correct grid-compliant alternative is `mt-1` (4px). For extremely tight alignment (the icon case at line 182), `items-start` on the flex container is preferable to a fractional `mt-`.

**`px-2.5` (10px) on the "Use template" button (line 320)** is inconsistent with the "Generate with AI" button which uses `px-2` (8px). These sibling buttons in the same toolbar row have different horizontal padding.

**Positive:** No arbitrary `[Npx]` or `[Nrem]` spacing values in the layout structure. All other spacing uses Tailwind scale tokens (`px-4`, `py-3`, `py-4`, `gap-2`, `gap-3`, `mt-1`, `mt-2`, `mt-3`, `w-64`).

---

### Pillar 6: Experience Design (2/4)

**BLOCKER — HTTP 422 (content_moderated) state is invisible and misleading.**

The moderation error path (Phase 20's core new user-facing state) is not handled. The user experience is:
1. User clicks "Professional" or "Friendly" on a review with moderated content.
2. Backend returns 422 with `{"code": "content_moderated", "detail": "AI reply isn't available for this review. Please write your reply manually."}`.
3. Frontend shows: "AI generation failed. Please try again or write your reply manually."
4. User retries — gets the same message again. The retry loop never resolves because D-25 ensures the backend skips this review permanently.

This is a user-completion failure: the user cannot distinguish "something went wrong, retry will help" from "this review cannot use AI, write manually".

**Positive experience design findings:**
- Loading state: `generatingTone` state correctly renders the active tone button with a spinner and `disabled` on all other tone buttons, preventing double-submission. `aria-busy="true"` is set.
- Abort/cancel: `AbortController` ref (lines 37, 82–84) cancels in-flight requests on re-click or unmount — correct race condition handling (IN-04).
- Destructive confirmation: delete reply has a two-step "Delete this reply?" → "Confirm" flow (lines 199–228), preventing accidental deletion.
- Empty draft guard: Submit Reply is disabled when `comment.trim().length === 0` (line 447).
- Template fetch silently fails (`catch(() => {})` at line 41) — this is correct; the composer degrades to manual entry without error noise.
- `role="alert"` on the error banner (line 429) ensures screen readers announce errors immediately.
- `aria-live="polite"` on the character counter (line 423) announces count changes without interrupting the user.

**WARNING — Error in the "replied" view (line 231) renders as a `<p>` without `role="alert"`.**

In the replied/delete state, `errorMessage` is rendered as `<p className="text-[12px] text-red text-right">{errorMessage}</p>` (line 231) — no `role="alert"`. The composer view correctly uses `role="alert"` (line 429). The inconsistency means delete-error messages may not be announced to screen readers.

---

## Registry Safety

No `components.json` found — shadcn not initialized. Registry audit skipped.

---

## Files Audited

- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/ReplyComposer.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/api.ts`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-01-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-02-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-03-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-04-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-05-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-06-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-07-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-08-SUMMARY.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/20-ai-guardrails/20-CONTEXT.md`
