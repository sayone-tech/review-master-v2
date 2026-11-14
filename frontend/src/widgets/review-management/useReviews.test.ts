import { afterEach, describe, expect, it } from "vitest";
import { parseUrlParams } from "./useReviews";

function setSearch(search: string) {
  window.history.pushState({}, "", `/admin/org/reviews/${search}`);
}

describe("parseUrlParams", () => {
  afterEach(() => setSearch(""));

  it("parses tags as a comma list", () => {
    setSearch("?tags=Wait%20time,Rude%20staff");
    expect(parseUrlParams().tags).toEqual(["Wait time", "Rude staff"]);
  });

  it("parses rating 1-5", () => {
    setSearch("?rating=2");
    expect(parseUrlParams().rating).toBe(2);
  });

  it("ignores invalid rating", () => {
    setSearch("?rating=9");
    expect(parseUrlParams().rating).toBeUndefined();
    setSearch("?rating=abc");
    expect(parseUrlParams().rating).toBeUndefined();
  });

  it("parses replied=false|true into is_replied", () => {
    setSearch("?replied=false");
    expect(parseUrlParams().is_replied).toBe(false);
    setSearch("?replied=true");
    expect(parseUrlParams().is_replied).toBe(true);
  });

  it("ignores invalid replied", () => {
    setSearch("?replied=maybe");
    expect(parseUrlParams().is_replied).toBeUndefined();
  });

  it("still parses store, sentiment, from, to", () => {
    setSearch("?store=3&sentiment=negative&from=2026-01-01&to=2026-02-01");
    expect(parseUrlParams()).toEqual({
      shop: 3,
      sentiment: "negative",
      from_date: "2026-01-01",
      to_date: "2026-02-01",
    });
  });

  it("ignores empty tags", () => {
    setSearch("?tags=");
    expect(parseUrlParams().tags).toBeUndefined();
  });
});
