import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterBar } from "./FilterBar";
import type { DashboardFilters, Region, Shop } from "./types";

const DEFAULTS: DashboardFilters = {
  region_id: null,
  shop_id: null,
  range: "all",
  date_from: null,
  date_to: null,
};

const REGIONS: Region[] = [
  { id: 1, name: "North" },
  { id: 2, name: "South" },
];

const SHOPS: Shop[] = [
  { id: 10, name: "Kochi Central", region_id: 1 },
  { id: 11, name: "Thrissur", region_id: 1 },
  { id: 20, name: "Trivandrum", region_id: 2 },
];

function setup(
  filters: DashboardFilters = DEFAULTS,
  regions: Region[] = REGIONS,
  shops: Shop[] = SHOPS,
) {
  const onApply = vi.fn();
  const onClear = vi.fn();
  render(
    <FilterBar
      filters={filters}
      regions={regions}
      shops={shops}
      onApply={onApply}
      onClear={onClear}
    />,
  );
  return { onApply, onClear };
}

/** The sentence as a sighted reader sees it: select option lists removed. */
function sentence(): string {
  const p = screen.getByTestId("filter-sentence").cloneNode(true) as HTMLElement;
  p.querySelectorAll("select").forEach((s) => s.remove());
  return (p.textContent ?? "").replace(/\s+/g, " ").replace(/ ▾/g, "").trim();
}

function optionLabels(label: string): string[] {
  const select = screen.getByLabelText(label) as HTMLSelectElement;
  return Array.from(select.options).map((o) => o.textContent ?? "");
}

describe("Dashboard FilterBar (sentence)", () => {
  it("should read the defaults as a sentence when no filter is set", () => {
    setup();
    expect(sentence()).toBe("Showing all regions, all stores for all time");
  });

  it("should name the region, store and range when they are chosen", () => {
    setup({ region_id: 1, shop_id: 10, range: "30d", date_from: "x", date_to: "y" });
    expect(sentence()).toBe("Showing North, Kochi Central for the last 30 days");
  });

  it("should offer sentence wording when the range list opens", () => {
    setup();
    expect(optionLabels("Filter by date range")).toEqual([
      "all time",
      "the last 7 days",
      "the last 30 days",
      "the last 90 days",
      "a custom range",
    ]);
  });

  it("should apply immediately when a range is picked, with no Apply button", () => {
    const { onApply } = setup();
    fireEvent.change(screen.getByLabelText("Filter by date range"), {
      target: { value: "30d" },
    });
    expect(onApply).toHaveBeenCalledWith(null, null, "30d", null, null);
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });

  it("should reset the store and apply when the region changes", () => {
    const { onApply } = setup({ ...DEFAULTS, shop_id: 20 });
    fireEvent.change(screen.getByLabelText("Filter by region"), {
      target: { value: "1" },
    });
    expect(onApply).toHaveBeenCalledWith(1, null, "all", null, null);
  });

  it("should narrow the store list when a region is chosen", () => {
    setup({ ...DEFAULTS, region_id: 1 });
    expect(optionLabels("Filter by store")).toEqual([
      "all stores",
      "Kochi Central",
      "Thrissur",
    ]);
  });

  it("should apply immediately when a store is picked", () => {
    const { onApply } = setup();
    fireEvent.change(screen.getByLabelText("Filter by store"), {
      target: { value: "11" },
    });
    expect(onApply).toHaveBeenCalledWith(null, 11, "all", null, null);
  });

  it("should apply a custom range only when both dates are valid", () => {
    const { onApply } = setup();
    fireEvent.change(screen.getByLabelText("Filter by date range"), {
      target: { value: "custom" },
    });
    expect(onApply).not.toHaveBeenCalled();
    expect(sentence()).toContain("for a custom range from to");

    fireEvent.change(screen.getByLabelText("From date"), {
      target: { value: "2026-10-01" },
    });
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("To date"), {
      target: { value: "2026-10-31" },
    });
    expect(onApply).toHaveBeenCalledWith(null, null, "custom", "2026-10-01", "2026-10-31");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("should show the error and not apply when the custom range is invalid", () => {
    const { onApply } = setup();
    fireEvent.change(screen.getByLabelText("Filter by date range"), {
      target: { value: "custom" },
    });
    fireEvent.change(screen.getByLabelText("From date"), {
      target: { value: "2026-10-31" },
    });
    fireEvent.change(screen.getByLabelText("To date"), {
      target: { value: "2026-10-01" },
    });
    expect(onApply).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("End date must be after start date.");
  });

  it("should hide Reset when filters are at the defaults", () => {
    setup();
    expect(screen.queryByRole("button", { name: "Reset" })).not.toBeInTheDocument();
  });

  it("should call onClear when Reset is clicked with a filter set", () => {
    const { onClear } = setup({ ...DEFAULTS, range: "7d" });
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("should hide the region part when there is one region or none", () => {
    setup(DEFAULTS, [REGIONS[0]]);
    expect(screen.queryByLabelText("Filter by region")).not.toBeInTheDocument();
    expect(sentence()).toBe("Showing all stores for all time");
  });

  it("should hide the store part when there is only one store", () => {
    setup(DEFAULTS, [], [SHOPS[0]]);
    expect(screen.queryByLabelText("Filter by store")).not.toBeInTheDocument();
    expect(sentence()).toBe("Showing all time");
  });
});
