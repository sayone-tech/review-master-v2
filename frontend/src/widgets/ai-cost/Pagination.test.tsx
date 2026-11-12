import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Pagination, buildPageRange } from "./Pagination";

describe("Pagination", () => {
  it("shows the range, marks the current page and wires the controls", () => {
    const onPage = vi.fn();
    const onPageSize = vi.fn();
    render(<Pagination page={2} pageSize={10} count={45} onPage={onPage} onPageSize={onPageSize} />);
    expect(screen.getByText(/Showing/)).toHaveTextContent("Showing 11–20 of 45");
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPage).toHaveBeenCalledWith(3);
    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onPage).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByRole("button", { name: "5" }));
    expect(onPage).toHaveBeenCalledWith(5);
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "50" } });
    expect(onPageSize).toHaveBeenCalledWith(50);
  });

  it("disables previous on the first page and next on the last", () => {
    const { rerender } = render(
      <Pagination page={1} pageSize={25} count={30} onPage={vi.fn()} onPageSize={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    rerender(<Pagination page={2} pageSize={25} count={30} onPage={vi.fn()} onPageSize={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("collapses long ranges with ellipses", () => {
    expect(buildPageRange(10, 20)).toEqual([1, "…", 9, 10, 11, "…", 20]);
  });
});
