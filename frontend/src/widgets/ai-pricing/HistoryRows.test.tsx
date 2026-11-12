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

  it("shows pills, source labels and who set each price", () => {
    render(<HistoryRows rows={rows} onDeleted={vi.fn()} />);
    const body = screen.getAllByRole("row").slice(1);
    expect(body).toHaveLength(3);
    expect(body[0]).toHaveTextContent("Seed");
    expect(body[0]).not.toHaveTextContent("Current");
    expect(body[1]).toHaveTextContent("Current");
    expect(body[1]).toHaveTextContent("Manual");
    expect(body[1]).toHaveTextContent("Ada Admin");
    expect(body[2]).toHaveTextContent("Scheduled");
    expect(body[2]).toHaveTextContent("LiteLLM sync");
  });

  it("disables delete with the tooltip unless can_delete", () => {
    render(<HistoryRows rows={rows} onDeleted={vi.fn()} />);
    const btns = screen.getAllByRole("button", { name: "Delete" });
    expect(btns[0]).toBeDisabled();
    expect(btns[0]).toHaveAttribute(
      "title",
      "This pricing is in effect or has been in effect — can't delete.",
    );
    expect(btns[1]).toBeDisabled();
    expect(btns[2]).toBeEnabled();
  });

  it("confirms, deletes the scheduled price and notifies the parent", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const onDeleted = vi.fn();
    render(<HistoryRows rows={rows} onDeleted={onDeleted} />);
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[2]);
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
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[2]);
    await userEvent.click(screen.getByTestId("confirm-cancel"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an error when delete fails", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Nope." }), { status: 409 }),
    );
    const onDeleted = vi.fn();
    render(<HistoryRows rows={rows} onDeleted={onDeleted} />);
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[2]);
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Nope\./)).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
