---
phase: 19-ai-reply-generation
plan: 03
subsystem: frontend/reviews
tags: [frontend, react, ai-reply, ui]
requires: [19-02]
provides:
  - "Generate with AI button + tone pills in ReplyComposer"
  - "generateReply(reviewId, tone) API client"
affects: [frontend/src/widgets/review-management]
tech-stack:
  added: []
  patterns: ["state-machine in component", "focus-management refs"]
key-files:
  created: []
  modified:
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/ReplyComposer.tsx
decisions:
  - "D-02 honoured: no pre-selection of tone pill based on rating — both pills visually equal"
  - "Reused existing ApiError class; 429 detection uses e.status === 429"
  - "Focus management uses native document.getElementById + ref pattern consistent with existing composer code"
metrics:
  duration: ~10min
  completed_date: "2026-05-22"
---

# Phase 19 Plan 03: Generate with AI — Frontend Wiring Summary

One-liner: ReplyComposer now exposes a Sparkles "Generate with AI" button that opens tone pills (Professional / Friendly), calls POST /api/v1/reviews/{id}/generate-reply/, fills the textarea on success, and surfaces 429 vs. generic errors inline — with full focus management and a Cancel/overwrite confirmation flow.

## Tasks

| Task | Name                                                                           | Commit  | Files                                                    |
| ---- | ------------------------------------------------------------------------------ | ------- | -------------------------------------------------------- |
| 1    | generateReply() in api.ts                                                      | bd24de1 | frontend/src/widgets/review-management/api.ts            |
| 2    | Generator button + tone pills + state machine in ReplyComposer.tsx             | 2deb64f | frontend/src/widgets/review-management/ReplyComposer.tsx |
| 3    | Checkpoint (human-verify)                                                      | n/a     | (interactive verification — see below)                   |

## What was built

### Task 1 — api.ts

Appended `generateReply(reviewId: number, tone: string): Promise<{ draft: string }>` after `fetchSyncingShops()`. Posts JSON body `{ tone }` to `/api/v1/reviews/{reviewId}/generate-reply/` using the existing `headers("POST")` (auto X-CSRFToken) and reuses `handle()` so non-OK responses throw `ApiError` with the original status — the caller inspects `e.status` to differentiate 429 from other failures.

### Task 2 — ReplyComposer.tsx

- **Imports:** added `Loader2, Sparkles` from `lucide-react` (both already in lucide-react 1.8.0 — verified via `node_modules/lucide-react/dist/esm/icons/`) and `generateReply` from `./api`.
- **State:** `generatorOpen: boolean`, `generatingTone: "professional" | "friendly" | null`.
- **Ref:** `generatorButtonRef: HTMLButtonElement` for focus-return on error/cancel.
- **Handlers:** `handleToggleGenerator`, `handleCancelGenerator`, `handleGenerate(tone)`. On 200 success: `setComment(draft)`, collapse pills, focus textarea via `document.getElementById('reply-textarea-${row.id}')`. On error: collapse pills, set `errorMessage` (429 → rate-limit copy; otherwise → generic copy), focus the Generate button.
- **Toolbar:** wrapped existing Use template div + new Generate button inside a `flex items-center gap-2` row. Generate button: Sparkles icon, `aria-expanded` and `aria-controls` wired to the pill row id `ai-generator-${row.id}`. Uses `bg-line-soft` background when open.
- **Pill row:** appears immediately below the toolbar inside the same `px-4 py-4` container. Renders the confirmation span only when `comment.trim() !== ""`, plus a Cancel button in that case. Pills follow the exact UI-SPEC className contract; loading pill uses `Loader2 animate-spin text-amber`.
- **Copy:** all strings verbatim per UI-SPEC (Title-case pill labels, U+2026 ellipsis on loading labels, exact 429 and generic error sentences).
- **D-02:** No logic inspects `row.star_rating` for pill highlighting — both pills are visually identical on open and the user explicitly chooses.

## Verification performed

- `npx tsc --noEmit` (run via symlinked node_modules from main repo) — **clean, exit 0** after both tasks.
- Pre-commit hooks ran on both commits — passed (no Python files touched, so Python-specific hooks were skipped; trailing-whitespace, EOF, merge-conflict, large-file, secret-detection checks all passed).
- Manual inspection of lucide-react 1.8.0 confirmed `sparkles.js` and `loader-2.js` exist.

## Deviations from Plan

None for Tasks 1–2. Plan executed exactly as written.

**Tooling note (not a deviation):** The worktree has no `frontend/node_modules` (parallel-executor checkout). I temporarily symlinked it to the main repo's `frontend/node_modules` to run `tsc --noEmit`, then removed the symlink before each commit so it never entered the git index. No source files were affected.

## Checkpoint — human verification required (Task 3)

This task is `type="checkpoint:human-verify" gate="blocking"` and cannot be auto-approved by a parallel executor. The orchestrator should surface the following verification script to the user before declaring the phase complete:

**To verify locally:**

1. `make up` — start the dev stack.
2. Log in as Org Admin or Staff Admin.
3. Navigate to Reviews, click "Reply" on a review with an unreplied state.
4. **Toolbar:** Confirm "Generate with AI" (with Sparkles icon) appears to the LEFT of "Use template".
5. **Empty path:** With empty textarea, click "Generate with AI" → see two equal pills `[Professional] [Friendly]` (no pre-selection). Click "Professional" → spinner on Professional, Friendly disabled. On 200 → textarea fills, pills collapse, textarea has focus.
6. **Overwrite path:** Type some text, click "Generate with AI" → see "Replace your draft with AI reply? [Professional] [Friendly] [Cancel]". Click Cancel → pills collapse, focus returns to Generate button.
7. **Error path:** Remove `OPENAI_API_KEY` from `.env`, restart, click a tone pill → see inline red error box with "AI generation failed. Please try again or write your reply manually." Pills collapse, focus on Generate button.
8. **Toggle:** Click Generate → open. Click Generate again → close.

Resume signal: type `approved` to mark phase 19 complete, or describe issues.

## Known Stubs

None.

## Threat Flags

None — all new surface area (the POST endpoint, CSRF, tone-enum validation, rate-limit) was already mitigated in the plan's threat register (T-19-08 through T-19-11) and the implementation matches those mitigations exactly. The frontend disables both pills during `generatingTone !== null`, preventing rapid concurrent calls from the same component instance (T-19-11 mitigation).

## Self-Check: PASSED

- `frontend/src/widgets/review-management/api.ts` — present, contains `generateReply`
- `frontend/src/widgets/review-management/ReplyComposer.tsx` — present, contains `generatorOpen`, `Sparkles`, `Loader2`, `handleGenerate`
- Commit `bd24de1` — present in `git log`
- Commit `2deb64f` — present in `git log`
