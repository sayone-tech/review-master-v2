import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewFilters } from "./ReviewFilters";
import type { ReviewFilterParams } from "./types";

const shops = [
  { id: 3, name: "Downtown" },
  { id: 4, name: "Uptown" },
] as never;
const tags = [
  { label: "Slow service", count: 4 },
  { label: "Great food", count: 9 },
];

function setup(filters: ReviewFilterParams = { page: 2 }) {
  const onChange = vi.fn();
  const utils = render(<ReviewFilters shops={shops} filters={filters} availableTags={tags} onChange={onChange} />);
  return { onChange, ...utils };
}

describe("ReviewFilters", () => {
  it("changing Store applies immediately with page 1", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByLabelText("Filter by store"), "Downtown");
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ page: 1, shop: 3 });
  });

  it("panel Apply sends tags, from/to date, is_replied and has_comment together", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.click(screen.getByRole("combobox", { name: "Filter by tag" }));
    await userEvent.type(screen.getByLabelText("Search tags"), "slow");
    await userEvent.click(screen.getByRole("option", { name: /Slow service/ }));
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-01-02" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-01-09" } });
    await userEvent.selectOptions(screen.getByLabelText("Filter by reply status"), "Not replied");
    await userEvent.selectOptions(screen.getByLabelText("Filter by comment presence"), "With comment");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onChange).toHaveBeenCalledWith({
      page: 1,
      tags: ["Slow service"],
      from_date: "2026-01-02",
      to_date: "2026-01-09",
      is_replied: false,
      has_comment: true,
    });
  });

  it("chips show Not replied, each tag, and the date chip; x removes just that filter", async () => {
    const filters = { is_replied: false, tags: ["A", "B"], from_date: "2026-01-02", to_date: "2026-01-09", shop: 3 };
    const { onChange } = setup(filters);
    expect(screen.getByText("Not replied")).toBeTruthy();
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
    expect(screen.getByText("Date: 2 Jan – 9 Jan")).toBeTruthy();
    await userEvent.click(screen.getByLabelText("Remove filter: A"));
    expect(onChange).toHaveBeenLastCalledWith({ ...filters, tags: ["B"], page: 1 });
    await userEvent.click(screen.getByLabelText("Remove filter: Not replied"));
    expect(onChange).toHaveBeenLastCalledWith({ ...filters, is_replied: undefined, page: 1 });
  });

  it("Clear all resets every filter including search", async () => {
    const { onChange } = setup({ search: "pizza", shop: 3, rating: 4, tags: ["A"], is_replied: true, page: 3 });
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onChange).toHaveBeenCalledWith({ page: 1 });
    expect((screen.getByLabelText("Search reviews") as HTMLInputElement).value).toBe("");
  });

  it("Enter applies the typed search immediately", () => {
    vi.useFakeTimers();
    try {
      const { onChange } = setup({});
      const input = screen.getByLabelText("Search reviews");
      fireEvent.change(input, { target: { value: "pizza" } });
      fireEvent.keyDown(input, { key: "Enter" });
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({ search: "pizza", page: 1 });
      vi.advanceTimersByTime(500);
      expect(onChange).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a Store change mid-debounce makes one onChange containing both", () => {
    vi.useFakeTimers();
    try {
      const { onChange } = setup({});
      fireEvent.change(screen.getByLabelText("Search reviews"), { target: { value: "pi" } });
      fireEvent.change(screen.getByLabelText("Filter by store"), { target: { value: "3" } });
      vi.advanceTimersByTime(500);
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({ search: "pi", shop: 3, page: 1 });
    } finally {
      vi.useRealTimers();
    }
  });

  it("an external search reset cancels a pending debounced search", () => {
    vi.useFakeTimers();
    try {
      const onChange = vi.fn();
      const { rerender } = render(
        <ReviewFilters shops={shops} filters={{ search: "old" }} availableTags={tags} onChange={onChange} />,
      );
      fireEvent.change(screen.getByLabelText("Search reviews"), { target: { value: "oldx" } });
      rerender(<ReviewFilters shops={shops} filters={{}} availableTags={tags} onChange={onChange} />);
      vi.advanceTimersByTime(500);
      expect(onChange).not.toHaveBeenCalled();
      expect((screen.getByLabelText("Search reviews") as HTMLInputElement).value).toBe("");
    } finally {
      vi.useRealTimers();
    }
  });

  it("opening the panel after an external tag filter shows that tag selected", async () => {
    setup({ tags: ["Slow service"] });
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    expect(screen.getByRole("combobox", { name: "Filter by tag" }).textContent).toContain("Slow service");
  });

  it("Escape with the tag list open closes only the tag list", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.click(screen.getByRole("combobox", { name: "Filter by tag" }));
    expect(screen.getByRole("listbox")).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("dialog", { name: "More filters" })).toBeTruthy();
  });

  it("clearing the search box applies immediately", async () => {
    const { onChange } = setup({ search: "pizza", page: 2 });
    await userEvent.clear(screen.getByLabelText("Search reviews"));
    expect(onChange).toHaveBeenCalledWith({ search: undefined, page: 1 });
  });

  it("typing in search applies after the debounce", () => {
    vi.useFakeTimers();
    try {
      const { onChange } = setup({});
      fireEvent.change(screen.getByLabelText("Search reviews"), { target: { value: "pi" } });
      expect(onChange).not.toHaveBeenCalled();
      vi.advanceTimersByTime(300);
      expect(onChange).toHaveBeenCalledWith({ search: "pi", page: 1 });
    } finally {
      vi.useRealTimers();
    }
  });
});
