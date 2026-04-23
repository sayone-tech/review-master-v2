import { useState } from "react";
import { ConfirmModal } from "../modal";
import { deleteOrg } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}

export function DeleteConfirmModal({ org, onClose, onDone }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!org || submitting) return;
    setSubmitting(true);
    try {
      await deleteOrg(org.id);
      emitToast({ kind: "success", title: `${org.name} has been deleted.` });
      onClose();
      await onDone();
    } catch {
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  // Guard: returning null re-mounts ConfirmModal on next open, which resets
  // ConfirmModal's internal `typed` state — ensuring a fresh empty input every
  // time the delete flow starts for a potentially different organisation.
  if (!org) return null;

  return (
    <ConfirmModal
      open={true}
      onClose={onClose}
      onConfirm={handleConfirm}
      variant="red"
      title="Delete Organisation"
      message="This organisation will be hidden from the list. It can be restored by an administrator."
      confirmLabel={submitting ? "Deleting…" : "Delete"}
      requireTypeToConfirm={org.name}
    />
  );
}
