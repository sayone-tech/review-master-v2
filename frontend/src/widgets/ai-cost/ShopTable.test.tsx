import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ShopTable, UNATTRIBUTED_HINT } from "./ShopTable";
import type { ShopCostRow, UnattributedCost } from "./types";

const shop: ShopCostRow = {
  shop_id: 3,
  name: "High St",
  region_name: "North",
  calls: 2,
  input_tokens: 1000,
  output_tokens: 400,
  cost: "4.000000",
  by_request_type: { enrichment: "3.000000", reply: "1.000000" },
};
const unattributed: UnattributedCost = {
  calls: 1,
  input_tokens: 500,
  output_tokens: 200,
  cost: "0.500000",
  by_request_type: { enrichment: "0.500000" },
};

function setup(u: UnattributedCost | null) {
  render(<ShopTable rows={[shop]} unattributed={u} sort="-cost" onSort={vi.fn()} />);
}

describe("ShopTable", () => {
  it("renders Unattributed as the last row, muted, non-clickable, without region badge", () => {
    setup(unattributed);
    const rows = screen.getAllByRole("row");
    const last = rows[rows.length - 1];
    expect(within(last).getByText("Unattributed")).toBeInTheDocument();
    expect(within(last).getByText(UNATTRIBUTED_HINT)).toHaveClass("sr-only");
    expect(within(last).queryByRole("link")).toBeNull();
    expect(within(last).queryByText("North")).toBeNull();
    expect(within(last).getAllByText("$0.50").length).toBeGreaterThan(0);
  });

  it("renders no Unattributed row when null", () => {
    setup(null);
    expect(screen.queryByText("Unattributed")).toBeNull();
  });

  it("shows the region badge for each shop", () => {
    setup(null);
    expect(screen.getByText("High St")).toBeInTheDocument();
    expect(screen.getByText("North")).toBeInTheDocument();
  });
});
