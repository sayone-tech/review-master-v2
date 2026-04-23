import { useState } from "react";
import { ConfirmModal } from "../modal";
import { updateOrg } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}

export function EnableConfirmModal({ org, onClose, onDone }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!org || submitting) return;
    setSubmitting(true);
    try {
      await updateOrg(org.id, { status: "ACTIVE" });
      emitToast({ kind: "success", title: `${org.name} has been enabled.` });
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

  return (
    <ConfirmModal
      open={org !== null}
      onClose={onClose}
      onConfirm={handleConfirm}
      variant="blue"
      title="Enable Organisation"
      message={
        <>
          Enable <strong>{org?.name}</strong>? The Org Admin will regain access
          immediately.
        </>
      }
      confirmLabel={submitting ? "Enabling…" : "Enable"}
    />
  );
}
