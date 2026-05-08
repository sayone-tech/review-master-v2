import { useEffect, useState } from "react";
import { UserCheck } from "lucide-react";
import { Modal } from "../modal/Modal";
import { updateActionItemBackend } from "./api";
import { emitToast } from "../../lib/toast";
import type { ActionItemListRow, TeamMember } from "./types";

interface Props {
  open: boolean;
  item: ActionItemListRow | null;
  teamMembers: TeamMember[];
  onClose: () => void;
  onAssigned: () => void;
}

export function AssignModal({ open, item, teamMembers, onClose, onAssigned }: Props) {
  const [selectedId, setSelectedId] = useState<number | "">(item?.assignee_id ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSelectedId(item?.assignee_id ?? "");
  }, [item?.id]);

  // SHOP-scoped items can only be assigned to org admins
  const assignableMembers =
    item?.scope === "SHOP"
      ? teamMembers.filter((m) => m.role === "ORG_ADMIN")
      : teamMembers;

  const handleSave = async () => {
    if (!item) return;
    setSaving(true);
    try {
      await updateActionItemBackend(item.id, {
        assignee: selectedId === "" ? null : Number(selectedId),
      });
      emitToast({
        kind: "success",
        title: selectedId === "" ? "Assignee removed" : "Assignee updated",
      });
      onAssigned();
      onClose();
    } catch {
      emitToast({ kind: "error", title: "Could not update assignee. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title="Assign action item"
      subtitle={item?.title}
    >
      <div className="p-5 space-y-4">
        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Assignee
          {item?.scope === "SHOP" && (
            <span className="ml-2 normal-case font-normal text-[11px] text-subtle">
              (shop items — org admins only)
            </span>
          )}
          <select
            value={selectedId}
            onChange={(e) =>
              setSelectedId(e.target.value === "" ? "" : Number(e.target.value))
            }
            disabled={saving}
            className="mt-2 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow disabled:opacity-50"
          >
            <option value="">Unassigned</option>
            {assignableMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
              </option>
            ))}
          </select>
        </label>

        <div className="flex justify-end gap-2 pt-2 border-t border-line-soft">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-[14px] bg-white border border-line rounded-md hover:bg-line-soft disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50"
          >
            <UserCheck size={14} aria-hidden="true" />
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
