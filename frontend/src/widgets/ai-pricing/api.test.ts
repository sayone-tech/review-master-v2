import { describe, it, expect, vi, afterEach } from "vitest";
import { createPrice, fetchHistory } from "./api";
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

describe("createPrice", () => {
  const body = {
    model: "m",
    input_token_price_per_1m: "1",
    output_token_price_per_1m: "1",
    cached_token_price_per_1m: "1",
    effective_from: "2030-01-01T00:00:00.000Z",
  };

  it("POSTs JSON with the CSRF header", async () => {
    document.cookie = "csrftoken=tok123";
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(priceRow()), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await createPrice(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/superadmin/ai-pricing/");
    expect(init.method).toBe("POST");
    expect(init.headers["X-CSRFToken"]).toBe("tok123");
    expect(JSON.parse(init.body)).toEqual(body);
  });

  it("exposes DRF field errors and {code, detail} errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ model: ["This field may not be blank."] }), { status: 400 }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ code: "scheduled_price_exists", detail: "Delete it first." }), {
            status: 409,
          }),
        ),
    );
    await expect(createPrice(body)).rejects.toMatchObject({
      status: 400,
      fields: { model: ["This field may not be blank."] },
    });
    await expect(createPrice(body)).rejects.toMatchObject({
      status: 409,
      message: "Delete it first.",
      code: "scheduled_price_exists",
    });
  });
});
