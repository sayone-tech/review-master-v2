import { ORG_TYPE_LABELS } from "../org-management/types";
const countFmt = new Intl.NumberFormat("en-US");

export function formatCost(v: string): string {
  const m = /^(-?)(\d*)(?:\.(\d*))?$/.exec(v.trim());
  if (!m) return v;
  const [, sign, int, frac = ""] = m;
  const grouped = (int || "0").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}$${grouped}.${frac.slice(0, 8).padEnd(8, "0")}`;
}

export function formatCount(n: number): string {
  return countFmt.format(n);
}

function abbrev(n: number, div: number, suffix: string): string {
  return `${(n / div).toFixed(1).replace(/\.0$/, "")}${suffix}`;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return abbrev(n, 1_000_000, "M");
  if (n >= 1_000) return abbrev(n, 1_000, "K");
  return String(n);
}

export function avgPerCall(total: number, calls: number): number {
  return calls === 0 ? 0 : total / calls;
}

export function formatUpdatedAgo(generatedAt: string, now: number = Date.now()): string {
  const mins = Math.floor((now - new Date(generatedAt).getTime()) / 60_000);
  if (!(mins >= 1)) return "Updated just now";
  return `Updated ${mins} min ago`;
}

export function titleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/(^|\s|-)\w/g, (m) => m.toUpperCase());
}

const REQUEST_TYPE_LABELS: Record<string, string> = {
  enrichment: "Enrichment",
  reply_generation: "Reply",
};

export function requestTypeLabel(key: string): string {
  return REQUEST_TYPE_LABELS[key] ?? titleCase(key);
}

export function orgTypeLabel(type: string): string {
  return (ORG_TYPE_LABELS as Record<string, string>)[type] ?? titleCase(type);
}
