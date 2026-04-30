import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AddTeamMemberModal } from "./AddTeamMemberModal";
import * as api from "./api";
import * as toast from "../../lib/toast";

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  regions: [{ id: 1, region_id: "R01", name: "North" }],
  activeShops: [{ id: 10, name: "Shop A", region: 1, region_id: "R01", region_name: "North" }],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AddTeamMemberModal", () => {
  it("default role is Manager — scope section hidden", () => {
    render(<AddTeamMemberModal {...defaultProps} />);
    expect(screen.queryByText("Access Scope")).not.toBeInTheDocument();
  });

  it("selecting Staff role reveals scope section", () => {
    render(<AddTeamMemberModal {...defaultProps} />);
    const roleSelect = screen.getByLabelText("Role");
    fireEvent.change(roleSelect, { target: { value: "STAFF_ADMIN" } });
    expect(screen.getByText("Access Scope")).toBeInTheDocument();
  });

  it("submitting with empty Name shows inline error", async () => {
    render(<AddTeamMemberModal {...defaultProps} />);
    fireEvent.click(screen.getByText("Send Invitation"));
    await waitFor(() => {
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    });
  });

  it("submitting Staff with no scope blocks submit and shows error", async () => {
    render(<AddTeamMemberModal {...defaultProps} />);
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "STAFF_ADMIN" } });
    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.click(screen.getByText("Send Invitation"));
    await waitFor(() => {
      expect(
        screen.getAllByText("Please select at least one region or store.").length,
      ).toBeGreaterThan(0);
    });
  });

  it("successful submit calls createTeamMember, fires toast, dispatches team:member-added, closes modal", async () => {
    const memberAdded = vi.fn();
    window.addEventListener("team:member-added", memberAdded);
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "createTeamMember").mockResolvedValue({
      id: 1,
      full_name: "Alice",
      email: "alice@example.com",
      role: "ORG_ADMIN",
      is_active: false,
      invited_at: null,
      accepted_at: null,
      status: "PENDING",
      access_scopes: [],
    });
    const onClose = vi.fn();
    render(<AddTeamMemberModal {...defaultProps} onClose={onClose} />);
    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "alice@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByText("Send Invitation"));
    });
    await waitFor(() => {
      expect(api.createTeamMember).toHaveBeenCalled();
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "success" }),
      );
      expect(memberAdded).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
    window.removeEventListener("team:member-added", memberAdded);
  });

  it("API 400 error with email field shows inline email error", async () => {
    vi.spyOn(api, "createTeamMember").mockRejectedValue(
      new api.ApiError(400, { email: ["A user with this email already exists."] }),
    );
    render(<AddTeamMemberModal {...defaultProps} />);
    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Bob" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bob@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByText("Send Invitation"));
    });
    await waitFor(() => {
      expect(
        screen.getByText("A user with this email already exists."),
      ).toBeInTheDocument();
    });
  });

  it("API 400 with non_field_errors shows message at top", async () => {
    vi.spyOn(api, "createTeamMember").mockRejectedValue(
      new api.ApiError(400, { non_field_errors: ["Something went wrong."] }),
    );
    render(<AddTeamMemberModal {...defaultProps} />);
    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Bob" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bob@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByText("Send Invitation"));
    });
    await waitFor(() => {
      expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
    });
  });
});
