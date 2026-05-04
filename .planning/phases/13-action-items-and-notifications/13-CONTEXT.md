---
phase: 13
phase_name: Action Items and Notifications
status: context_complete
created_at: "2026-05-03"
---

# Phase 13 Context — Action Items and Notifications

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the full ActionItem module and notification bell. Covers:

1. **ActionItem model and data layer** — promote Phase 12's `extracted_action_items` JSON into full `ActionItem` rows; support manual creation; status workflow with audit log
2. **Action Items list page** at `/admin/org/action-items/` — filterable, sortable table with row actions and three-dot menu
3. **Action Item modal** — three-tab detail view (Details, Notes, Source Review) with in-place editing and append-only notes
4. **Notification bell** — separate topbar icon showing unread count (numeric badge), opens popover with last 10 notifications; 60-second poll

Phase 12 owns enrichment and chip rendering scaffolding. Phase 13 promotes those JSON entries to real rows and makes the chips interactive.
Email notifications and notification preferences are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Status change UX

- **Three-dot row menu includes a full status submenu** — lists all 4 states (To Do, In Progress, Complete, Won't Do). User can transition to any state directly from the table row without opening a modal. This is the fastest path for the common "mark complete" action.
- **Modal status control is a dropdown at the top of the Details tab** — positioned near the modal title, styled inline (not a buttons row). Single click shows all 4 options; selecting one transitions immediately. Consistent with Linear / Asana-style detail views.
- **Status badge in the table row is decorative only** — it is display-only, not a click target. All status changes go through the three-dot submenu or the modal dropdown. No surprise interactive elements.

### Modal — Details tab and edit mode

- **Edit transforms in-place** — clicking the Edit button on the Details tab changes editable fields (Title, Priority, Due Date, Assignee) into inputs within the same tab. Save and Cancel appear at the bottom. No new modal, no navigation change. Consistent with Phase 11's ReplyComposer inline expand pattern.
- **ACTN-07 read-only fields still apply** — Scope and Shop are NOT editable for AI-extracted items even in edit mode (rendered as read-only text, not inputs).
- **Modal always opens on the Details tab** — regardless of how it was opened. Source Review tab is contextual and rarely the first thing needed.

### Modal — Notes tab

- **Always-visible textarea at the bottom** — a textarea and "Add note" submit button are permanently visible below the note timeline. No toggle button. Low friction — the input is immediately accessible when switching to the Notes tab.
- **Notes are append-only** (ACTN-10) — existing notes cannot be edited or deleted. Timeline shows newest-first or oldest-first (Claude's discretion — oldest-first is conventional for log-style timelines).

### Notification bell

- **Numeric badge** — a small circle with the unread count sits on the bell icon (e.g. "3"). Consistent with the existing TopbarBell sync indicator which also uses a numeric count. Badge disappears when count reaches 0.
- **Each notification row shows: title + shop name + relative time** — e.g. "3 new reviews at The Bakery · 5m ago". Enough context for Staff users to judge relevance without opening the page.
- **Two separate icons** — the existing sync indicator (TopbarBell) is unchanged. A new bell icon is added to the right of it for notifications. Each opens its own independent popover. No merging of sync state and notification inbox.
- **60-second HTTP poll** (NOTF-04) — counter refreshes immediately after any notification interaction (mark read, mark all read).

### AI chip click on review card

- **Clicking an action item chip navigates to** `/admin/org/action-items/?review={review_id}` — the action items page pre-filtered to show all items extracted from that review. Simple, reversible, consistent with the existing "Open in Reviews" reverse link on the action item modal (ACTN-11).
- **Hover affordance** — chips show `cursor: pointer` and a subtle darker background on hover to signal they are clickable. Visual treatment must not clash with the overall chip design.
- **Chips with no ActionItem rows remain non-interactive** — if a review has `extracted_action_items` JSON but Phase 13's promotion task hasn't created `ActionItem` rows yet (e.g. enrichment happened but promotion hasn't run), the chip should be non-interactive or disable the hover state. Exact behavior at Claude's discretion.

### Claude's Discretion

- Notes timeline sort order (oldest-first vs newest-first)
- Exact chip disabled state when ActionItem rows don't exist yet
- Empty state illustrations and copy for the action items list
- Loading skeleton design for the action items table
- Popover positioning and animation for the notification bell
- How the action items page handles the `?review=` query parameter when no items exist for that review

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Action Items requirements (ACTN-01 through ACTN-13)
- `.planning/REQUIREMENTS.md` §ACTN — All 13 acceptance criteria for the ActionItem module; covers data model, API, list page, modal tabs, edit constraints, status workflow, manual creation, audit log, and query count ceiling

### Notification requirements (NOTF-01 through NOTF-05)
- `.planning/REQUIREMENTS.md` §NOTF — All 5 notification requirements; covers badge style, notification types, click behaviour, poll interval, and Staff scoping

### Phase 12 context (enrichment handoff)
- `.planning/phases/12-ai-enrichment-pipeline/12-CONTEXT.md` — Action item storage decision: GPT output stored as `extracted_action_items = JSONField` on Review; Phase 13 promotes these to ActionItem rows. Also: REVW-08 rendering scaffolding already in place.

### Existing UI components (reuse)
- `frontend/src/widgets/data-table/DataTable.tsx` — Shared DataTable with `renderExpanded` and `renderRowActions` props; ReviewTable already uses it with inline accordion expansion
- `frontend/src/widgets/modal/Modal.tsx` — Base Modal with `open`, `onClose`, `title`, `size`, `footer` props; use for ActionItem detail modal
- `frontend/src/widgets/modal/ConfirmModal.tsx` — Confirm pattern (uses `open=` prop); reuse for delete confirmation
- `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` — Existing TopbarBell component; new notification bell must coexist alongside it without modifying it

### Established patterns
- `frontend/src/lib/toast.ts` — Toast API: `emitToast({kind, title})`; use for success/error feedback on status transitions and note submission
- `apps/reviews/services/enrichment.py` — Service/selector pattern; ActionItem services follow the same thin-service-function approach
- `apps/common/models.py` — TimeStampedModel base (use for ActionItem)
- `apps/reviews/models.py` — AuditLog model already exists (entity_type/entity_id string FK pattern, not GenericForeignKey); Phase 13 writes `action_item.*` events to it

### RBAC and scoping rules
- `CLAUDE.md` §9 — Phase 3 scope guardrail: Staff sees only SHOP-scoped items for their accessible shops; brand-scoped items blocked at selector + permission + UI layers
- `.planning/phases/11-reviews/11-CONTEXT.md` §Code Context → "Reusable assets" — StaffAccessScope pattern, IsOrgScoped permission, get_accessible_shop_ids selector

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DataTable` — columns, rows, renderRowActions, renderExpanded props. ActionItem table uses the same component without modification.
- `Modal` (`size="lg"`) — already handles three-tab content via children; tab switching is a local state concern within the ActionItemModal component.
- `ConfirmModal` — reuse for "delete action item" confirmation flow.
- `TopbarBell` (sync indicator) — the existing component reads `notificationCount` via prop from the entrypoint. New notification bell follows the same mount pattern at `<div id="notif-bell-root">` in `topbar.html`.
- `AuditLog` model — exists in `apps/reviews/models.py` (or `apps/common/`); Phase 13 writes `action_item.created`, `action_item.status_changed`, `action_item.assigned`, `action_item.note_added` events to it.
- `emitToast` — use for status transition success, note submission, manual creation success.

### Established Patterns
- **Services/Selectors pattern** — `apps/action_items/services/lifecycle.py` (create, status transitions, assignment, notes) and `apps/action_items/selectors/items.py` (list queries with Staff scoping). Views stay thin.
- **Celery task for promotion** — `enrich_review_task` already runs post-upsert. A `promote_action_items_task` (or inline promotion within `enrich_review`) converts `extracted_action_items` JSON to `ActionItem` rows after enrichment succeeds.
- **CursorPagination** — already used for reviews list (O(1) performance for large tables). ActionItem list uses PageNumberPagination (table has 10/25/50/100 selector per ACTN-05) — acceptable since action items won't approach review volumes.
- **`IsOrgScoped` + `StaffAccessScope`** — existing permission class and scope helper; ActionItem viewset reuses these for the Staff filter.

### Integration Points
- `templates/partials/topbar.html` — add `<div id="notif-bell-root">` mount point for the new notification bell entrypoint
- `frontend/src/entrypoints/` — new `action-items-management.tsx` entrypoint (for the list page widget) and `notif-bell.tsx` entrypoint (for the topbar bell)
- `apps/action_items/models.py` — currently a skeleton (`"""Phase 10 skeleton — models added in Phase 13."""`). Phase 13 adds the full model.
- `apps/notifications/models.py` — same skeleton. Phase 13 adds the `Notification` model.
- `apps/reviews/models.py` — `Review.extracted_action_items` JSONField exists; Phase 13 reads it to promote rows.
- `config/urls.py` — add `path("admin/org/action-items/", ...)` template view and `path("api/v1/action-items/", ...)` DRF router.

</code_context>

<specifics>
## Specific Ideas

- No specific "I want it like X" references were given — open to standard patterns consistent with the existing reviews/shops/team table and modal designs.
- The status submenu in the three-dot menu should visually indicate the current state (e.g. checkmark or highlight on the active status option) so the user can see at a glance what the item's status is before choosing.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-action-items-and-notifications*
*Context gathered: 2026-05-03*
