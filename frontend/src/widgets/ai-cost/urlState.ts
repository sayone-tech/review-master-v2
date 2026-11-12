import { PAGE_SIZES, type CostFilters, type RangeKey } from "./types";

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

/** Sort / paging state of the platform org list, kept in the URL so Back restores it. */
export interface ListState {
  sort: string;
  page: number;
  pageSize: number;
}

export const DEFAULT_LIST: ListState = { sort: "-cost", page: 1, pageSize: 25 };

export function readListState(search: string): ListState {
  const p = new URLSearchParams(search);
  const page = Number(p.get("page"));
  const pageSize = Number(p.get("page_size"));
  return {
    sort: p.get("sort") || DEFAULT_LIST.sort,
    page: Number.isInteger(page) && page >= 1 ? page : DEFAULT_LIST.page,
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize)
      ? pageSize
      : DEFAULT_LIST.pageSize,
  };
}

/** `writeFilters` plus any non-default list state. */
export function writeUrlState(f: CostFilters, list: ListState = DEFAULT_LIST): string {
  const p = new URLSearchParams(writeFilters(f).slice(1));
  if (list.sort !== DEFAULT_LIST.sort) p.set("sort", list.sort);
  if (list.page !== DEFAULT_LIST.page) p.set("page", String(list.page));
  if (list.pageSize !== DEFAULT_LIST.pageSize) p.set("page_size", String(list.pageSize));
  return `?${p.toString()}`;
}
