import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SummaryStrip } from "./SummaryStrip";
import type { CostSummaryTotals } from "./types";

const base: CostSummaryTotals = {
  calls: 12,
  success_calls: 10,
  failed_calls: 1,
  moderated_calls: 1,
  input_tokens: 5000,
  output_tokens: 1000,
  cost: "3.000000",
  org_count: 4,
  active_shops: 2,
};

describe("SummaryStrip", () => {
  it("renders the four spec cells and footers", () => {
    render(<SummaryStrip totals={base} />);
    for (const l of ["Total cost", "API calls", "Input tokens", "Output tokens"])
      expect(screen.getByText(l)).toBeTruthy();
    expect(screen.getByText("Across 4 organisations")).toBeTruthy();
    expect(screen.getByText("10 succeeded, 1 failed, 1 moderated")).toBeTruthy();
    expect(screen.getByText("Avg 500 per call")).toBeTruthy();
    expect(screen.getByText("Avg 100 per call")).toBeTruthy();
  });
  it("shows the total cost with 8 decimals, padding zeros faded", () => {
    render(<SummaryStrip totals={base} />);
    expect(screen.getByTestId("cost-summary")).toHaveTextContent("$3.00000000");
    expect(screen.getByText("000000")).toHaveClass("text-faint");
  });
  it("uses singular organisation", () => {
    render(<SummaryStrip totals={{ ...base, org_count: 1 }} />);
    expect(screen.getByText("Across 1 organisation")).toBeTruthy();
  });
  it("accepts a footer override for the cost cell", () => {
    render(<SummaryStrip totals={base} costFooter="Across 2 active shops" />);
    expect(screen.getByText("Across 2 active shops")).toBeTruthy();
    expect(screen.queryByText(/organisation/)).toBeNull();
  });
  it("averages are 0 with no successful calls", () => {
    render(<SummaryStrip totals={{ ...base, success_calls: 0 }} />);
    expect(screen.getAllByText("Avg 0 per call")).toHaveLength(2);
  });
});
