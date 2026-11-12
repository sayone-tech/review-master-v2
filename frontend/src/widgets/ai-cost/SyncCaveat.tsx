import { useEffect, useState } from "react";
import { fetchSyncStatus } from "../ai-pricing/api";
import type { SyncStatus } from "../ai-pricing/types";

const CAVEAT = "Estimated from configured pricing. The OpenAI invoice is authoritative.";

const DAY_MS = 86_400_000;
const utcDay = (d: Date) => Math.floor(d.getTime() / DAY_MS);

/** Status word for the footer. A failed last run takes precedence, even when sync is off. */
export function syncStatusWord(s: SyncStatus, now: Date = new Date()): string {
  if (s.last_status === "failed") return "sync failed";
  if (s.last_status === "running") return "sync in progress";
  if (!s.enabled) return "sync off";
  if (!s.last_success_at) return "not synced yet";
  const days = utcDay(now) - utcDay(new Date(s.last_success_at));
  if (days <= 0) return "synced today";
  return days === 1 ? "synced 1 day ago" : `synced ${days} days ago`;
}

/** Footer caveat; falls back to the plain text if the sync status is unavailable. */
export function SyncCaveat() {
  const [status, setStatus] = useState<SyncStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSyncStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch(() => {
        /* keep the plain caveat */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status) return <>{CAVEAT}</>;
  return (
    <>
      Estimated from configured pricing ({syncStatusWord(status)}). The OpenAI invoice is
      authoritative.
    </>
  );
}
