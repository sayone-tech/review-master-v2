import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OrgTable } from "./OrgTable";
import type { OrgRow } from "./types";

/** SA-090: force useIsMobile() to report mobile by stubbing matchMedia. */
function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        onchange: null,
      }) as unknown as MediaQueryList,
  );
}

const BASE_ROW: OrgRow = {
  id: 1,
  name: "Acme",
  org_type: "RETAIL",
  email: "a@b.com",
  address: "",
  number_of_stores: 10,
  status: "ACTIVE",
  created_at: "2026-04-22T10:00:00Z",
  total_stores: 10,
  active_stores: 0,
  activation_status: "pending",
  last_invited_at: "2026-04-22T10:00:00Z",
  allow_custom_sync_depth: false,
};

function noopHandlers() {
  return {
    onOpenView: vi.fn(),
    onOpenEdit: vi.fn(),
    onOpenResend: vi.fn(),
    onOpenAdjustStores: vi.fn(),
    onOpenEnable: vi.fn(),
    onOpenDisable: vi.fn(),
    onOpenDelete: vi.fn(),
  };
}

describe("OrgTable", () => {
  it("renders 6 data columns plus auto-emitted Actions column header (aria-labelled)", () => {
    render(<OrgTable rows={[BASE_ROW]} loading={false} handlers={noopHandlers()} />);
    // 6 data columns — all have visible text in the thead
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Stores")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Created")).toBeInTheDocument();
    // Actions column — auto-emitted by DataTable when renderRowActions is passed;
    // the <th> has no visible text, only aria-label="Actions" (ORGL-02).
    expect(screen.getByLabelText("Actions")).toBeInTheDocument();
    // Row content smoke-check
    expect(screen.getByText("0 used of 10 allocated")).toBeInTheDocument();
  });

  it("clicking the name column calls onOpenView", async () => {
    const h = noopHandlers();
    render(<OrgTable rows={[BASE_ROW]} loading={false} handlers={h} />);
    await userEvent.click(screen.getByRole("button", { name: /view details for Acme/i }));
    expect(h.onOpenView).toHaveBeenCalledWith(BASE_ROW);
  });

  it("row action menu shows Resend when activation_status is pending", async () => {
    const h = noopHandlers();
    render(<OrgTable rows={[BASE_ROW]} loading={false} handlers={h} />);
    await userEvent.click(screen.getByTestId("row-actions-trigger-1"));
    const menu = screen.getByTestId("row-actions-menu-1");
    expect(within(menu).getByText("Resend Invitation")).toBeInTheDocument();
    expect(within(menu).getByText("Disable")).toBeInTheDocument();
    expect(within(menu).queryByText("Enable")).not.toBeInTheDocument();
  });

  it("row action menu shows Enable instead of Disable when status=DISABLED", async () => {
    const row: OrgRow = { ...BASE_ROW, id: 2, status: "DISABLED" };
    render(<OrgTable rows={[row]} loading={false} handlers={noopHandlers()} />);
    await userEvent.click(screen.getByTestId("row-actions-trigger-2"));
    const menu = screen.getByTestId("row-actions-menu-2");
    expect(within(menu).getByText("Enable")).toBeInTheDocument();
    expect(within(menu).queryByText("Disable")).not.toBeInTheDocument();
  });

  it("row action menu hides Resend when activation_status is active", async () => {
    const row: OrgRow = { ...BASE_ROW, id: 3, activation_status: "active" };
    render(<OrgTable rows={[row]} loading={false} handlers={noopHandlers()} />);
    await userEvent.click(screen.getByTestId("row-actions-trigger-3"));
    const menu = screen.getByTestId("row-actions-menu-3");
    expect(within(menu).queryByText("Resend Invitation")).not.toBeInTheDocument();
  });
});

describe("OrgTable — mobile card layout (SA-090)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a stacked card list instead of a table below the md breakpoint", () => {
    mockMatchMedia(true);
    render(<OrgTable rows={[BASE_ROW]} loading={false} handlers={noopHandlers()} />);
    // Card list present, table absent — no horizontal-scroll table on mobile.
    expect(screen.getByTestId("org-card-list")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const card = screen.getByTestId("org-card-1");
    expect(within(card).getByText("Acme")).toBeInTheDocument();
    expect(within(card).getByText("0 used of 10 allocated")).toBeInTheDocument();
  });

  it("card name button calls onOpenView", async () => {
    mockMatchMedia(true);
    const h = noopHandlers();
    render(<OrgTable rows={[BASE_ROW]} loading={false} handlers={h} />);
    await userEvent.click(screen.getByRole("button", { name: /view details for Acme/i }));
    expect(h.onOpenView).toHaveBeenCalledWith(BASE_ROW);
  });

  it("shows the empty state as a card when there are no rows", () => {
    mockMatchMedia(true);
    render(<OrgTable rows={[]} loading={false} handlers={noopHandlers()} />);
    expect(screen.getByTestId("org-card-list-empty")).toBeInTheDocument();
  });
});
