---
plan: 3
phase: 7
slug: regions
wave: 2
status: pending
requirements: [RGN-01, RGN-02, RGN-03, RGN-04, RGN-05, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11]
---

# Plan 3 — Frontend: React Region Management Widget

## Goal

Build the complete React region-management widget: type definitions, API layer, data hook, table with inline action buttons, empty state, Create modal with auto-ID state machine, Edit modal (no auto-ID), delete-blocked amber popup (RGN-10), and red delete confirmation popup (RGN-11). Wire Vite entrypoint and register in `vite.config.ts`.

## Wave 0 Dependencies

The backend (Plans 01 and 02) must be complete before the frontend can be exercised against the real API. However, the frontend files can be written in parallel with Plan 02 if desired; the Vite build does not depend on the Django server.

Plan 01 must be complete so that the Django template (`templates/regions/region_list.html`) and the URL at `/admin/org/regions/` exist.

---

## Tasks

### Task 7-03-01: Create types, API layer, data hook, and Vite entrypoint registration

**Requirement:** RGN-01, RGN-04, RGN-05, RGN-06, RGN-07, RGN-09, RGN-10, RGN-11

**Files:**
- `frontend/src/widgets/region-management/types.ts`
- `frontend/src/widgets/region-management/api.ts`
- `frontend/src/widgets/region-management/useRegions.ts`
- `frontend/src/entrypoints/region-management.tsx`
- `vite.config.ts`

**Action:**

**`frontend/src/widgets/region-management/types.ts`** — TypeScript types matching the backend `RegionReadSerializer` output and the API contract from `07-UI-SPEC.md`:

```typescript
export interface RegionRow {
  id: number;
  name: string;
  region_id: string;
  created_at: string; // ISO 8601
}

export interface CreateRegionPayload {
  name: string;
  region_id: string;
}

export interface UpdateRegionPayload {
  name?: string;
  region_id?: string;
}

export interface RegionBlockedError {
  shop_count: number;
}
```

**`frontend/src/widgets/region-management/api.ts`** — Follow the `org-management/api.ts` pattern exactly. CSRF token from cookie, `credentials: "same-origin"`, `Content-Type: application/json`. The `deleteRegion` function MUST return `RegionBlockedError` when the server returns 409 (do NOT throw — the caller checks the return type to decide which popup to show):

```typescript
import type { CreateRegionPayload, RegionBlockedError, RegionRow, UpdateRegionPayload } from "./types";

function getCsrfToken(): string {
  const name = "csrftoken";
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [key, val] = cookie.trim().split("=");
    if (key === name) return decodeURIComponent(val ?? "");
  }
  return "";
}

function headers(method: string): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (["POST", "PATCH", "PUT", "DELETE"].includes(method)) {
    h["X-CSRFToken"] = getCsrfToken();
  }
  return h;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(`API error ${status}`);
  }
}

async function handle(resp: Response): Promise<unknown> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new ApiError(resp.status, data);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export async function listRegions(): Promise<RegionRow[]> {
  const resp = await fetch("/api/v1/regions/", {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  const data = await handle(resp) as { results?: RegionRow[] } | RegionRow[];
  // Handle both paginated (DRF PageNumberPagination) and plain array responses
  if (Array.isArray(data)) return data;
  return (data as { results: RegionRow[] }).results ?? [];
}

export async function createRegion(payload: CreateRegionPayload): Promise<RegionRow> {
  const resp = await fetch("/api/v1/regions/", {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as RegionRow;
}

export async function updateRegion(id: number, payload: UpdateRegionPayload): Promise<RegionRow> {
  const resp = await fetch(`/api/v1/regions/${id}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return (await handle(resp)) as RegionRow;
}

export async function deleteRegion(id: number): Promise<void | RegionBlockedError> {
  const resp = await fetch(`/api/v1/regions/${id}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  if (resp.status === 409) {
    const body = await resp.json() as RegionBlockedError;
    return body; // caller checks: if (result && "shop_count" in result) → blocked
  }
  await handle(resp);
}
```

**`frontend/src/widgets/region-management/useRegions.ts`** — Data hook. Reads the initial data from `window.__regionData` (seeded by Django's `json_script` filter and parsed in the entrypoint) and re-fetches on the `region:refresh` custom event. Exposes `rows`, `loading`, and `refresh()`:

```typescript
import { useState, useEffect, useCallback } from "react";
import type { RegionRow } from "./types";
import { listRegions } from "./api";

export function useRegions(initialRows: RegionRow[]) {
  const [rows, setRows] = useState<RegionRow[]>(initialRows);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRegions();
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener("region:refresh", handler);
    return () => window.removeEventListener("region:refresh", handler);
  }, [refresh]);

  return { rows, loading, refresh };
}
```

**`frontend/src/entrypoints/region-management.tsx`** — Two-root pattern. Mirrors `org-management.tsx` exactly. Mounts `#region-modals-root` always (holds `RegionModals` component which renders all modals + CreateButtonBridge). Mounts `#region-table-root` only when it exists in the DOM (present when `regions_count > 0` per Django template). Reads initial data from the `<script id="region-data">` json_script tag:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RegionModals } from "../widgets/region-management/RegionModals";
import { RegionTableWidget } from "../widgets/region-management/RegionTable";

// Parse initial data seeded by Django json_script
function parseInitialData() {
  const el = document.getElementById("region-data");
  if (!el) return [];
  try {
    return JSON.parse(el.textContent ?? "[]");
  } catch {
    return [];
  }
}

const initialRows = parseInitialData();

const modalsRoot = document.getElementById("region-modals-root");
if (modalsRoot) {
  createRoot(modalsRoot).render(
    <StrictMode>
      <RegionModals initialRows={initialRows} />
    </StrictMode>,
  );
}

const tableRoot = document.getElementById("region-table-root");
if (tableRoot) {
  createRoot(tableRoot).render(
    <StrictMode>
      <RegionTableWidget initialRows={initialRows} />
    </StrictMode>,
  );
}
```

**`vite.config.ts`** — Add `"region-management"` to `rollupOptions.input`:

```typescript
rollupOptions: {
  input: {
    "app-shell": resolve(__dirname, "src/entrypoints/app-shell.ts"),
    showcase: resolve(__dirname, "src/entrypoints/showcase.tsx"),
    "org-management": resolve(__dirname, "src/entrypoints/org-management.tsx"),
    "region-management": resolve(__dirname, "src/entrypoints/region-management.tsx"),
  },
},
```

**Test:** `cd frontend && npm run build 2>&1 | tail -20` — confirm `region-management` appears in the manifest output without errors.

**Done:** `types.ts`, `api.ts`, `useRegions.ts`, and `region-management.tsx` exist. Vite config includes the new entrypoint. `npm run build` succeeds (no TypeScript errors).

---

### Task 7-03-02: Build region table, badges, empty state, create/edit modals, and delete popups

**Requirement:** RGN-01, RGN-02, RGN-03, RGN-04, RGN-05, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11

**Files:**
- `frontend/src/widgets/region-management/RegionIdBadge.tsx`
- `frontend/src/widgets/region-management/RegionEmptyState.tsx`
- `frontend/src/widgets/region-management/RegionTable.tsx`
- `frontend/src/widgets/region-management/CreateRegionModal.tsx`
- `frontend/src/widgets/region-management/EditRegionModal.tsx`
- `frontend/src/widgets/region-management/RegionModals.tsx`
- `frontend/src/widgets/region-management/RegionModals.test.tsx`

**Action:**

**`frontend/src/widgets/region-management/RegionIdBadge.tsx`** — Monospace pill, no dot indicator, neutral colors. Matches `TypeBadge` pattern from `OrgTable.tsx`:

```tsx
export function RegionIdBadge({ regionId }: { regionId: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-[3px] rounded-[999px] text-[12px] font-normal font-mono bg-line-soft text-muted"
      data-testid="region-id-badge"
    >
      {regionId}
    </span>
  );
}
```

**`frontend/src/widgets/region-management/RegionEmptyState.tsx`** — MapPin icon, "No regions yet" heading, body text, yellow CTA button. Button id `"open-create-region-empty"` is listened to by `CreateButtonBridge` in `RegionModals`:

```tsx
import { MapPin } from "lucide-react";

export function RegionEmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center py-16"
      data-testid="regions-empty-state"
    >
      <MapPin size={40} className="text-faint" />
      <h3 className="text-[15px] font-semibold text-ink mt-4">No regions yet</h3>
      <p className="text-[13.5px] text-muted mt-1.5">
        Regions help you organise your shops by area or location.
      </p>
      <button
        id="open-create-region-empty"
        className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
      >
        Create your first region
      </button>
    </div>
  );
}
```

**`frontend/src/widgets/region-management/RegionTable.tsx`** — Wraps `DataTable` with 3-column config (Name, Region ID pill, Actions). Action buttons are direct Edit (`Pencil`) + Delete (`Trash2`) icon buttons — NO three-dot menu (RGN-01 is explicit). Opacity trick on action cell: `opacity-35 group-hover:opacity-100 transition-opacity`. Exports both `RegionTable` (just the table) and `RegionTableWidget` (table + event-driven refresh wiring):

```tsx
import { Pencil, Trash2 } from "lucide-react";
import { DataTable } from "../data-table/DataTable";
import { RegionIdBadge } from "./RegionIdBadge";
import { RegionEmptyState } from "./RegionEmptyState";
import { useRegions } from "./useRegions";
import type { RegionRow } from "./types";

interface RegionTableProps {
  rows: RegionRow[];
  loading: boolean;
  onEdit: (region: RegionRow) => void;
  onDelete: (region: RegionRow) => void;
}

export function RegionTable({ rows, loading, onEdit, onDelete }: RegionTableProps) {
  const columns = [
    {
      key: "name" as const,
      header: "REGION NAME",
      skeletonWidth: "140px",
      render: (row: RegionRow) => (
        <span className="text-[13.5px] font-normal text-ink">{row.name}</span>
      ),
    },
    {
      key: "region_id" as const,
      header: "REGION ID",
      skeletonWidth: "80px",
      render: (row: RegionRow) => <RegionIdBadge regionId={row.region_id} />,
    },
    {
      key: "actions" as const,
      header: "",
      className: "w-20",
      render: (row: RegionRow) => (
        <div className="flex items-center gap-2 opacity-35 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onEdit(row)}
            aria-label={`Edit ${row.name}`}
            className="w-8 h-8 inline-flex items-center justify-center text-subtle hover:text-ink rounded"
          >
            <Pencil size={15} />
          </button>
          <button
            onClick={() => onDelete(row)}
            aria-label={`Delete ${row.name}`}
            className="w-8 h-8 inline-flex items-center justify-center text-subtle hover:text-red rounded"
          >
            <Trash2 size={15} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <DataTable
      rows={rows}
      columns={columns}
      loading={loading}
      emptyState={<RegionEmptyState />}
    />
  );
}

export function RegionTableWidget({ initialRows }: { initialRows: RegionRow[] }) {
  const { rows, loading } = useRegions(initialRows);

  const handleEdit = (region: RegionRow) => {
    window.dispatchEvent(new CustomEvent("region:open-edit", { detail: region }));
  };

  const handleDelete = (region: RegionRow) => {
    window.dispatchEvent(new CustomEvent("region:open-delete", { detail: region }));
  };

  return <RegionTable rows={rows} loading={loading} onEdit={handleEdit} onDelete={handleDelete} />;
}
```

**`frontend/src/widgets/region-management/CreateRegionModal.tsx`** — Contains the `autoMode` state machine (RGN-04 / RGN-05). When `autoMode` is `true`, every keystroke in the Region Name field triggers `deriveRegionId`. User editing the Region ID sets `autoMode = false`. Clearing the Region ID field sets `autoMode = true` (RGN-05). No auto-ID in edit mode — this component is Create only. Field styling from `07-UI-SPEC.md` Surface 4. Submit button is yellow with spinner when submitting:

```tsx
import { useState, useCallback } from "react";
import { Modal } from "../modal/Modal";
import { ApiError, createRegion } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionRow } from "./types";

function deriveRegionId(name: string, count: number): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const prefix = words
    .slice(0, 4)
    .map((w) => w[0].toUpperCase())
    .join("");
  const suffix = String(count + 1).padStart(3, "0");
  return prefix + suffix;
}

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls = "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface CreateRegionModalProps {
  open: boolean;
  regionCount: number;
  onClose: () => void;
  onCreated: (region: RegionRow) => void;
}

export function CreateRegionModal({ open, regionCount, onClose, onCreated }: CreateRegionModalProps) {
  const [name, setName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [autoMode, setAutoMode] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; region_id?: string }>({});

  const reset = useCallback(() => {
    setName("");
    setRegionId("");
    setAutoMode(true);
    setErrors({});
    setSubmitting(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setName(val);
    if (autoMode) {
      setRegionId(deriveRegionId(val, regionCount));
    }
  };

  const handleRegionIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setRegionId(val);
    if (val === "") {
      setAutoMode(true); // RGN-05: resume auto-population when cleared
    } else {
      setAutoMode(false); // RGN-04: stop auto-population on manual edit
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setSubmitting(true);
    try {
      const region = await createRegion({ name, region_id: regionId });
      emitToast({ type: "success", title: `Region '${region.name}' created.` });
      onCreated(region);
      reset();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors(err.data as { name?: string; region_id?: string });
      } else {
        emitToast({ type: "error", title: "Something went wrong.", message: "Please try again. If the problem persists, contact support." });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Create Region"
      subtitle="Enter a name and ID for the new region."
      size="default"
      onClose={handleClose}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-region-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting && (
              <span className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
            )}
            Create Region
          </button>
        </>
      }
    >
      <form id="create-region-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="create-region-name" className={labelCls}>Region Name</label>
          <input
            id="create-region-name"
            type="text"
            value={name}
            onChange={handleNameChange}
            placeholder="e.g. North West"
            className={errors.name ? inputErrorCls : inputCls}
            autoFocus
          />
          {errors.name && (
            <p role="alert" data-testid="error-create-region-name" className="mt-1 text-[12px] text-red">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="create-region-id" className={labelCls}>Region ID</label>
          <input
            id="create-region-id"
            type="text"
            value={regionId}
            onChange={handleRegionIdChange}
            placeholder="e.g. NW001"
            className={errors.region_id ? inputErrorCls : inputCls}
            data-testid="field-region_id"
            data-auto-mode={autoMode}
          />
          {errors.region_id && (
            <p role="alert" data-testid="error-create-region-id" className="mt-1 text-[12px] text-red">
              {Array.isArray(errors.region_id) ? errors.region_id[0] : errors.region_id}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
```

**`frontend/src/widgets/region-management/EditRegionModal.tsx`** — Same field structure as Create but with NO `autoMode` logic at all. Both fields pre-filled from `region` prop. Typing in Region Name does NOT update Region ID (RGN-08). Clearing Region ID leaves it empty — no auto-resume (CONTEXT.md: edit mode auto-resume is disabled). Submit button label is "Save Region":

Create `EditRegionModal` with the same `inputCls`/`labelCls` constants and `Modal` wrapper, but:
- No `autoMode` state variable
- `handleNameChange` only calls `setName` — never touches `setRegionId`
- `handleRegionIdChange` only calls `setRegionId`
- Footer submit button label: `"Save Region"`
- On success: `emitToast({ type: "success", title: "Region updated." })`
- Calls `updateRegion(region.id, { name, region_id: regionId })`

**`frontend/src/widgets/region-management/RegionModals.tsx`** — Orchestrator component that manages all modal state, the `CreateButtonBridge` pattern, and dispatches `region:refresh` after mutations. Uses `window.addEventListener` for `"region:open-edit"` and `"region:open-delete"` events from the table widget. Manages four state booleans: `createOpen`, `editOpen`, `deleteBlockedOpen`, `deleteConfirmOpen`. Also manages `selectedRegion: RegionRow | null` and `blockedShopCount: number`.

Import and use `ConfirmModal` (from `../modal/ConfirmModal`) for the red delete confirmation (RGN-11). Use `Modal` directly (from `../modal/Modal`) with a custom amber icon block for the delete-blocked popup (RGN-10) — do NOT use `ConfirmModal` for this because `ConfirmModal` forces a two-button footer and RGN-10 needs only a single "Got it" button.

Delete-blocked popup body copy (from `07-UI-SPEC.md`): `"This region has {count} shop{count > 1 ? 's' : ''} assigned to it. Reassign or remove all shops before deleting this region."` with a "Manage Shops" link to `/admin/org/shops/?region={region.pk}` (integer PK — CONTEXT.md §Shops pre-filter URL).

Delete confirmation popup uses `ConfirmModal` with `variant="red"`, `title="Delete region"`, `confirmLabel={submitting ? "Deleting…" : "Delete Region"}`. On confirm, calls `deleteRegion(region.id)`. If the response is a `RegionBlockedError` object (has `shop_count`), close the red popup and open the amber blocked popup instead. If success (undefined return), emit toast `"Region '{name}' deleted."` and dispatch `region:refresh`.

**`frontend/src/widgets/region-management/RegionModals.test.tsx`** — Vitest unit tests for the auto-ID mechanic and autoMode state:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CreateRegionModal } from "./CreateRegionModal";

describe("CreateRegionModal — auto-ID mechanic (RGN-04 / RGN-05)", () => {
  it("populates Region ID from Region Name as user types", () => {
    render(
      <CreateRegionModal open={true} regionCount={3} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(nameInput, { target: { value: "North West" } });
    expect(idInput).toHaveValue("NW004");
    expect(idInput).toHaveAttribute("data-auto-mode", "true");
  });

  it("stops auto-population when Region ID is manually edited", () => {
    render(
      <CreateRegionModal open={true} regionCount={0} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(idInput, { target: { value: "MANUAL1" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "false");
    fireEvent.change(nameInput, { target: { value: "North East" } });
    expect(idInput).toHaveValue("MANUAL1"); // not overwritten
  });

  it("resumes auto-population when Region ID is cleared (RGN-05)", () => {
    render(
      <CreateRegionModal open={true} regionCount={0} onClose={() => {}} onCreated={() => {}} />,
    );
    const nameInput = screen.getByPlaceholderText("e.g. North West");
    const idInput = screen.getByTestId("field-region_id");
    fireEvent.change(idInput, { target: { value: "MANUAL1" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "false");
    fireEvent.change(idInput, { target: { value: "" } });
    expect(idInput).toHaveAttribute("data-auto-mode", "true");
    fireEvent.change(nameInput, { target: { value: "South East" } });
    expect(idInput).toHaveValue("SE001");
  });
});

describe("EditRegionModal — no auto-ID in edit mode (RGN-08)", () => {
  it("typing in Region Name does not update Region ID in edit mode", async () => {
    const { EditRegionModal } = await import("./EditRegionModal");
    const region = { id: 1, name: "Old Name", region_id: "OLD001", created_at: "" };
    render(
      <EditRegionModal open={true} region={region} onClose={() => {}} onUpdated={() => {}} />,
    );
    const nameInput = screen.getByDisplayValue("Old Name");
    const idInput = screen.getByDisplayValue("OLD001");
    fireEvent.change(nameInput, { target: { value: "New Name Changed" } });
    expect(idInput).toHaveValue("OLD001"); // Region ID unchanged
  });
});
```

**Test:** `cd frontend && npm run test -- region-management`

**Done:**
- All 3 vitest tests pass (auto-ID populates, stops on manual edit, resumes on clear)
- Edit modal test confirms Region ID does not change when Region Name is typed
- `npm run build` succeeds with `region-management` in manifest
- Widget renders correctly at `/admin/org/regions/` (visual check):
  - Empty state shows MapPin icon + "No regions yet" heading + yellow CTA
  - Table renders with Name, Region ID pill (monospace badge), Edit + Delete icon buttons
  - Create modal auto-ID fires on every keystroke
  - Delete blocked (RGN-10): amber Modal with single "Got it" button, shop count, Manage Shops link to `/admin/org/shops/?region={pk}`
  - Delete confirm (RGN-11): red ConfirmModal, "Delete Region" button, toast on success

---

## Requirements Coverage

| Requirement | Task | Status |
|-------------|------|--------|
| RGN-01 | 7-03-02 (RegionTable, direct Edit/Delete buttons, RegionIdBadge) | pending |
| RGN-02 | 7-03-02 (RegionEmptyState with MapPin, heading, CTA) | pending |
| RGN-03 | 7-03-02 (CreateRegionModal fields, validation display) | pending |
| RGN-04 | 7-03-01 (deriveRegionId fn) + 7-03-02 (autoMode state machine in CreateRegionModal) | pending |
| RGN-05 | 7-03-02 (autoMode = true when regionId cleared; test in RegionModals.test.tsx) | pending |
| RGN-06 | 7-03-02 (ApiError 400 → inline error "This Region ID is already in use.") | pending |
| RGN-07 | 7-03-02 (createRegion → emitToast "Region '{name}' created." → region:refresh) | pending |
| RGN-08 | 7-03-02 (EditRegionModal, no autoMode, typing name does not update ID) | pending |
| RGN-09 | 7-03-02 (updateRegion → emitToast "Region updated." → region:refresh) | pending |
| RGN-10 | 7-03-01 (deleteRegion returns 409 body) + 7-03-02 (amber Modal, shop count, Manage Shops link) | pending |
| RGN-11 | 7-03-02 (red ConfirmModal → deleteRegion → toast "Region '{name}' deleted.") | pending |
