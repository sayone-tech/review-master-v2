import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { ShopModals } from "./ShopModals";
import type { ShopRow } from "./types";
import * as api from "./api";
import * as creditsApi from "../credits/creditsApi";
import { resetCreditsStoreForTests } from "../credits/creditsStore";

function row(over: Partial<ShopRow> = {}): ShopRow {
  return {
    id: 1,
    name: "ACME",
    phone: "",
    street_address: "",
    place_id: "",
    connection_method: "GOOGLE_OAUTH",
    connection_status: "CONNECTED",
    sync_depth: "TWO_YEARS",
    is_active: true,
    region: 1,
    region_name: "N",
    region_region_id: "N001",
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "",
    ...over,
  };
}

function creditsPayload(over: Partial<creditsApi.ShopCredits> = {}): creditsApi.ShopCredits {
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

describe("ShopModals", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetCreditsStoreForTests();
  });

  it("should open Shop Details with a populated credits card focused on its heading when shop:open-credits fires", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(creditsPayload());
    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:open-credits", { detail: row() }));
    });

    const dialog = screen.getByRole("dialog", { name: "Shop Details" });
    expect(await within(dialog).findByText("/ 100")).toBeInTheDocument();
    expect(within(dialog).getByText("AI Reply Credits")).toBeInTheDocument();
    expect(within(dialog).getByText("35")).toBeInTheDocument();
    expect(within(dialog).getByText("November 2026")).toBeInTheDocument();
    expect(within(dialog).getByText("Renews 1 Dec 2026 (UTC)")).toBeInTheDocument();
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(dialog).getByRole("heading", { name: "AI Reply Credits" }),
      ),
    );
  });

  it("opens deactivate confirm on shop:open-deactivate", () => {
    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:open-deactivate", { detail: row() }));
    });
    expect(screen.getByText("Deactivate shop?")).toBeInTheDocument();
  });

  it("opens activate (blue) confirm on shop:open-activate", () => {
    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(
        new CustomEvent("shop:open-activate", { detail: row({ is_active: false }) }),
      );
    });
    expect(screen.getByText("Activate shop?")).toBeInTheDocument();
  });

  it("at_limit Add Shop click emits toast and does NOT open create modal", () => {
    const btn = document.createElement("button");
    btn.id = "open-create-shop";
    btn.setAttribute("data-at-limit", "true");
    document.body.appendChild(btn);

    render(
      <ShopModals allocation={{ current: 5, max: 5, at_limit: true }} regions={[]} />,
    );
    fireEvent.click(btn);

    // Modal title "Add Shop" should NOT be in document
    expect(screen.queryByText("Add Shop")).not.toBeInTheDocument();

    document.body.removeChild(btn);
  });

  it("successful deactivate dispatches shop:refresh", async () => {
    const spy = vi.spyOn(api, "deactivateShop").mockResolvedValue(row());
    const ev = vi.fn();
    window.addEventListener("shop:refresh", ev);

    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:open-deactivate", { detail: row() }));
    });
    fireEvent.click(screen.getByTestId("confirm-confirm"));

    await waitFor(() => expect(spy).toHaveBeenCalledWith(1));
    await waitFor(() => expect(ev).toHaveBeenCalled());

    window.removeEventListener("shop:refresh", ev);
  });

  it("renders deactivate confirm with slot-retention message", () => {
    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(
        new CustomEvent("shop:open-deactivate", { detail: row({ name: "TestShop" }) }),
      );
    });
    expect(screen.getByText(/allocated store slot remains used/)).toBeInTheDocument();
  });

  it("opens details modal on shop:open-details", () => {
    render(
      <ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />,
    );
    act(() => {
      window.dispatchEvent(
        new CustomEvent("shop:open-details", { detail: row({ name: "DetailShop" }) }),
      );
    });
    expect(screen.getByText("Shop Details")).toBeInTheDocument();
  });
});

describe("ShopModals Buy More from the credits card", () => {
  let contactEl: HTMLScriptElement;

  beforeEach(() => {
    vi.restoreAllMocks();
    resetCreditsStoreForTests();
    contactEl = document.createElement("script");
    contactEl.id = "credit-contact";
    contactEl.type = "application/json";
    contactEl.textContent = JSON.stringify({
      organisation_name: "Acme Org",
      support_email: "support@reviewbee.test",
    });
    document.body.appendChild(contactEl);
    vi.spyOn(creditsApi, "getShopCredits").mockResolvedValue(creditsPayload());
  });

  afterEach(() => contactEl.remove());

  async function openBuyMore() {
    render(<ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:open-credits", { detail: row({ name: "Downtown" }) }));
    });
    const button = await screen.findByRole("button", { name: "Buy More Credits" });
    button.focus(); // a real click focuses the button; fireEvent.click alone does not
    fireEvent.click(button);
    return button;
  }

  it("should open Buy More as a sibling dialog with the shop context in the mailto", async () => {
    await openBuyMore();

    const buyMore = screen.getByRole("dialog", { name: "Buy More Credits" });
    const details = screen.getByRole("dialog", { name: "Shop Details" });
    expect(details.contains(buyMore)).toBe(false);
    expect(buyMore.contains(details)).toBe(false);

    const href = within(buyMore).getByRole("link", { name: "Contact Admin" }).getAttribute("href") ?? "";
    const url = new URL(href);
    expect(url.pathname).toBe("support@reviewbee.test");
    expect(url.searchParams.get("subject")).toBe("Credit request — Acme Org / Downtown");
    const body = url.searchParams.get("body") ?? "";
    expect(body).toContain("Current balance: 35 of 100 credits remaining");
    expect(body).toContain("Month: November 2026");
  });

  it("should close only Buy More on the first Escape and Shop Details on the second", async () => {
    await openBuyMore();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Buy More Credits" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Shop Details" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Shop Details" })).not.toBeInTheDocument();
  });

  it("should return focus to the Buy More Credits button when Buy More closes", async () => {
    const button = await openBuyMore();
    const buyMore = screen.getByRole("dialog", { name: "Buy More Credits" });
    fireEvent.click(within(buyMore).getByText("Close"));
    await waitFor(() => expect(document.activeElement).toBe(button));
  });

  it("should keep Shop Details usable when the credits fetch fails", async () => {
    vi.spyOn(creditsApi, "getShopCredits").mockRejectedValue(new creditsApi.ShopCreditsError(500));
    render(<ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />);
    act(() => {
      window.dispatchEvent(new CustomEvent("shop:open-details", { detail: row() }));
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load credits.");
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.queryByRole("dialog", { name: "Shop Details" })).not.toBeInTheDocument();
  });

  it("should fetch credits again each time Shop Details is reopened", async () => {
    const spy = creditsApi.getShopCredits as unknown as ReturnType<typeof vi.fn>;
    render(<ShopModals allocation={{ current: 0, max: 5, at_limit: false }} regions={[]} />);
    for (let i = 0; i < 2; i += 1) {
      act(() => {
        window.dispatchEvent(new CustomEvent("shop:open-details", { detail: row() }));
      });
      await screen.findByText("/ 100");
      fireEvent.click(screen.getByText("Close"));
    }
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
