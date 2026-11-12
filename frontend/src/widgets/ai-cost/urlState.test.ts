import { describe, it, expect } from "vitest";
import { readFilters, writeFilters } from "./urlState";

describe("urlState", () => {
  it("defaults to this_month", () => {
    expect(readFilters("")).toEqual({ range: "this_month" });
  });
  it("round-trips a custom range", () => {
    const f = { range: "custom" as const, from: "2026-10-01", to: "2026-10-31" };
    expect(readFilters(writeFilters(f))).toEqual(f);
  });
  it("ignores unknown range keys", () => {
    expect(readFilters("?range=bogus")).toEqual({ range: "this_month" });
  });
});
