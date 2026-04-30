import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { DisableMemberModal } from "./DisableMemberModal";
import type { TeamMemberRow } from "./types";
import * as api from "./api";
import * as toast from "../../lib/toast";

const member: TeamMemberRow = {
  id: 1,
  full_name: "Alice",
  email: "alice@example.com",
  role: "ORG_ADMIN",
  is_active: true,
  invited_at: null,
  accepted_at: null,
  status: "ACTIVE",
  access_scopes: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("DisableMemberModal", () => {
  it("renders with amber variant and Disable Member confirm label", () => {
    render(<DisableMemberModal isOpen={true} member={member} onClose={vi.fn()} />);
    expect(screen.getByText("Disable Alice?")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-confirm")).toHaveTextContent("Disable Member");
  });

  it("on confirm calls disableTeamMember(id), fires toast, dispatches team:member-toggled, closes", async () => {
    const toggled = vi.fn();
    window.addEventListener("team:member-toggled", toggled);
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "disableTeamMember").mockResolvedValue({ ...member, is_active: false });
    const onClose = vi.fn();
    render(<DisableMemberModal isOpen={true} member={member} onClose={onClose} />);
    await act(async () => {
      screen.getByTestId("confirm-confirm").click();
    });
    await waitFor(() => {
      expect(api.disableTeamMember).toHaveBeenCalledWith(1);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "success", title: "Alice disabled." }),
      );
      expect(toggled).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
    window.removeEventListener("team:member-toggled", toggled);
  });
});
