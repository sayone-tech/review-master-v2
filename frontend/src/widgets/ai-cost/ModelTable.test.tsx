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
    expect(rows[0]).toHaveTextContent("$4.00");
    expect(rows[1]).toHaveTextContent("small-model");
    expect(rows[1]).toHaveTextContent("$0.25");
  });
});
