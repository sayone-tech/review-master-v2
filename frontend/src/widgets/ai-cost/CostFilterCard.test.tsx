import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CostFilterCard, validateDraft } from "./CostFilterCard";

const setCustom = (from: string, to: string) => {
  fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "custom" } });
  fireEvent.change(screen.getByLabelText("From date"), { target: { value: from } });
  fireEvent.change(screen.getByLabelText("To date"), { target: { value: to } });
};

describe("CostFilterCard", () => {
  it("does not apply until Apply is clicked", () => {
    const onApply = vi.fn();
    render(<CostFilterCard filters={{ range: "this_month" }} onApply={onApply} />);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "30d" } });
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith({ range: "30d" });
  });

  it("shows From/To only for Custom and applies a valid custom range", () => {
    const onApply = vi.fn();
    render(<CostFilterCard filters={{ range: "7d" }} onApply={onApply} />);
    expect(screen.queryByLabelText("From date")).toBeNull();
    setCustom("2026-10-01", "2026-10-31");
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith({ range: "custom", from: "2026-10-01", to: "2026-10-31" });
  });

  it("blocks Apply with an inline error for missing, inverted or over-long ranges", () => {
    const onApply = vi.fn();
    render(<CostFilterCard filters={{ range: "7d" }} onApply={onApply} />);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "custom" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.getByRole("alert")).toHaveTextContent("both");
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-31" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.getByRole("alert")).toHaveTextContent("on or before");
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2025-01-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(screen.getByRole("alert")).toHaveTextContent("365");
    expect(onApply).not.toHaveBeenCalled();
  });

  it("accepts exactly 365 days inclusive", () => {
    expect(validateDraft({ range: "custom", from: "2026-01-01", to: "2026-12-31" })).toBeNull();
    expect(validateDraft({ range: "custom", from: "2026-01-01", to: "2027-01-01" })).not.toBeNull();
  });

  it("shows Clear only for non-default applied filters and applies the default immediately", () => {
    const onApply = vi.fn();
    const { rerender } = render(<CostFilterCard filters={{ range: "this_month" }} onApply={onApply} />);
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
    rerender(<CostFilterCard filters={{ range: "90d" }} onApply={onApply} />);
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onApply).toHaveBeenCalledWith({ range: "this_month" });
  });

  it("shows a server error from the API", () => {
    render(<CostFilterCard filters={{ range: "7d" }} onApply={vi.fn()} serverError="Bad range" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Bad range");
  });
});
