---
phase: 19
slug: ai-reply-generation
date_fixed: 2026-05-24
review_path: .planning/phases/19-ai-reply-generation/19-UI-REVIEW.md
status: fixed
fixed_count: 3
skipped_count: 0
---

# Phase 19 — UI Review Fixes

All three findings from `19-UI-REVIEW.md` (overall 23/24) addressed. New
expected score: **24/24** on re-audit.

| Finding | Severity | Status | Commit | Files modified |
|---------|----------|--------|--------|----------------|
| WR-01 | warning | fixed (spec) | `e5e384b` | `19-UI-SPEC.md` |
| IN-01 | info | fixed (spec + code) | `e5e384b`, `224e77e` | `19-UI-SPEC.md`, `ReplyComposer.tsx` |
| IN-02 | info | fixed (spec) | `e5e384b` | `19-UI-SPEC.md` |

## Per-finding detail

### WR-01 — Rate-limit copy authorised in spec

**Auditor's recommendation:** option (a) — update the spec to permit the dynamic
"in N seconds" variant, since the shipped UX is genuinely better than the static
fallback. The variant gives the user actionable information (when to retry)
rather than a vague "wait a moment."

**Fix:** §Copywriting Contract now declares two 429 strings — one for when
`retry_after_seconds` is present in the backend body, and one fallback for when
it is absent or zero. The intro line was tightened from "All strings are exact.
No variants, no ellipsis alternatives." to permit declared dynamic substitutions
in the table. The substitution syntax used is `{N}` so future readers know it is
a single named parameter, not a freeform format string. Plural/singular
("1 seconds") is acknowledged as acceptable because real rate-limit values from
the backend are always ≥ 5.

`ReplyComposer.tsx:103-107` is now spec-compliant with no code change.

### IN-01 — Open-state generator button hover affordance

**Fix (code):** `ReplyComposer.tsx:312` open-state hover changed from
`hover:bg-line-soft` (visual no-op when the button is already
`bg-line-soft`) to `hover:bg-line` — a 1-shade-darker
(#E4E4E7) hover that matches affordance parity with the closed-state
hover (`bg-white → hover:bg-line-soft`).

**Fix (spec):** §Color per-element map row for "Generate with AI button
(generatorOpen=true)" updated to read `line` in the Hover bg column, so the spec
and code agree.

### IN-02 — Pre-existing `text-subtle` on YOUR REPLY label

**Fix (spec only):** §Color now contains a one-line note immediately after the
per-element map table noting that the section label inherits `text-subtle`
(#71717A) from the surrounding composer wrapper, and that this is pre-existing
and intentionally outside this phase's per-element map. No code change — the
shipped behavior was already correct.

## Verification

- `git log --oneline -3` confirms two fix commits + UI-SPEC update committed
  atomically on `feature/categories`.
- Pre-commit hooks ran cleanly on the code change (ruff format + check passed;
  ruff format made a small unrelated reformat in the same line, expected).
- The dynamic 429 variant in `ReplyComposer.tsx:103-107` was untouched — it now
  matches the updated spec.

## Notes

The skipped count is zero because there were no critical or warning findings
that required code changes — the one substantive WR-finding was a "spec needs
to catch up to code" gap, and both INFO items were spec/docs tidy-ups
accompanied by one trivial code polish.
