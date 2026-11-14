// Pure layout maths for the dark dashboard panels (no React, no DOM).

/**
 * Turn counts into whole percentages that sum to exactly 100 (largest-remainder
 * rounding). Ties go to the earlier entry. All-zero input returns all zeros.
 */
export function toHundred(counts: readonly number[]): number[] {
  const total = counts.reduce((a, b) => a + Math.max(0, b), 0);
  if (total <= 0) return counts.map(() => 0);
  const exact = counts.map((c) => (Math.max(0, c) * 100) / total);
  const out = exact.map(Math.floor);
  let left = 100 - out.reduce((a, b) => a + b, 0);
  const order = exact
    .map((v, i) => ({ i, frac: v - Math.floor(v) }))
    .sort((a, b) => b.frac - a.frac || a.i - b.i);
  for (const { i } of order) {
    if (left <= 0) break;
    out[i] += 1;
    left -= 1;
  }
  return out;
}

export const LADDER_MIN = 3;
export const LADDER_MAX = 5;

/** Position on the 3★–5★ ladder as a 0–100 percentage; below 3★ pins to 0. */
export function ladderX(rating: number): number {
  if (!Number.isFinite(rating)) return 0;
  const r = Math.min(LADDER_MAX, Math.max(LADDER_MIN, rating));
  return Math.round(((r - LADDER_MIN) / (LADDER_MAX - LADDER_MIN)) * 10000) / 100;
}

export function ellipsize(name: string, max = 14): string {
  return name.length > max ? `${name.slice(0, max).trimEnd()}…` : name;
}

/** Rough rendered width of an 11px label, in px. */
export function labelWidthPx(text: string): number {
  return text.length * 6.4 + 4;
}

export interface LaneInput {
  id: number;
  x: number; // 0–100
  text: string;
}

/**
 * Greedy lane assignment so labels never overlap: a label goes in the first
 * lane where it clears every label already placed there. `widthPx` is the
 * ladder's rendered width. Returns lane index per id (0 = nearest the line).
 */
export function assignLanes(labels: readonly LaneInput[], widthPx: number): Map<number, number> {
  const w = Math.max(widthPx, 1);
  const gap = 8;
  const span = (l: LaneInput) => {
    const half = labelWidthPx(l.text) / 2;
    const centre = Math.min(Math.max((l.x / 100) * w, half), w - half);
    return [centre - half, centre + half] as const;
  };
  const lanes: Array<Array<readonly [number, number]>> = [];
  const result = new Map<number, number>();
  for (const l of [...labels].sort((a, b) => a.x - b.x || a.id - b.id)) {
    const [s, e] = span(l);
    let lane = lanes.findIndex((placed) => placed.every(([ps, pe]) => e + gap <= ps || s >= pe + gap));
    if (lane === -1) {
      lanes.push([]);
      lane = lanes.length - 1;
    }
    lanes[lane].push([s, e]);
    result.set(l.id, lane);
  }
  return result;
}
