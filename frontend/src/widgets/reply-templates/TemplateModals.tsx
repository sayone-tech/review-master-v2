import { useState, useEffect, useCallback } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { CreateTemplateModal } from "./CreateTemplateModal";
import { EditTemplateModal } from "./EditTemplateModal";
import { deleteTemplate } from "./api";
import { emitToast } from "../../lib/toast";
import { useTemplates } from "./useTemplates";
import type { TemplateRow } from "./types";

function CreateButtonBridge({ onOpen }: { onOpen: () => void }) {
  useEffect(() => {
    const headerBtn = document.getElementById("open-create-template");
    const headerHandler = () => onOpen();
    if (headerBtn) {
      headerBtn.addEventListener("click", headerHandler);
    }
    const eventHandler = () => onOpen();
    window.addEventListener("template:open-create", eventHandler);
    return () => {
      if (headerBtn) {
        headerBtn.removeEventListener("click", headerHandler);
      }
      window.removeEventListener("template:open-create", eventHandler);
    };
  }, [onOpen]);
  return null;
}

interface TemplateModalsProps {
  initialRows: TemplateRow[];
}

export function TemplateModals({ initialRows }: TemplateModalsProps) {
  const { rows, refresh } = useTemplates(initialRows);

  const [createOpen, setCreateOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const handleOpenCreate = useCallback(() => setCreateOpen(true), []);

  useEffect(() => {
    const handleOpenEdit = (e: Event) => {
      const template = (e as CustomEvent<TemplateRow>).detail;
      setSelectedTemplate(template);
      setEditOpen(true);
    };
    const handleOpenDelete = (e: Event) => {
      const template = (e as CustomEvent<TemplateRow>).detail;
      setSelectedTemplate(template);
      setDeleteConfirmOpen(true);
    };
    window.addEventListener("template:open-edit", handleOpenEdit);
    window.addEventListener("template:open-delete", handleOpenDelete);
    return () => {
      window.removeEventListener("template:open-edit", handleOpenEdit);
      window.removeEventListener("template:open-delete", handleOpenDelete);
    };
  }, []);

  const handleCreated = useCallback(
    async (_template: TemplateRow) => {
      const tableRoot = document.getElementById("template-table-root");
      if (tableRoot) {
        await refresh();
        window.dispatchEvent(new CustomEvent("template:refresh"));
      } else {
        await new Promise((r) => setTimeout(r, 800));
        window.location.reload();
      }
    },
    [refresh],
  );

  const handleUpdated = useCallback(async (_template: TemplateRow) => {
    await refresh();
    window.dispatchEvent(new CustomEvent("template:refresh"));
  }, [refresh]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!selectedTemplate) return;
    setDeleteSubmitting(true);
    try {
      await deleteTemplate(selectedTemplate.id);
      emitToast({ kind: "success", title: `Template '${selectedTemplate.name}' deleted.` });
      setDeleteConfirmOpen(false);
      await refresh();
      window.dispatchEvent(new CustomEvent("template:refresh"));
    } catch {
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setDeleteSubmitting(false);
    }
  }, [selectedTemplate, refresh]);

  return (
    <>
      <CreateButtonBridge onOpen={handleOpenCreate} />

      <CreateTemplateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async (template) => {
          setCreateOpen(false);
          await handleCreated(template);
        }}
      />

      <EditTemplateModal
        open={editOpen}
        template={selectedTemplate}
        onClose={() => {
          setEditOpen(false);
          setSelectedTemplate(null);
        }}
        onUpdated={async (template) => {
          setEditOpen(false);
          setSelectedTemplate(null);
          await handleUpdated(template);
        }}
      />

      <ConfirmModal
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false);
          setSelectedTemplate(null);
        }}
        onConfirm={() => void handleDeleteConfirm()}
        variant="red"
        title="Delete template"
        message={
          selectedTemplate
            ? `This will permanently delete '${selectedTemplate.name}'. This action cannot be undone.`
            : ""
        }
        confirmLabel={deleteSubmitting ? "Deleting…" : "Delete Template"}
      />
    </>
  );
}
