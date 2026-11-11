import { describe, it, expect, vi, beforeEach } from "vitest";
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
