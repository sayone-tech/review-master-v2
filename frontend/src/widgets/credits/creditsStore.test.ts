import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import {
  getShopCredits,
  resetCreditsStoreForTests,
  setShopCredits,
  subscribeShopCredits,
  useShopCredits,
} from "./creditsStore";

describe("creditsStore", () => {
  beforeEach(() => {
    resetCreditsStoreForTests();
  });

  it("should return the entry that was set", () => {
    setShopCredits(1, { remaining: 35, total: 100, isEnabled: true, periodLabel: "November 2026" });
    expect(getShopCredits(1)).toEqual({
      remaining: 35,
      total: 100,
      isEnabled: true,
      periodLabel: "November 2026",
    });
  });

  it("should return undefined for an unknown shop", () => {
    expect(getShopCredits(999)).toBeUndefined();
  });

  it("should keep the earlier total and periodLabel when a later update omits them", () => {
    setShopCredits(1, { remaining: 35, total: 100, periodLabel: "November 2026" });
    setShopCredits(1, { remaining: 30 });
    expect(getShopCredits(1)).toEqual({
      remaining: 30,
      total: 100,
      isEnabled: true,
      periodLabel: "November 2026",
    });
    setShopCredits(1, { remaining: 20, total: null, periodLabel: null });
    expect(getShopCredits(1)?.total).toBe(100);
    expect(getShopCredits(1)?.periodLabel).toBe("November 2026");
  });

  it.each([null, undefined, Number.NaN, Number.POSITIVE_INFINITY])(
    "should ignore an update whose remaining is %s and not notify",
    (bad) => {
      setShopCredits(1, { remaining: 35, total: 100 });
      const listener = vi.fn();
      const unsubscribe = subscribeShopCredits(listener);
      const before = getShopCredits(1);
      setShopCredits(1, { remaining: bad as number | null | undefined, total: 5 });
      expect(getShopCredits(1)).toBe(before);
      expect(listener).not.toHaveBeenCalled();
      unsubscribe();
    },
  );

  it("should default isEnabled to true and keep the previous value when omitted", () => {
    setShopCredits(1, { remaining: 0, isEnabled: false });
    setShopCredits(1, { remaining: 0 });
    expect(getShopCredits(1)?.isEnabled).toBe(false);
    setShopCredits(2, { remaining: 4 });
    expect(getShopCredits(2)?.isEnabled).toBe(true);
  });

  it("should create a new entry object on every accepted change", () => {
    setShopCredits(1, { remaining: 10, total: 100 });
    const first = getShopCredits(1);
    setShopCredits(1, { remaining: 9 });
    expect(getShopCredits(1)).not.toBe(first);
  });

  it("should notify subscribers once per accepted set and not after unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeShopCredits(listener);
    setShopCredits(1, { remaining: 10 });
    expect(listener).toHaveBeenCalledTimes(1);
    setShopCredits(1, { remaining: 9 });
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
    setShopCredits(1, { remaining: 8 });
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("should clear entries on reset", () => {
    setShopCredits(1, { remaining: 10 });
    resetCreditsStoreForTests();
    expect(getShopCredits(1)).toBeUndefined();
  });
});

describe("useShopCredits", () => {
  beforeEach(() => {
    resetCreditsStoreForTests();
  });

  function Probe({ shopId, onRender }: { shopId: number; onRender: () => void }) {
    const entry = useShopCredits(shopId);
    onRender();
    return createElement(
      "p",
      { "data-testid": "probe" },
      entry ? `remaining ${entry.remaining}` : "unknown",
    );
  }

  it("should return undefined for an unknown shop", () => {
    render(createElement(Probe, { shopId: 1, onRender: () => {} }));
    expect(screen.getByTestId("probe")).toHaveTextContent("unknown");
  });

  it("should re-render when its shop changes and not when another shop changes", () => {
    const onRender = vi.fn();
    render(createElement(Probe, { shopId: 1, onRender }));
    const initialRenders = onRender.mock.calls.length;

    act(() => {
      setShopCredits(1, { remaining: 7 });
    });
    expect(screen.getByTestId("probe")).toHaveTextContent("remaining 7");
    const afterOwn = onRender.mock.calls.length;
    expect(afterOwn).toBeGreaterThan(initialRenders);

    act(() => {
      setShopCredits(2, { remaining: 50 });
    });
    expect(onRender.mock.calls.length).toBe(afterOwn);
    expect(screen.getByTestId("probe")).toHaveTextContent("remaining 7");
  });
});
