import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TeamTableWidget } from "./TeamTable";
import type { TeamMemberRow, TeamStats } from "./types";
import * as api from "./api";

function makeRow(over: Partial<TeamMemberRow> = {}): TeamMemberRow {
  return {
    id: 1,
    full_name: "Alice Manager",
    email: "alice@example.com",
    role: "ORG_ADMIN",
    is_active: true,
    invited_at: "2026-01-01T00:00:00Z",
    accepted_at: "2026-01-02T00:00:00Z",
    status: "ACTIVE",
    access_scopes: [],
    ...over,
  };
}

const defaultStats: TeamStats = {
  total_members: 2,
  managers: 1,
  active_members: 2,
};

const defaultProps = {
  initial: { rows: [makeRow()], stats: defaultStats },
  regions: [],
  activeShops: [],
  currentUserId: 99,
};

beforeEach(() => {
  vi.spyOn(api, "listTeam").mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [makeRow()],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TeamTableWidget", () => {
  it("renders MEMBER, ROLE, ACCESS, STATUS, ENABLED columns", () => {
    render(<TeamTableWidget {...defaultProps} />);
    expect(screen.getByText("MEMBER")).toBeInTheDocument();
    expect(screen.getByText("ROLE")).toBeInTheDocument();
    expect(screen.getByText("ACCESS")).toBeInTheDocument();
    expect(screen.getByText("STATUS")).toBeInTheDocument();
    expect(screen.getByText("ENABLED")).toBeInTheDocument();
  });

  it("renders member name and email in the table", () => {
    render(<TeamTableWidget {...defaultProps} />);
    expect(screen.getByText("Alice Manager")).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("own row Edit button has aria-disabled and tooltip", () => {
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [makeRow({ id: 99 })], stats: defaultStats }}
        currentUserId={99}
      />,
    );
    const editBtn = screen.getByLabelText("Edit Alice Manager");
    expect(editBtn).toHaveAttribute("aria-disabled", "true");
    expect(editBtn).toHaveAttribute("title", "You cannot edit yourself.");
  });

  it("own row Remove button has aria-disabled and tooltip", () => {
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [makeRow({ id: 99 })], stats: defaultStats }}
        currentUserId={99}
      />,
    );
    const removeBtn = screen.getByLabelText("Remove Alice Manager");
    expect(removeBtn).toHaveAttribute("aria-disabled", "true");
    expect(removeBtn).toHaveAttribute("title", "You cannot remove yourself.");
  });

  it("last-manager Remove button disabled with tooltip", () => {
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{
          rows: [makeRow({ id: 2, role: "ORG_ADMIN" })],
          stats: { ...defaultStats, managers: 1 },
        }}
        currentUserId={99}
      />,
    );
    const removeBtn = screen.getByLabelText("Remove Alice Manager");
    expect(removeBtn).toHaveAttribute("aria-disabled", "true");
    expect(removeBtn).toHaveAttribute("title", "Cannot remove the last Manager.");
  });

  it("clicking Edit fires team:open-edit CustomEvent", () => {
    const handler = vi.fn();
    window.addEventListener("team:open-edit", handler);
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [makeRow({ id: 2 })], stats: defaultStats }}
        currentUserId={99}
      />,
    );
    fireEvent.click(screen.getByLabelText("Edit Alice Manager"));
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("team:open-edit", handler);
  });

  it("clicking Remove fires team:open-remove CustomEvent", () => {
    const handler = vi.fn();
    window.addEventListener("team:open-remove", handler);
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{
          rows: [makeRow({ id: 2, role: "ORG_ADMIN" })],
          stats: { ...defaultStats, managers: 2 },
        }}
        currentUserId={99}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove Alice Manager"));
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("team:open-remove", handler);
  });

  it("Pending row shows Resend icon that fires team:open-resend", () => {
    const handler = vi.fn();
    window.addEventListener("team:open-resend", handler);
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{
          rows: [makeRow({ id: 2, status: "PENDING", is_active: false })],
          stats: defaultStats,
        }}
        currentUserId={99}
      />,
    );
    const resendBtn = screen.getByLabelText(/Resend invitation/);
    fireEvent.click(resendBtn);
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("team:open-resend", handler);
  });

  it("toggle ON→OFF fires team:open-disable", () => {
    const handler = vi.fn();
    window.addEventListener("team:open-disable", handler);
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [makeRow({ id: 2, is_active: true })], stats: defaultStats }}
        currentUserId={99}
      />,
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("team:open-disable", handler);
  });

  it("toggle OFF→ON fires team:open-enable", () => {
    const handler = vi.fn();
    window.addEventListener("team:open-enable", handler);
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [makeRow({ id: 2, is_active: false, status: "DISABLED" })], stats: defaultStats }}
        currentUserId={99}
      />,
    );
    fireEvent.click(screen.getByRole("switch"));
    expect(handler).toHaveBeenCalled();
    window.removeEventListener("team:open-enable", handler);
  });

  it("dispatching team:member-added triggers listTeam refetch", async () => {
    const spy = vi.spyOn(api, "listTeam").mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [makeRow()],
    });
    render(<TeamTableWidget {...defaultProps} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("team:member-added"));
    });
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });

  it("solo banner appears when total_members === 1", () => {
    render(
      <TeamTableWidget
        {...defaultProps}
        initial={{ rows: [], stats: { total_members: 1, managers: 1, active_members: 1 } }}
      />,
    );
    expect(screen.getByText(/only member/)).toBeInTheDocument();
  });
});
