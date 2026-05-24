---
phase: 21
plan: 04
subsystem: frontend / audit-log widget
tags: [react, typescript, audit-log, ui]
dependency-graph:
  requires:
    - "21-01 (AuditLog selectors + serializer + cursor pagination)"
    - "21-02 (AuditLogViewSet wired at /api/v1/audit-logs/)"
  provides:
    - "AuditLogWidget — React mount for #audit-log-root"
    - "fetchAuditLogs(params, pageSize, cursor?) — typed audit-log API client"
    - "useAuditLog hook — cursor state + URL-synced filters"
    - "Vite entrypoint registered as audit-log"
  affects:
    - "frontend/vite.config.ts (single line added — new entry)"
tech-stack:
  added: []
  patterns:
    - "draft-then-apply filter pattern (matches ActionItemFilters)"
    - "cursor pagination via Link-header URLs returned in JSON next/previous"
    - "json_script-only data flow (no inline data-* JSON blobs)"
    - "one-row-expanded state held in the widget root (controlled via expandedId)"
key-files:
  created:
    - frontend/src/widgets/audit-log/types.ts
    - frontend/src/widgets/audit-log/utils.ts
    - frontend/src/widgets/audit-log/api.ts
    - frontend/src/widgets/audit-log/useAuditLog.ts
    - frontend/src/widgets/audit-log/TypePill.tsx
    - frontend/src/widgets/audit-log/AuditLogFilters.tsx
    - frontend/src/widgets/audit-log/AuditLogTable.tsx
    - frontend/src/widgets/audit-log/AuditLogWidget.tsx
    - frontend/src/entrypoints/audit-log.tsx
  modified:
    - frontend/vite.config.ts
decisions:
  - "Use `void _userRole` instead of removing the prop — keeps the entrypoint contract stable while we wait for Phase 22+ role-specific UI."
  - "Default 30d preset is computed in BOTH useAuditLog and AuditLogWidget. The hook needs it for initial filter state on mount; the widget needs it to compute `hasActiveFilters`. Keeping the helper duplicated rather than promoting to a shared module — the date-window constant is the same in both places and any future change must update both."
  - "URL param sync only fires on applyFilters/resetFilters (the explicit user gestures), not on preset clicks that themselves call applyFilters — the URL stays in sync without extra effects."
  - "Cursor back-navigation uses an in-memory stack (prevCursorsRef) AND falls back to the server-provided `previous` cursor when the stack is empty (e.g., after a hot reload mid-session)."
metrics:
  duration: ~25 min
  completed: 2026-05-23
---

# Phase 21 Plan 04: Audit Log React Widget Summary

Built the complete React widget for the Activity Log page — types, utilities, API
client, cursor-state hook, filter bar with 7d/30d/90d/Custom presets, 5-column data
table with expandable JSON detail rows, TypePill, the Vite entrypoint, and the
`vite.config.ts` registration — wiring directly to the `/api/v1/audit-logs/` API
shipped in plans 21-01 and 21-02.

## What was built

- **types.ts** — `AuditLogRow`, `AuditLogResponse`, `FilterParams`, `ActorOption`,
  and the `ACTION_LABEL` map (8 entries from D-20 + raw-string fallback).
- **utils.ts** — `formatRelativeDate` copied verbatim from `ReviewTable.tsx`
  (lines 37–49) per UI-SPEC instruction to avoid cross-widget imports.
- **api.ts** — `fetchAuditLogs(params, pageSize, cursor?)` using
  `credentials: "same-origin"`, with cursor-URL passthrough so the server's
  `next`/`previous` URLs are used unchanged.
- **useAuditLog.ts** — encapsulates filters, pageSize, cursor, prevCursors stack,
  rows, loading, error, `expandedId`, plus `goNext`, `goPrev`, `applyFilters`,
  `resetFilters`, `changePageSize`, and `refetch`. Reads URL params on mount;
  writes URL params via `pushState` on `applyFilters`/`resetFilters`.
- **TypePill.tsx** — blue "Reply" pill for `review`, amber "Action Item" pill for
  `action_item`. Renders raw type in `text-muted` for unknown values.
- **AuditLogFilters.tsx** — draft-then-apply filter bar. Type / Date Range /
  Actor / Apply / Reset. Presets 7d / 30d / 90d apply immediately; Custom keeps
  date inputs editable and requires Apply.
- **AuditLogTable.tsx** — wraps `DataTable<AuditLogRow>` with the 5 columns
  required by UI-SPEC §6. Expanded row renders `JSON.stringify(after_data, null, 2)`
  inside a `font-mono` `<pre>` with `max-h-48 overflow-y-auto`. Empty and error
  states match UI-SPEC §11–§12 copy.
- **AuditLogWidget.tsx** — composes everything. Cursor-pagination footer with
  page-size select (10/25/50) and Previous/Next buttons.
- **audit-log.tsx entrypoint** — mounts into `#audit-log-root`, reads
  `data-user-role` and the `audit-log-actors-data` json_script element.
- **vite.config.ts** — single line added to `rollupOptions.input`.

## Cross-checks against the API contract (Plans 21-01/02)

| Plan 21-04 expectation | Plan 21-01/02 reality | Match |
|---|---|---|
| API path `/api/v1/audit-logs/` | Wired at `/api/v1/audit-logs/` (21-02) | ✓ |
| Response keys: `next`, `previous`, `results` | `AuditLogCursorPagination` shape (21-01) | ✓ |
| Row shape: `id, created_at, entity_type, entity_id, action, actor_id, actor_name, after_data` | `AuditLogReadSerializer` fields (21-01) | ✓ |
| Filter params: `entity_type`, `actor`, `date_from`, `date_to` | `AuditLogFilterSet` (21-01) | ✓ |
| `actor=system` returns system-only entries | Selectors handle the literal `"system"` (21-01) | ✓ |
| `action_item.merged` payload = `{merged_ids: [...]}` (no `count`) | Producers in Phase 18 write `merged_ids` only (RESEARCH.md Pitfall 5) | ✓ |

## Verification gaps

`npx tsc --noEmit --project tsconfig.json` could not be executed in this worktree
— `frontend/node_modules` is not installed (this worktree skips frontend installs
to keep parallel-executor spin-up fast). Type discipline was applied manually:

- All exports have explicit return types.
- `FilterParams` and `AuditLogRow` are imported as `type`-only where used.
- `Props` for each component is declared inline; no `any` anywhere.
- The `Record<string, PillStyle | undefined>` cast in `TypePill` is the only
  cast in the patch — it's required because `entityType` is typed `string` so
  the union narrowing from `keyof TYPE_PILL` is intentionally widened to allow
  defensive rendering of unknown entity types.

Type-check should be re-run in CI (`make typecheck` or `npm --prefix frontend run typecheck`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] DataTable column interface uses `accessor`/`label`/`rowKey`, not `render`/`header`/`getRowKey`**
- **Found during:** Task 3 — drafting `AuditLogTable.tsx`
- **Issue:** The plan's `<interfaces>` block documented the DataTable API as
  `{key, header, render, getRowKey}` but the actual `DataTable.tsx` exports
  `DataTableColumn` with `{key, label, accessor, align?, skeletonWidth?}` and
  `DataTableProps` uses `rowKey` rather than `getRowKey`.
- **Fix:** Used the real `DataTable.tsx` API — `accessor` returns the cell node,
  `label` is the header text, `rowKey: (r) => r.id`. The expanded row is wired
  via the `renderExpanded` prop, which already has the correct colSpan logic
  built in (`columns.length + (renderRowActions ? 1 : 0)`).
- **Files modified:** `frontend/src/widgets/audit-log/AuditLogTable.tsx`
- **Commit:** 0db90ec

**2. [Rule 2 — Critical functionality] Added `refetch()` to the hook**
- **Found during:** Task 2 — drafting `useAuditLog.ts`
- **Issue:** The UI-SPEC §12 error state has a Retry button, but the plan-listed
  hook return signature only included goNext/goPrev/applyFilters/resetFilters
  with no way to re-fetch without otherwise mutating state. A user hitting Retry
  needs to retry the same query, not change the cursor or filters.
- **Fix:** Added a `refreshTick` state and exposed `refetch()` that increments
  it. The fetch effect depends on `refreshTick` so any change triggers a refetch.
- **Files modified:** `frontend/src/widgets/audit-log/useAuditLog.ts`
- **Commit:** 5aa906e

**3. [Rule 2 — Critical functionality] hasPrev falls back to server-provided `previous` cursor when stack is empty**
- **Found during:** Task 2
- **Issue:** Plan said `prevCursors` stack only — but if the user reloads the
  page mid-paginated session, the in-memory stack is empty even though the
  server may still emit a `previous` URL pointing back into the result window.
- **Fix:** `hasPrev = stack.length > 0 || Boolean(prevUrl)` and `goPrev` uses the
  server cursor when the stack is empty. This makes "Previous" work correctly
  after a refresh.
- **Files modified:** `frontend/src/widgets/audit-log/useAuditLog.ts`
- **Commit:** 5aa906e

### No Rule 4 (architectural) changes.

## Known Stubs

None. Every widget reads real data from `/api/v1/audit-logs/` and the actors
dropdown reads real data from the json_script element rendered by the template
in plan 21-03.

## Threat Flags

None. The widget makes a single `GET /api/v1/audit-logs/` with `same-origin`
credentials — same surface the threat register already covers (T-21-09 through
T-21-11). No new endpoints, no new auth paths, no new file access patterns.

## Self-Check: PASSED

Verified all created files exist:

- ✓ frontend/src/widgets/audit-log/types.ts
- ✓ frontend/src/widgets/audit-log/utils.ts
- ✓ frontend/src/widgets/audit-log/api.ts
- ✓ frontend/src/widgets/audit-log/useAuditLog.ts
- ✓ frontend/src/widgets/audit-log/TypePill.tsx
- ✓ frontend/src/widgets/audit-log/AuditLogFilters.tsx
- ✓ frontend/src/widgets/audit-log/AuditLogTable.tsx
- ✓ frontend/src/widgets/audit-log/AuditLogWidget.tsx
- ✓ frontend/src/entrypoints/audit-log.tsx
- ✓ frontend/vite.config.ts (modified — `audit-log` entry present)

Verified all commits exist:

- ✓ 913da9e — feat(21-04): types, utils, api, vite entry
- ✓ 5aa906e — feat(21-04): hook, TypePill, entrypoint
- ✓ 0db90ec — feat(21-04): AuditLogFilters, AuditLogTable, AuditLogWidget
