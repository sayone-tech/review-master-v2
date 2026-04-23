import { useState, StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { OrgTable } from "../widgets/org-management/OrgTable";
import { CreateOrgModal } from "../widgets/org-management/CreateOrgModal";
import { ViewOrgModal } from "../widgets/org-management/ViewOrgModal";
import { EditOrgModal } from "../widgets/org-management/EditOrgModal";
import { useOrgs } from "../widgets/org-management/useOrgs";
import { emitToast } from "../lib/toast";
import type { OrgRow } from "../widgets/org-management/types";

function OrgManagement() {
  const { rows, loading, refresh } = useOrgs();
  const [createOpen, setCreateOpen] = useState(false);
  const [viewRow, setViewRow] = useState<OrgRow | null>(null);
  const [editRow, setEditRow] = useState<OrgRow | null>(null);

  // Plan 05 replaces these noop handlers with real destructive modals.
  const notImplemented = (action: string) => () => {
    emitToast({ kind: "info", title: `${action}: coming in Plan 05.` });
  };

  return (
    <>
      <OrgTable
        rows={rows}
        loading={loading}
        handlers={{
          onOpenView: (r) => setViewRow(r),
          onOpenEdit: (r) => setEditRow(r),
          onOpenResend: notImplemented("Resend Invitation"),
          onOpenAdjustStores: notImplemented("Adjust Store Count"),
          onOpenEnable: notImplemented("Enable"),
          onOpenDisable: notImplemented("Disable"),
          onOpenDelete: notImplemented("Delete"),
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
        onResend={notImplemented("Resend Invitation")}
      />
      <EditOrgModal
        org={editRow}
        onClose={() => setEditRow(null)}
        onUpdated={async () => {
          setEditRow(null);
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
