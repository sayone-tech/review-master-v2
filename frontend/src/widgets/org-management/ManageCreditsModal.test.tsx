import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
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

type Factory = () => Response | Promise<Response>;

function shop(id: number, name: string, over: Partial<CreditShopRow> = {}): CreditShopRow {
  return { id, name, allocated: 100, bonus: 0, consumed: 0, remaining: 100, is_materialized: false, ...over };
}

describe("ManageCreditsModal", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let toasts: ReturnType<typeof captureToasts>;
  let user: ReturnType<typeof userEvent.setup>;
  let lists: Factory[];
  let posts: Factory[];

  const listCalls = () => fetchMock.mock.calls.filter((c) => String(c[0]).includes("/credits/shops/"));
  const postCalls = () => fetchMock.mock.calls.filter((c) => String(c[0]).includes("/credits/bonus/"));
  // Each queue repeats its last entry once exhausted.
  const take = (q: Factory[]) => (q.length > 1 ? q.shift()! : q[0])();

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-11-15T12:00:00Z"));
    user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    document.cookie = "csrftoken=tok123";
    lists = [() => jsonResponse(listBody([ALPHA, BRAVO]))];
    posts = [];
    fetchMock = vi.fn((url: string) =>
      Promise.resolve(String(url).includes("/credits/bonus/") ? take(posts) : take(lists)),
    );
    vi.stubGlobal("fetch", fetchMock);
    toasts = captureToasts();
  });
  afterEach(() => {
    toasts.cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const okPost = (over: object = {}) => () =>
    jsonResponse(
      { shop_id: 11, period: { year: 2026, month: 11 }, allocated: 100, bonus: 70, consumed: 85, remaining: 85, transaction_id: 9, ...over },
      201,
    );

  async function openBonusFor(id: number, name: string) {
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    const row = await screen.findByTestId(`credits-row-${id}`);
    await user.click(within(row).getByRole("button", { name: `Add bonus credits for ${name}` }));
  }

  it("should allocate bonus credits to a shop and return to the refreshed list", async () => {
    lists = [
      () => jsonResponse(listBody([ALPHA, BRAVO])),
      () => jsonResponse(listBody([{ ...ALPHA, bonus: 70, remaining: 85 }, BRAVO])),
    ];
    posts = [okPost()];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);

    const alphaRow = await screen.findByTestId("credits-row-11");
    expect(listCalls()[0][0]).toBe("/api/v1/superadmin/organisations/7/credits/shops/?page=1");
    expect(screen.getByText("Acme — November 2026 · 100 credits per shop")).toBeInTheDocument();
    expect(alphaRow).toHaveTextContent("Remaining 35");
    expect(alphaRow).toHaveTextContent("Monthly 100 · Bonus 20 · Used 85");

    await user.click(within(alphaRow).getByRole("button", { name: "Add bonus credits for Alpha" }));
    expect(screen.getByText("Add Bonus Credits")).toBeInTheDocument();
    expect(listCalls()).toHaveLength(1);

    await user.type(screen.getByTestId("credits-amount"), "50");
    expect(screen.getByTestId("credits-preview")).toHaveTextContent("Remaining 35 → 85 · Bonus 20 → 70");
    await user.click(screen.getByTestId("credits-allocate"));

    await waitFor(() => expect(listCalls()).toHaveLength(2));
    const [postUrl, postInit] = postCalls()[0];
    expect(postUrl).toBe("/api/v1/superadmin/shops/11/credits/bonus/");
    expect(postInit.method).toBe("POST");
    expect(postInit.headers["X-CSRFToken"]).toBe("tok123");
    expect(JSON.parse(postInit.body)).toEqual({ amount: 50, period_year: 2026, period_month: 11 });
    expect(toasts.titles()).toContain("Added 50 credits to Alpha.");
    await waitFor(() => expect(screen.getByTestId("credits-row-11")).toHaveTextContent("Remaining 85"));
    expect(screen.getByText("Manage Credits")).toBeInTheDocument();
  });

  it("should send one debounced search request and refetch immediately when cleared", async () => {
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    await screen.findByTestId("credits-row-11");
    await user.type(screen.getByTestId("credits-search"), "alp");
    expect(listCalls()).toHaveLength(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    await waitFor(() => expect(listCalls()).toHaveLength(2));
    expect(listCalls()[1][0]).toBe("/api/v1/superadmin/organisations/7/credits/shops/?page=1&search=alp");
    await user.clear(screen.getByTestId("credits-search"));
    await waitFor(() => expect(listCalls()).toHaveLength(3));
    expect(listCalls()[2][0]).toBe("/api/v1/superadmin/organisations/7/credits/shops/?page=1");
  });

  it("should not let a slower earlier response replace a newer one", async () => {
    let releaseSlow: (r: Response) => void = () => {};
    lists = [
      () => jsonResponse(listBody([ALPHA, BRAVO])),
      () => new Promise<Response>((res) => (releaseSlow = res)),
      () => jsonResponse(listBody([shop(30, "Newer Shop")])),
    ];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    await screen.findByTestId("credits-row-11");
    await user.type(screen.getByTestId("credits-search"), "a");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    await user.type(screen.getByTestId("credits-search"), "b");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(await screen.findByTestId("credits-row-30")).toBeInTheDocument();
    await act(async () => {
      releaseSlow(jsonResponse(listBody([shop(31, "Stale Shop")])));
    });
    expect(screen.queryByTestId("credits-row-31")).not.toBeInTheDocument();
    expect(screen.getByTestId("credits-row-30")).toBeInTheDocument();
  });

  it("should paginate ten per page with a count line and disabled arrows at the ends", async () => {
    const page = (from: number, n: number) =>
      jsonResponse(listBody(Array.from({ length: n }, (_, i) => shop(from + i, `Shop ${from + i}`)), { count: 23 }));
    lists = [() => page(100, 10), () => page(200, 10), () => page(300, 3)];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    expect(await screen.findByText("Showing 1–10 of 23")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Showing 11–20 of 23")).toBeInTheDocument();
    expect(listCalls()[1][0]).toContain("page=2");
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Showing 21–23 of 23")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("should show the no-active-shops empty state with No results", async () => {
    lists = [() => jsonResponse(listBody([], { count: 0 }))];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    expect(await screen.findByText("No active shops")).toBeInTheDocument();
    expect(
      screen.getByText("This organisation has no active shops yet. Shops added by its Org Admin will appear here."),
    ).toBeInTheDocument();
    expect(screen.getByText("No results")).toBeInTheDocument();
  });

  it("should show a no-match state for a search and clear it with Clear search", async () => {
    lists = [
      () => jsonResponse(listBody([ALPHA])),
      () => jsonResponse(listBody([], { count: 0 })),
      () => jsonResponse(listBody([ALPHA])),
    ];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    await screen.findByTestId("credits-row-11");
    await user.type(screen.getByTestId("credits-search"), "zzz");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(await screen.findByText('No shops match "zzz"')).toBeInTheDocument();
    expect(screen.getByText("Check the spelling or try a shorter name.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getByTestId("credits-search")).toHaveValue("");
    expect(await screen.findByTestId("credits-row-11")).toBeInTheDocument();
    expect(listCalls()).toHaveLength(3);
  });

  it("should show five skeleton rows with aria-busy while loading and keep search interactive", async () => {
    lists = [() => new Promise<Response>(() => {})];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    const list = await screen.findByTestId("credits-list");
    expect(list).toHaveAttribute("aria-busy", "true");
    expect(list.querySelectorAll(".animate-sk-pulse")).toHaveLength(5);
    expect(screen.getByTestId("credits-search")).toBeEnabled();
  });

  it("should show a load error with Retry that refetches and renders rows", async () => {
    lists = [() => jsonResponse({}, 500), () => jsonResponse(listBody([ALPHA]))];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    expect(await screen.findByText("Couldn't load shops.")).toBeInTheDocument();
    expect(screen.getByText("Please try again. If the problem persists, contact support.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("credits-row-11")).toBeInTheDocument();
    expect(screen.queryByText("Couldn't load shops.")).not.toBeInTheDocument();
  });

  it("should keep Allocate disabled and show the range message for invalid amounts", async () => {
    await openBonusFor(11, "Alpha");
    const amount = screen.getByTestId("credits-amount");
    const allocate = screen.getByTestId("credits-allocate");
    expect(allocate).toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByTestId("credits-preview")).toHaveTextContent("Enter an amount to preview the new balance.");
    for (const bad of ["0", "10001", "1.5"]) {
      await user.clear(amount);
      await user.type(amount, bad);
      expect(screen.getByRole("alert")).toHaveTextContent("Enter a whole number between 1 and 10,000.");
      expect(allocate).toBeDisabled();
      expect(screen.getByTestId("credits-preview")).toHaveTextContent("Enter an amount to preview the new balance.");
    }
    await user.clear(amount);
    await user.type(amount, "10000");
    expect(allocate).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("should disable inputs and navigation while submitting and send a single POST", async () => {
    let release: (r: Response) => void = () => {};
    posts = [() => new Promise<Response>((res) => (release = res))];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.click(screen.getByTestId("credits-allocate"));
    expect(screen.getByTestId("credits-allocate")).toBeDisabled();
    expect(screen.getByTestId("credits-back")).toBeDisabled();
    expect(screen.getByTestId("credits-amount")).toBeDisabled();
    await user.click(screen.getByTestId("credits-allocate"));
    expect(postCalls()).toHaveLength(1);
    await act(async () => {
      release(okPost()());
    });
    await screen.findByTestId("credits-row-11");
  });

  it("should handle a 409 period mismatch by refreshing, keeping inputs and requiring a fresh click", async () => {
    lists = [
      () => jsonResponse(listBody([ALPHA, BRAVO])),
      () =>
        jsonResponse(
          listBody([shop(11, "Alpha"), BRAVO], { period: { year: 2026, month: 12 } }),
        ),
    ];
    posts = [
      () =>
        jsonResponse(
          {
            code: "period_mismatch",
            detail: "stale",
            period: { year: 2026, month: 12 },
            balance: { shop_id: 11, allocated: 100, bonus: 0, consumed: 0, remaining: 100 },
          },
          409,
        ),
      okPost({ period: { year: 2026, month: 12 } }),
    ];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "50");
    await user.type(screen.getByTestId("credits-reason"), "Goodwill");
    await user.click(screen.getByTestId("credits-allocate"));

    const banner = await screen.findByTestId("credits-period-banner");
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner).toHaveTextContent("A new month started — balances have been refreshed. Review and try again.");
    await waitFor(() => expect(listCalls()).toHaveLength(2));
    expect(screen.getByText("Alpha — December 2026")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        Array.from(screen.getByTestId("credits-balance-block").querySelectorAll("dd")).map((d) => d.textContent),
      ).toEqual(["100", "0", "0", "100"]),
    );
    expect(screen.getByTestId("credits-amount")).toHaveValue(50);
    expect(screen.getByTestId("credits-reason")).toHaveValue("Goodwill");
    expect(screen.getByTestId("credits-preview")).toHaveTextContent("Remaining 100 → 150 · Bonus 0 → 50");
    expect(postCalls()).toHaveLength(1);

    await user.type(screen.getByTestId("credits-amount"), "0");
    expect(screen.queryByTestId("credits-period-banner")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(postCalls()).toHaveLength(2));
    expect(JSON.parse(postCalls()[1][1].body)).toMatchObject({ amount: 500, period_month: 12, reason: "Goodwill" });
  });

  it("should toast, return to the list and reload when the shop is no longer active (404)", async () => {
    posts = [() => jsonResponse({ code: "shop_unavailable", detail: "This shop is no longer active." }, 404)];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(listCalls()).toHaveLength(2));
    const toast = toasts.events.map((e) => e.detail as { kind: string; title: string; msg?: string });
    expect(toast).toContainEqual({
      kind: "error",
      title: "This shop is no longer active.",
      msg: "The list has been refreshed.",
    });
    expect(await screen.findByTestId("credits-row-11")).toBeInTheDocument();
    expect(screen.getByText("Manage Credits")).toBeInTheDocument();
  });

  it("should render 400 field messages under the amount and reason fields without a toast", async () => {
    posts = [
      () => jsonResponse({ amount: ["Ensure this value is less than or equal to 10000."] }, 400),
      () => jsonResponse({ reason: ["Ensure this field has no more than 255 characters."] }, 400),
    ];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.click(screen.getByTestId("credits-allocate"));
    expect(await screen.findByText("Ensure this value is less than or equal to 10000.")).toBeInTheDocument();
    expect(toasts.events).toHaveLength(0);
    await user.type(screen.getByTestId("credits-amount"), "0");
    expect(screen.queryByText("Ensure this value is less than or equal to 10000.")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("credits-allocate"));
    expect(await screen.findByText("Ensure this field has no more than 255 characters.")).toBeInTheDocument();
    expect(toasts.events).toHaveLength(0);
  });

  it("should show the generic error toast and keep the form on a server error", async () => {
    posts = [() => jsonResponse({}, 500)];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.type(screen.getByTestId("credits-reason"), "why");
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(toasts.events).toHaveLength(1));
    expect(toasts.events[0].detail).toEqual({
      kind: "error",
      title: "Something went wrong.",
      msg: "Please try again. If the problem persists, contact support.",
    });
    expect(screen.getByTestId("credits-amount")).toHaveValue(5);
    expect(screen.getByTestId("credits-reason")).toHaveValue("why");
    expect(screen.getByTestId("credits-allocate")).toBeEnabled();
  });

  it("should trim the reason and omit it when only whitespace", async () => {
    posts = [okPost(), okPost()];
    await openBonusFor(11, "Alpha");
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.type(screen.getByTestId("credits-reason"), "  Goodwill  ");
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(postCalls()).toHaveLength(1));
    expect(JSON.parse(postCalls()[0][1].body).reason).toBe("Goodwill");

    await user.click(await screen.findByTestId("credits-add-bonus-11"));
    await user.type(screen.getByTestId("credits-amount"), "7");
    await user.type(screen.getByTestId("credits-reason"), "   ");
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(postCalls()).toHaveLength(2));
    expect(JSON.parse(postCalls()[1][1].body)).not.toHaveProperty("reason");
  });

  it("should focus search on open, the amount on the bonus view and the updated row after success", async () => {
    posts = [okPost()];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    const row = await screen.findByTestId("credits-row-11");
    expect(screen.getByTestId("credits-search")).toHaveFocus();
    await user.click(within(row).getByTestId("credits-add-bonus-11"));
    expect(screen.getByTestId("credits-amount")).toHaveFocus();
    await user.type(screen.getByTestId("credits-amount"), "5");
    await user.click(screen.getByTestId("credits-allocate"));
    const updated = await screen.findByTestId("credits-row-11");
    await waitFor(() => expect(screen.getByTestId("credits-add-bonus-11")).toHaveFocus());
    expect(updated).toHaveClass("bg-yellow-tint");
    expect(screen.getByTestId("credits-row-12")).not.toHaveClass("bg-yellow-tint");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByTestId("credits-row-11")).not.toHaveClass("bg-yellow-tint");
  });

  it("should discard typed values on Back to list and close the modal on Close", async () => {
    const onClose = vi.fn();
    render(<ManageCreditsModal org={ORG} onClose={onClose} />);
    await user.click(await screen.findByTestId("credits-add-bonus-11"));
    await user.type(screen.getByTestId("credits-amount"), "42");
    await user.click(screen.getByTestId("credits-back"));
    await user.click(await screen.findByTestId("credits-add-bonus-11"));
    expect(screen.getByTestId("credits-amount")).toHaveValue(null);
    await user.click(screen.getByTestId("credits-back"));
    await user.click(screen.getByTestId("credits-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("should show one credit and thousands separators in subtitle and toast", async () => {
    lists = [
      () => jsonResponse(listBody([shop(11, "Alpha")], { allocation_per_shop: 1 })),
      () => jsonResponse(listBody([shop(11, "Alpha")], { allocation_per_shop: 1 })),
    ];
    posts = [okPost()];
    render(<ManageCreditsModal org={ORG} onClose={vi.fn()} />);
    expect(await screen.findByText("Acme — November 2026 · 1 credit per shop")).toBeInTheDocument();
    await user.click(screen.getByTestId("credits-add-bonus-11"));
    await user.type(screen.getByTestId("credits-amount"), "1000");
    await user.click(screen.getByTestId("credits-allocate"));
    await waitFor(() => expect(toasts.titles()).toContain("Added 1,000 credits to Alpha."));
  });
});
