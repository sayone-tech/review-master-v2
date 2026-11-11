import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ViewOrgModal } from "./ViewOrgModal";
import type { OrgRow } from "./types";

const BASE: OrgRow = {
  id: 7,
  name: "Acme",
  org_type: "RETAIL",
  email: "a@acme.com",
  address: "",
  number_of_stores: 10,
  status: "ACTIVE",
  created_at: "2026-04-22T10:00:00Z",
  total_stores: 10,
  active_stores: 2,
  activation_status: "active",
  last_invited_at: null,
  allow_custom_sync_depth: false,
  monthly_credit_allocation: 100,
  current_month_credit_allocation: 100,
};

function renderView(over: Partial<OrgRow>) {
  render(<ViewOrgModal org={{ ...BASE, ...over }} onClose={vi.fn()} onEdit={vi.fn()} onResend={vi.fn()} />);
}

describe("ViewOrgModal monthly credits", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-15T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("should show the allocation with no pending pill when this month matches", () => {
    renderView({ monthly_credit_allocation: 100, current_month_credit_allocation: 100 });
    expect(screen.getByText("Monthly credits per shop")).toBeInTheDocument();
    expect(screen.getByText(/^100 credits/)).toBeInTheDocument();
    expect(screen.queryByTestId("view-credit-pending")).not.toBeInTheDocument();
  });

  it("should use the singular for one credit", () => {
    renderView({ monthly_credit_allocation: 1, current_month_credit_allocation: 1 });
    expect(screen.getByText(/^1 credit$/)).toBeInTheDocument();
  });

  it("should say AI replies are disabled when the allocation is 0 and nothing is pending", () => {
    renderView({ monthly_credit_allocation: 0, current_month_credit_allocation: 0 });
    expect(screen.getByText(/Off — AI replies are disabled/)).toBeInTheDocument();
    expect(screen.queryByTestId("view-credit-pending")).not.toBeInTheDocument();
  });

  it("should show a pending pill when a decrease takes effect next month", () => {
    renderView({ monthly_credit_allocation: 50, current_month_credit_allocation: 100 });
    expect(screen.getByTestId("view-credit-pending")).toHaveTextContent(
      "This month: 100 (changes to 50 on 1 Dec 2026)",
    );
  });

  it("should show a turns-off pill when the saved allocation is 0 but this month still has credits", () => {
    renderView({ monthly_credit_allocation: 0, current_month_credit_allocation: 100 });
    expect(screen.getByTestId("view-credit-pending")).toHaveTextContent(
      "This month: 100 (turns off on 1 Dec 2026)",
    );
  });
});
