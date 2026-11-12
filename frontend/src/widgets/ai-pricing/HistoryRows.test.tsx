import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistoryRows } from "./HistoryRows";
import { priceRow } from "./fixtures";

const fetchMock = vi.fn();

const rows = [
  priceRow({
    id: 1,
    status: "historical",
    source: "seed",
    created_by: null,
    effective_from: "2025-01-01T00:00:00Z",
    effective_to: "2026-01-05T00:00:00Z",
  }),
  priceRow({ id: 2 }),
  priceRow({
    id: 3,
    status: "scheduled",
    source: "sync",
    effective_from: "2026-11-17T10:00:00Z",
    can_delete: true,
  }),
];

describe("HistoryRows", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "csrftoken=tok123";
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows a dated timeline with status and source badges and who set each price", () => {
    render(<HistoryRows rows={rows} onDeleted={vi.fn()} />);
    expect(screen.getByRole("list", { name: "Price history" })).toBeInTheDocument();
    const body = screen.getAllByRole("listitem");
    expect(body).toHaveLength(3);
    expect(body[0]).toHaveTextContent("2025-01-01 to 2026-01-05");
    expect(body[0]).toHaveTextContent("Seed");
    expect(body[0]).not.toHaveTextContent("Set by");
    expect(body[0]).not.toHaveTextContent("Current");
    expect(body[1]).toHaveTextContent("Current");
    expect(body[1]).toHaveTextContent("Manual");
    expect(body[1]).toHaveTextContent("2026-01-05 to now");
    expect(body[1]).toHaveTextContent("Set by Ada Admin");
    expect(body[1]).toHaveTextContent("Input $0.150000");
    expect(body[2]).toHaveTextContent("From 2026-11-17 10:00 UTC");
    expect(body[2]).toHaveTextContent("Scheduled");
    expect(body[2]).toHaveTextContent("LiteLLM sync");
  });

  it("offers Delete only on the scheduled price", () => {
    render(<HistoryRows rows={rows} onDeleted={vi.fn()} />);
    const body = screen.getAllByRole("listitem");
    expect(within(body[0]).queryByRole("button", { name: "Delete" })).toBeNull();
    expect(within(body[1]).queryByRole("button", { name: "Delete" })).toBeNull();
    expect(within(body[2]).getByRole("button", { name: "Delete" })).not.toHaveAttribute("aria-disabled");
  });

  const locked = [priceRow({ id: 9, status: "scheduled", can_delete: false })];
  const reason = "This price is or has been in effect, so it can't be deleted.";

  it("disables delete with the tooltip unless can_delete", () => {
    render(<HistoryRows rows={locked} onDeleted={vi.fn()} />);
    const b = screen.getByRole("button", { name: "Delete" });
    expect(b).toHaveAttribute("title", reason);
    expect(b).toHaveAttribute("aria-disabled", "true");
    b.focus();
    expect(b).toHaveFocus();
    expect(b).toHaveAccessibleDescription(reason);
  });

  it("clicking a locked delete does nothing", async () => {
    render(<HistoryRows rows={locked} onDeleted={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.queryByTestId("confirm-confirm")).not.toBeInTheDocument();
  });

  it("confirms, deletes the scheduled price and notifies the parent", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const onDeleted = vi.fn();
    render(<HistoryRows rows={rows} onDeleted={onDeleted} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/superadmin/ai-pricing/3/", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-CSRFToken": "tok123" },
    });
    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("cancelling the confirmation does not delete", async () => {
    render(<HistoryRows rows={rows} onDeleted={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByTestId("confirm-cancel"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an error when delete fails", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Nope." }), { status: 409 }),
    );
    const onDeleted = vi.fn();
    render(<HistoryRows rows={rows} onDeleted={onDeleted} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Nope\./)).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
