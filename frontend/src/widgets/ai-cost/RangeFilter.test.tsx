import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RangeFilter } from "./RangeFilter";

describe("RangeFilter custom range", () => {
  it("does not call onChange until both dates are set", () => {
    const onChange = vi.fn();
    render(<RangeFilter filters={{ range: "7d" }} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "custom" } });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByLabelText("From date")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-01" } });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-31" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ range: "custom", from: "2026-10-01", to: "2026-10-31" });
  });

  it("does not call onChange for an inverted range and shows a message", () => {
    const onChange = vi.fn();
    render(<RangeFilter filters={{ range: "7d" }} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-31" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("switching back to a preset applies immediately", () => {
    const onChange = vi.fn();
    render(<RangeFilter filters={{ range: "7d" }} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "30d" } });
    expect(onChange).toHaveBeenCalledWith({ range: "30d" });
  });
});
