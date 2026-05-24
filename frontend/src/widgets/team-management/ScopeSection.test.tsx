import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScopeSection } from "./ScopeSection";
import type { RegionOption, ShopOption } from "./types";

const regions: RegionOption[] = [
  { id: 1, region_id: "R01", name: "North" },
  { id: 2, region_id: "R02", name: "South" },
];

const shops: ShopOption[] = [
  { id: 10, name: "Shop Alpha", region: 1, region_id: "R01", region_name: "North" },
  { id: 11, name: "Shop Beta", region: 2, region_id: "R02", region_name: "South" },
];

const defaultProps = {
  regions,
  activeShops: shops,
  selectedRegionIds: new Set<number>(),
  selectedShopIds: new Set<number>(),
  onChangeRegions: vi.fn(),
  onChangeShops: vi.fn(),
};

describe("ScopeSection", () => {
  it("renders region checkbox list when regions provided", () => {
    render(<ScopeSection {...defaultProps} />);
    expect(screen.getByText("North")).toBeInTheDocument();
    expect(screen.getByText("South")).toBeInTheDocument();
  });

  it("renders shop checkbox list (all active shops)", () => {
    render(<ScopeSection {...defaultProps} initialMode="store" />);
    expect(screen.getByText("Shop Alpha")).toBeInTheDocument();
    expect(screen.getByText("Shop Beta")).toBeInTheDocument();
  });

  it("toggling a region checkbox calls onChangeRegions with updated set", () => {
    const onChangeRegions = vi.fn();
    render(<ScopeSection {...defaultProps} onChangeRegions={onChangeRegions} />);
    fireEvent.click(screen.getByLabelText("North") ?? screen.getAllByRole("checkbox")[0]);
    expect(onChangeRegions).toHaveBeenCalledOnce();
    const [nextSet] = onChangeRegions.mock.calls[0] as [Set<number>];
    expect(nextSet.has(1)).toBe(true);
  });

  it("toggling a shop checkbox calls onChangeShops with updated set", () => {
    const onChangeShops = vi.fn();
    render(<ScopeSection {...defaultProps} onChangeShops={onChangeShops} initialMode="store" />);
    const allCheckboxes = screen.getAllByRole("checkbox");
    fireEvent.click(allCheckboxes[0]);
    expect(onChangeShops).toHaveBeenCalledOnce();
    const [nextSet] = onChangeShops.mock.calls[0] as [Set<number>];
    expect(nextSet.size).toBeGreaterThan(0);
  });

  it("renders validationError when prop is set", () => {
    render(
      <ScopeSection
        {...defaultProps}
        validationError="Please select at least one region or store."
      />,
    );
    expect(
      screen.getByText("Please select at least one region or store."),
    ).toBeInTheDocument();
  });

  it("shows placeholder when no regions exist", () => {
    render(<ScopeSection {...defaultProps} regions={[]} />);
    expect(
      screen.getByText("No regions to assign — create regions first."),
    ).toBeInTheDocument();
  });
});
