import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ShopTableWidget } from "./ShopTable";
import type { ShopRow } from "./types";
import * as api from "./api";
import { ShopModals } from "./ShopModals";
import { getShopCredits, resetCreditsStoreForTests } from "../credits/creditsStore";

function fakeRow(over: Partial<ShopRow> = {}): ShopRow {
  return {
    id: 1,
    name: "ACME Cafe",
    phone: "",
    street_address: "",
    place_id: "ChIJ",
    connection_method: "GOOGLE_OAUTH",
    connection_status: "CONNECTED",
    sync_depth: "TWO_YEARS",
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
  resetCreditsStoreForTests();
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

describe("ShopTableWidget credits column", () => {
  it("should render a credits badge that dispatches shop:open-credits with the row when clicked", () => {
    const shop = fakeRow({ credits_remaining: 35, credits_total: 100 });
    const handler = vi.fn();
    window.addEventListener("shop:open-credits", handler);
    render(
      <ShopTableWidget
        initial={{
          rows: [shop],
          allocation: { current: 1, max: 5, at_limit: false },
          hasRegions: true,
        }}
      />,
    );
    expect(screen.getByText("CREDITS")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "35 credits remaining this month" }));
    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0][0] as CustomEvent).detail).toEqual(shop);
    window.removeEventListener("shop:open-credits", handler);
  });
});

const ALLOC = { current: 1, max: 5, at_limit: false };

describe("ShopTableWidget credit seeding", () => {
  it("should seed the store from bootstrap rows that carry credit fields", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [fakeRow({ id: 5, credits_remaining: 35, credits_total: 100 })],
          allocation: ALLOC,
          hasRegions: true,
        }}
      />,
    );
    expect(getShopCredits(5)).toMatchObject({ remaining: 35, total: 100, isEnabled: true });
  });

  it("should seed from refreshed rows and keep the last known badge when a later row lacks credit fields", async () => {
    render(
      <ShopTableWidget
        initial={{ rows: [], allocation: ALLOC, hasRegions: true }}
      />,
    );
    // Let the widget's debounced initial search refresh settle before scripting refreshes.
    const list = vi.mocked(api.listShops);
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1));
    list.mockResolvedValueOnce({
      count: 1,
      next: null,
      previous: null,
      results: [fakeRow({ id: 5, credits_remaining: 20, credits_total: 100 })],
      allocation_status: ALLOC,
      has_regions: true,
    });
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:refresh"));
    });
    expect(await screen.findByTestId("credits-badge-5")).toHaveTextContent("20 credits");

    list.mockResolvedValueOnce({
      count: 1,
      next: null,
      previous: null,
      results: [fakeRow({ id: 5 })],
      allocation_status: ALLOC,
      has_regions: true,
    });
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:refresh"));
    });
    await waitFor(() => expect(list).toHaveBeenCalledTimes(3));
    expect(await screen.findByTestId("credits-badge-5")).toHaveTextContent("20 credits");
  });

  it("should show a dash for a row that never had credit fields", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [fakeRow({ id: 6, phone: "555-0100" })],
          allocation: ALLOC,
          hasRegions: true,
        }}
      />,
    );
    expect(screen.queryByTestId("credits-badge-6")).not.toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("ShopTableWidget Staff empty state", () => {
  const empty = { rows: [], allocation: ALLOC, hasRegions: true };

  it("should show No shops assigned without a create call to action when not an Org Admin", () => {
    render(<ShopTableWidget initial={empty} isOrgAdmin={false} />);
    expect(screen.getByText("No shops assigned")).toBeInTheDocument();
    expect(
      screen.getByText(
        "You don't have access to any shops yet. Ask your organisation admin to give you access.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("+ Add your first shop")).not.toBeInTheDocument();
    expect(screen.queryByText("Go to Regions")).not.toBeInTheDocument();
  });

  it("should keep the existing empty states for an Org Admin by default", () => {
    render(<ShopTableWidget initial={empty} />);
    expect(screen.getByTestId("empty-state-b")).toBeInTheDocument();
    expect(screen.queryByText("No shops assigned")).not.toBeInTheDocument();
  });

  it("should keep the filtered-empty copy for Staff when a filter is active", async () => {
    window.history.replaceState({}, "", "/admin/org/shops/?region=3");
    render(<ShopTableWidget initial={empty} isOrgAdmin={false} />);
    expect(await screen.findByText("No matching shops.")).toBeInTheDocument();
    expect(screen.queryByText("No shops assigned")).not.toBeInTheDocument();
  });
});

describe("ShopTableWidget", () => {
  it("renders shop name and Active status for a connected shop", () => {
    render(
      <ShopTableWidget
        initial={{
          rows: [fakeRow()],
          allocation: { current: 1, max: 5, at_limit: false },
          hasRegions: true,
        }}
      />,
    );
    expect(screen.getByText("ACME Cafe")).toBeInTheDocument();
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
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

describe("ShopTableWidget add button in the filter row", () => {
  const mk = (atLimit: boolean) => ({
    rows: [fakeRow()],
    allocation: { current: atLimit ? 5 : 1, max: 5, at_limit: atLimit },
    hasRegions: true,
  });

  it("renders the Add Shop end-cap with shops used of the limit in the filter card", () => {
    render(<ShopTableWidget initial={mk(false)} />);
    const search = screen.getByTestId("shops-search");
    const btn = document.getElementById("open-create-shop") as HTMLElement;
    expect(btn).toHaveTextContent("Add Shop");
    expect(btn).toHaveTextContent("1 of 5 used");
    expect(search.closest(".rounded-\\[16px\\]")).toContainElement(btn);
    expect(btn).not.toHaveAttribute("aria-disabled");
  });

  it("is aria-disabled with the limit tooltip when at limit", () => {
    render(<ShopTableWidget initial={mk(true)} />);
    const btn = document.getElementById("open-create-shop") as HTMLElement;
    expect(btn).toHaveAttribute("aria-disabled", "true");
    expect(btn).toHaveAttribute("title", "Shop limit reached.");
    expect(btn).toHaveTextContent("Shop limit reached");
    expect(btn).toHaveTextContent("5 of 5 used");
    expect(btn.className).toContain("cursor-not-allowed");
  });

  it.each(["modals-first", "table-first"])(
    "clicking the table's Add Shop opens the create modal (%s)",
    (order) => {
      const modals = (
        <ShopModals allocation={{ current: 1, max: 5, at_limit: false }} regions={[]} />
      );
      const table = <ShopTableWidget initial={mk(false)} />;
      const a = document.createElement("div");
      const b = document.createElement("div");
      document.body.append(a, b);
      if (order === "modals-first") {
        render(modals, { container: a });
        render(table, { container: b });
      } else {
        render(table, { container: a });
        render(modals, { container: b });
      }
      fireEvent.click(document.getElementById("open-create-shop") as HTMLElement);
      expect(screen.getAllByText("Add Shop").length).toBeGreaterThan(0);
    },
  );
});
