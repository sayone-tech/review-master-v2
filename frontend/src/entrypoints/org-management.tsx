import { useState, StrictMode, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { OrgTable } from "../widgets/org-management/OrgTable";
import { CreateOrgModal } from "../widgets/org-management/CreateOrgModal";
import { ViewOrgModal } from "../widgets/org-management/ViewOrgModal";
import { EditOrgModal } from "../widgets/org-management/EditOrgModal";
import { DisableConfirmModal } from "../widgets/org-management/DisableConfirmModal";
import { EnableConfirmModal } from "../widgets/org-management/EnableConfirmModal";
import { DeleteConfirmModal } from "../widgets/org-management/DeleteConfirmModal";
import { StoreAllocationModal } from "../widgets/org-management/StoreAllocationModal";
import { ResendInvitationModal } from "../widgets/org-management/ResendInvitationModal";
import { useOrgs } from "../widgets/org-management/useOrgs";
import type { OrgRow } from "../widgets/org-management/types";

/**
 * The Create button(s) are rendered by Django template (so they appear inside
 * the page header / empty-state before React mounts). This component listens
 * for clicks on any element with id "open-create-org" OR "open-create-org-empty"
 * and triggers the React modal.
 */
function CreateButtonBridge({ onOpen }: { onOpen: () => void }) {
  useEffect(() => {
    const ids = ["open-create-org", "open-create-org-empty"];
    const handlers: Array<{ btn: HTMLElement; handler: () => void }> = [];

    for (const id of ids) {
      const btn = document.getElementById(id);
      if (btn) {
        const handler = () => onOpen();
        btn.addEventListener("click", handler);
        handlers.push({ btn, handler });
      }
    }

    return () => {
      for (const { btn, handler } of handlers) {
        btn.removeEventListener("click", handler);
      }
    };
  }, [onOpen]);
  return null;
}

/**
 * OrgModals — always mounts on #org-modals-root so that Create modal and
 * CreateButtonBridge are available regardless of whether the table has rows.
 */
function OrgModals() {
  const { refresh } = useOrgs();

  const [createOpen, setCreateOpen] = useState(false);
  const [viewRow, setViewRow] = useState<OrgRow | null>(null);
  const [editRow, setEditRow] = useState<OrgRow | null>(null);
  const [disableRow, setDisableRow] = useState<OrgRow | null>(null);
  const [enableRow, setEnableRow] = useState<OrgRow | null>(null);
  const [deleteRow, setDeleteRow] = useState<OrgRow | null>(null);
  const [storeRow, setStoreRow] = useState<OrgRow | null>(null);
  const [resendRow, setResendRow] = useState<OrgRow | null>(null);

  const handleOpenCreate = useCallback(() => setCreateOpen(true), []);

  // Expose row-action setters on the window so OrgTableWidget can call them
  // without prop-drilling across separate React roots.
  useEffect(() => {
    (window as Window & typeof globalThis & {
      _orgModalHandlers?: {
        onOpenView: (r: OrgRow) => void;
        onOpenEdit: (r: OrgRow) => void;
        onOpenAdjustStores: (r: OrgRow) => void;
        onOpenEnable: (r: OrgRow) => void;
        onOpenDisable: (r: OrgRow) => void;
        onOpenDelete: (r: OrgRow) => void;
        onOpenResend: (r: OrgRow) => void;
        refresh: () => Promise<void>;
      };
    })._orgModalHandlers = {
      onOpenView: (r) => setViewRow(r),
      onOpenEdit: (r) => setEditRow(r),
      onOpenAdjustStores: (r) => setStoreRow(r),
      onOpenEnable: (r) => setEnableRow(r),
      onOpenDisable: (r) => setDisableRow(r),
      onOpenDelete: (r) => setDeleteRow(r),
      onOpenResend: (r) => setResendRow(r),
      refresh,
    };
    return () => {
      delete (window as Window & typeof globalThis & { _orgModalHandlers?: unknown })
        ._orgModalHandlers;
    };
  }, [refresh]);

  return (
    <>
      <CreateButtonBridge onOpen={handleOpenCreate} />

      <CreateOrgModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async () => {
          setCreateOpen(false);
          // If the table widget is already mounted (count > 0 page), signal it to refresh.
          // If on the empty-state page (count == 0), reload so Django re-renders with the new row.
          const tableRoot = document.getElementById("org-table-root");
          if (tableRoot) {
            await refresh();
            window.dispatchEvent(new CustomEvent("org:refresh"));
          } else {
            // Brief pause so the toast fires before reload
            await new Promise((r) => setTimeout(r, 800));
            window.location.reload();
          }
        }}
      />
      <ViewOrgModal
        org={viewRow}
        onClose={() => setViewRow(null)}
        onEdit={(r) => {
          setViewRow(null);
          setEditRow(r);
        }}
        onResend={(r) => {
          setViewRow(null);
          setResendRow(r);
        }}
      />
      <EditOrgModal
        org={editRow}
        onClose={() => setEditRow(null)}
        onUpdated={async () => {
          setEditRow(null);
          await refresh();
          window.dispatchEvent(new CustomEvent("org:refresh"));
        }}
      />
      <DisableConfirmModal
        org={disableRow}
        onClose={() => setDisableRow(null)}
        onDone={async () => {
          await refresh();
          window.dispatchEvent(new CustomEvent("org:refresh"));
        }}
      />
      <EnableConfirmModal
        org={enableRow}
        onClose={() => setEnableRow(null)}
        onDone={async () => {
          await refresh();
          window.dispatchEvent(new CustomEvent("org:refresh"));
        }}
      />
      <ResendInvitationModal
        org={resendRow}
        onClose={() => setResendRow(null)}
      />
      <DeleteConfirmModal
        org={deleteRow}
        onClose={() => setDeleteRow(null)}
        onDone={async () => {
          await refresh();
          window.dispatchEvent(new CustomEvent("org:refresh"));
        }}
      />
      <StoreAllocationModal
        org={storeRow}
        onClose={() => setStoreRow(null)}
        onDone={async () => {
          await refresh();
          window.dispatchEvent(new CustomEvent("org:refresh"));
        }}
      />
    </>
  );
}

/**
 * OrgTableWidget — mounts on #org-table-root only when there are rows.
 * Delegates modal open calls to OrgModals via window._orgModalHandlers.
 */
function OrgTableWidget() {
  const { rows, loading, refresh } = useOrgs();

  // Re-fetch when OrgModals signals a mutation (create/edit/delete/etc.)
  useEffect(() => {
    const handler = () => {
      void refresh();
    };
    window.addEventListener("org:refresh", handler);
    return () => window.removeEventListener("org:refresh", handler);
  }, [refresh]);

  const getHandlers = () =>
    (
      window as Window &
        typeof globalThis & {
          _orgModalHandlers?: {
            onOpenView: (r: OrgRow) => void;
            onOpenEdit: (r: OrgRow) => void;
            onOpenAdjustStores: (r: OrgRow) => void;
            onOpenEnable: (r: OrgRow) => void;
            onOpenDisable: (r: OrgRow) => void;
            onOpenDelete: (r: OrgRow) => void;
            onOpenResend: (r: OrgRow) => void;
          };
        }
    )._orgModalHandlers;

  return (
    <OrgTable
      rows={rows}
      loading={loading}
      handlers={{
        onOpenView: (r) => getHandlers()?.onOpenView(r),
        onOpenEdit: (r) => getHandlers()?.onOpenEdit(r),
        onOpenResend: (r) => getHandlers()?.onOpenResend(r),
        onOpenAdjustStores: (r) => getHandlers()?.onOpenAdjustStores(r),
        onOpenEnable: (r) => getHandlers()?.onOpenEnable(r),
        onOpenDisable: (r) => getHandlers()?.onOpenDisable(r),
        onOpenDelete: (r) => getHandlers()?.onOpenDelete(r),
      }}
    />
  );
}

// Mount modals root — always present regardless of row count
const modalsRoot = document.getElementById("org-modals-root");
if (modalsRoot) {
  createRoot(modalsRoot).render(
    <StrictMode>
      <OrgModals />
    </StrictMode>,
  );
}

// Mount table root — only present when paginator.count > 0
const tableRoot = document.getElementById("org-table-root");
if (tableRoot) {
  createRoot(tableRoot).render(
    <StrictMode>
      <OrgTableWidget />
    </StrictMode>,
  );
}
