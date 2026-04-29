import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createShop, listShops } from "./api";

beforeEach(() => {
  document.cookie = "csrftoken=test-csrf";
  vi.restoreAllMocks();
});

describe("listShops", () => {
  it("calls /api/v1/shops/ with filter params", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          count: 0,
          next: null,
          previous: null,
          results: [],
          allocation_status: { current: 0, max: 5, at_limit: false },
          has_regions: true,
        }),
    });
    global.fetch = mock as unknown as typeof fetch;
    await listShops({ search: "abc", status: "active", region: 7 });
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/shops/");
    expect(url).toContain("search=abc");
    expect(url).toContain("status=active");
    expect(url).toContain("region=7");
  });

  it("throws ApiError on 400", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "bad" }),
    }) as unknown as typeof fetch;
    await expect(listShops()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("createShop", () => {
  it("sends X-CSRFToken header on POST", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ id: 1 }),
    });
    global.fetch = mock as unknown as typeof fetch;
    await createShop({ name: "X", region: 1, connection_method: "NOT_CONNECTED" });
    const init = mock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBe("test-csrf");
  });
});
