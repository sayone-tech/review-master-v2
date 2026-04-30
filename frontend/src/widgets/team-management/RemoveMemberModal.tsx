import { useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { emitToast } from "../../lib/toast";
import { removeTeamMember, ApiError } from "./api";
import type { TeamMemberRow } from "./types";

interface RemoveMemberModalProps {
  isOpen: boolean;
  member: TeamMemberRow;
  onClose: () => void;
}

export function RemoveMemberModal({ isOpen, member, onClose }: RemoveMemberModalProps) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await removeTeamMember(member.id);
      emitToast({ kind: "success", title: `${member.full_name} removed from team.` });
      window.dispatchEvent(new CustomEvent("team:member-removed"));
      onClose();
    } catch (e) {
      const detail =
        e instanceof ApiError &&
        typeof e.data === "object" &&
        e.data &&
        "detail" in e.data
          ? String((e.data as { detail: string }).detail)
          : "Please try again.";
      emitToast({ kind: "error", title: "Could not remove member.", msg: detail });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ConfirmModal
      open={isOpen}
      variant="red"
      title={`Remove ${member.full_name}?`}
      message={`${member.full_name} will lose access immediately. All active sessions will be terminated and any pending invitations will be cancelled. This cannot be undone.`}
      confirmLabel={loading ? "Removing…" : "Remove Member"}
      onClose={onClose}
      onConfirm={() => void handleConfirm()}
    />
  );
}
