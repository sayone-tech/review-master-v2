import { describe, it, expect } from "vitest";
import { readFilters, readListState, writeFilters, writeUrlState } from "./urlState";

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
  it("defaults list state when absent or invalid", () => {
    const d = { sort: "-cost", page: 1, pageSize: 25 };
    expect(readListState("?range=7d")).toEqual(d);
    expect(readListState("?page=0&page_size=7")).toEqual(d);
  });
  it("round-trips sort, page and page size", () => {
    const l = { sort: "name", page: 3, pageSize: 50 };
    const q = writeUrlState({ range: "7d" }, l);
    expect(q).toContain("sort=name");
    expect(readListState(q)).toEqual(l);
    expect(readFilters(q)).toEqual({ range: "7d" });
  });
  it("omits default list state from the URL", () => {
    expect(writeUrlState({ range: "7d" })).toBe("?range=7d");
  });
});
