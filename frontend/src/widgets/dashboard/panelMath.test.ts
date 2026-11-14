import { describe, expect, it } from "vitest";

import { assignLanes, ellipsize, ladderX, toHundred } from "./panelMath";

describe("toHundred", () => {
  it("should round counts with largest remainder so they sum to 100", () => {
    expect(toHundred([260, 82, 46])).toEqual([67, 21, 12]);
    expect(toHundred([1, 1, 1])).toEqual([34, 33, 33]);
  });

  it("should always sum to exactly 100 for non-empty input", () => {
    for (const counts of [[7, 3, 1], [999, 1, 0], [5, 5, 5, 5, 5, 5, 5], [1, 0, 0]]) {
      expect(toHundred(counts).reduce((a, b) => a + b, 0)).toBe(100);
    }
  });

  it("should return zeros when every count is zero", () => {
    expect(toHundred([0, 0, 0])).toEqual([0, 0, 0]);
  });
});

describe("ladderX", () => {
  it("should map 3–5 stars onto 0–100 and pin values below 3 to the left end", () => {
    expect(ladderX(3)).toBe(0);
    expect(ladderX(4)).toBe(50);
    expect(ladderX(5)).toBe(100);
    expect(ladderX(2.1)).toBe(0);
  });
});

describe("ellipsize", () => {
  it("should keep short names and shorten names over 14 characters", () => {
    expect(ellipsize("Kochi")).toBe("Kochi");
    expect(ellipsize("Thiruvananthapuram Central")).toBe("Thiruvananthap…");
  });
});

describe("assignLanes", () => {
  it("should keep far-apart labels in one lane", () => {
    const lanes = assignLanes(
      [
        { id: 1, x: 10, text: "Kochi 4.5" },
        { id: 2, x: 90, text: "Calicut 4.9" },
      ],
      560,
    );
    expect(lanes.get(1)).toBe(0);
    expect(lanes.get(2)).toBe(0);
  });

  it("should push colliding labels into separate lanes", () => {
    const lanes = assignLanes(
      [
        { id: 1, x: 50, text: "Kochi 4.50" },
        { id: 2, x: 52, text: "Calicut 4.54" },
        { id: 3, x: 54, text: "Kannur 4.58" },
      ],
      560,
    );
    expect(new Set([lanes.get(1), lanes.get(2), lanes.get(3)]).size).toBe(3);
  });
});
