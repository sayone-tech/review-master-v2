import { describe, it, expect } from "vitest";
import {
  avgPerCall,
  formatCost,
  formatCount,
  formatTokens,
  requestTypeLabel,
  orgTypeLabel,
  titleCase,
} from "./format";

describe("format", () => {
  it("formats cost with separators and 8dp", () => {
    expect(formatCost("1245.67000000")).toBe("$1,245.67000000");
    expect(formatCost("0.00019500")).toBe("$0.00019500");
    expect(formatCost("0.00000000")).toBe("$0.00000000");
  });
  it("formats large costs exactly without float conversion", () => {
    expect(formatCost("123456789012.12345678")).toBe("$123,456,789,012.12345678");
    expect(formatCost("4.5")).toBe("$4.50000000");
  });
  it("abbreviates tokens", () => {
    expect(formatTokens(12_400_000)).toBe("12.4M");
    expect(formatTokens(342_000)).toBe("342K");
    expect(formatTokens(999)).toBe("999");
  });
  it("formats counts", () => {
    expect(formatCount(48312)).toBe("48,312");
  });
  it("avgPerCall is 0 when no calls", () => {
    expect(avgPerCall(500, 0)).toBe(0);
    expect(avgPerCall(500, 2)).toBe(250);
  });
});

describe("labels", () => {
  it("maps known request types and humanises unknown ones", () => {
    expect(requestTypeLabel("reply_generation")).toBe("Reply");
    expect(requestTypeLabel("enrichment")).toBe("Enrichment");
    expect(requestTypeLabel("tag_merge")).toBe("Tag Merge");
  });
  it("title-cases", () => {
    expect(titleCase("RETAIL")).toBe("Retail");
  });
  it("uses the shared org-type labels with a title-case fallback", () => {
    expect(orgTypeLabel("RESTAURANT")).toBe("Restaurant & Cafe");
    expect(orgTypeLabel("HOTEL_RESORT")).toBe("Hotel & Resort");
    expect(orgTypeLabel("GYM_FITNESS")).toBe("Gym & Fitness");
    expect(orgTypeLabel("UNKNOWN_TYPE")).toBe("Unknown Type");
  });
});
