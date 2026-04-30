import { useEffect, useState } from "react";
import { AddTeamMemberModal } from "./AddTeamMemberModal";
import { EditTeamMemberModal } from "./EditTeamMemberModal";
import { DisableMemberModal } from "./DisableMemberModal";
import { RemoveMemberModal } from "./RemoveMemberModal";
import { ResendMemberInviteModal } from "./ResendMemberInviteModal";
import { enableTeamMember, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionOption, ShopOption, TeamMemberRow } from "./types";

interface TeamModalsProps {
  regions: RegionOption[];
  activeShops: ShopOption[];
  currentUserId: number;
  managerCount: number;
}

type Open =
  | { kind: "none" }
  | { kind: "add" }
  | { kind: "edit"; member: TeamMemberRow }
  | { kind: "disable"; member: TeamMemberRow }
  | { kind: "remove"; member: TeamMemberRow }
  | { kind: "resend"; member: TeamMemberRow };

export function TeamModals({
  regions,
  activeShops,
  currentUserId: _currentUserId,
  managerCount: _managerCount,
}: TeamModalsProps) {
  const [open, setOpen] = useState<Open>({ kind: "none" });

  useEffect(() => {
    const onAdd = () => setOpen({ kind: "add" });
    const onEdit = (e: Event) =>
      setOpen({ kind: "edit", member: (e as CustomEvent<TeamMemberRow>).detail });
    const onDisable = (e: Event) =>
      setOpen({ kind: "disable", member: (e as CustomEvent<TeamMemberRow>).detail });
    const onRemove = (e: Event) =>
      setOpen({ kind: "remove", member: (e as CustomEvent<TeamMemberRow>).detail });
    const onResend = (e: Event) =>
      setOpen({ kind: "resend", member: (e as CustomEvent<TeamMemberRow>).detail });
    const onEnable = async (e: Event) => {
      const member = (e as CustomEvent<TeamMemberRow>).detail;
      try {
        await enableTeamMember(member.id);
        emitToast({ kind: "success", title: `${member.full_name} enabled.` });
        window.dispatchEvent(new CustomEvent("team:member-toggled"));
      } catch (err) {
        const detail =
          err instanceof ApiError &&
          typeof err.data === "object" &&
          err.data &&
          "detail" in err.data
            ? String((err.data as { detail: string }).detail)
            : "Please try again.";
        emitToast({ kind: "error", title: "Could not enable member.", msg: detail });
      }
    };

    window.addEventListener("team:open-add", onAdd);
    window.addEventListener("team:open-edit", onEdit as EventListener);
    window.addEventListener("team:open-disable", onDisable as EventListener);
    window.addEventListener("team:open-enable", onEnable as EventListener);
    window.addEventListener("team:open-remove", onRemove as EventListener);
    window.addEventListener("team:open-resend", onResend as EventListener);

    return () => {
      window.removeEventListener("team:open-add", onAdd);
      window.removeEventListener("team:open-edit", onEdit as EventListener);
      window.removeEventListener("team:open-disable", onDisable as EventListener);
      window.removeEventListener("team:open-enable", onEnable as EventListener);
      window.removeEventListener("team:open-remove", onRemove as EventListener);
      window.removeEventListener("team:open-resend", onResend as EventListener);
    };
  }, []);

  // Wire the page-header "+ Add Team Member" button (id="open-add-team-member" from template)
  useEffect(() => {
    const btn = document.getElementById("open-add-team-member");
    if (!btn) return;
    const handler = () => setOpen({ kind: "add" });
    btn.addEventListener("click", handler);
    return () => btn.removeEventListener("click", handler);
  }, []);

  const close = () => setOpen({ kind: "none" });

  return (
    <>
      {open.kind === "add" && (
        <AddTeamMemberModal
          isOpen={true}
          onClose={close}
          regions={regions}
          activeShops={activeShops}
        />
      )}
      {open.kind === "edit" && (
        <EditTeamMemberModal
          isOpen={true}
          onClose={close}
          member={open.member}
          regions={regions}
          activeShops={activeShops}
        />
      )}
      {open.kind === "disable" && (
        <DisableMemberModal isOpen={true} onClose={close} member={open.member} />
      )}
      {open.kind === "remove" && (
        <RemoveMemberModal isOpen={true} onClose={close} member={open.member} />
      )}
      {open.kind === "resend" && (
        <ResendMemberInviteModal isOpen={true} onClose={close} member={open.member} />
      )}
    </>
  );
}
