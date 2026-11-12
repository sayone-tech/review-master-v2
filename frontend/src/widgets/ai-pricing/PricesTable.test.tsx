import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PricesTable } from "./PricesTable";
import { priceRow } from "./fixtures";

const rows = [
  {
    model: "gpt-4o-mini",
    current: priceRow(),
    scheduled: priceRow({
      id: 2,
      status: "scheduled",
      input_token_price_per_1m: "0.10000000",
      output_token_price_per_1m: "0.50000000",
      cached_token_price_per_1m: "0.05000000",
      effective_from: "2026-11-17T10:00:00Z",
      can_delete: true,
    }),
  },
  { model: "gpt-x", current: priceRow({ id: 5, model: "gpt-x" }), scheduled: null },
];

describe("PricesTable", () => {
  it("renders columns, active-since and the scheduled line", () => {
    render(<PricesTable rows={rows} expandedModel={null} onViewHistory={vi.fn()} />);
    for (const h of [
      "Model",
      "Input (per 1M tokens)",
      "Output (per 1M tokens)",
      "Cached Input (per 1M)",
      "Effective From",
      "Actions",
    ]) {
      expect(screen.getByRole("columnheader", { name: h })).toBeInTheDocument();
    }
    const first = screen.getAllByRole("row")[1];
    expect(first).toHaveTextContent("gpt-4o-mini");
    expect(first).toHaveTextContent("Active since 2026-01-05");
    expect(first).toHaveTextContent("$0.150000");
    expect(first).toHaveTextContent("$0.600000");
    expect(first).toHaveTextContent("$0.075000");
    expect(first).toHaveTextContent(
      "Scheduled: $0.100000/$0.500000/$0.050000 from 2026-11-17 10:00 UTC",
    );
    expect(screen.getAllByText(/Scheduled:/)).toHaveLength(1);
  });

  it("renders the empty state with a disabled CTA until the modal exists", () => {
    render(<PricesTable rows={[]} expandedModel={null} onViewHistory={vi.fn()} />);
    expect(
      screen.getByText(
        "No pricing configured. Add pricing for at least one model to enable cost tracking.",
      ),
    ).toBeInTheDocument();
    const cta = screen.getByRole("button", { name: "Add New Price" });
    expect(cta).toHaveAttribute("aria-disabled", "true");
    expect(cta).toHaveAccessibleDescription("Coming in the next step");
    expect(cta).toHaveAttribute("title", "Coming in the next step");
  });

  it("disables row add-price actions without a handler, enables them with one", async () => {
    const { rerender } = render(
      <PricesTable rows={rows} expandedModel={null} onViewHistory={vi.fn()} />,
    );
    const btns = screen.getAllByRole("button", { name: "Add new price for this model" });
    expect(btns[0]).toHaveAttribute("aria-disabled", "true");
    btns[0].focus();
    expect(btns[0]).toHaveFocus();
    expect(btns[0]).toHaveAccessibleDescription("Coming in the next step");
    expect(btns[0]).toHaveAttribute("title", "Coming in the next step");

    const onAddPrice = vi.fn();
    rerender(
      <PricesTable
        rows={rows}
        expandedModel={null}
        onViewHistory={vi.fn()}
        onAddPrice={onAddPrice}
      />,
    );
    await userEvent.click(screen.getAllByRole("button", { name: "Add new price for this model" })[1]);
    expect(onAddPrice).toHaveBeenCalledWith("gpt-x");
  });

  it("toggles history and renders expanded content under the row", async () => {
    const onViewHistory = vi.fn();
    render(
      <PricesTable
        rows={rows}
        expandedModel="gpt-x"
        onViewHistory={onViewHistory}
        renderExpanded={(m) => <div>history for {m}</div>}
      />,
    );
    expect(screen.getByText("history for gpt-x")).toBeInTheDocument();
    const views = screen.getAllByRole("button", { name: /history/i });
    expect(views[1]).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(views[0]);
    expect(onViewHistory).toHaveBeenCalledWith("gpt-4o-mini");
  });
});
