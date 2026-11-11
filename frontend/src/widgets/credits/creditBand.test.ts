import { describe, expect, it } from "vitest";
import {
  BADGE_BAND_CLASSES,
  BAR_BAND_CLASSES,
  creditBand,
  creditBarPercent,
} from "./creditBand";

describe("creditBand", () => {
  it.each([
    [5, 0, "not_enabled"],
    [0, 0, "not_enabled"],
    [0, 100, "empty"],
    [-3, 100, "empty"],
    [26, 100, "green"],
    [100, 100, "green"],
    [25, 100, "amber"],
    [5, 100, "amber"],
    [4, 100, "red"],
    [1, 3, "green"],
    [1, 21, "red"],
    [1, 20, "amber"],
  ] as const)("should return the band for remaining=%s total=%s -> %s", (remaining, total, band) => {
    expect(creditBand(remaining, total)).toBe(band);
  });
});

describe("creditBarPercent", () => {
  it.each([
    [35, 100, 35],
    [150, 100, 100],
    [-1, 100, 0],
    [5, 0, 0],
    [1, 3, 33],
  ] as const)("should clamp and round remaining=%s total=%s -> %s", (remaining, total, pct) => {
    expect(creditBarPercent(remaining, total)).toBe(pct);
  });
});

describe("band class maps", () => {
  it("should map every band to its badge classes", () => {
    expect(BADGE_BAND_CLASSES.green).toBe("bg-green-tint text-[#166534]");
    expect(BADGE_BAND_CLASSES.amber).toBe("bg-amber-tint text-[#92400E]");
    expect(BADGE_BAND_CLASSES.red).toBe("bg-red-tint text-[#991B1B]");
    expect(BADGE_BAND_CLASSES.empty).toBe("bg-muted text-white");
    expect(BADGE_BAND_CLASSES.not_enabled).toBe("bg-line-soft text-muted");
  });

  it("should map every enabled band to a bar colour and have none for not_enabled", () => {
    expect(BAR_BAND_CLASSES).toEqual({
      green: "bg-green",
      amber: "bg-amber",
      red: "bg-red",
      empty: "bg-muted",
    });
    expect("not_enabled" in BAR_BAND_CLASSES).toBe(false);
  });
});
