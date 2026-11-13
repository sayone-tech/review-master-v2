import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReportsWidget } from "./ReportsWidget";
import { useReportData } from "./useReportData";
import { setHeaderCount } from "../../shell/header";

vi.mock("./useReportData", () => ({ useReportData: vi.fn() }));
vi.mock("./FilterBar", () => ({ FilterBar: () => null }));
vi.mock("./ReportsTable", () => ({ ReportsTable: () => null }));
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
});
