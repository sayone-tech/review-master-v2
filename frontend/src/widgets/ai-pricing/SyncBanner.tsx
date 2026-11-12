import { useCallback, useEffect, useRef, useState } from "react";
import { ConfirmModal, Modal } from "../modal";
import { ApiError, fetchSyncStatus, toggleSync, triggerSync } from "./api";
import { Badge, type BadgeTone } from "../ai-cost/PageHeader";
import { Money } from "../ai-cost/Money";
import { formatPrice, formatSyncDate, formatSyncDateTime } from "./format";
import type { PriceTriple, SyncStatus } from "./types";

interface Props {
  /** Called after Enable/Disable succeeds (the missing-pricing alert should refetch). */
  onChanged: () => void;
  /** Called with each freshly loaded status. */
  onStatus?: (status: SyncStatus) => void;
  /** "Use LiteLLM price": open the add-price modal pre-filled. */
  onUseLiteLLM?: (model: string, prices: PriceTriple) => void;
  /** Bump to reload the status (e.g. after a price save changed the skipped-manual list). */
  refreshKey?: number;
}

const POLL_INTERVAL_MS = 10_000;
const POLL_MAX_TICKS = 12; // 2 minutes
const BTN =
  "px-2.5 py-[5px] bg-white text-ink border border-line rounded-sm text-[12.5px] font-medium hover:bg-line-soft hover:border-[#D4D4D8] disabled:opacity-50 disabled:cursor-not-allowed";
const LINK_BTN = "rounded-sm font-medium text-ink underline underline-offset-2 hover:no-underline";

function Triple({ p }: { p: PriceTriple }) {
  return (
    <>
      <Money value={formatPrice(p.input)} /> / <Money value={formatPrice(p.output)} /> /{" "}
      <Money value={formatPrice(p.cached)} />
    </>
  );
}

export function SyncBanner({ onChanged, onStatus, onUseLiteLLM, refreshKey = 0 }: Props) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [details, setDetails] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const req = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;
  const onChangedRef = useRef(onChanged);
  onChangedRef.current = onChanged;
  const statusRef = useRef<SyncStatus | null>(null);
  statusRef.current = status;

  const load = useCallback(() => {
    const mine = ++req.current;
    return fetchSyncStatus()
      .then((s): SyncStatus | null => {
        if (mine !== req.current) return null;
        setStatus(s);
        setLoadError(false);
        onStatusRef.current?.(s);
        return s;
      })
      .catch((): null => {
        if (mine === req.current) setLoadError(true);
        return null;
      });
  }, []);

  const pollGen = useRef(0);
  const stopPolling = useCallback(() => {
    pollGen.current++;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  // One poller at a time: every Sync Now click restarts it. It stops once the run has settled
  // (seen running, or last_run_at moved, and is no longer running) or after two minutes.
  const startPolling = useCallback(() => {
    stopPolling();
    const gen = pollGen.current;
    const baseline = statusRef.current?.last_run_at ?? null;
    let seenRunning = false;
    let ticks = 0;
    const tick = async () => {
      ticks += 1;
      const s = await load();
      if (gen !== pollGen.current) return; // stopped, restarted or unmounted mid-request
      if (s) {
        if (s.last_status === "running") seenRunning = true;
        else if (seenRunning || s.last_run_at !== baseline) {
          stopPolling();
          onChangedRef.current();
          return;
        }
      }
      if (ticks >= POLL_MAX_TICKS) {
        stopPolling();
        return;
      }
      timer.current = setTimeout(() => void tick(), POLL_INTERVAL_MS);
    };
    timer.current = setTimeout(() => void tick(), POLL_INTERVAL_MS);
  }, [load, stopPolling]);

  useEffect(() => {
    void load();
    return () => {
      req.current++;
      stopPolling();
    };
  }, [load, stopPolling]);

  const firstRefresh = useRef(true);
  useEffect(() => {
    if (firstRefresh.current) {
      firstRefresh.current = false;
      return;
    }
    void load();
  }, [refreshKey, load]);

  const confirmToggle = async () => {
    if (!status || busy) return;
    setConfirming(false);
    setBusy(true);
    setMessage(null);
    try {
      const next = await toggleSync(!status.enabled);
      req.current++; // supersede any in-flight status fetch
      setStatus(next);
      onStatusRef.current?.(next);
      onChanged();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not change the sync setting.");
    } finally {
      setBusy(false);
    }
  };

  const syncNow = async () => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await triggerSync();
      setMessage("Sync started. Refresh in a minute to see results.");
      startPolling();
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.status === 429
          ? "Sync now can be used once every 15 minutes."
          : "Could not start the sync.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return loadError ? (
      <div role="alert" className="text-[13px] text-red">
        Could not load the pricing sync status.{" "}
        <button type="button" className="underline" onClick={() => void load()}>
          Retry
        </button>
      </div>
    ) : null;
  }

  const failed = status.last_status === "failed";
  const running = status.last_status === "running";
  const overdue = !failed && !running && status.enabled && status.overdue;

  // One badge for the most important state; the toggle button carries on/off when they differ.
  let badge: [BadgeTone, string];
  if (running) badge = ["blue", "Syncing"];
  else if (failed) badge = ["amber", "Failed"];
  else if (overdue) badge = ["amber", "Overdue"];
  else if (status.enabled) badge = ["green", "On"];
  else badge = ["gray", "Off"];

  let text: React.ReactNode;
  if (running) {
    // Sync now stays available; a second run while this one holds the lock is skipped.
    text = "Sync in progress…";
  } else if (failed || overdue) {
    text = (
      <>
        {failed
          ? `Last sync failed${status.last_run_at ? ` ${formatSyncDate(status.last_run_at)}` : ""}.`
          : "No successful sync in over 14 days."}{" "}
        <button type="button" className={LINK_BTN} onClick={() => setDetails(true)}>
          View details
        </button>
      </>
    );
  } else if (status.enabled) {
    const next = status.next_run_at ? ` Next sync ${formatSyncDateTime(status.next_run_at)}.` : "";
    text = status.last_success_at
      ? `Last synced ${formatSyncDateTime(status.last_success_at)}.${next}`
      : `Not synced yet.${next}`;
  } else {
    text = "Prices change only when you add them.";
  }

  const skipped = status.summary.skipped_manual;
  const concurrent = status.summary.skipped_concurrent ?? [];
  const toggleLabel = status.enabled ? "Turn off" : "Turn on";

  return (
    <section
      className="rounded-card border border-line bg-white px-4 py-3 text-[13.5px] text-ink"
      aria-label="Automatic pricing sync"
      data-testid="sync-banner"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="font-medium">Automatic pricing sync</span>
          <Badge tone={badge[0]} dot>
            {badge[1]}
          </Badge>
          <span className="text-muted" data-testid="sync-status-text">
            {text}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className={BTN} disabled={busy} onClick={() => void syncNow()}>
            Sync now
          </button>
          <button
            type="button"
            className={BTN}
            disabled={busy}
            aria-label={`${toggleLabel} automatic pricing sync`}
            onClick={() => setConfirming(true)}
          >
            {toggleLabel}
          </button>
        </div>
      </div>
      {message && (
        <p role="status" className="mt-1.5 text-[12.5px] text-muted">
          {message}
        </p>
      )}
      {skipped.length > 0 && (
        <div className="mt-2 border-t border-line-soft pt-2 text-[12.5px]">
          <p className="text-muted">
            {skipped.length} hand-set {skipped.length === 1 ? "price differs" : "prices differ"} from
            LiteLLM.{" "}
            <button
              type="button"
              className={LINK_BTN}
              aria-expanded={reviewOpen}
              aria-controls="sync-skipped-manual"
              onClick={() => setReviewOpen((o) => !o)}
            >
              {reviewOpen ? "Hide" : "Review"}
            </button>
          </p>
          {reviewOpen && (
            <div id="sync-skipped-manual" className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr className="text-left text-[12px] text-muted">
                    <th scope="col" className="py-1 pr-4 font-medium">Model</th>
                    <th scope="col" className="py-1 pr-4 font-medium">Ours (input / output / cached)</th>
                    <th scope="col" className="py-1 pr-4 font-medium">LiteLLM</th>
                    <th scope="col" className="py-1 font-medium"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {skipped.map((r) => (
                    <tr key={r.model} className="border-t border-line-soft">
                      <td className="py-1.5 pr-4 font-medium">{r.model}</td>
                      <td className="py-1.5 pr-4 whitespace-nowrap"><Triple p={r.ours} /></td>
                      <td className="py-1.5 pr-4 whitespace-nowrap"><Triple p={r.litellm} /></td>
                      <td className="py-1.5 text-right">
                        <button
                          type="button"
                          className={BTN}
                          onClick={() => onUseLiteLLM?.(r.model, r.litellm)}
                        >
                          Use LiteLLM price
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <ConfirmModal
        open={confirming}
        onClose={() => setConfirming(false)}
        onConfirm={() => void confirmToggle()}
        variant="blue"
        title="Automatic pricing sync"
        message={
          status.enabled
            ? "Turn off automatic pricing sync?"
            : "Turn on automatic pricing sync? Prices for models you use will update every Monday 09:00 UTC. Hand-set prices are never changed."
        }
        confirmLabel={toggleLabel}
      />
      <Modal
        open={details}
        onClose={() => setDetails(false)}
        title="Sync details"
        size="sm"
        footer={
          <button type="button" className={BTN} onClick={() => setDetails(false)}>
            Close
          </button>
        }
      >
        <div className="space-y-2 text-[13.5px]">
          <p>
            Last run: {status.last_run_at ? formatSyncDateTime(status.last_run_at) : "never"}
          </p>
          <p className="font-mono text-[12.5px] break-words">{status.last_error || "No error recorded."}</p>
          {concurrent.length > 0 && (
            <p data-testid="sync-skipped-concurrent">
              Skipped because the price changed at the same time:{" "}
              {concurrent.map((m, i) => (
                <span key={m}>
                  {i > 0 && ", "}
                  <span className="font-medium">{m}</span>
                </span>
              ))}
              . The next sync will retry.
            </p>
          )}
        </div>
      </Modal>
    </section>
  );
}
