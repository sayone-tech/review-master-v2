import { describe, expect, it } from "vitest";
import { creditsLabel, formatUtcDate } from "./format";

describe("creditsLabel", () => {
  it.each([
    [0, "0 credits"],
    [1, "1 credit"],
    [2, "2 credits"],
    [10000, "10,000 credits"],
  ] as const)("should render %s as %s", (n, label) => {
    expect(creditsLabel(n)).toBe(label);
  });
});

describe("formatUtcDate", () => {
  it.each([
    ["2026-12-01", "1 Dec 2026"],
    ["2027-01-01", "1 Jan 2027"],
    ["2026-09-01", "1 Sep 2026"],
    ["2026-11-30", "30 Nov 2026"],
  ] as const)("should format %s as %s", (iso, expected) => {
    expect(formatUtcDate(iso)).toBe(expected);
  });

  it.each(["", "2026-13-01", "not-a-date", "2026-00-10", "2026-12-32", "26-12-01", "2026-12-01T00:00:00Z"])(
    "should return null for malformed input %j",
    (input) => {
      expect(formatUtcDate(input)).toBeNull();
    },
  );

  it("should not depend on the process time zone (no Date construction)", () => {
    const original = globalThis.Date;
    // Any Date construction would throw; the formatter must be pure string handling.
    class ForbiddenDate {
      constructor() {
        throw new Error("Date must not be constructed");
      }
    }
    globalThis.Date = ForbiddenDate as unknown as DateConstructor;
    try {
      expect(formatUtcDate("2026-12-01")).toBe("1 Dec 2026");
    } finally {
      globalThis.Date = original;
    }
  });
});
