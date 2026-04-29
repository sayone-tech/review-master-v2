import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AccessChips } from "./AccessChips";
import type { TeamMemberRow, AccessScopeRow } from "./types";

function makeRow(over: Partial<TeamMemberRow> = {}): TeamMemberRow {
  return {
    id: 1,
    full_name: "Alice",
    email: "alice@example.com",
    role: "STAFF_ADMIN",
    is_active: true,
    invited_at: null,
    accepted_at: null,
    status: "ACTIVE",
    access_scopes: [],
    ...over,
  };
}

function regionScope(id: number, regionId = "RGN001"): AccessScopeRow {
  return {
    id,
    scope_type: "REGION",
    region: id,
    region_name: `Region ${id}`,
    region_region_id: regionId,
    shop: null,
    shop_name: null,
  };
}

function shopScope(id: number, name = "Shop A"): AccessScopeRow {
  return {
    id,
    scope_type: "SHOP",
    region: null,
    region_name: null,
    region_region_id: null,
    shop: id,
    shop_name: name,
  };
}

describe("AccessChips", () => {
  it("Manager role renders Crown + All stores pill", () => {
    render(<AccessChips member={makeRow({ role: "ORG_ADMIN" })} />);
    expect(screen.getByText("All stores")).toBeInTheDocument();
  });

  it("Staff with 0 scopes renders dash placeholder", () => {
    render(<AccessChips member={makeRow({ role: "STAFF_ADMIN", access_scopes: [] })} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("Staff with 2 scopes renders 2 chips, no +N more", () => {
    render(
      <AccessChips
        member={makeRow({ access_scopes: [regionScope(1), shopScope(2)] })}
      />,
    );
    expect(screen.getByText("RGN001")).toBeInTheDocument();
    expect(screen.getByText("Shop A")).toBeInTheDocument();
    expect(screen.queryByText(/more/)).not.toBeInTheDocument();
  });

  it("Staff with 5 scopes renders first 2 + '+3 more'", () => {
    render(
      <AccessChips
        member={makeRow({
          access_scopes: [
            regionScope(1, "R01"),
            regionScope(2, "R02"),
            shopScope(3, "S1"),
            shopScope(4, "S2"),
            shopScope(5, "S3"),
          ],
        })}
      />,
    );
    expect(screen.getByText("R01")).toBeInTheDocument();
    expect(screen.getByText("R02")).toBeInTheDocument();
    expect(screen.getByText("+3 more")).toBeInTheDocument();
    expect(screen.queryByText("S1")).not.toBeInTheDocument();
  });

  it("Region scope renders region_region_id in monospace", () => {
    render(<AccessChips member={makeRow({ access_scopes: [regionScope(1, "XYZ")] })} />);
    expect(screen.getByText("XYZ")).toBeInTheDocument();
  });

  it("Shop scope renders shop_name", () => {
    render(<AccessChips member={makeRow({ access_scopes: [shopScope(1, "MyShop")] })} />);
    expect(screen.getByText("MyShop")).toBeInTheDocument();
  });
});
