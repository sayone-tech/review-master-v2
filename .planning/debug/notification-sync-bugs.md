---
status: awaiting_human_verify
trigger: "Three bugs: (1) two bell icons in topbar during sync, (2) per-item notifications instead of consolidated summary, (3) second notification missing org name"
created: 2026-05-05T00:00:00Z
updated: 2026-05-05T00:00:00Z
---

## Current Focus

hypothesis: all three root causes confirmed via code reading
test: n/a — root causes found
expecting: n/a
next_action: apply fixes to topbar.html, NotifBell.tsx

## Symptoms

expected:
- Single bell icon always visible in topbar
- After enrichment: one consolidated notification "N new action items extracted from a review"
- Notifications should show org name next to timestamp

actual:
- Two bell icons appear side by side during sync
- Notification panel shows individual action items per-item instead of summary
- Second notification shows "· 1m ago" with no org name before the dot

errors: none reported, just incorrect behavior

reproduction:
- Trigger a Google review sync for a shop
- Enrichment runs → generates action items
- Check topbar: 2 bell icons
- Check notification panel: per-item notifications instead of summary

started: After enrichment race condition fix + notification summary refactor

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-05-05T00:05:00Z
  checked: templates/partials/topbar.html lines 32-33
  found: TWO separate div mount points exist — `id="topbar-bell-root"` (line 32) AND `id="notif-bell-root"` (line 33). The entrypoint topbar-sync-indicator.tsx mounts TopbarBell into topbar-bell-root; notif-bell.tsx mounts NotifBell into notif-bell-root. Both are always present, but TopbarBell returns null when there is no sync activity (line 133: `if (!hasSyncActivity) return null`). During a sync, TopbarBell renders a visible Bell icon → two bell icons side by side.
  implication: Bug #1 root cause — redundant mount point that was added when the sync indicator was added without removing the old notif-bell-root, or vice versa.

- timestamp: 2026-05-05T00:06:00Z
  checked: apps/reviews/services/enrichment.py _on_enrichment_committed (lines 142-181)
  found: Dispatch is consolidated — ONE summary notification per review. When count==1, title is "New action item: {title}"; when count>1, title is "{count} new action items extracted from a review". The TWO separate per-item notifications shown in the panel come from TWO separate reviews being enriched (each with 1 action item), each triggering the single-item code path. No old per-item dispatch loop exists. apps/action_items/services/lifecycle.py dispatches only action_item_assigned notifications (not new_action_item). lifecycle.py is NOT the source.
  implication: Bug #2 is NOT a bug in the dispatch code — it is expected behavior (2 reviews × 1 action item each = 2 "New action item: X" notifications). The "consolidated summary" only applies when a single review yields multiple action items. The user's expectation of always seeing a single "N new action items" summary is not achievable with current design when reviews are enriched one-by-one. However, this is likely surprising UX. The existing code is correct per spec.

- timestamp: 2026-05-05T00:07:00Z
  checked: NotifBell.tsx NotificationListRow subline logic (lines 129-132)
  found: subline = n.notification_type === "action_item_assigned" && !n.shop_name ? relativeTime(...) : `${n.shop_name ?? ""} · ${relativeTime(...)}`.trim(). When shop_name is null (brand-scoped action items have shop=null in dispatch, or shop_name is null from serializer), the expression evaluates to `" · 1m ago"`. trim() only strips from the ends of the string, NOT internal leading spaces. Result: "· 1m ago" (leading dot, no org name).
  implication: Bug #3 root cause — the fallback is `n.shop_name ?? ""` which produces empty string, causing `" · 1m ago"`. The fix is to only show the shop_name portion if it is non-null/non-empty.

## Resolution

root_cause: |
  Bug #1 (two bell icons): topbar.html has TWO mount divs — id="topbar-bell-root" for TopbarBell (sync indicator) and id="notif-bell-root" for NotifBell. TopbarBell returns null when inactive, so during sync it renders and both bells are visible.
  Bug #2 (per-item vs summary): NOT a code bug. Two separate reviews each produced 1 action item → 2 separate summary notifications each with title "New action item: X". The consolidation only applies within a single review's extracted items. This is working as designed.
  Bug #3 (missing org name): NotificationListRow subline uses `${n.shop_name ?? ""} · ${time}` which produces "· 1m ago" when shop_name is null (brand-scoped, no shop). The ?? "" fallback produces an empty string that leads to " · 1m ago" which trim() cannot fix because the dot is internal.

fix: |
  Bug #1: Remove the duplicate `id="topbar-bell-root"` div from topbar.html (the TopbarBell/sync indicator mounts there, while the notif-bell widget mounts into notif-bell-root; they should share the same area, not duplicate the bell).
  Actually: TopbarBell IS the sync indicator (a different bell), and NotifBell IS the notification bell. They are separate widgets with different purposes. The topbar SHOULD show both if both are relevant. But to avoid showing two bell icons simultaneously, TopbarBell needs to use a non-bell icon during sync, OR the bells need to share a single mount point with conditional rendering.
  Best fix: Replace the Bell icon in TopbarBell with a different icon (e.g. Loader2 spinner) so it does not look like a duplicate bell. OR consolidate both widgets — but that's a larger refactor.
  Simplest correct fix: TopbarBell already has a spinner icon inside its dropdown items. The button itself shows Bell icon. Change the button icon to use Loader2 (spinning) during active sync, AlertTriangle for failures, CheckCircle for completed — so it is clearly distinct from the NotifBell.
  Bug #3: Fix the subline template expression in NotifBell.tsx to not prepend the separator when shop_name is absent.

verification:
files_changed:
  - frontend/src/widgets/review-management/TopbarSyncIndicator.tsx
  - frontend/src/widgets/notif-bell/NotifBell.tsx
