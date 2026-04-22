---
phase: "01"
plan: "05"
subsystem: "design-system"
status: "complete"
tags: ["react", "widgets", "modal", "data-table", "design-system", "accessibility", "vitest", "focus-trap"]
dependency_graph:
  requires: ["01-03 (vite/react setup)", "01-04 (component library)"]
  provides: ["Modal primitive", "ConfirmModal", "DataTable", "emitToast", "/__ui__/ showcase page"]
  affects: ["all phases using React modals or data tables"]
tech_stack:
  added:
    - "vitest@2.1.8 — frontend unit test runner"
    - "@testing-library/react@16.1.0 — React component testing"
    - "@testing-library/jest-dom@6.6.3 — jest-dom matchers for vitest"
    - "@testing-library/user-event@14.5.2 — realistic user interaction simulation"
    - "jsdom@25.0.1 — DOM environment for vitest"
  patterns:
    - "React portal pattern for Modal (document.body)"
    - "focus-trap-react with fallbackFocus for jsdom compatibility"
    - "shell_open/shell_close template split to enable Django block inheritance"
    - "emitToast — CustomEvent bridge between React and Alpine.js"
key_files:
  created:
    - "frontend/src/widgets/modal/Modal.tsx — React Modal primitive with focus-trap + portal + Escape + backdrop dismiss"
    - "frontend/src/widgets/modal/ConfirmModal.tsx — Confirmation modal amber/blue/red variants + type-to-confirm gate"
    - "frontend/src/widgets/modal/index.ts — public exports for modal widgets"
    - "frontend/src/widgets/modal/Modal.test.tsx — 8 vitest tests for Modal, ConfirmModal, emitToast"
    - "frontend/src/widgets/data-table/DataTable.tsx — Generic DataTable: loading skeleton (6 rows), empty state, populated rows, row actions"
    - "frontend/src/widgets/data-table/index.ts — public exports for data-table widget"
    - "frontend/src/widgets/data-table/DataTable.test.tsx — 4 vitest tests for DataTable states"
    - "frontend/src/lib/toast.ts — emitToast helper dispatching app:toast CustomEvent"
    - "frontend/src/entrypoints/showcase.tsx — React showcase entrypoint mounting all widgets"
    - "frontend/src/test-setup.ts — vitest test setup with jest-dom + cleanup"
    - "frontend/vitest.config.ts — vitest config with jsdom environment, esbuild JSX"
    - "templates/pages/showcase.html — Component showcase page at /__ui__/"
    - "templates/partials/shell_open.html — Shell opening wrapper (split for block inheritance)"
    - "templates/partials/shell_close.html — Shell closing wrapper"
    - "apps/common/tests/test_showcase.py — 3 Django pytest tests for /__ui__/"
  modified:
    - "frontend/package.json — added test scripts + vitest/testing-library devDependencies"
    - "frontend/vite.config.ts — added showcase entrypoint to rollupOptions.input"
    - "apps/common/views.py — added showcase view with fake pagination context"
    - "apps/common/urls.py — added path('__ui__/', showcase, name='showcase')"
    - "templates/base.html — restructured to use shell_open/shell_close for block inheritance"
    - "templates/partials/shell.html — updated to use shell_open/shell_close includes"
decisions:
  - "focus-trap-react fallbackFocus=document.body required for jsdom compatibility in tests (no tabbable nodes in jsdom)"
  - "vitest.config.ts uses esbuild JSX transform directly (not @vitejs/plugin-react) due to @vitejs/plugin-react@6.0.1 requiring vite ^8 while project uses vite 6.0.1"
  - "base.html restructured with shell_open/shell_close to fix Django block inheritance through {% include %} — {% block content %} was unreachable in included shell.html"
  - "@types/react and @types/react-dom bumped to 19.2.14 and 19.2.3 (pinned versions 19.2.5 did not exist)"
metrics:
  duration_minutes: 12
  completed_date: "2026-04-22"
  tasks_completed: 3
  tasks_total: 3
  files_created: 15
  files_modified: 6
  tests_added: 15
---

# Phase 01 Plan 05: React Widgets + Showcase Page Summary

**One-liner:** React Modal/ConfirmModal/DataTable widgets with focus-trap + vitest smoke tests, and a `/__ui__/` showcase page proving every design system primitive renders side-by-side.

## Execution Status

**3 of 3 tasks complete. Plan fully executed.**

---

## Tasks Completed

### Task 1: React Modal + ConfirmModal primitives with focus trap

Delivered:
- `Modal` — React portal + `focus-trap-react` with `fallbackFocus` for jsdom compatibility, Escape key dismiss, backdrop click dismiss, `role="dialog"` + `aria-modal="true"` + `aria-label="Close"` close button.
- `ConfirmModal` — amber/blue/red icon variants via lucide-react, locked "Cancel" button, configurable `confirmLabel`, optional `requireTypeToConfirm` gate that disables the confirm button until the user types the exact string.
- `emitToast` — dispatches `new CustomEvent('app:toast', { detail })` on window, picked up by Alpine.js `@app:toast.window` listener in `templates/components/toasts.html`.
- Vitest test infrastructure (`vitest@2.1.8`, `@testing-library/react@16.1.0`, `jsdom@25.0.1`).
- All 8 unit tests pass.

**Commit:** `471c534`

### Task 2: DataTable skeleton widget + showcase page

Delivered:
- `DataTable<T>` — Generic TypeScript component. `loading=true` → 6 skeleton rows with `data-testid="data-table-skeleton-row"`. Empty state (`emptyState` prop). Populated rows with `data-testid="data-table-row"` and row-actions slot (`opacity-35 group-hover:opacity-100`).
- `/__ui__/` showcase page — Django view rendering every template component (buttons, form fields, badges, empty state, skeletons, filter bar, pagination, toasts) plus React widget mount (`<div id="showcase-root">`).
- Fixed Django template block inheritance: `{% block content %}` in `shell.html` is inside `{% include %}` and is unreachable by child templates. Restructured to `shell_open.html` / `shell_close.html` with `{% block content %}` directly in `base.html`. Added `data-testid="main-content"` to `<main>`.
- All 4 DataTable vitest tests + all 3 Django showcase pytest tests pass.
- Total: 12 vitest tests + 52 Django tests passing.

**Commit:** `a1fb6c0`

---

## React Widget Public API

### Modal

```tsx
import { Modal } from 'frontend/src/widgets/modal';

<Modal
  open={boolean}               // required — controls visibility
  onClose={() => void}         // required — called on Escape / backdrop click
  title?: string               // renders h2 header with close button
  subtitle?: string            // muted subtext below title
  size?: 'sm' | 'default' | 'lg'   // default: 'default'
  dismissible?: boolean        // default: true — Escape + backdrop dismiss
  footer?: ReactNode           // renders in footer bar
>
  {children}
</Modal>
```

### ConfirmModal

```tsx
import { ConfirmModal } from 'frontend/src/widgets/modal';

<ConfirmModal
  open={boolean}
  onClose={() => void}
  onConfirm={() => void}
  variant: 'amber' | 'blue' | 'red'
  title: string
  message: ReactNode
  confirmLabel: string         // "Disable" | "Enable" | "Delete" | "Resend" (locked copy)
  requireTypeToConfirm?: string  // if set, confirm button disabled until user types exact match
/>
```

### DataTable

```tsx
import { DataTable, type DataTableColumn } from 'frontend/src/widgets/data-table';

const columns: DataTableColumn<Row>[] = [{
  key: string,
  label: string,
  accessor: (row: T) => ReactNode,
  align?: 'left' | 'right',
  skeletonWidth?: string,
}];

<DataTable<Row>
  columns={columns}
  rows={Row[]}
  loading?: boolean               // shows 6 skeleton rows
  emptyState?: ReactNode          // rendered when !loading && rows.length === 0
  renderRowActions?: (row) => ReactNode
  rowKey: (row: T) => string      // required unique key accessor
/>
```

### emitToast

```ts
import { emitToast } from 'frontend/src/lib/toast';

emitToast({ kind: 'success' | 'error' | 'info' | 'warning', title: string, msg?: string });
// Dispatches window CustomEvent 'app:toast' picked up by Alpine.js toasts.html
```

---

## How to Run Tests

```bash
# Frontend vitest (12 tests)
cd frontend && npm test

# Django pytest (52 tests)
.venv/bin/pytest apps/ --tb=short

# Full suite (requires docker-compose up)
make test
```

---

## Showcase URL

`http://localhost:8000/__ui__/` — renders every design system primitive (requires docker-compose up + superadmin login for protected pages; showcase is unauthenticated in Phase 1).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] @types/react / @types/react-dom version pinning**
- **Found during:** Task 1 (npm install)
- **Issue:** Plan specified `@types/react@19.2.5` and `@types/react-dom@19.2.5` but these exact versions do not exist on npm
- **Fix:** Bumped to `@types/react@19.2.14` (latest) and `@types/react-dom@19.2.3` (latest available)
- **Files modified:** `frontend/package.json`

**2. [Rule 1 - Bug] @vitejs/plugin-react vite compatibility conflict**
- **Found during:** Task 1 (vitest config)
- **Issue:** `@vitejs/plugin-react@6.0.1` requires `vite@^8.0.0` but project uses `vite@6.0.1`. Using the plugin in vitest.config.ts caused `ERR_PACKAGE_PATH_NOT_EXPORTED` at startup.
- **Fix:** Configured `vitest.config.ts` to use esbuild's native JSX transform (`esbuild: { jsx: 'automatic', jsxImportSource: 'react' }`) instead of the plugin. The React plugin is only needed for HMR in dev, not for test transforms.
- **Files modified:** `frontend/vitest.config.ts`

**3. [Rule 1 - Bug] focus-trap-react requires tabbable nodes — jsdom has none**
- **Found during:** Task 1 (vitest GREEN phase)
- **Issue:** `focus-trap-react` throws `"Your focus-trap must have at least one container with at least one tabbable node"` when activated in jsdom (no visible/focusable elements)
- **Fix:** Added `fallbackFocus: () => document.body` to `focusTrapOptions`. This satisfies focus-trap's requirement without affecting browser behavior.
- **Files modified:** `frontend/src/widgets/modal/Modal.tsx`

**4. [Rule 1 - Bug] Django template block inheritance through {% include %} is broken**
- **Found during:** Task 2 (Django tests)
- **Issue:** `{% block content %}{% endblock %}` in `templates/partials/shell.html` was unreachable by child templates using `{% extends "base.html" %}` because Django `{% include %}` does not participate in block inheritance. The showcase page rendered the shell but with empty `<main>`.
- **Fix:** Split `shell.html` into `shell_open.html` (sidebar + topbar) and `shell_close.html` (closing divs). Moved `{% block content %}` directly into `base.html` between the two includes. Added `data-testid="main-content"` to `<main>`.
- **Files modified:** `templates/base.html`, `templates/partials/shell.html`, created `templates/partials/shell_open.html`, `templates/partials/shell_close.html`

**5. [Rule 1 - Bug] Ruff N801 — inner class named `paginator`**
- **Found during:** Task 2 pre-commit
- **Issue:** Ruff N801 requires class names to use CapWords. The `_FakePage.paginator` inner class used lowercase.
- **Fix:** Extracted into a separate `_FakePaginator` class and assigned as instance attribute `paginator = _FakePaginator()`.
- **Files modified:** `apps/common/views.py`

---

## Human-Verify Checkpoint

Task 3 requires visual/functional verification of:
- Desktop 1440px layout, tablet 768px, mobile 375px
- Keyboard navigation (Tab, Enter, Escape, focus trap in modal)
- Screen reader ARIA announcements (VoiceOver / NVDA)
- Toast integration end-to-end
- Lighthouse accessibility audit

**Status:** Approved. All checks passed across 7 verification zones (desktop 1440px, tablet 768px, mobile 375px, keyboard navigation, screen reader ARIA, toast integration, color contrast Lighthouse audit).

---

## Phase Readiness

**DSYS-01..08 complete; ready for `/gsd:verify-work 01-foundation`**

All design system requirements fulfilled:
- DSYS-01..04: Shell chrome (sidebar 240px/64px/mobile drawer, topbar, nav active states)
- DSYS-05..06: Responsive breakpoints (1440/768/375) verified by human
- DSYS-07: React widgets (Modal, ConfirmModal, DataTable) with typed public API
- DSYS-08: Accessibility — WCAG AA contrast, keyboard navigation, focus trap, ARIA labels, screen reader announcements — all verified by human

---

## Self-Check: PASSED

All created files verified present. Task commits verified in git history:
- `471c534` feat(01-05): Modal, ConfirmModal, emitToast widgets
- `a1fb6c0` feat(01-05): DataTable widget, showcase page, shell template fix
- Task 3 human-verify checkpoint: approved 2026-04-22
