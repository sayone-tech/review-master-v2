import { useState } from "react";
import { ConfirmModal } from "../modal";
import { ApiError, updateOrg } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}

export function DisableConfirmModal({ org, onClose, onDone }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!org || submitting) return;
    setSubmitting(true);
    try {
      await updateOrg(org.id, { status: "DISABLED" });
      emitToast({ kind: "success", title: `${org.name} has been disabled.` });
      onClose();
      await onDone();
    } catch (err) {
      void (err instanceof ApiError);
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ConfirmModal
      open={org !== null}
      onClose={onClose}
      onConfirm={handleConfirm}
      variant="amber"
      title="Disable Organisation"
      message={
        <>
          Disable <strong>{org?.name}</strong>? Disabled organisations cannot be
          accessed by their Org Admins.
        </>
      }
      confirmLabel={submitting ? "Disabling…" : "Disable"}
    />
  );
}
