import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EditTeamMemberModal } from "./EditTeamMemberModal";
import type { TeamMemberRow } from "./types";
import * as api from "./api";
import * as toast from "../../lib/toast";

const activeMember: TeamMemberRow = {
  id: 2,
  full_name: "Bob Staff",
  email: "bob@example.com",
  role: "STAFF_ADMIN",
  is_active: true,
  invited_at: "2026-01-01T00:00:00Z",
  accepted_at: "2026-01-02T00:00:00Z",
  status: "ACTIVE",
  access_scopes: [
    {
      id: 1,
      scope_type: "REGION",
      region: 1,
      region_name: "North",
      region_region_id: "R01",
      shop: null,
      shop_name: null,
    },
  ],
};

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  member: activeMember,
  regions: [{ id: 1, region_id: "R01", name: "North" }],
  activeShops: [{ id: 10, name: "Shop A", region: 1, region_id: "R01", region_name: "North" }],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("EditTeamMemberModal", () => {
  it("renders with member current values pre-filled", () => {
    render(<EditTeamMemberModal {...defaultProps} />);
    expect(screen.getByLabelText("Full Name")).toHaveValue("Bob Staff");
    expect(screen.getByLabelText("Email")).toHaveValue("bob@example.com");
  });

  it("Email field is rendered as readOnly", () => {
    render(<EditTeamMemberModal {...defaultProps} />);
    const emailInput = screen.getByLabelText("Email");
    expect(emailInput).toHaveAttribute("readonly");
  });

  it("role change Manager to Staff reveals scope section", () => {
    render(<EditTeamMemberModal {...defaultProps} member={{ ...activeMember, role: "ORG_ADMIN", access_scopes: [] }} />);
    expect(screen.queryByText("Access Scope")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "STAFF_ADMIN" } });
    expect(screen.getByText("Access Scope")).toBeInTheDocument();
  });

  it("successful submit calls updateTeamMember, fires success toast, dispatches team:member-updated", async () => {
    const memberUpdated = vi.fn();
    window.addEventListener("team:member-updated", memberUpdated);
    const toastSpy = vi.spyOn(toast, "emitToast");
    vi.spyOn(api, "updateTeamMember").mockResolvedValue({ ...activeMember });
    const onClose = vi.fn();
    render(<EditTeamMemberModal {...defaultProps} onClose={onClose} />);
    await act(async () => {
      fireEvent.click(screen.getByText("Save Changes"));
    });
    await waitFor(() => {
      expect(api.updateTeamMember).toHaveBeenCalledWith(
        activeMember.id,
        expect.objectContaining({ full_name: "Bob Staff" }),
      );
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "success" }),
      );
      expect(memberUpdated).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
    window.removeEventListener("team:member-updated", memberUpdated);
  });
});
