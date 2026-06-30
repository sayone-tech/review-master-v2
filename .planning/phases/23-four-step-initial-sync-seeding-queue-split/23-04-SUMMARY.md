---
phase: 23-four-step-initial-sync-seeding-queue-split
plan: 04
subsystem: ui
tags: [react, typescript, websocket, progress, tailwind, accessibility]

requires:
  - phase: 03-channels-sync-progress
    provides: ProgressModal + TopbarSyncIndicator widgets and sync.*.progress WebSocket event handling
provides:
  - "Four-step ProgressModal: Fetching Reviews -> Building Tag Vocabulary -> AI Enrichment -> Finalising, visible from open with per-step counters and step-specific bar colors"
  - "New sync.vocab.progress and sync.finalising.progress event handlers + extended SnapshotState (step discriminator, vocab/finalising counters)"
  - "TopbarSyncIndicator four-stage sub-label and per-stage spinner color"
affects: [23-03-sync-orchestration, review-management-frontend]

tech-stack:
  added: []
  patterns: ["Step-discriminator-driven multi-stage progress UI rendered from WebSocket events + reconnect snapshot"]

key-files:
  created: []
  modified:
    - frontend/src/widgets/review-management/ProgressModal.tsx
    - frontend/src/widgets/review-management/TopbarSyncIndicator.tsx

key-decisions:
  - "D-01: the four named steps rendered verbatim — Fetching Reviews, Building Tag Vocabulary, AI Enrichment, Finalising"
  - "D-02: per-step counters rendered from the new sync.vocab.progress / sync.finalising.progress events plus the snapshot step discriminator"

patterns-established:
  - "SnapshotState.step discriminator drives which of four steps is active; pending steps render dimmed (opacity-60) with track-only bars"
  - "Each step bar uses role=progressbar with ARIA attrs; the step block is wrapped in aria-live=polite"

requirements-completed: [SEED-01]

duration: ~4min
completed: 2026-06-10
---

# Phase 23 — Plan 04: Four-step progress UI Summary

**Extended the ProgressModal from two sections to four named sync steps with per-step counters, step-specific bar colors, and reconnect-aware step discrimination, plus a four-stage topbar indicator.**

## Performance

- **Duration:** ~4 min (code); Task 3 human-verify gate deferred to phase end
- **Completed:** 2026-06-10 (code) — manual verification pending
- **Tasks:** 2 of 3 (Task 3 is a human-verify checkpoint, deferred)
- **Files modified:** 2

## Accomplishments
- `ProgressModal` renders four named steps visible from open: **Fetching Reviews** (yellow bar), **Building Tag Vocabulary** (green), **AI Enrichment** (green), **Finalising** (amber). Steps not yet reached render at `opacity-60` with a "–" counter and a track-only bar.
- Extended `SnapshotState` with `step`, `vocab_enriched`, `vocab_total`, `finalising_processed`, `finalising_total`; wired new `sync.vocab.progress` and `sync.finalising.progress` event handlers and the reconnect-snapshot step discriminator.
- Accessibility: each bar has `role="progressbar"` + correct ARIA attributes; the four-step block is `aria-live="polite"`.
- `TopbarSyncIndicator` now shows a four-stage sub-label and per-stage spinner color; `SyncingShop.stage` union extended to `"fetching" | "vocab" | "enriching" | "finalising"`.

## Task Commits

1. **Task 1: Four-step rendering + extended SnapshotState + event handlers (ProgressModal.tsx)** — `60bf813` (feat)
2. **Task 2: Four-stage sub-label + spinner color (TopbarSyncIndicator.tsx)** — `6d3556e` (feat)
3. **Task 3: Human-verify four-step progress renders/advances** — DEFERRED to phase-end HUMAN-UAT (requires full backend Waves 1–3 running end-to-end)

**Worktree merge:** `1576b38`

## Files Created/Modified
- `frontend/src/widgets/review-management/ProgressModal.tsx` — four-step UI, new event handlers, extended SnapshotState
- `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` — four-stage sub-label + spinner color

## Verification
- `npx tsc --noEmit` (frontend) — pass, no type errors
- Manual visual/UX verification (`<human-check>`): **deferred to phase end**. Requires backend Plans 01–03 merged and frontend+backend running so live `sync.vocab.progress` / `sync.enrichment.progress` / `sync.finalising.progress` events flow during a real 50+ review initial sync. Recorded as a phase-end HUMAN-UAT item.

## Notes / Deviations
- This is a non-autonomous plan (`autonomous: false`). The executor stopped at the Task 3 human-verify checkpoint as designed. Per user decision, the visual verification is deferred to phase end (after Wave 3 backend orchestration lands), since the gate cannot be satisfied until the full event stream is wired. The plan's code (Tasks 1–2) is complete, type-checked, and merged.

## Self-Check: PASSED (code); manual gate OPEN
