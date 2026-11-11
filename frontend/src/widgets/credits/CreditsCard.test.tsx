import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CreditsCard } from "./CreditsCard";
import { CreditBadge } from "./CreditBadge";
import * as creditsApi from "./creditsApi";
import { resetCreditsStoreForTests } from "./creditsStore";

function payload(over: Partial<creditsApi.ShopCredits> = {}): creditsApi.ShopCredits {
  return {
    shop_id: 1,
    period: { year: 2026, month: 11 },
    period_label: "November 2026",
    renews_on: "2026-12-01",
    allocated: 100,
    bonus: 0,
    consumed: 65,
    remaining: 35,
    total: 100,
    is_enabled: true,
    ...over,
  };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const noop = () => undefined;

beforeEach(() => resetCreditsStoreForTests());
afterEach(() => vi.restoreAllMocks());

describe("CreditsCard", () => {
  it("should show an aria-busy skeleton without Buy More while the fetch is pending", () => {
    vi.spyOn(creditsApi, "getShopCredits").mockReturnValue(new Promise(() => undefined));
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);

    const card = screen.getByTestId("credits-card");
    expect(card).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("heading", { name: "AI Reply Credits" })).toBeInTheDocument();
    expect(card.querySelectorAll(".animate-sk-pulse")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: "Buy More Credits" })).not.toBeInTheDocument();
  });

  it("should show an alert with Retry when the fetch fails and recover on Retry", async () => {
    const spy = vi
      .spyOn(creditsApi, "getShopCredits")
      .mockRejectedValueOnce(new creditsApi.ShopCreditsError(500))
      .mockResolvedValueOnce(payload());
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Couldn't load credits.");
    expect(alert).toHaveTextContent("Please try again.");
    expect(screen.queryByRole("button", { name: "Buy More Credits" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry Loading Credits" }));
    expect(await screen.findByText("/ 100")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("should show the not-enabled copy with period and Buy More but no bar when total is 0", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(
      payload({ total: 0, remaining: 0, allocated: 0, consumed: 0, is_enabled: false }),
    );
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);

    expect(await screen.findByText("AI replies aren't enabled for this shop.")).toBeInTheDocument();
    expect(screen.getByText("November 2026")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buy More Credits" })).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText(/\/ 0/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Monthly/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Renews/)).not.toBeInTheDocument();
  });

  it.each([
    [30, 100, "bg-green", 30],
    [25, 100, "bg-amber", 25],
    [5, 100, "bg-amber", 5],
    [4, 100, "bg-red", 4],
    [0, 100, "bg-muted", 0],
  ])("should colour the bar for %i of %i credits as %s", async (remaining, total, cls, width) => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(
      payload({ remaining, total, consumed: total - remaining }),
    );
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);

    const bar = await screen.findByRole("progressbar", { name: "AI reply credits remaining" });
    expect(bar.className).toContain(cls);
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", String(total));
    expect(bar).toHaveAttribute("aria-valuenow", String(remaining));
    expect(bar).toHaveAttribute("aria-valuetext", `${remaining} of ${total} credits remaining`);
    expect(bar).toHaveStyle({ width: `${width}%` });
    expect(screen.getByText(String(remaining))).toBeInTheDocument();
  });

  it("should use singular copy and thousands separators in the used/available line", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(
      payload({ consumed: 1, remaining: 1, total: 2 }),
    );
    const { unmount } = render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);
    expect(await screen.findByText("1 credit used · 1 credit available")).toBeInTheDocument();
    unmount();

    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(
      payload({ consumed: 1000, remaining: 9000, total: 10000, allocated: 10000 }),
    );
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);
    expect(
      await screen.findByText("1,000 credits used · 9,000 credits available"),
    ).toBeInTheDocument();
  });

  it("should omit the renews and period lines when the server does not send them", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(
      payload({ renews_on: "", period_label: "" }),
    );
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);

    expect(await screen.findByText("/ 100")).toBeInTheDocument();
    expect(screen.queryByText(/Renews/)).not.toBeInTheDocument();
    expect(screen.queryByText("November 2026")).not.toBeInTheDocument();
  });

  it("should abort the request when the card unmounts", () => {
    const spy = vi.spyOn(creditsApi, "getShopCredits").mockReturnValue(new Promise(() => undefined));
    const { unmount } = render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);
    const signal = spy.mock.calls[0][1] as AbortSignal;
    expect(signal.aborted).toBe(false);
    unmount();
    expect(signal.aborted).toBe(true);
  });

  it("should never render a slow response for shop A after switching to shop B", async () => {
    const a = deferred<creditsApi.ShopCredits>();
    const b = deferred<creditsApi.ShopCredits>();
    vi.spyOn(creditsApi, "getShopCredits").mockImplementation((id) =>
      id === 1 ? a.promise : b.promise,
    );
    const { rerender } = render(<CreditsCard shopId={1} shopName="A" onBuyMore={noop} />);
    rerender(<CreditsCard shopId={2} shopName="B" onBuyMore={noop} />);

    await act(async () => {
      a.resolve(payload({ shop_id: 1, remaining: 11, total: 50, consumed: 39 }));
    });
    expect(screen.queryByText("11")).not.toBeInTheDocument();
    expect(screen.getByTestId("credits-card")).toHaveAttribute("aria-busy", "true");

    await act(async () => {
      b.resolve(payload({ shop_id: 2, remaining: 77, total: 80, consumed: 3 }));
    });
    expect(await screen.findByText("77")).toBeInTheDocument();
    expect(screen.queryByText("11")).not.toBeInTheDocument();
  });

  it("should refetch each time the card is mounted again for the same shop", async () => {
    const spy = vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(payload());
    const first = render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);
    await first.findByText("/ 100");
    first.unmount();
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />);
    await screen.findByText("/ 100");
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("should update the shop's badge to the card's remaining after the card loads", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(payload({ remaining: 12 }));
    render(
      <>
        <CreditBadge shopId={1} remaining={35} total={100} onOpen={noop} />
        <CreditsCard shopId={1} shopName="ACME" onBuyMore={noop} />
      </>,
    );
    expect(screen.getByTestId("credits-badge-1")).toHaveTextContent("35 credits");
    await waitFor(() =>
      expect(screen.getByTestId("credits-badge-1")).toHaveTextContent("12 credits"),
    );
  });

  it("should call onBuyMore with the shop context when Buy More Credits is clicked", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(payload());
    const onBuyMore = vi.fn();
    render(<CreditsCard shopId={1} shopName="ACME" onBuyMore={onBuyMore} />);
    fireEvent.click(await screen.findByRole("button", { name: "Buy More Credits" }));
    expect(onBuyMore).toHaveBeenCalledWith({
      name: "ACME",
      remaining: 35,
      total: 100,
      isEnabled: true,
      periodLabel: "November 2026",
    });
  });
});
