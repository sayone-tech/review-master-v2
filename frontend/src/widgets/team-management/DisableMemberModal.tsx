import { useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { emitToast } from "../../lib/toast";
import { disableTeamMember, ApiError } from "./api";
import type { TeamMemberRow } from "./types";

interface DisableMemberModalProps {
  isOpen: boolean;
  member: TeamMemberRow;
  onClose: () => void;
}

export function DisableMemberModal({ isOpen, member, onClose }: DisableMemberModalProps) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await disableTeamMember(member.id);
      emitToast({ kind: "success", title: `${member.full_name} disabled.` });
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
      emitToast({ kind: "error", title: "Could not disable member.", msg: detail });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ConfirmModal
      open={isOpen}
      variant="amber"
      title={`Disable ${member.full_name}?`}
      message={`${member.full_name} will be signed out immediately and won't be able to log in until re-enabled.`}
      confirmLabel={loading ? "Disabling…" : "Disable Member"}
      onClose={onClose}
      onConfirm={() => void handleConfirm()}
    />
  );
}
