import { useState, useEffect, useCallback } from "react";
import { AlertTriangle } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ConfirmModal } from "../modal/ConfirmModal";
import { CreateRegionModal } from "./CreateRegionModal";
import { EditRegionModal } from "./EditRegionModal";
import { deleteRegion } from "./api";
import { emitToast } from "../../lib/toast";
import { useRegions } from "./useRegions";
import type { RegionRow } from "./types";

/**
 * CreateButtonBridge: listens for clicks on the "Create Region" buttons rendered
 * by Django template (page header) and empty state CTA, and triggers the React modal.
 */
function CreateButtonBridge({ onOpen }: { onOpen: () => void }) {
  useEffect(() => {
    const ids = ["open-create-region", "open-create-region-empty"];
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

interface RegionModalsProps {
  initialRows: RegionRow[];
}

export function RegionModals({ initialRows }: RegionModalsProps) {
  const { rows, refresh } = useRegions(initialRows);

  const [createOpen, setCreateOpen] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState<RegionRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteBlockedOpen, setDeleteBlockedOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [blockedShopCount, setBlockedShopCount] = useState(0);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const handleOpenCreate = useCallback(() => setCreateOpen(true), []);

  // Listen for table widget events
  useEffect(() => {
    const handleOpenEdit = (e: Event) => {
      const region = (e as CustomEvent<RegionRow>).detail;
      setSelectedRegion(region);
      setEditOpen(true);
    };

    const handleOpenDelete = (e: Event) => {
      const region = (e as CustomEvent<RegionRow>).detail;
      setSelectedRegion(region);
      setDeleteConfirmOpen(true);
    };

    window.addEventListener("region:open-edit", handleOpenEdit);
    window.addEventListener("region:open-delete", handleOpenDelete);

    return () => {
      window.removeEventListener("region:open-edit", handleOpenEdit);
      window.removeEventListener("region:open-delete", handleOpenDelete);
    };
  }, []);

  const handleCreated = useCallback(
    async (_region: RegionRow) => {
      // If the table is mounted (count > 0), refresh it; otherwise reload so Django re-renders
      const tableRoot = document.getElementById("region-table-root");
      if (tableRoot) {
        await refresh();
        window.dispatchEvent(new CustomEvent("region:refresh"));
      } else {
        await new Promise((r) => setTimeout(r, 800));
        window.location.reload();
      }
    },
    [refresh],
  );

  const handleUpdated = useCallback(async (_region: RegionRow) => {
    await refresh();
    window.dispatchEvent(new CustomEvent("region:refresh"));
  }, [refresh]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!selectedRegion) return;
    setDeleteSubmitting(true);
    try {
      const result = await deleteRegion(selectedRegion.id);
      if (result && "shop_count" in result) {
        // RGN-10: region has shops — close red popup, open amber blocked popup
        setDeleteConfirmOpen(false);
        setBlockedShopCount(result.shop_count);
        setDeleteBlockedOpen(true);
      } else {
        // RGN-11: success
        emitToast({ kind: "success", title: `Region '${selectedRegion.name}' deleted.` });
        setDeleteConfirmOpen(false);
        await refresh();
        window.dispatchEvent(new CustomEvent("region:refresh"));
      }
    } catch {
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setDeleteSubmitting(false);
    }
  }, [selectedRegion, refresh]);

  return (
    <>
      <CreateButtonBridge onOpen={handleOpenCreate} />

      <CreateRegionModal
        open={createOpen}
        regionCount={rows.length}
        onClose={() => setCreateOpen(false)}
        onCreated={async (region) => {
          setCreateOpen(false);
          await handleCreated(region);
        }}
      />

      <EditRegionModal
        open={editOpen}
        region={selectedRegion}
        onClose={() => {
          setEditOpen(false);
          setSelectedRegion(null);
        }}
        onUpdated={async (region) => {
          setEditOpen(false);
          setSelectedRegion(null);
          await handleUpdated(region);
        }}
      />

      {/* RGN-11: Red delete confirmation */}
      <ConfirmModal
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false);
          setSelectedRegion(null);
        }}
        onConfirm={() => void handleDeleteConfirm()}
        variant="red"
        title="Delete region"
        message={
          selectedRegion
            ? `This will permanently delete ${selectedRegion.name}. This action cannot be undone.`
            : ""
        }
        confirmLabel={deleteSubmitting ? "Deleting…" : "Delete Region"}
      />

      {/* RGN-10: Amber delete-blocked popup — single "Got it" button */}
      <Modal
        open={deleteBlockedOpen}
        onClose={() => setDeleteBlockedOpen(false)}
        size="sm"
        footer={
          <button
            type="button"
            onClick={() => setDeleteBlockedOpen(false)}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Got it
          </button>
        }
      >
        <div className="flex gap-3.5">
          <div
            className="w-11 h-11 shrink-0 rounded-confirm-icon flex items-center justify-center bg-amber-tint text-amber"
            aria-hidden="true"
          >
            <AlertTriangle size={22} />
          </div>
          <div>
            <h3 className="text-[18px] font-semibold text-ink mb-1.5">Cannot delete region</h3>
            <p className="text-[13.5px] text-muted leading-[1.5]">
              This region has {blockedShopCount} shop
              {blockedShopCount !== 1 ? "s" : ""} assigned to it. Reassign or remove all shops
              before deleting this region.
            </p>
            {selectedRegion && (
              <a
                href={`/admin/org/shops/?region=${selectedRegion.id}`}
                className="inline-block mt-2 text-[13.5px] text-yellow hover:text-yellow-hover underline font-normal"
              >
                Manage Shops
              </a>
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}
