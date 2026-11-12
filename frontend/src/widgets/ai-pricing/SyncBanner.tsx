import { useCallback, useEffect, useRef, useState } from "react";
import { ConfirmModal, Modal } from "../modal";
import { ApiError, fetchSyncStatus, toggleSync, triggerSync } from "./api";
import { formatPrice, formatSyncDate, formatSyncDateTime } from "./format";
import type { PriceTriple, SyncStatus } from "./types";

interface Props {
  /** Called after Enable/Disable succeeds (the missing-pricing alert should refetch). */
  onChanged: () => void;
  /** Called with each freshly loaded status. */
  onStatus?: (status: SyncStatus) => void;
  /** "Use LiteLLM price": open Add New Price pre-filled. */
  onUseLiteLLM?: (model: string, prices: PriceTriple) => void;
}

const REFETCH_AFTER_SYNC_MS = 30_000;
const BTN = "px-3 py-1.5 bg-white border border-line rounded-md text-[13px] hover:bg-line-soft disabled:opacity-50";

const triple = (p: PriceTriple) => `${formatPrice(p.input)}/${formatPrice(p.output)}/${formatPrice(p.cached)}`;

export function SyncBanner({ onChanged, onStatus, onUseLiteLLM }: Props) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [details, setDetails] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const req = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onStatusRef = useRef(onStatus);
  onStatusRef.current = onStatus;

  const load = useCallback(() => {
    const mine = ++req.current;
    return fetchSyncStatus()
      .then((s) => {
        if (mine !== req.current) return;
        setStatus(s);
        setLoadError(false);
        onStatusRef.current?.(s);
      })
      .catch(() => {
        if (mine === req.current) setLoadError(true);
      });
  }, []);

  useEffect(() => {
    void load();
    return () => {
      req.current++;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load]);

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
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void load(), REFETCH_AFTER_SYNC_MS);
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.status === 429
          ? "Sync Now can be used once every 15 minutes."
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
  const attention = failed || (!running && status.enabled && status.overdue);
  const tone = attention
    ? "bg-amber-50 border-amber-300"
    : status.enabled && !running
      ? "bg-green-50 border-green-300"
      : "bg-line-soft border-line";

  let text: React.ReactNode;
  if (running) {
    // Sync Now stays available; a second run while this one holds the lock is skipped.
    text = "Sync in progress…";
  } else if (attention) {
    const label = failed
      ? `Last sync failed${status.last_run_at ? ` ${formatSyncDate(status.last_run_at)}` : ""}. Click to view details.`
      : "No successful sync in over 14 days. Click to view details.";
    text = (
      <button type="button" className="underline underline-offset-2 text-left" onClick={() => setDetails(true)}>
        {label}
      </button>
    );
  } else if (status.enabled) {
    text = status.last_success_at
      ? `Automatic pricing sync is on. Last synced: ${formatSyncDateTime(status.last_success_at)}.`
      : "Automatic pricing sync is on. Not synced yet.";
  } else {
    text = "Automatic pricing sync is off. Prices update only when you add them manually.";
  }

  const skipped = status.summary.skipped_manual;
  const concurrent = status.summary.skipped_concurrent ?? [];

  return (
    <section
      className={`${tone} border rounded-card p-4 text-[13.5px] text-ink space-y-2`}
      data-testid="sync-banner"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p>{text}</p>
        <div className="flex items-center gap-2">
          <button type="button" className={BTN} disabled={busy} onClick={() => setConfirming(true)}>
            {status.enabled ? "Disable sync" : "Enable sync"}
          </button>
          <button type="button" className={BTN} disabled={busy} onClick={() => void syncNow()}>
            Sync Now
          </button>
        </div>
      </div>
      {message && (
        <p role="status" className="text-[12.5px] text-muted">
          {message}
        </p>
      )}
      {skipped.length > 0 && (
        <div>
          <p className="font-medium">
            {skipped.length} hand-set {skipped.length === 1 ? "price differs" : "prices differ"} from LiteLLM
          </p>
          <ul className="mt-1 space-y-1">
            {skipped.map((r) => (
              <li key={r.model} className="flex flex-wrap items-center gap-2 text-[12.5px]">
                <span>
                  <code className="font-mono">{r.model}</code>: ours {triple(r.ours)} · LiteLLM {triple(r.litellm)}
                </span>
                <button
                  type="button"
                  className={BTN}
                  onClick={() => onUseLiteLLM?.(r.model, r.litellm)}
                >
                  Use LiteLLM price
                </button>
              </li>
            ))}
          </ul>
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
        confirmLabel={status.enabled ? "Disable sync" : "Enable sync"}
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
                  <code className="font-mono">{m}</code>
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
