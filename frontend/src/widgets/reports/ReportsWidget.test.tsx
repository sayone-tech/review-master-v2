import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReportsWidget } from "./ReportsWidget";
import { useReportData } from "./useReportData";
import { setHeaderCount } from "../../shell/header";

vi.mock("./useReportData", () => ({ useReportData: vi.fn() }));
vi.mock("../../shell/header", () => ({ setHeaderCount: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

describe("ReportsWidget", () => {
  it("renders no page heading (the header owns the title) and reports the store count", () => {
    vi.mocked(useReportData).mockReturnValue({
      data: [{}, {}, {}],
      isLoading: false,
      error: null,
    } as never);
    render(<ReportsWidget />);
    expect(screen.queryByRole("heading")).toBeNull();
    expect(setHeaderCount).toHaveBeenLastCalledWith(3);
  });

  it("hides the count while loading", () => {
    vi.mocked(useReportData).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never);
    render(<ReportsWidget />);
    expect(setHeaderCount).toHaveBeenLastCalledWith(null);
  });

  const rows = [
    { shop_id: 1, shop_name: "Alpha", total_reviews: 5, avg_rating: 4.5, replied_count: 1, not_replied_count: 4, positive_count: 1, neutral_count: 0, negative_count: 4 },
    { shop_id: 2, shop_name: "Beta", total_reviews: 9, avg_rating: 3.0, replied_count: 8, not_replied_count: 1, positive_count: 8, neutral_count: 0, negative_count: 1 },
  ];
  const storeOrder = () => screen.getAllByText(/^(Alpha|Beta)$/).map((e) => e.textContent);

  it("has no Apply button", () => {
    vi.mocked(useReportData).mockReturnValue({ data: rows, isLoading: false, error: null } as never);
    render(<ReportsWidget />);
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
  });

  it("sort links in the toolbar reorder the table exactly as before", () => {
    vi.mocked(useReportData).mockReturnValue({ data: rows, isLoading: false, error: null } as never);
    render(<ReportsWidget />);
    expect(storeOrder()).toEqual(["Beta", "Alpha"]);
    fireEvent.click(screen.getByRole("button", { name: "Avg Rating" }));
    expect(storeOrder()).toEqual(["Alpha", "Beta"]);
    fireEvent.click(screen.getByRole("button", { name: "Avg Rating" }));
    expect(storeOrder()).toEqual(["Beta", "Alpha"]);
  });
});
