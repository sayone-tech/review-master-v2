import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { RemoveMemberModal } from "./RemoveMemberModal";
import type { TeamMemberRow } from "./types";
import * as api from "./api";
import * as toast from "../../lib/toast";

const member: TeamMemberRow = {
  id: 2,
  full_name: "Bob",
  email: "bob@example.com",
  role: "STAFF_ADMIN",
  is_active: true,
  invited_at: null,
  accepted_at: null,
  status: "ACTIVE",
  access_scopes: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("RemoveMemberModal", () => {
  it("renders with red variant and Remove Member confirm label", () => {
    render(<RemoveMemberModal isOpen={true} member={member} onClose={vi.fn()} />);
    expect(screen.getByText("Remove Bob?")).toBeInTheDocument();
    expect(screen.getByTestId("confirm-confirm")).toHaveTextContent("Remove Member");
  });

  it("on confirm calls removeTeamMember, fires toast, dispatches team:member-removed, closes", async () => {
    const removed = vi.fn();
    window.addEventListener("team:member-removed", removed);
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "removeTeamMember").mockResolvedValue(null);
    const onClose = vi.fn();
    render(<RemoveMemberModal isOpen={true} member={member} onClose={onClose} />);
    await act(async () => {
      screen.getByTestId("confirm-confirm").click();
    });
    await waitFor(() => {
      expect(api.removeTeamMember).toHaveBeenCalledWith(2);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "success", title: "Bob removed from team." }),
      );
      expect(removed).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
    window.removeEventListener("team:member-removed", removed);
  });

  it("on 403 error shows server detail in error toast", async () => {
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "removeTeamMember").mockRejectedValue(
      new api.ApiError(403, { detail: "Cannot remove the last Manager." }),
    );
    render(<RemoveMemberModal isOpen={true} member={member} onClose={vi.fn()} />);
    await act(async () => {
      screen.getByTestId("confirm-confirm").click();
    });
    await waitFor(() => {
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "error" }),
      );
    });
  });
});
