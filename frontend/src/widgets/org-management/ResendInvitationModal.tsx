import { useState } from "react";
import { ConfirmModal } from "../modal";
import { ApiError, resendInvitation } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
}

export function ResendInvitationModal({ org, onClose }: Props) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!org || submitting) return;
    setSubmitting(true);
    try {
      await resendInvitation(org.id);
      emitToast({ kind: "success", title: `Invitation resent to ${org.email}.` });
      onClose();
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
      variant="blue"
      title="Resend Invitation"
      message={
        <>
          Resend invitation to <strong>{org?.email}</strong> for{" "}
          <strong>{org?.name}</strong>? The previous invitation link will be
          invalidated.
        </>
      }
      confirmLabel={submitting ? "Sending…" : "Resend Invitation"}
    />
  );
}
