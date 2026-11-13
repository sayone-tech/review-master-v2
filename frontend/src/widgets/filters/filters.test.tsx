import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Star } from "lucide-react";
import { FilterChips, FilterSearch, FilterSelect, MoreFiltersPanel, formatDateChip } from "./index";

describe("FilterSelect", () => {
  it("shows the selected label and calls onChange with undefined for the placeholder", async () => {
    const onChange = vi.fn();
    render(
      <FilterSelect<number>
        icon={Star}
        ariaLabel="Rating"
        placeholder="Any rating"
        value={4}
        options={[
          { value: 4, label: "4 stars" },
          { value: 5, label: "5 stars" },
        ]}
        onChange={onChange}
      />,
    );
    const select = screen.getByLabelText("Rating") as HTMLSelectElement;
    expect(select.selectedOptions[0].textContent).toBe("4 stars");
    await userEvent.selectOptions(select, "Any rating");
    expect(onChange).toHaveBeenLastCalledWith(undefined);
    await userEvent.selectOptions(select, "5 stars");
    expect(onChange).toHaveBeenLastCalledWith(5);
  });
});

describe("FilterSearch", () => {
  it("calls onChange per keystroke and onSubmit on Enter", async () => {
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    render(<FilterSearch value="" placeholder="Search" ariaLabel="Search reviews" onChange={onChange} onSubmit={onSubmit} />);
    const input = screen.getByLabelText("Search reviews");
    await userEvent.type(input, "ab");
    expect(onChange).toHaveBeenCalledTimes(2);
    await userEvent.type(input, "{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});

function Harness({
  applied = "a",
  activeCount = 0,
  onApply = () => {},
  onReset = () => {},
  onChildKey,
}: {
  applied?: string;
  activeCount?: number;
  onApply?: (d: string) => void;
  onReset?: () => void;
  onChildKey?: (e: React.KeyboardEvent) => void;
}) {
  return (
    <div>
      <div data-testid="outside">outside</div><input aria-label="outside input" />
      <MoreFiltersPanel<string> applied={applied} activeCount={activeCount} onApply={onApply} onReset={onReset}>
        {(draft, setDraft) => (
          <input aria-label="draft" value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onChildKey} />
        )}
      </MoreFiltersPanel>
    </div>
  );
}

describe("MoreFiltersPanel", () => {
  it("shows a badge only when activeCount > 0", () => {
    const { rerender } = render(<Harness activeCount={0} />);
    expect(screen.queryByTestId("more-filters-badge")).toBeNull();
    rerender(<Harness activeCount={2} />);
    expect(screen.getByTestId("more-filters-badge").textContent).toBe("2");
  });

  it("initialises the draft from applied on every open", async () => {
    const { rerender } = render(<Harness applied="a" />);
    const btn = screen.getByRole("button", { name: /more filters/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(btn);
    expect(screen.getByRole("dialog", { name: "More filters" })).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-expanded", "true");
    await userEvent.clear(screen.getByLabelText("draft"));
    await userEvent.type(screen.getByLabelText("draft"), "zzz");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    rerender(<Harness applied="b" />);
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    expect((screen.getByLabelText("draft") as HTMLInputElement).value).toBe("b");
  });

  it("Apply calls onApply with the draft and closes; Reset calls onReset and closes", async () => {
    const onApply = vi.fn();
    const onReset = vi.fn();
    render(<Harness onApply={onApply} onReset={onReset} />);
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.type(screen.getByLabelText("draft"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith("ax");
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape and outside click discard the draft and return focus to the button", async () => {
    const onApply = vi.fn();
    render(<Harness onApply={onApply} />);
    const btn = screen.getByRole("button", { name: /more filters/i });
    await userEvent.click(btn);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(btn).toHaveFocus();
    await userEvent.click(btn);
    await userEvent.click(screen.getByTestId("outside"));
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(btn).toHaveFocus());
    expect(onApply).not.toHaveBeenCalled();
  });

  it("outside click discards the draft; reopening shows the applied value", async () => {
    render(<Harness applied="a" />);
    const btn = screen.getByRole("button", { name: /more filters/i });
    await userEvent.click(btn);
    await userEvent.type(screen.getByLabelText("draft"), "zzz");
    await userEvent.click(screen.getByTestId("outside"));
    await userEvent.click(btn);
    expect((screen.getByLabelText("draft") as HTMLInputElement).value).toBe("a");
  });

  it("clicking an outside input leaves focus in that input", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    const input = screen.getByLabelText("outside input");
    await userEvent.click(input);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(input).toHaveFocus();
  });

  it("Apply and Reset return focus to the button", async () => {
    render(<Harness />);
    const btn = screen.getByRole("button", { name: /more filters/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(btn).toHaveFocus();
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(btn).toHaveFocus();
  });

  it("ignores an Escape already handled by a nested listbox", async () => {
    render(<Harness onChildKey={(e) => e.key === "Escape" && e.preventDefault()} />);
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    fireEvent.keyDown(screen.getByLabelText("draft"), { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("treats clicks inside data-filter-popover elements as inside", async () => {
    function WithPortal() {
      const [v, setV] = useState("");
      return (
        <>
          <MoreFiltersPanel<string> applied="" activeCount={0} onApply={() => {}} onReset={() => {}}>
            {() => <span>{v}</span>}
          </MoreFiltersPanel>
          <div data-filter-popover>
            <button onClick={() => setV("hit")}>portal item</button>
          </div>
        </>
      );
    }
    render(<WithPortal />);
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.click(screen.getByRole("button", { name: "portal item" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("FilterChips", () => {
  it("renders nothing with no chips; x calls onRemove; Clear all calls onClearAll", async () => {
    const { container, rerender } = render(<FilterChips chips={[]} onClearAll={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    const onRemove = vi.fn();
    const onClearAll = vi.fn();
    rerender(<FilterChips chips={[{ key: "r", label: "Not replied", onRemove }]} onClearAll={onClearAll} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove filter: Not replied" }));
    expect(onRemove).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onClearAll).toHaveBeenCalledTimes(1);
  });
});

describe("formatDateChip", () => {
  it("formats the four cases", () => {
    expect(formatDateChip("2026-11-01", "2026-11-13")).toBe("Date: 1 Nov – 13 Nov");
    expect(formatDateChip("2026-11-01", undefined)).toBe("From 1 Nov");
    expect(formatDateChip(undefined, "2026-11-13")).toBe("Until 13 Nov");
    expect(formatDateChip(undefined, undefined)).toBeNull();
  });
});
