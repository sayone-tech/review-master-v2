import { useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { emitToast } from "../../lib/toast";
import { resendTeamInvitation, ApiError } from "./api";
import type { TeamMemberRow } from "./types";

interface ResendMemberInviteModalProps {
  isOpen: boolean;
  member: TeamMemberRow;
  onClose: () => void;
}

export function ResendMemberInviteModal({
  isOpen,
  member,
  onClose,
}: ResendMemberInviteModalProps) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await resendTeamInvitation(member.id);
      emitToast({
        kind: "success",
        title: `Invitation resent to ${member.email}.`,
      });
      window.dispatchEvent(new CustomEvent("team:member-toggled"));
      onClose();
    } catch (e) {
      const detail =
        e instanceof ApiError &&
        typeof e.data === "object" &&
        e.data &&
        "detail" in e.data
          ? String((e.data as { detail: string }).detail)
          : "Please try again.";
      emitToast({ kind: "error", title: "Could not resend invitation.", msg: detail });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ConfirmModal
      open={isOpen}
      variant="blue"
      title="Resend Invitation"
      message={`Send a new invitation link to ${member.email}? The previous link will be invalidated.`}
      confirmLabel={loading ? "Sending…" : "Resend Invitation"}
      onClose={onClose}
      onConfirm={() => void handleConfirm()}
    />
  );
}
