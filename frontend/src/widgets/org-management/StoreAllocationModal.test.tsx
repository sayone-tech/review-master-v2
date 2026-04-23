import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreAllocationModal } from "./StoreAllocationModal";
import type { OrgRow } from "./types";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return { ...actual, updateOrg: vi.fn() };
});

import { updateOrg } from "./api";

const ORG: OrgRow = {
  id: 7,
  name: "Acme Corp",
  org_type: "RETAIL",
  email: "a@acme.com",
  address: "",
  number_of_stores: 10,
  status: "ACTIVE",
  created_at: "2026-04-22T10:00:00Z",
  total_stores: 10,
  active_stores: 6,
  activation_status: "active",
  last_invited_at: null,
};

function captureToasts() {
  const events: CustomEvent[] = [];
  const handler = (e: Event) => events.push(e as CustomEvent);
  window.addEventListener("app:toast", handler);
  return { events, cleanup: () => window.removeEventListener("app:toast", handler) };
}

describe("StoreAllocationModal", () => {
  beforeEach(() => {
    vi.mocked(updateOrg).mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders 'Currently using X of Y stores.' helper with correct values", () => {
    render(<StoreAllocationModal org={ORG} onClose={vi.fn()} onDone={vi.fn()} />);
    const helper = screen.getByText(/Currently using/);
    expect(helper.textContent).toContain("6");
    expect(helper.textContent).toContain("10");
    expect(helper.textContent).toContain("stores");
  });

  it("Update disabled and amber warning shows when value < active_stores", async () => {
    render(<StoreAllocationModal org={ORG} onClose={vi.fn()} onDone={vi.fn()} />);
    const input = screen.getByTestId("store-alloc-input");
    await userEvent.clear(input);
    await userEvent.type(input, "3");
    expect(screen.getByTestId("store-alloc-update")).toBeDisabled();
    const warning = screen.getByTestId("store-alloc-warning");
    expect(warning.textContent).toContain("Value cannot be lower than current usage (6 stores).");
  });

  it("clicking Update transitions to confirm step with old/new values", async () => {
    render(<StoreAllocationModal org={ORG} onClose={vi.fn()} onDone={vi.fn()} />);
    const input = screen.getByTestId("store-alloc-input");
    await userEvent.clear(input);
    await userEvent.type(input, "15");
    await userEvent.click(screen.getByTestId("store-alloc-update"));
    const confirmDialog = await screen.findByText(/Change store allocation for/);
    expect(confirmDialog.textContent).toContain("Acme Corp");
    expect(confirmDialog.textContent).toContain("10");
    expect(confirmDialog.textContent).toContain("15");
  });

  it("confirming calls updateOrg({number_of_stores}) and emits success toast + onDone", async () => {
    vi.mocked(updateOrg).mockResolvedValue({ ...ORG, number_of_stores: 15 });
    const onDone = vi.fn();
    const onClose = vi.fn();
    const toasts = captureToasts();

    render(<StoreAllocationModal org={ORG} onClose={onClose} onDone={onDone} />);
    const input = screen.getByTestId("store-alloc-input");
    await userEvent.clear(input);
    await userEvent.type(input, "15");
    await userEvent.click(screen.getByTestId("store-alloc-update"));
    await userEvent.click(screen.getByTestId("confirm-confirm"));

    await waitFor(() => expect(updateOrg).toHaveBeenCalledWith(7, { number_of_stores: 15 }));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(
      toasts.events.some(
        (e) =>
          (e.detail as { kind: string; title: string }).title ===
          "Store allocation updated to 15.",
      ),
    ).toBe(true);
    toasts.cleanup();
  });
});
