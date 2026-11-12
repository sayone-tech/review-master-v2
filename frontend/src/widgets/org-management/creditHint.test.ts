import { describe, expect, it } from "vitest";
import {
  computeCreditHint,
  formatCount,
  formatMonthYear,
  formatNextMonthStart,
  parseCreditInput,
} from "./creditHint";

const NOW = new Date("2026-11-15T12:00:00Z");
const OFF = "0 means AI replies are off for this organisation.";
const IMMEDIATE = "Takes effect immediately for this month.";

describe("computeCreditHint", () => {
  it("should say AI replies are off when creating with 0", () => {
    expect(
      computeCreditHint({ mode: "create", saved: 0, thisMonth: 0, typed: "0", nowUtc: NOW }),
    ).toEqual({ kind: "off", text: OFF });
  });

  it("should say the change is immediate when creating with a positive value", () => {
    expect(
      computeCreditHint({ mode: "create", saved: 0, thisMonth: 0, typed: "25", nowUtc: NOW }),
    ).toEqual({ kind: "immediate", text: IMMEDIATE });
  });

  it("should be immediate when editing from saved 0 and this month 0", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 0, thisMonth: 0, typed: "50", nowUtc: NOW }),
    ).toEqual({ kind: "immediate", text: IMMEDIATE });
  });

  it("should defer using this month's value when saved is 0 but shops still hold 100 (D-21)", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 0, thisMonth: 100, typed: "50", nowUtc: NOW }),
    ).toEqual({
      kind: "deferred",
      text: "Takes effect on 1 Dec 2026. Shops keep 100 this month.",
    });
  });

  it("should defer a decrease from 100 to 40", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 100, thisMonth: 100, typed: "40", nowUtc: NOW }),
    ).toEqual({
      kind: "deferred",
      text: "Takes effect on 1 Dec 2026. Shops keep 100 this month.",
    });
  });

  it("should warn that AI replies turn off after a deferred change to 0", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 100, thisMonth: 100, typed: "0", nowUtc: NOW }),
    ).toEqual({
      kind: "deferred-off",
      text: "Takes effect on 1 Dec 2026. Shops keep 100 this month, then AI replies turn off.",
    });
  });

  it("should hide the hint when an unchanged positive value is shown", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 100, thisMonth: 100, typed: "100", nowUtc: NOW }),
    ).toEqual({ kind: "hidden", text: "" });
  });

  it("should show the off copy when an unchanged 0 is shown", () => {
    expect(
      computeCreditHint({ mode: "edit", saved: 0, thisMonth: 0, typed: "0", nowUtc: NOW }),
    ).toEqual({ kind: "off", text: OFF });
  });

  it("should use the December rollover date in the deferred copy", () => {
    const december = new Date("2026-12-31T23:59:59Z");
    expect(
      computeCreditHint({ mode: "edit", saved: 10, thisMonth: 10, typed: "20", nowUtc: december }).text,
    ).toBe("Takes effect on 1 Jan 2027. Shops keep 10 this month.");
  });

  it.each(["", "abc", "1.5", "-1", "10001"])(
    "should hide the hint in both modes when the input %j is invalid",
    (typed) => {
      for (const mode of ["create", "edit"] as const) {
        expect(
          computeCreditHint({ mode, saved: 100, thisMonth: 100, typed, nowUtc: NOW }),
        ).toEqual({ kind: "hidden", text: "" });
      }
    },
  );
});

describe("formatNextMonthStart", () => {
  it.each([
    ["2026-11-15T12:00:00Z", "1 Dec 2026"],
    ["2026-12-31T23:59:59Z", "1 Jan 2027"],
    ["2026-08-10T00:00:00Z", "1 Sep 2026"],
    ["2026-11-30T23:30:00Z", "1 Dec 2026"],
  ])("should format %s as %s", (iso, expected) => {
    expect(formatNextMonthStart(new Date(iso))).toBe(expected);
  });
});

describe("formatMonthYear and formatCount", () => {
  it("should format the month and year with the full month name", () => {
    expect(formatMonthYear(2026, 11)).toBe("November 2026");
    expect(formatMonthYear(2027, 1)).toBe("January 2027");
  });

  it("should add a thousands separator only from 1,000", () => {
    expect(formatCount(1000)).toBe("1,000");
    expect(formatCount(7)).toBe("7");
  });
});

describe("parseCreditInput", () => {
  it("should accept whole numbers from 0 to 10,000 and trim whitespace", () => {
    expect(parseCreditInput("0")).toBe(0);
    expect(parseCreditInput("10000")).toBe(10000);
    expect(parseCreditInput(" 25 ")).toBe(25);
  });

  it.each(["10001", "-1", "1.5", "1e3", ""])("should reject %j", (raw) => {
    expect(parseCreditInput(raw)).toBeNull();
  });
});
