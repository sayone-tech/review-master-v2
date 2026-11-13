import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Money, ShareBar, splitMoney } from "./Money";

describe("splitMoney", () => {
  it("fades zeros after the last significant digit but keeps cents", () => {
    expect(splitMoney("$1,245.67000000")).toEqual(["$1,245.67", "000000"]);
    expect(splitMoney("$0.00044200")).toEqual(["$0.000442", "00"]);
    expect(splitMoney("$3.00000000")).toEqual(["$3.00", "000000"]);
    expect(splitMoney("$0.12345678")).toEqual(["$0.12345678", ""]);
    expect(splitMoney("$0.150000")).toEqual(["$0.15", "0000"]);
    expect(splitMoney("$5")).toEqual(["$5", ""]);
  });
});

describe("Money", () => {
  it("keeps the full value as text with the padding zeros faint", () => {
    const { container } = render(<Money value="$0.00044200" />);
    expect(container).toHaveTextContent("$0.00044200");
    expect(screen.getByText("00")).toHaveClass("text-subtle");
  });
});

describe("ShareBar", () => {
  it("draws the cost's share of the total and hides with no total", () => {
    const { rerender } = render(<ShareBar cost="2.5" total={10} />);
    expect(screen.getByTestId("share-bar")).toHaveAttribute("title", "25% of total");
    expect((screen.getByTestId("share-bar").firstChild as HTMLElement).style.width).toBe("25%");
    rerender(<ShareBar cost="2.5" total={0} />);
    expect(screen.queryByTestId("share-bar")).toBeNull();
  });
});
