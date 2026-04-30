import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { TeamModals } from "./TeamModals";
import type { TeamMemberRow } from "./types";
import * as api from "./api";
import * as toast from "../../lib/toast";

const member: TeamMemberRow = {
  id: 1,
  full_name: "Dave",
  email: "dave@example.com",
  role: "ORG_ADMIN",
  is_active: true,
  invited_at: null,
  accepted_at: null,
  status: "ACTIVE",
  access_scopes: [],
};

const defaultProps = {
  regions: [{ id: 1, region_id: "R01", name: "North" }],
  activeShops: [],
  currentUserId: 99,
  managerCount: 2,
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "enableTeamMember").mockResolvedValue({ ...member });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TeamModals", () => {
  it("subscribes to team:open-add and opens Add modal", () => {
    render(<TeamModals {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:open-add"));
    });
    expect(screen.getByText("Add Team Member")).toBeInTheDocument();
  });

  it("subscribes to team:open-edit and opens Edit modal", () => {
    render(<TeamModals {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:open-edit", { detail: member }));
    });
    expect(screen.getByText("Edit Team Member")).toBeInTheDocument();
  });

  it("subscribes to team:open-disable and opens Disable modal", () => {
    render(<TeamModals {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:open-disable", { detail: member }));
    });
    expect(screen.getByText("Disable Dave?")).toBeInTheDocument();
  });

  it("subscribes to team:open-remove and opens Remove modal", () => {
    render(<TeamModals {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:open-remove", { detail: member }));
    });
    expect(screen.getByText("Remove Dave?")).toBeInTheDocument();
  });

  it("subscribes to team:open-resend and opens Resend modal", () => {
    render(<TeamModals {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:open-resend", { detail: member }));
    });
    // ConfirmModal renders "Resend Invitation" in both title (h3) and confirm button
    // Check for the message text that uniquely identifies the modal
    expect(
      screen.getByText(/Send a new invitation link/),
    ).toBeInTheDocument();
  });

  it("team:open-enable triggers direct API call and emits success toast", async () => {
    const toastSpy = vi.spyOn(toast, "emitToast");
    render(<TeamModals {...defaultProps} />);
    await act(async () => {
      window.dispatchEvent(new CustomEvent("team:open-enable", { detail: member }));
    });
    await waitFor(() => {
      expect(api.enableTeamMember).toHaveBeenCalledWith(1);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "success", title: "Dave enabled." }),
      );
    });
  });

  it("team:open-enable on API 403 shows error toast with server detail", async () => {
    vi.spyOn(api, "enableTeamMember").mockRejectedValue(
      new api.ApiError(403, { detail: "Cannot remove the last Manager." }),
    );
    const toastSpy = vi.spyOn(toast, "emitToast");
    render(<TeamModals {...defaultProps} />);
    await act(async () => {
      window.dispatchEvent(new CustomEvent("team:open-enable", { detail: member }));
    });
    await waitFor(() => {
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "error" }),
      );
    });
  });
});
