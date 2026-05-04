---
phase: 13-action-items-and-notifications
plan: 08
subsystem: notifications
tags: [react, vite, http-polling, notif-bell, topbar, NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05]

requires:
  - phase: 13-05
    provides: GET /api/v1/notifications/bell/ + POST /{id}/read/ + POST /mark-all-read/

provides:
  - frontend/src/widgets/notif-bell/types.ts (NotificationRow, BellResponse, NotificationType union)
  - frontend/src/widgets/notif-bell/api.ts (getBell, markRead, markAllRead with CSRF)
  - frontend/src/widgets/notif-bell/useNotifications.ts (60s HTTP poll hook, optimistic mark-read)
  - frontend/src/widgets/notif-bell/NotifBell.tsx (bell button + popover + 3 type icons + unread indicator)
  - frontend/src/entrypoints/notif-bell.tsx (mounts at #notif-bell-root)
  - vite entry "notif-bell" (registered in frontend/vite.config.ts)
  - Mount point #notif-bell-root in templates/partials/topbar.html (right of existing sync indicator)

affects: []

tech-stack:
  added: []
  patterns:
    - "HTTP polling via setInterval(60_000) — no WebSocket / Channels consumer (CLAUDE.md §13.2 mandate)"
    - "Initial fetch BEFORE setInterval (Pitfall 7) — avoids count-flash on mount"
    - "Optimistic UI on mark-read with server reconfirm via fetchBell()"
    - "Bell coexists additively with existing TopbarBell sync indicator (no modification)"
    - "django-vite {% vite_asset %} loader (matches topbar-sync-indicator pattern)"
    - "Outside-click + Escape close for popover (accessibility)"

key-files:
  created:
    - frontend/src/widgets/notif-bell/types.ts
    - frontend/src/widgets/notif-bell/api.ts
    - frontend/src/widgets/notif-bell/useNotifications.ts
    - frontend/src/widgets/notif-bell/NotifBell.tsx
    - frontend/src/entrypoints/notif-bell.tsx
  modified:
    - frontend/vite.config.ts (registered notif-bell entry; coordinated with 13-06)
    - templates/partials/topbar.html (added #notif-bell-root mount + {% vite_asset %} include)

key-decisions:
  - "HTTP polling, never WebSocket. CLAUDE.md §13.2 explicitly prohibits new Channels consumers; the bell counter MUST poll every 60s. setInterval(fetchBell, 60_000) inside useNotifications."
  - "Pitfall 7 mitigation: initial fetch fires inside useEffect BEFORE setInterval is scheduled. The bell renders count=0 (no badge) for ~1 RTT then populates — same flash window as the sync indicator's first paint, acceptable per UI-SPEC §5."
  - "Optimistic mark-read with reconfirm. setCount(c => c-1) and is_read flip happen synchronously before the POST; fetchBell() runs after the POST resolves to reconcile against any other tabs the user has open. Errors are swallowed because the next 60s poll will recover."
  - "Bell registered as a separate vite entry. No bundling with review-management — the bell loads on every authenticated page (it's in the topbar partial), so it must be its own small chunk (5.79 kB / 2.42 kB gzip vs the 27 kB review-management bundle)."
  - "Topbar mount uses {% vite_asset 'src/entrypoints/notif-bell.tsx' %}, matching the existing topbar-sync-indicator include pattern (django-vite)."
  - "Coordinated vite.config.ts edit: per the orchestrator coordination note, this plan added the notif-bell entry rather than waiting for 13-06. 13-06 simultaneously added action-items-management; the file accepts both entries cleanly with no merge conflict (additive lines in the same input map)."
  - "Widget kept stateless about server connectivity. On bell fetch error, the existing badge state is retained and the next poll retries; no error UI is rendered (the bell is best-effort per the dispatch service contract)."
  - "Inlined relativeTime helper rather than importing from review-management/. Keeps notif-bell loosely coupled. Future refactor (lift to lib/time.ts) noted in the source comment."

requirements-completed: [NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05]

duration: 3min
completed: 2026-05-04
---

# Phase 13 Plan 08: Notification Bell — Topbar Widget Summary

**Independent React notification bell rendered in the topbar to the right of the existing TopbarBell sync indicator. Polls `GET /api/v1/notifications/bell/` every 60 seconds via HTTP (NOT WebSocket, per CLAUDE.md §13.2). Numeric red badge with `99+` cap; click opens popover with up to 10 unread notifications, three icon types (Star / Sparkles / UserCheck), unread left-border indicator, mark-all-read; click row → optimistic mark-read + navigate to target_url.**

## Performance

- **Duration:** ~3 min
- **Tasks:** 2
- **Files created:** 5 (4 widget files + 1 entrypoint)
- **Files modified:** 2 (vite.config.ts entry registration + topbar.html mount)

## Accomplishments

- `types.ts` — `NotificationType` union (`new_review | new_action_item | action_item_assigned`), `NotificationRow`, `BellResponse` matching the 13-05 server contract.
- `api.ts` — `getBell()`, `markRead(id)`, `markAllRead()` with CSRF token from `csrftoken` cookie and `credentials: same-origin`. `ApiError` class for non-OK responses.
- `useNotifications.ts` — 60s polling hook. Initial fetch fires inside useEffect BEFORE `setInterval` is scheduled (Pitfall 7). Optimistic state updates on mark-read with server reconfirm via `fetchBell()`.
- `NotifBell.tsx` — `w-9 h-9` bell button with absolutely-positioned red badge (`min-w-[18px] h-[18px]`, `bg-red text-white text-[10px] font-semibold`). Popover (`w-[320px]`, `z-50`, `border-line`, `shadow-lg`) with header (Notifications / Mark all as read), notification rows with type-specific icons (Star yellow / Sparkles amber / UserCheck blue), unread border-left-yellow indicator, and "No new notifications" empty state. Outside-click + Escape close.
- `entrypoints/notif-bell.tsx` — `createRoot` mounts `<NotifBell />` at `#notif-bell-root` if present.
- `vite.config.ts` — registered `notif-bell` entry (additive edit; coexists cleanly with 13-06's `action-items-management` entry).
- `templates/partials/topbar.html` — `<div id="notif-bell-root" class="ml-2"></div>` placed immediately after the existing `#topbar-bell-root`; `{% vite_asset 'src/entrypoints/notif-bell.tsx' %}` include added beneath the existing sync-indicator vite_asset call.

## Task Commits

1. **Task 1: types + api + useNotifications hook + Vite entry + entrypoint** — `62646b5` (feat)
2. **Task 2: NotifBell component + topbar mount** — `b725a3c` (feat)

## Files Created/Modified

**Created:**
- `frontend/src/widgets/notif-bell/types.ts`
- `frontend/src/widgets/notif-bell/api.ts`
- `frontend/src/widgets/notif-bell/useNotifications.ts`
- `frontend/src/widgets/notif-bell/NotifBell.tsx`
- `frontend/src/entrypoints/notif-bell.tsx`

**Modified:**
- `frontend/vite.config.ts` — registered `"notif-bell"` entry (additive)
- `templates/partials/topbar.html` — added `#notif-bell-root` mount + `{% vite_asset %}` include for `notif-bell.tsx`

## Decisions Made

- **HTTP polling only.** `setInterval(fetchBell, 60_000)` inside `useNotifications`. Zero WebSocket code in this widget — verified by `grep -rn "WebSocket\|channels.consumer\|ws/notif" frontend/src/widgets/notif-bell/` returning no matches. CLAUDE.md §13.2 explicitly forbids adding a Channels consumer for the bell counter.
- **Initial fetch before interval (Pitfall 7).** The useEffect first invokes `void fetchBell()` and then schedules `setInterval`. Without this ordering, the bell would render count=0 for a full 60s before the first poll arrived, causing a perceived "missed notifications" flash when the badge finally appeared.
- **Optimistic mark-read with server reconfirm.** `markReadAndNavigate` decrements `count` and flips `is_read` synchronously, then fires the POST, then re-fetches the bell to reconcile against any other open tabs. Failure is swallowed because the next 60s poll will recover the true state.
- **Coordinated vite.config.ts edit.** Per the orchestrator's coordination note, this plan registered its `notif-bell` entry rather than deferring to 13-06. 13-06 simultaneously registered `action-items-management`; both edits were additive in the same `input` map and merged cleanly without conflict.
- **Bell coexists with sync indicator additively.** `templates/partials/topbar.html` retains `#topbar-bell-root` (sync indicator) untouched and adds `#notif-bell-root` immediately to its right with `class="ml-2"`. The two React roots are independent; neither component knows about the other.
- **Inlined `relativeTime` helper.** Avoids cross-widget coupling between notif-bell and review-management. If a single source of truth is later wanted, the source comment marks the lift point.
- **`role="menuitem"` on each notification button** with the popover container at `role="menu"` and `aria-label="Notifications"`. The bell button itself uses `aria-expanded`, `aria-haspopup="menu"`, and `aria-label` reflecting the live count (per UI-SPEC §Accessibility).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Coordination override] Vite entry registration**

- **Found during:** Task 1 prep (verifying `grep -n "notif-bell" frontend/vite.config.ts`).
- **Issue:** The plan body Step 4 stated "NO EDIT NEEDED" and asserted that 13-06 had already registered the entry. The current `vite.config.ts` had no `notif-bell` entry at the time of execution (13-06 was running in parallel and had not yet committed).
- **Resolution:** The orchestrator coordination note explicitly told this plan it "will edit `frontend/vite.config.ts`". I added the entry as an additive single line (`"notif-bell": resolve(__dirname, "src/entrypoints/notif-bell.tsx"),`) to keep the merge surface minimal. 13-06 subsequently added `"action-items-management"` to the same input map — both edits coexisted cleanly.
- **Files modified:** `frontend/vite.config.ts`
- **Committed in:** `62646b5`

**2. [Rule 3 - UX hardening] Added Escape-key close for popover**

- **Found during:** Task 2 implementation (writing the outside-click handler).
- **Issue:** UI-SPEC §5 says "Closes on outside click or Escape" but the plan body code snippet only showed outside-click. Adding Escape support is a trivial keyboard accessibility win and matches the spec.
- **Resolution:** Added a `keydown` handler in the same `useEffect` that closes on `Escape`.
- **Files modified:** `frontend/src/widgets/notif-bell/NotifBell.tsx`
- **Committed in:** `b725a3c`

---

**Total deviations:** 2 auto-fixed (both Rule 3 — non-architectural blocking/UX). No Rule 4 escalations.

## Issues Encountered

- None. Both `npx tsc --noEmit -p .` and `npx vite build` exited 0 on first run for both tasks. Build emits `notif-bell-CPuHgV7P.js` at 5.79 kB / 2.42 kB gzip — within budget for a topbar-loaded chunk.

## User Setup Required

None — the bell auto-mounts on every page that includes `templates/partials/topbar.html`. Backend dispatch service (Plan 13-05) is already wired for action item create/assign, enrichment success, and review sync new-row events. To verify visually:

1. Log in as Org Admin.
2. Trigger a new review (or insert a `Notification` row in `python manage.py shell`).
3. Within 60s the bell shows the badge.
4. Click → popover with the row.
5. Click row → navigates to `target_url` and badge decrements.

## Next Phase Readiness

- Phase 13 is now feature-complete in the topbar dimension. The bell + sync indicator coexist independently.
- Future enhancements (lazy fetch of full popover items only on open; pagination beyond 10; categorisation tabs) can layer on without touching the polling contract.
- If a future phase needs to broadcast notification updates faster than 60s, the architectural decision (per CLAUDE.md §13.2) requires sign-off before adding a Channels consumer. A simpler path would be to shorten the poll interval, with care for server load.

## Self-Check

Verifying claimed artifacts:

- `frontend/src/widgets/notif-bell/types.ts` — FOUND
- `frontend/src/widgets/notif-bell/api.ts` — FOUND (3 endpoints: bell/, /read/, /mark-all-read/)
- `frontend/src/widgets/notif-bell/useNotifications.ts` — FOUND (`setInterval(...60_000)` present; initial `void fetchBell()` BEFORE interval)
- `frontend/src/widgets/notif-bell/NotifBell.tsx` — FOUND (Star, Sparkles, UserCheck imported; `min-w-[18px] h-[18px]` badge; "Mark all as read" + "No new notifications" copy)
- `frontend/src/entrypoints/notif-bell.tsx` — FOUND (references `notif-bell-root`)
- `frontend/vite.config.ts` — MODIFIED (`"notif-bell"` entry registered)
- `templates/partials/topbar.html` — MODIFIED (`#notif-bell-root` + `{% vite_asset %}` for notif-bell)
- Existing `#topbar-bell-root` (sync indicator) preserved — VERIFIED via grep
- `cd frontend && npx tsc --noEmit -p .` — exits 0
- `cd frontend && npx vite build` — exits 0; emits `notif-bell-CPuHgV7P.js` (5.79 kB)
- `grep -rn "WebSocket\|channels.consumer\|ws/notif" frontend/src/widgets/notif-bell/` — returns 0 matches (HTTP polling only, NOTF-04 + CLAUDE.md §13.2 satisfied)
- Commit `62646b5` — FOUND
- Commit `b725a3c` — FOUND

## Self-Check: PASSED

---
*Phase: 13-action-items-and-notifications*
*Completed: 2026-05-04*
