import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ResendInvitationModal } from "./ResendInvitationModal";
import type { OrgRow } from "./types";

// Mock the api module
vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    resendInvitation: vi.fn(),
  };
});

// Mock the toast lib
vi.mock("../../lib/toast", () => ({
  emitToast: vi.fn(),
}));

import { resendInvitation } from "./api";
import { emitToast } from "../../lib/toast";

const resendInvitationMock = resendInvitation as unknown as ReturnType<typeof vi.fn>;
const emitToastMock = emitToast as unknown as ReturnType<typeof vi.fn>;

function makeOrg(overrides: Partial<OrgRow> = {}): OrgRow {
  return {
    id: 1,
    name: "Acme Holdings",
    org_type: "RETAIL",
    email: "owner@acme.com",
    address: "",
    number_of_stores: 10,
    status: "ACTIVE",
    created_at: "2026-04-01T00:00:00Z",
    total_stores: 0,
    active_stores: 0,
    activation_status: "pending",
    last_invited_at: null,
    ...overrides,
  };
}

describe("ResendInvitationModal", () => {
  beforeEach(() => {
    resendInvitationMock.mockReset();
    emitToastMock.mockReset();
  });

  test("renders nothing visually when org is null", () => {
    const { container } = render(<ResendInvitationModal org={null} onClose={() => {}} />);
    // ConfirmModal with open=false should not show the title
    expect(screen.queryByText("Resend Invitation")).toBeNull();
    // Container is still rendered (portal) but title absent
    void container;
  });

  test("shows title and locked message when org is set", () => {
    render(<ResendInvitationModal org={makeOrg()} onClose={() => {}} />);
    // Title appears in h3 and button — use getAllByText and check at least one
    expect(screen.getAllByText("Resend Invitation").length).toBeGreaterThanOrEqual(1);
    // Message contains the interpolated email and name
    expect(screen.getByText(/Resend invitation to/)).toBeInTheDocument();
    expect(screen.getByText("owner@acme.com")).toBeInTheDocument();
    expect(screen.getByText("Acme Holdings")).toBeInTheDocument();
    expect(
      screen.getByText(/The previous invitation link will be invalidated\./)
    ).toBeInTheDocument();
  });

  test("confirm button label is 'Resend Invitation' initially", () => {
    render(<ResendInvitationModal org={makeOrg()} onClose={() => {}} />);
    const btn = screen.getByTestId("confirm-confirm");
    expect(btn).toHaveTextContent("Resend Invitation");
  });

  test("clicking confirm calls resendInvitation with org.id", async () => {
    resendInvitationMock.mockResolvedValueOnce(undefined);
    const onClose = vi.fn();
    render(<ResendInvitationModal org={makeOrg({ id: 42 })} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("confirm-confirm"));
    await waitFor(() => expect(resendInvitationMock).toHaveBeenCalledWith(42));
  });

  test("success path: emits success toast and calls onClose", async () => {
    resendInvitationMock.mockResolvedValueOnce(undefined);
    const onClose = vi.fn();
    render(<ResendInvitationModal org={makeOrg()} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("confirm-confirm"));
    await waitFor(() =>
      expect(emitToastMock).toHaveBeenCalledWith({
        kind: "success",
        title: "Invitation resent to owner@acme.com.",
      })
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("failure path: emits error toast and does NOT call onClose", async () => {
    resendInvitationMock.mockRejectedValueOnce(new Error("API down"));
    const onClose = vi.fn();
    render(<ResendInvitationModal org={makeOrg()} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("confirm-confirm"));
    await waitFor(() =>
      expect(emitToastMock).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "error", title: "Something went wrong." })
      )
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  test("submitting: confirm label becomes 'Sending…' while API is in flight", async () => {
    let resolve!: () => void;
    const pending = new Promise<void>((r) => (resolve = r));
    resendInvitationMock.mockReturnValueOnce(pending);
    render(<ResendInvitationModal org={makeOrg()} onClose={() => {}} />);
    fireEvent.click(screen.getByTestId("confirm-confirm"));
    await waitFor(() =>
      expect(screen.getByTestId("confirm-confirm")).toHaveTextContent("Sending…")
    );
    resolve();
  });

  test("double-click guard: clicking confirm twice only calls API once", async () => {
    let resolve!: () => void;
    const pending = new Promise<void>((r) => (resolve = r));
    resendInvitationMock.mockReturnValueOnce(pending);
    render(<ResendInvitationModal org={makeOrg()} onClose={() => {}} />);
    const btn = screen.getByTestId("confirm-confirm");
    fireEvent.click(btn);
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(resendInvitationMock).toHaveBeenCalledTimes(1);
    resolve();
  });
});
