import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { ResendMemberInviteModal } from "./ResendMemberInviteModal";
import type { TeamMemberRow } from "./types";
import * as api from "./api";
import * as toast from "../../lib/toast";

const member: TeamMemberRow = {
  id: 3,
  full_name: "Carol",
  email: "carol@example.com",
  role: "STAFF_ADMIN",
  is_active: false,
  invited_at: null,
  accepted_at: null,
  status: "PENDING",
  access_scopes: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ResendMemberInviteModal", () => {
  it("renders with blue variant and Resend Invitation confirm label", () => {
    render(<ResendMemberInviteModal isOpen={true} member={member} onClose={vi.fn()} />);
    // "Resend Invitation" appears in both title h3 and confirm button
    expect(screen.getAllByText("Resend Invitation").length).toBeGreaterThan(0);
    expect(screen.getByTestId("confirm-confirm")).toHaveTextContent("Resend Invitation");
  });

  it("on confirm calls resendTeamInvitation, fires toast, dispatches team:member-toggled", async () => {
    const toggled = vi.fn();
    window.addEventListener("team:member-toggled", toggled);
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "resendTeamInvitation").mockResolvedValue({ ...member });
    const onClose = vi.fn();
    render(<ResendMemberInviteModal isOpen={true} member={member} onClose={onClose} />);
    await act(async () => {
      screen.getByTestId("confirm-confirm").click();
    });
    await waitFor(() => {
      expect(api.resendTeamInvitation).toHaveBeenCalledWith(3);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "success",
          title: "Invitation resent to carol@example.com.",
        }),
      );
      expect(toggled).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
    window.removeEventListener("team:member-toggled", toggled);
  });
});
