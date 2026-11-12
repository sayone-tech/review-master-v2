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
    expect(screen.getByRole("button", { name: "Add New Price" })).toHaveAttribute("aria-disabled", "true");
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

  it("ignores a slow history response for a model that is no longer expanded", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { model: "model-a", current: priceRow({ id: 1, model: "model-a" }), scheduled: null },
        { model: "model-b", current: priceRow({ id: 2, model: "model-b" }), scheduled: null },
      ],
    });
    let resolveA!: (v: Awaited<ReturnType<typeof api.fetchHistory>>) => void;
    const pageOf = (rows: ReturnType<typeof priceRow>[]) => ({
      count: rows.length,
      next: null,
      previous: null,
      results: rows,
    });
    vi.mocked(api.fetchHistory).mockImplementation((m) =>
      m === "model-a"
        ? new Promise((res) => {
            resolveA = res;
          })
        : Promise.resolve(pageOf([priceRow({ id: 20, model: "model-b", source: "sync" })])),
    );
    render(<AiPricingWidget />);
    await screen.findByText("model-a");
    await userEvent.click(screen.getByRole("button", { name: "View history for model-a" }));
    await userEvent.click(screen.getByRole("button", { name: "View history for model-b" }));
    await screen.findByText("LiteLLM sync");

    resolveA(pageOf([priceRow({ id: 10, model: "model-a", source: "seed" })]));
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByText("LiteLLM sync")).toBeInTheDocument();
    expect(screen.queryByText("Seed")).not.toBeInTheDocument();
  });
});
