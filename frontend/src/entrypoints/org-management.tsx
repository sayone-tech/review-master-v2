import { useState, StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { OrgTable } from "../widgets/org-management/OrgTable";
import { CreateOrgModal } from "../widgets/org-management/CreateOrgModal";
import { ViewOrgModal } from "../widgets/org-management/ViewOrgModal";
import { EditOrgModal } from "../widgets/org-management/EditOrgModal";
import { DisableConfirmModal } from "../widgets/org-management/DisableConfirmModal";
import { EnableConfirmModal } from "../widgets/org-management/EnableConfirmModal";
import { DeleteConfirmModal } from "../widgets/org-management/DeleteConfirmModal";
import { StoreAllocationModal } from "../widgets/org-management/StoreAllocationModal";
import { useOrgs } from "../widgets/org-management/useOrgs";
import { emitToast } from "../lib/toast";
import type { OrgRow } from "../widgets/org-management/types";

function OrgManagement() {
  const { rows, loading, refresh } = useOrgs();

  const [createOpen, setCreateOpen] = useState(false);
  const [viewRow, setViewRow] = useState<OrgRow | null>(null);
  const [editRow, setEditRow] = useState<OrgRow | null>(null);
  const [disableRow, setDisableRow] = useState<OrgRow | null>(null);
  const [enableRow, setEnableRow] = useState<OrgRow | null>(null);
  const [deleteRow, setDeleteRow] = useState<OrgRow | null>(null);
  const [storeRow, setStoreRow] = useState<OrgRow | null>(null);

  // Resend invitation lands in Phase 4 (INVT-01). Keep a single placeholder toast.
  const handleResendPlaceholder = () =>
    emitToast({ kind: "info", title: "Resend Invitation arrives in Phase 4." });

  return (
    <>
      <OrgTable
        rows={rows}
        loading={loading}
        handlers={{
          onOpenView: (r) => setViewRow(r),
          onOpenEdit: (r) => setEditRow(r),
          onOpenResend: handleResendPlaceholder,
          onOpenAdjustStores: (r) => setStoreRow(r),
          onOpenEnable: (r) => setEnableRow(r),
          onOpenDisable: (r) => setDisableRow(r),
          onOpenDelete: (r) => setDeleteRow(r),
        }}
      />

      <CreateOrgModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async () => {
          setCreateOpen(false);
          await refresh();
        }}
      />
      <ViewOrgModal
        org={viewRow}
        onClose={() => setViewRow(null)}
        onEdit={(r) => {
          setViewRow(null);
          setEditRow(r);
        }}
        onResend={handleResendPlaceholder}
      />
      <EditOrgModal
        org={editRow}
        onClose={() => setEditRow(null)}
        onUpdated={async () => {
          setEditRow(null);
          await refresh();
        }}
      />
      <DisableConfirmModal
        org={disableRow}
        onClose={() => setDisableRow(null)}
        onDone={async () => {
          await refresh();
        }}
      />
      <EnableConfirmModal
        org={enableRow}
        onClose={() => setEnableRow(null)}
        onDone={async () => {
          await refresh();
        }}
      />
      <DeleteConfirmModal
        org={deleteRow}
        onClose={() => setDeleteRow(null)}
        onDone={async () => {
          await refresh();
        }}
      />
      <StoreAllocationModal
        org={storeRow}
        onClose={() => setStoreRow(null)}
        onDone={async () => {
          await refresh();
        }}
      />

      <CreateButtonBridge onOpen={() => setCreateOpen(true)} />
    </>
  );
}

/**
 * The Create button is rendered by Django template (so it appears inside the
 * page header before React mounts). This component listens for clicks and
 * triggers the React modal.
 */
function CreateButtonBridge({ onOpen }: { onOpen: () => void }) {
  useEffect(() => {
    const btn = document.getElementById("open-create-org");
    if (!btn) return undefined;
    const handler = () => onOpen();
    btn.addEventListener("click", handler);
    return () => btn.removeEventListener("click", handler);
  }, [onOpen]);
  return null;
}

const root = document.getElementById("org-table-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <OrgManagement />
    </StrictMode>,
  );
}
