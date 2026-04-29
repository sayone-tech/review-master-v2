import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ShopTableWidget } from "./ShopTable";
import type { ShopRow } from "./types";
import * as api from "./api";

function fakeRow(over: Partial<ShopRow> = {}): ShopRow {
  return {
    id: 1,
    name: "ACME Cafe",
    phone: "",
    street_address: "",
    place_id: "ChIJ",
    connection_method: "GOOGLE_OAUTH",
    connection_status: "CONNECTED",
    is_active: true,
    region: 1,
    region_name: "North",
    region_region_id: "N001",
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "",
    ...over,
  };
}

beforeEach(() => {
  vi.spyOn(api, "listShops").mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [],
    allocation_status: { current: 0, max: 5, at_limit: false },
    has_regions: true,
  });
  window.history.replaceState({}, "", "/admin/org/shops/");
});

describe("ShopTableWidget", () => {
  it("renders ConnectionStatusPill text for OAuth connected shop", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [fakeRow()],
          allocation: { current: 1, max: 5, at_limit: false },
          hasRegions: true,
        }}
      />,
    );
    expect(screen.getByText("Connected via Google")).toBeInTheDocument();
  });

  it("renders Empty State A when hasRegions=false and no shops", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [],
          allocation: { current: 0, max: 5, at_limit: false },
          hasRegions: false,
        }}
      />,
    );
    expect(screen.getByTestId("empty-state-a")).toBeInTheDocument();
    expect(screen.getByText("Go to Regions")).toBeInTheDocument();
  });

  it("renders Empty State B when hasRegions=true and no shops", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [],
          allocation: { current: 0, max: 5, at_limit: false },
          hasRegions: true,
        }}
      />,
    );
    expect(screen.getByTestId("empty-state-b")).toBeInTheDocument();
    expect(screen.getByText("+ Add your first shop")).toBeInTheDocument();
  });

  it("clicking shop name dispatches shop:open-details", () => {
    const row = fakeRow();
    const spy = vi.fn();
    window.addEventListener("shop:open-details", spy);
    render(
      <ShopTableWidget
        initial={{ rows: [row], allocation: { current: 1, max: 5, at_limit: false }, hasRegions: true }}
      />,
    );
    fireEvent.click(screen.getByTestId("shop-name-1"));
    expect(spy).toHaveBeenCalledTimes(1);
    window.removeEventListener("shop:open-details", spy);
  });

  it("shows pagination controls", () => {
    const rows = Array.from({ length: 5 }, (_, i) => fakeRow({ id: i + 1, name: `Shop ${i + 1}` }));
    render(
      <ShopTableWidget
        initial={{ rows, allocation: { current: 5, max: 10, at_limit: false }, hasRegions: true }}
      />,
    );
    expect(screen.getByTestId("shops-page-size")).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toBeInTheDocument();
  });
});
