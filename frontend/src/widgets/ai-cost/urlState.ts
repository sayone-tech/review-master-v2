import type { CostFilters, RangeKey } from "./types";

const RANGES: RangeKey[] = ["this_month", "last_month", "7d", "30d", "90d", "custom"];

export function readFilters(search: string): CostFilters {
  const p = new URLSearchParams(search);
  const r = p.get("range") as RangeKey | null;
  const range: RangeKey = r && RANGES.includes(r) ? r : "this_month";
  const f: CostFilters = { range };
  if (range === "custom") {
    const from = p.get("from");
    const to = p.get("to");
    if (from) f.from = from;
    if (to) f.to = to;
  }
  return f;
}

export function writeFilters(f: CostFilters): string {
  const p = new URLSearchParams();
  p.set("range", f.range);
  if (f.range === "custom") {
    if (f.from) p.set("from", f.from);
    if (f.to) p.set("to", f.to);
  }
  return `?${p.toString()}`;
}
