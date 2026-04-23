import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import type { OrgRow } from "./types";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    deleteOrg: vi.fn(),
  };
});

import { ApiError, deleteOrg } from "./api";

const ORG: OrgRow = {
  id: 42,
  name: "Acme Corp",
  org_type: "RETAIL",
  email: "ops@acme.com",
  address: "",
  number_of_stores: 5,
  status: "ACTIVE",
  created_at: "2026-04-22T10:00:00Z",
  total_stores: 0,
  active_stores: 0,
  activation_status: "pending",
  last_invited_at: null,
};

function captureToasts() {
  const events: CustomEvent[] = [];
  const handler = (e: Event) => events.push(e as CustomEvent);
  window.addEventListener("app:toast", handler);
  return {
    events,
    cleanup: () => window.removeEventListener("app:toast", handler),
  };
}

describe("DeleteConfirmModal", () => {
  beforeEach(() => {
    vi.mocked(deleteOrg).mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("confirm button is disabled until org name is typed", () => {
    render(<DeleteConfirmModal org={ORG} onClose={vi.fn()} onDone={vi.fn()} />);
    const confirm = screen.getByTestId("confirm-confirm");
    expect(confirm).toBeDisabled();
  });

  it("typing the exact org name enables the confirm button", async () => {
    render(<DeleteConfirmModal org={ORG} onClose={vi.fn()} onDone={vi.fn()} />);
    await userEvent.type(screen.getByTestId("type-to-confirm-input"), ORG.name);
    expect(screen.getByTestId("confirm-confirm")).toBeEnabled();
  });

  it("on confirm, calls deleteOrg(id) and emits success toast then onDone", async () => {
    vi.mocked(deleteOrg).mockResolvedValue(undefined);
    const onClose = vi.fn();
    const onDone = vi.fn();
    const toasts = captureToasts();

    render(<DeleteConfirmModal org={ORG} onClose={onClose} onDone={onDone} />);
    await userEvent.type(screen.getByTestId("type-to-confirm-input"), ORG.name);
    await userEvent.click(screen.getByTestId("confirm-confirm"));

    await waitFor(() => expect(deleteOrg).toHaveBeenCalledWith(ORG.id));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(
      toasts.events.some(
        (e) =>
          (e.detail as { kind: string }).kind === "success" &&
          (e.detail as { title: string }).title === "Acme Corp has been deleted.",
      ),
    ).toBe(true);
    toasts.cleanup();
  });

  it("on API error, emits generic error toast and does NOT call onDone", async () => {
    vi.mocked(deleteOrg).mockRejectedValue(new ApiError(500, {}, "boom"));
    const onClose = vi.fn();
    const onDone = vi.fn();
    const toasts = captureToasts();

    render(<DeleteConfirmModal org={ORG} onClose={onClose} onDone={onDone} />);
    await userEvent.type(screen.getByTestId("type-to-confirm-input"), ORG.name);
    await userEvent.click(screen.getByTestId("confirm-confirm"));

    await waitFor(() => expect(deleteOrg).toHaveBeenCalledTimes(1));
    expect(onDone).not.toHaveBeenCalled();
    expect(
      toasts.events.some(
        (e) =>
          (e.detail as { kind: string }).kind === "error" &&
          (e.detail as { title: string }).title === "Something went wrong.",
      ),
    ).toBe(true);
    toasts.cleanup();
  });
});
