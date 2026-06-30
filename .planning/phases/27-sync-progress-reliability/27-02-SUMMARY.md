---
phase: 27-sync-progress-reliability
plan: "02"
subsystem: frontend
tags: [sync-progress, poll-fallback, websocket, react, vitest]
dependency_graph:
  requires: [27-01]
  provides: [SYNC-REL-01-frontend]
  affects:
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/ProgressModal.tsx
    - frontend/src/widgets/review-management/ProgressModal.test.tsx
tech_stack:
  added: []
  patterns: [poll-fallback-alongside-ws, forward-only-merge-by-timestamp, terminal-status-gate]
key_files:
  created:
    - frontend/src/widgets/review-management/ProgressModal.test.tsx
  modified:
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/ProgressModal.tsx
decisions:
  - "Poll interval chosen as 4s (within D-02 3–5s discretion range)"
  - "fetchSyncProgress returns Record<string,unknown>|null — null on 404 so poll failure is a no-op"
  - "Forward-only merge uses Date.parse comparison on last_update_at; stale-or-equal polls are dropped"
  - "Poll useEffect depends on [open, shopId, snapshotStatus] so the interval re-creates only when open/shopId/terminal-status changes — not on every snapshot update"
  - "Type cast uses unknown intermediary (Record<string,unknown> -> unknown -> SnapshotState) to satisfy strict TypeScript"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-24"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 3
---

# Phase 27 Plan 02: Sync Progress Reliability — Frontend Summary

**One-liner:** ProgressModal gets a 4s snapshot-poll fallback alongside the WebSocket, merging forward-only by `last_update_at`, stopping on terminal state/close — so a dropped WebSocket event no longer freezes the modal.

## Tasks Completed

| Task | Commit | Files |
|------|--------|-------|
| 1: Add fetchSyncProgress api helper + poll-fallback effect with forward-only merge (SYNC-REL-01, D-02) | `5279093` | api.ts, ProgressModal.tsx, ProgressModal.test.tsx |

## What Was Built

### Task 1 — SYNC-REL-01 Frontend (D-02)

**`frontend/src/widgets/review-management/api.ts`**

Added `fetchSyncProgress(shopId: number): Promise<Record<string, unknown> | null>`:
- GETs `GET /api/v1/reviews/sync-progress/{shopId}/` using the existing `headers("GET")` + `credentials:"same-origin"` pattern (mirrors `fetchSyncingShops`)
- Returns `null` on 404 (no snapshot yet — not an error condition for polling)
- Delegates other errors to the existing `handle()` / `ApiError` flow; the caller swallows them (best-effort)

**`frontend/src/widgets/review-management/ProgressModal.tsx`**

Added a second `useEffect` — the poll fallback — that runs alongside the existing WebSocket effect (the WS was NOT modified or removed):

- Polls `fetchSyncProgress` every `POLL_MS = 4_000` ms (4s) using `window.setInterval`
- **Forward-only merge:** `setSnapshot(prev => ...)` — if the poll result is null (404) or its `last_update_at` is ≤ current snapshot's, the state is unchanged; only strictly newer poll results advance state
- **Terminal gate:** effect dependency on `snapshotStatus` — when `snapshotStatus` is `"success"` or `"failed"` the effect returns early without setting an interval (no polling on terminal state)
- **Cleanup:** `return () => window.clearInterval(id)` clears the interval on modal close / unmount
- **Best-effort:** `try/catch` swallows transient network/API errors (mirrors `useMergeProgress`)

**`frontend/src/widgets/review-management/ProgressModal.test.tsx`** (new file — 10 tests)

| Test | What it verifies |
|------|-----------------|
| polls on interval | `fetchSyncProgress` called ≥ 2× over 2 intervals while open + non-terminal |
| merge forward-only (newer) | poll with newer `last_update_at` advances snapshot |
| merge forward-only (stale) | poll with older `last_update_at` does NOT overwrite current snapshot |
| stop on terminal (success) | no further calls after success snapshot applied |
| stop on terminal (failed) | no further calls after failed snapshot applied |
| stop on close (open=false) | interval cleared when `open` flips to false |
| stop on unmount | interval cleared when component unmounts |
| WS preserved | `MockWebSocket` instantiated on open (poll is additive) |
| 404 tolerated (with state) | null poll doesn't overwrite existing snapshot |
| 404 tolerated (no state) | null poll on empty state doesn't crash |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the poll is fully wired to the Plan-01 endpoint.

## Threat Flags

No new threat surface. T-27-07/08/09 mitigated as designed:
- T-27-08 (DoS): interval is gated (terminal stop + close cleanup) — no unbounded polling
- T-27-09 (Tampering): forward-only merge prevents stale replay from regressing displayed progress
- T-27-07 (Disclosure): auth enforced entirely server-side by the Plan-01 endpoint

## Self-Check: PASSED

- `frontend/src/widgets/review-management/api.ts` — `fetchSyncProgress` present
- `frontend/src/widgets/review-management/ProgressModal.tsx` — poll `useEffect` present, WS effect unchanged
- `frontend/src/widgets/review-management/ProgressModal.test.tsx` — 10 tests present
- Commit `5279093` exists: feat(27-02): add snapshot-poll fallback to ProgressModal (SYNC-REL-01 D-02)
- `npx vitest run src/widgets/review-management/ProgressModal.test.tsx` → 10 passed
- `npx tsc --noEmit` → 0 errors
- No file deletions in commit
