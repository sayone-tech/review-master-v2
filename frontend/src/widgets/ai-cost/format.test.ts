import { describe, it, expect } from "vitest";
import { avgPerCall, formatCost, formatCount, formatTokens } from "./format";

describe("format", () => {
  it("formats cost with separators and 2dp", () => {
    expect(formatCost("1245.670000")).toBe("$1,245.67");
    expect(formatCost("0.000195")).toBe("$0.00");
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
