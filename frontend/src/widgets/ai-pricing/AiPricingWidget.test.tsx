import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AiPricingWidget } from "./AiPricingWidget";
import { priceRow } from "./fixtures";
import * as api from "./api";
import { syncStatus } from "./syncFixtures";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchPriceSummary: vi.fn(),
  fetchHistory: vi.fn(),
  deleteScheduledPrice: vi.fn(),
  fetchMissing: vi.fn(),
  refreshMissing: vi.fn(),
  fetchSuggestions: vi.fn(),
  createPrice: vi.fn(),
  fetchSyncStatus: vi.fn(),
  toggleSync: vi.fn(),
  triggerSync: vi.fn(),
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
    vi.mocked(api.createPrice).mockReset();
    vi.mocked(api.fetchMissing).mockReset();
    vi.mocked(api.fetchMissing).mockResolvedValue({ models: [], generated_at: "x" });
    vi.mocked(api.fetchSuggestions).mockResolvedValue({ results: [] });
    vi.mocked(api.fetchSyncStatus).mockReset();
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.toggleSync).mockReset();
  });

  it("renders header, an enabled Add New Price, and the table", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    render(<AiPricingWidget />);
    expect(screen.getByRole("heading", { name: "AI Pricing" })).toBeInTheDocument();
    expect(
      screen.getByText("Token rates used to calculate AI cost"),
    ).toBeInTheDocument();
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add new price" })).not.toHaveAttribute("aria-disabled");
  });

  it("opens the modal from the header, a row action and the alert, pre-filling the model", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    vi.mocked(api.fetchMissing).mockResolvedValue({
      models: [{ model: "gpt-new", last_used_at: null, configured: false }],
      generated_at: "x",
    });
    render(<AiPricingWidget />);
    await screen.findByText("gpt-4o-mini");

    await userEvent.click(screen.getByRole("button", { name: "Add new price" }));
    expect(screen.getByRole("combobox", { name: "Model" })).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: "Add price for gpt-new" }));
    expect(screen.getByRole("combobox", { name: "Model" })).toHaveValue("gpt-new");
  });

  it("after saving, closes the modal and refetches table, open history and alert", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    vi.mocked(api.fetchHistory).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [priceRow()],
    });
    vi.mocked(api.createPrice).mockResolvedValue(priceRow({ id: 9 }));
    render(<AiPricingWidget />);
    await screen.findByText("gpt-4o-mini");
    await userEvent.click(screen.getByRole("button", { name: "View history for gpt-4o-mini" }));
    await vi.waitFor(() => expect(api.fetchHistory).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(api.fetchMissing).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole("button", { name: "Add new price" }));
    await userEvent.type(screen.getByRole("combobox", { name: "Model" }), "gpt-new");
    await userEvent.type(screen.getByLabelText(/Input price/), "1");
    await userEvent.type(screen.getByLabelText(/^Output price/), "2");
    await userEvent.type(screen.getByLabelText(/Cached input price/), "0.5");
    await userEvent.click(screen.getByRole("button", { name: "Save price" }));

    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await vi.waitFor(() => {
      expect(api.fetchPriceSummary).toHaveBeenCalledTimes(2);
      expect(api.fetchHistory).toHaveBeenCalledTimes(2);
      expect(api.fetchMissing).toHaveBeenCalledTimes(2);
      expect(api.fetchSyncStatus).toHaveBeenCalledTimes(2); // banner list refreshed after a save
    });
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
    await screen.findByText("gpt-4o-mini");
    expect(api.fetchHistory).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "View history for gpt-4o-mini" }));
    expect(api.fetchHistory).toHaveBeenCalledWith("gpt-4o-mini");
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await userEvent.click(screen.getByTestId("confirm-confirm"));

    expect(api.deleteScheduledPrice).toHaveBeenCalledWith(2);
    await vi.waitFor(() => {
      expect(api.fetchPriceSummary).toHaveBeenCalledTimes(2);
      expect(api.fetchHistory).toHaveBeenCalledTimes(2);
    });
    await vi.waitFor(() => expect(screen.queryByText(/Scheduled from/)).not.toBeInTheDocument());
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

  it("'Use LiteLLM price' opens the add-price modal pre-filled with model and LiteLLM values", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    const base = syncStatus({ enabled: true });
    vi.mocked(api.fetchSyncStatus).mockResolvedValue({
      ...base,
      summary: {
        ...base.summary,
        skipped_manual: [
          {
            model: "m3",
            ours: { input: "0.15000000", output: "0.60000000", cached: "0.07500000" },
            litellm: { input: "0.10000000", output: "0.40000000", cached: "0.05000000" },
          },
        ],
      },
    });
    render(<AiPricingWidget />);
    await userEvent.click(await screen.findByRole("button", { name: "Review" }));
    await userEvent.click(screen.getByRole("button", { name: "Use LiteLLM price" }));
    expect(screen.getByRole("combobox", { name: "Model" })).toHaveValue("m3");
    expect(screen.getByLabelText(/Input price/)).toHaveValue("0.10000000");
    expect(screen.getByLabelText(/Cached input price/)).toHaveValue("0.05000000");
  });

  it("toggling sync refetches the missing alert, whose sync note follows the enabled state", async () => {
    vi.mocked(api.fetchPriceSummary).mockResolvedValue(page(null));
    vi.mocked(api.fetchMissing).mockResolvedValue({
      models: [{ model: "gpt-new", last_used_at: null, configured: false }],
      generated_at: "x",
    });
    vi.mocked(api.toggleSync).mockResolvedValue(syncStatus({ enabled: true }));
    render(<AiPricingWidget />);
    await screen.findByText("1 model is logged without pricing.");
    expect(screen.queryByText(/next weekly sync/)).not.toBeInTheDocument();
    const before = vi.mocked(api.fetchMissing).mock.calls.length;
    await userEvent.click(await screen.findByRole("button", { name: "Turn on automatic pricing sync" }));
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    expect(await screen.findByText(/next weekly sync/)).toBeInTheDocument();
    expect(vi.mocked(api.fetchMissing).mock.calls.length).toBeGreaterThan(before);
  });
});
