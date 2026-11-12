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

const SYNC_DATE = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  month: "short",
  day: "numeric",
  year: "numeric",
});
const SYNC_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** ISO instant -> "Nov 10, 2026" in UTC. */
export function formatSyncDate(iso: string): string {
  return SYNC_DATE.format(new Date(iso));
}

/** ISO instant -> "Nov 10, 2026 at 09:00 UTC". */
export function formatSyncDateTime(iso: string): string {
  const d = new Date(iso);
  return `${SYNC_DATE.format(d)} at ${SYNC_TIME.format(d)} UTC`;
}
