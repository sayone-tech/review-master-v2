import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchHistory } from "./api";
import { priceRow } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("fetchHistory", () => {
  it("follows pagination until next is null", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ count: 2, next: "http://x/?page=2", previous: null, results: [priceRow({ id: 1 })] }),
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ count: 2, next: null, previous: "x", results: [priceRow({ id: 2 })] }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const r = await fetchHistory("gpt x");
    expect(r.results.map((p) => p.id)).toEqual([1, 2]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/superadmin/ai-pricing/history/?model=gpt%20x&page_size=100&page=2",
    );
  });
});
