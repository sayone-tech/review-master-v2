import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelTable } from "./ModelTable";

describe("ModelTable", () => {
  it("renders rows in the given order with formatted cost", () => {
    render(
      <ModelTable
        rows={[
          { model: "big-model", calls: 10, input_tokens: 2000, output_tokens: 300, cost: "4.000000" },
          { model: "small-model", calls: 1, input_tokens: 5, output_tokens: 5, cost: "0.250000" },
        ]}
      />,
    );
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("big-model");
    expect(rows[0]).toHaveTextContent("$4.00000000");
    expect(rows[1]).toHaveTextContent("small-model");
    expect(rows[1]).toHaveTextContent("$0.25000000");
  });

  it("shows input and output tokens as visible text, not a tooltip", () => {
    render(
      <ModelTable
        rows={[{ model: "m", calls: 3, input_tokens: 12400, output_tokens: 3100, cost: "1.000000" }]}
      />,
    );
    expect(screen.getByText("12.4K in · 3.1K out")).toBeVisible();
    expect(screen.getAllByRole("row")[1]).not.toHaveAttribute("title");
  });
});
