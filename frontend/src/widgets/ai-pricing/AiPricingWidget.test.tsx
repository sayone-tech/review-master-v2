import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AiPricingWidget } from "./AiPricingWidget";
import { priceRow } from "./fixtures";
import * as api from "./api";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchPriceSummary: vi.fn(),
  fetchHistory: vi.fn(),
  deleteScheduledPrice: vi.fn(),
}));

const scheduled = priceRow({
  id: 2,
  status: "scheduled",
  effective_from: "2026-11-17T10:00:00Z",
  can_delete: true,
});
const page = (s: typeof scheduled | null) => ({
  count: 1,
  next: null,
  previous: null,
  results: [{ model: "gpt-4o-mini", current: priceRow(), scheduled: s }],
});

describe("AiPricingWidget", () => {
  beforeEach(() => {
    vi.mocked(api.fetchPriceSummary).mockReset();
    vi.mocked(api.fetchHistory).mockReset();
    vi.mocked(api.deleteScheduledPrice).mockReset();
  });

  it("renders header, disabled Add New Price, and the table", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    render(<AiPricingWidget />);
    expect(screen.getByRole("heading", { name: "AI Pricing" })).toBeInTheDocument();
    expect(
      screen.getByText("Current and historical token rates for OpenAI models"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Active since 2026-01-05")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add New Price" })).toBeDisabled();
  });

  it("lazily loads history on expand and refetches both after a delete", async () => {
    vi.mocked(api.fetchPriceSummary)
      .mockResolvedValueOnce(page(scheduled))
      .mockResolvedValueOnce(page(null));
    vi.mocked(api.fetchHistory)
      .mockResolvedValueOnce({ count: 2, next: null, previous: null, results: [priceRow(), scheduled] })
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [priceRow()] });
    vi.mocked(api.deleteScheduledPrice).mockResolvedValue();
    render(<AiPricingWidget />);
    await screen.findByText("Active since 2026-01-05");
    expect(api.fetchHistory).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "View history for gpt-4o-mini" }));
    expect(api.fetchHistory).toHaveBeenCalledWith("gpt-4o-mini");
    const deletes = await screen.findAllByRole("button", { name: "Delete" });
    await userEvent.click(deletes[1]);
    await userEvent.click(screen.getByTestId("confirm-confirm"));

    expect(api.deleteScheduledPrice).toHaveBeenCalledWith(2);
    await vi.waitFor(() => {
      expect(api.fetchPriceSummary).toHaveBeenCalledTimes(2);
      expect(api.fetchHistory).toHaveBeenCalledTimes(2);
    });
    await vi.waitFor(() => expect(screen.queryByText(/Scheduled:/)).not.toBeInTheDocument());
  });
});
