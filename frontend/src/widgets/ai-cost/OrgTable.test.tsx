import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { OrgTable } from "./OrgTable";
import type { OrgCostRow } from "./types";

const row: OrgCostRow = {
  organisation_id: 7,
  name: "Big Org",
  org_type: "retail",
  active_shops: 3,
  calls: 48312,
  input_tokens: 12_400_000,
  output_tokens: 400,
  cost: "7.500000",
  by_request_type: { enrichment: "5.000000", reply: "2.500000" },
};

function setup(sort = "-cost") {
  const onSort = vi.fn();
  const onOpen = vi.fn();
  render(<OrgTable rows={[row]} sort={sort} onSort={onSort} onOpen={onOpen} />);
  return { onSort, onOpen };
}

describe("OrgTable", () => {
  it("sorts ascending first when column is not active", () => {
    const { onSort } = setup("name");
    fireEvent.click(screen.getByRole("button", { name: /^Cost/ }));
    expect(onSort).toHaveBeenCalledWith("cost");
  });
  it("toggles to descending when column already ascending", () => {
    const { onSort } = setup("cost");
    fireEvent.click(screen.getByRole("button", { name: /^Cost/ }));
    expect(onSort).toHaveBeenCalledWith("-cost");
  });
  it("opens the org on row click", () => {
    const { onOpen } = setup();
    fireEvent.click(screen.getByText("Big Org"));
    expect(onOpen).toHaveBeenCalledWith(7);
  });
  it("shows full token count in a title tooltip", () => {
    setup();
    expect(screen.getByTitle("12,400,000")).toBeTruthy();
    expect(screen.getByText("48,312")).toBeTruthy();
  });
});
