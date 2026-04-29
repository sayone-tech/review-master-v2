import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { useShops } from "./useShops";

beforeEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/admin/org/shops/");
});

describe("useShops", () => {
  const initial = {
    rows: [],
    allocation: { current: 0, max: 5, at_limit: false },
    hasRegions: true,
  };

  it("setSearch triggers listShops with search param", async () => {
    const spy = vi.spyOn(api, "listShops").mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [],
      allocation_status: initial.allocation,
      has_regions: true,
    });
    const { result } = renderHook(() => useShops(initial));
    act(() => result.current.setSearch("hello"));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls.at(-1)?.[0]).toMatchObject({ search: "hello", page: 1 });
  });

  it("pre-populates region filter from URL", async () => {
    const spy = vi.spyOn(api, "listShops").mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
      allocation_status: initial.allocation,
      has_regions: true,
    });
    window.history.replaceState({}, "", "/admin/org/shops/?region=42");
    const { result } = renderHook(() => useShops(initial));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(spy.mock.calls[0][0]).toMatchObject({ region: 42 });
    expect(result.current.filters.region).toBe(42);
  });
});
