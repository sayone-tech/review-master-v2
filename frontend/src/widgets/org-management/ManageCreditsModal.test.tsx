import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManageCreditsModal } from "./ManageCreditsModal";
import type { CreditShopListResponse, CreditShopRow } from "./creditsApi";
import type { OrgRow } from "./types";

const ORG: OrgRow = {
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

const ALPHA: CreditShopRow = {
  id: 11,
  name: "Alpha",
  allocated: 100,
  bonus: 20,
  consumed: 85,
  remaining: 35,
  is_materialized: true,
};
const BRAVO: CreditShopRow = {
  id: 12,
  name: "Bravo",
  allocated: 100,
  bonus: 0,
  consumed: 0,
  remaining: 100,
  is_materialized: false,
};

function listBody(
  results: CreditShopRow[],
  extra: Partial<CreditShopListResponse> = {},
): CreditShopListResponse {
  return {
    count: results.length,
    next: null,
    previous: null,
    period: { year: 2026, month: 11 },
    allocation_per_shop: 100,
    results,
    ...extra,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function captureToasts() {
  const events: CustomEvent[] = [];
  const handler = (e: Event) => events.push(e as CustomEvent);
  window.addEventListener("app:toast", handler);
  return {
    events,
    titles: () => events.map((e) => (e.detail as { title: string }).title),
    cleanup: () => window.removeEventListener("app:toast", handler),
  };
}

describe("ManageCreditsModal", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let toasts: ReturnType<typeof captureToasts>;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-15T12:00:00Z"));
    document.cookie = "csrftoken=tok123";
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    toasts = captureToasts();
  });
  afterEach(() => {
    toasts.cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("allocates bonus credits to a shop and returns to the refreshed list", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(listBody([ALPHA, BRAVO])));
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);

    const alphaRow = await screen.findByTestId("credits-row-11");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/superadmin/organisations/7/credits/shops/?page=1");
    expect(screen.getByText("Acme — November 2026 · 100 credits per shop")).toBeInTheDocument();
    expect(alphaRow).toHaveTextContent("Remaining 35");
    expect(alphaRow).toHaveTextContent("Monthly 100 · Bonus 20 · Used 85");

    await userEvent.click(within(alphaRow).getByRole("button", { name: "Add bonus credits for Alpha" }));
    expect(screen.getByText("Add Bonus Credits")).toBeInTheDocument();
    // Bonus view opens from the loaded row: no extra request.
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getByTestId("credits-amount"), "50");
    expect(screen.getByTestId("credits-preview")).toHaveTextContent("Remaining 35 → 85 · Bonus 20 → 70");

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          shop_id: 11,
          period: { year: 2026, month: 11 },
          allocated: 100,
          bonus: 70,
          consumed: 85,
          remaining: 85,
          transaction_id: 99,
        },
        201,
      ),
    );
    fetchMock.mockResolvedValueOnce(
      jsonResponse(listBody([{ ...ALPHA, bonus: 70, remaining: 85 }, BRAVO])),
    );
    await userEvent.click(screen.getByTestId("credits-allocate"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const [postUrl, postInit] = fetchMock.mock.calls[1];
    expect(postUrl).toBe("/api/v1/superadmin/shops/11/credits/bonus/");
    expect(postInit.method).toBe("POST");
    expect(postInit.headers["X-CSRFToken"]).toBe("tok123");
    expect(JSON.parse(postInit.body)).toEqual({ amount: 50, period_year: 2026, period_month: 11 });
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/superadmin/organisations/7/credits/shops/?page=1");

    expect(toasts.titles()).toContain("Added 50 credits to Alpha.");
    const refreshed = await screen.findByTestId("credits-row-11");
    await waitFor(() => expect(refreshed).toHaveTextContent("Remaining 85"));
    expect(screen.getByText("Manage Credits")).toBeInTheDocument();
  });
});
