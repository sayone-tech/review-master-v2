import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FilterBar } from "./FilterBar";
import type { ReportFilters } from "./types";

const DEFAULTS: ReportFilters = {
  range: "30d",
  date_from: null,
  date_to: null,
  reply_status: "all",
  sentiment: "all",
};

function setup(filters: ReportFilters = DEFAULTS) {
  const onChange = vi.fn();
  const onSort = vi.fn();
  render(
    <FilterBar
      filters={filters}
      onChange={onChange}
      sortKey="total_reviews"
      sortDir="desc"
      onSort={onSort}
    />,
  );
  return { onChange, onSort };
}

describe("Reports FilterBar", () => {
  it("Period, Reply and Sentiment apply immediately", () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByLabelText("Filter by period"), { target: { value: "7d" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULTS, range: "7d" });
    fireEvent.change(screen.getByLabelText("Filter by reply status"), { target: { value: "replied" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULTS, reply_status: "replied" });
    fireEvent.change(screen.getByLabelText("Filter by sentiment"), { target: { value: "negative" } });
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULTS, sentiment: "negative" });
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
  });

  it("custom period shows from/to inputs and applies only when both dates are valid", () => {
    const { onChange } = setup();
    fireEvent.change(screen.getByLabelText("Filter by period"), { target: { value: "custom" } });
    expect(onChange).not.toHaveBeenCalled();
    const from = screen.getByLabelText("From date");
    const to = screen.getByLabelText("To date");

    fireEvent.change(from, { target: { value: "2026-01-01" } });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(to, { target: { value: "2025-12-01" } });
    expect(screen.getByText("End date must be after start date.")).toBeTruthy();
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(to, { target: { value: "2027-06-01" } });
    expect(screen.getByText("Range cannot exceed 365 days.")).toBeTruthy();
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(to, { target: { value: "2026-02-01" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULTS,
      range: "custom",
      date_from: "2026-01-01",
      date_to: "2026-02-01",
    });
  });

  it("Reset link appears only when filters differ from 30d/all/all and restores them", () => {
    const first = render(
      <FilterBar filters={DEFAULTS} onChange={vi.fn()} sortKey="total_reviews" sortDir="desc" onSort={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /reset/i })).toBeNull();
    first.unmount();
    const { onChange } = setup({ ...DEFAULTS, sentiment: "positive" });
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onChange).toHaveBeenCalledWith(DEFAULTS);
  });

  it("sort links call onSort", () => {
    const { onSort } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Avg Rating" }));
    expect(onSort).toHaveBeenCalledWith("avg_rating");
  });

  it("re-selecting Custom after a preset shows empty date boxes and fires nothing", () => {
    const { onChange } = setup();
    const period = screen.getByLabelText("Filter by period");
    fireEvent.change(period, { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-11-13" } });
    expect(onChange).toHaveBeenCalledTimes(1);
    fireEvent.change(period, { target: { value: "7d" } });
    expect(onChange).toHaveBeenCalledTimes(2);
    fireEvent.change(period, { target: { value: "custom" } });
    expect(onChange).toHaveBeenCalledTimes(2);
    expect((screen.getByLabelText("From date") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("To date") as HTMLInputElement).value).toBe("");
  });
});
