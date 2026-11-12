import type { PriceSource } from "./types";

/** "0.15000000" -> "$0.150000" (6 dp, matching the stored precision shown to admins). */
export function formatPrice(v: string): string {
  return `$${Number(v).toFixed(6)}`;
}

/** ISO instant -> "YYYY-MM-DD" in UTC. */
export function formatDate(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

/** ISO instant -> "YYYY-MM-DD HH:MM UTC". */
export function formatDateTime(iso: string): string {
  return `${new Date(iso).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

const SOURCE_LABELS: Record<PriceSource, string> = {
  manual: "Manual",
  sync: "LiteLLM sync",
  seed: "Seed",
};

export function sourceLabel(source: PriceSource): string {
  return SOURCE_LABELS[source];
}
