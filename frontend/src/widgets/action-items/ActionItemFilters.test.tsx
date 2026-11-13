import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ActionItemFilters } from "./ActionItemFilters";
import type { ListParams, UserRole } from "./types";

const base: ListParams = { page: 1, page_size: 25, ordering: "-created_at" };

function setup(over: Partial<ListParams> = {}, userRole: UserRole = "ORG_ADMIN", search = "") {
  const onChange = vi.fn();
  const onClearAll = vi.fn();
  const onSearchChange = vi.fn();
  render(
    <ActionItemFilters
      userRole={userRole}
      shops={[{ id: 1, name: "Main" }] as never}
      teamMembers={[{ id: 7, full_name: "Ann" }] as never}
      filters={{ ...base, ...over }}
      searchInput={search}
      onSearchChange={onSearchChange}
      onChange={onChange}
      onClearAll={onClearAll}
    />,
  );
  return { onChange, onClearAll, onSearchChange };
}

describe("ActionItemFilters", () => {
  it("Status and Assignee apply immediately", async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "TODO");
    expect(onChange).toHaveBeenLastCalledWith({ status: "TODO" });
    await userEvent.selectOptions(screen.getByLabelText("Filter by assignee"), "unassigned");
    expect(onChange).toHaveBeenLastCalledWith({ assignee: "unassigned" });
  });

  it("panel offers Scope, Category and Date range for Org Admin", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    const dlg = screen.getByRole("dialog");
    expect(within(dlg).getByLabelText("Filter by scope")).toBeTruthy();
    expect(within(dlg).getByLabelText("Filter by category")).toBeTruthy();
    expect(within(dlg).getByLabelText("From date")).toBeTruthy();
    expect(within(dlg).getByLabelText("To date")).toBeTruthy();
  });

  it("panel offers only Category and Date range for Staff and no Scope chip ever renders", async () => {
    setup({ scope: "BRAND", category: "SERVICE" }, "STAFF_ADMIN");
    expect(screen.queryByText(/scope/i)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    const dlg = screen.getByRole("dialog");
    expect(within(dlg).queryByLabelText("Filter by scope")).toBeNull();
    expect(within(dlg).getByLabelText("Filter by category")).toBeTruthy();
    expect(within(dlg).getByLabelText("From date")).toBeTruthy();
  });

  it("chips show Category and the date chip; Clear all resets to defaults", async () => {
    const { onChange, onClearAll } = setup({
      category: "SERVICE",
      from_date: "2026-11-01",
      to_date: "2026-11-13",
    });
    expect(screen.getByText("Category: Service")).toBeTruthy();
    expect(screen.getByText("Date: 1 Nov – 13 Nov")).toBeTruthy();
    expect(screen.getByTestId("more-filters-badge").textContent).toBe("2");
    await userEvent.click(screen.getByRole("button", { name: "Remove filter: Date: 1 Nov – 13 Nov" }));
    expect(onChange).toHaveBeenLastCalledWith({ from_date: undefined, to_date: undefined });
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onClearAll).toHaveBeenCalledTimes(1);
  });

  it("panel Reset clears only panel filters", async () => {
    const { onChange } = setup({ category: "SERVICE", status: "TODO" });
    await userEvent.click(screen.getByRole("button", { name: /more filters/i }));
    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(onChange).toHaveBeenLastCalledWith({
      scope: undefined,
      category: undefined,
      from_date: undefined,
      to_date: undefined,
    });
  });

  it("clearing the search box applies immediately", async () => {
    const { onChange, onSearchChange } = setup({ search: "x" }, "ORG_ADMIN", "x");
    await userEvent.clear(screen.getByLabelText("Search action items"));
    expect(onSearchChange).toHaveBeenLastCalledWith("");
    expect(onChange).toHaveBeenLastCalledWith({ search: undefined });
  });

  it("folds a typed-but-unapplied search into another change (one call with both)", async () => {
    const { onChange } = setup({}, "ORG_ADMIN", "pizza");
    await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "TODO");
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ status: "TODO", search: "pizza" });
  });

  it("does not add search when it is already applied", async () => {
    const { onChange } = setup({ search: "pizza" }, "ORG_ADMIN", "pizza");
    await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "TODO");
    expect(onChange).toHaveBeenCalledWith({ status: "TODO" });
  });
});
