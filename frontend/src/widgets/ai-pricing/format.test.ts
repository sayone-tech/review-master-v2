import { describe, it, expect } from "vitest";
import { formatDate, formatDateTime, formatPrice, sourceLabel } from "./format";

describe("ai-pricing format", () => {
  it("formats prices with 6 decimals", () => {
    expect(formatPrice("0.15000000")).toBe("$0.150000");
    expect(formatPrice("0.00000000")).toBe("$0.000000");
    expect(formatPrice("1000.00000000")).toBe("$1000.000000");
  });

  it("formats dates in UTC", () => {
    expect(formatDate("2026-11-12T23:30:00Z")).toBe("2026-11-12");
    expect(formatDateTime("2026-11-17T10:05:00Z")).toBe("2026-11-17 10:05 UTC");
  });

  it("labels sources", () => {
    expect(sourceLabel("manual")).toBe("Manual");
    expect(sourceLabel("sync")).toBe("LiteLLM sync");
    expect(sourceLabel("seed")).toBe("Seed");
  });
});
