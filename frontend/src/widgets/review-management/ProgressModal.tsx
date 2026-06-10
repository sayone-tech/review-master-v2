import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { Modal } from "../modal/Modal";

interface SnapshotState {
  shop_id: number;
  status: "fetching" | "enriching" | "success" | "failed";
  step: "fetching" | "vocab" | "enriching" | "finalising" | "success" | "failed";
  fetched: number;
  total_estimate: number | null;
  enriched: number;
  started_at: string;
  last_update_at: string;
  page_count: number;
  duration_seconds?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  vocab_enriched?: number;
  vocab_total?: number;
  finalising_processed?: number;
  finalising_total?: number;
}

interface Props {
  open: boolean;
  shopId: number;
  shopName: string;
  onClose: () => void;
}

function buildWsUrl(shopId: number): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/sync-progress/${shopId}/`;
}

function pct(num: number, denom: number | null | undefined): number {
  if (!denom || denom <= 0) return 0;
  return Math.min(100, Math.round((num / denom) * 100));
}

function computeEtaMinutes(snap: SnapshotState | null): number | null {
  if (!snap || snap.page_count < 2 || !snap.total_estimate || !snap.started_at) {
    return null;
  }
  const elapsed = (Date.now() - new Date(snap.started_at).getTime()) / 1000;
  const ratePerSec = snap.fetched > 0 ? snap.fetched / elapsed : 0;
  if (ratePerSec <= 0) return null;
  const remaining = snap.total_estimate - snap.fetched;
  if (remaining <= 0) return 0;
  return Math.max(1, Math.round(remaining / ratePerSec / 60));
}

export function ProgressModal({ open, shopId, shopName, onClose }: Props) {
  const [snapshot, setSnapshot] = useState<SnapshotState | null>(null);
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const wsRef = useRef<WebSocket | null>(null);

  // WebSocket lifecycle
  useEffect(() => {
    if (!open || !shopId) return;
    const ws = new WebSocket(buildWsUrl(shopId));
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "sync.fetch.progress") {
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  step: "fetching",
                  fetched: data.fetched,
                  total_estimate: data.total_estimate ?? prev.total_estimate,
                  last_update_at: new Date().toISOString(),
                  page_count: prev.page_count + 1,
                }
              : {
                  shop_id: shopId,
                  status: "fetching",
                  step: "fetching",
                  fetched: data.fetched,
                  total_estimate: data.total_estimate ?? null,
                  enriched: 0,
                  started_at: new Date().toISOString(),
                  last_update_at: new Date().toISOString(),
                  page_count: 1,
                },
          );
        } else if (data.type === "sync.vocab.progress") {
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  step: "vocab",
                  vocab_enriched: data.enriched,
                  vocab_total: data.total,
                  last_update_at: new Date().toISOString(),
                }
              : null,
          );
        } else if (data.type === "sync.enrichment.progress") {
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  step: "enriching",
                  enriched: data.enriched,
                  status: prev.fetched > 0 && data.enriched >= prev.fetched ? "success" : "enriching",
                  last_update_at: new Date().toISOString(),
                }
              : null,
          );
        } else if (data.type === "sync.finalising.progress") {
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  step: "finalising",
                  finalising_processed: data.processed,
                  finalising_total: data.total,
                  last_update_at: new Date().toISOString(),
                }
              : null,
          );
        } else if (data.type === "sync.complete") {
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  status: "success",
                  step: "success",
                  fetched: data.total_fetched,
                  enriched: data.total_enriched ?? 0,
                  duration_seconds: data.duration_seconds,
                  last_update_at: new Date().toISOString(),
                }
              : null,
          );
        } else if (data.type === "sync.error") {
          setSnapshot((prev) => ({
            shop_id: prev?.shop_id ?? shopId,
            status: "failed",
            step: "failed",
            fetched: prev?.fetched ?? 0,
            total_estimate: prev?.total_estimate ?? null,
            enriched: prev?.enriched ?? 0,
            started_at: prev?.started_at ?? new Date().toISOString(),
            last_update_at: new Date().toISOString(),
            page_count: prev?.page_count ?? 0,
            error_code: data.error_code,
            error_message: data.error_message,
          }));
        } else if (typeof data.status === "string") {
          // Initial snapshot from consumer.connect
          setSnapshot(data as SnapshotState);
        }
      } catch {
        // ignore malformed messages
      }
    };
    ws.onerror = () => {
      // Network error — keep last snapshot; user can dismiss.
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [open, shopId]);

  // Last-update tick
  useEffect(() => {
    if (!snapshot) {
      setSecondsAgo(0);
      return;
    }
    const tick = () => {
      const last = new Date(snapshot.last_update_at).getTime();
      setSecondsAgo(Math.max(0, Math.round((Date.now() - last) / 1000)));
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [snapshot]);

  const status = snapshot?.status ?? "fetching";
  const currentStep = snapshot?.step ?? "fetching";
  const fetched = snapshot?.fetched ?? 0;
  const total = snapshot?.total_estimate ?? null;
  // When total is known, show a determinate percentage bar.
  // When total is null (date-bounded sync), show an indeterminate pulse bar.
  const fetchPct = pct(fetched, total);
  const hasDeterminate = total != null;
  const enrichPct = pct(snapshot?.enriched ?? 0, fetched || 1);
  const eta = computeEtaMinutes(snapshot);
  const isComplete = status === "success";
  const isError = status === "failed";

  // Step ordering for determining active/pending/complete states
  const stepOrder: Array<SnapshotState["step"]> = ["fetching", "vocab", "enriching", "finalising", "success", "failed"];
  const currentStepIndex = stepOrder.indexOf(currentStep);

  function getStepState(stepName: "fetching" | "vocab" | "enriching" | "finalising"): "pending" | "active" | "complete" {
    const stepIdx = stepOrder.indexOf(stepName);
    if (isError) {
      // In error state, show steps up to current as complete/active, rest pending
      if (stepIdx < currentStepIndex) return "complete";
      if (stepIdx === currentStepIndex) return "active";
      return "pending";
    }
    if (isComplete) return "complete";
    if (stepIdx < currentStepIndex) return "complete";
    if (stepIdx === currentStepIndex) return "active";
    return "pending";
  }

  const footer = (
    <div className="flex items-center justify-between w-full">
      {!isComplete && !isError ? (
        <button
          type="button"
          onClick={() => {
            window.dispatchEvent(
              new CustomEvent("sync:shop-moved-to-background", {
                detail: { shop_id: shopId, shop_name: shopName },
              }),
            );
            onClose();
          }}
          aria-label="Run sync in background and close this dialog"
          className="text-[14px] text-muted underline hover:text-ink"
        >
          Run in background
        </button>
      ) : (
        <span />
      )}
      <button
        type="button"
        onClick={() => {
          window.location.href = "/admin/org/shops/";
        }}
        disabled={!isComplete && !isError}
        aria-disabled={!isComplete && !isError}
        className={
          "bg-white text-ink border border-line px-4 py-2 text-[14px] font-semibold rounded-md " +
          (!isComplete && !isError
            ? "opacity-40 cursor-not-allowed pointer-events-none"
            : "hover:bg-line-soft")
        }
      >
        View Shop Details
      </button>
    </div>
  );

  // Step 1: Fetching Reviews
  const fetchState = getStepState("fetching");
  // Step 2: Building Tag Vocabulary
  const vocabState = getStepState("vocab");
  const vocabEnriched = snapshot?.vocab_enriched ?? 0;
  const vocabTotal = snapshot?.vocab_total ?? null;
  const vocabPct = pct(vocabEnriched, vocabTotal);
  // Step 3: AI Enrichment
  const enrichState = getStepState("enriching");
  // Step 4: Finalising
  const finalisingState = getStepState("finalising");
  const finalisingProcessed = snapshot?.finalising_processed ?? 0;
  const finalisingTotal = snapshot?.finalising_total ?? null;
  const finalisingPct = pct(finalisingProcessed, finalisingTotal);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Syncing ${shopName} Reviews`}
      subtitle="We're fetching your reviews from Google. This may take a few minutes."
      size="lg"
      dismissible
      footer={footer}
    >
      <div className="px-6 pb-6 space-y-5">
        {isError ? (
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <AlertTriangle size={20} className="text-red mt-0.5" aria-hidden="true" />
              <div>
                <h3 className="text-[14px] font-semibold text-ink">Sync paused</h3>
                <p className="text-[14px] text-muted">
                  {snapshot?.error_code === "invalid_grant"
                    ? "Your Google connection has expired."
                    : "We'll retry automatically. Click Reconnect Google if you've revoked access."}
                </p>
              </div>
            </div>
            {snapshot?.error_code === "invalid_grant" && (
              <button
                type="button"
                onClick={() => {
                  window.location.href = "/admin/org/shops/";
                }}
                className="bg-white text-ink border border-line hover:bg-line-soft px-4 py-2 text-[14px] font-semibold rounded-md"
              >
                Reconnect Google
              </button>
            )}
          </div>
        ) : isComplete ? (
          <div className="flex items-start gap-2">
            <CheckCircle size={20} className="text-green mt-0.5" aria-hidden="true" />
            <div>
              <h3 className="text-[14px] font-semibold text-ink">Sync complete</h3>
              <p className="text-[14px] text-muted">
                Fetched {snapshot?.fetched ?? 0} reviews
                {snapshot?.duration_seconds != null
                  ? ` in ${Math.round(snapshot.duration_seconds)}s`
                  : ""}.
              </p>
            </div>
          </div>
        ) : (
          <div aria-live="polite" className="space-y-5">
            {/* Step 1: Fetching Reviews */}
            {fetchState === "pending" ? (
              <div className="opacity-60">
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Fetched from Google
                </label>
                <div className="text-[14px] text-muted mt-1">–</div>
                <div
                  className="w-full h-2 bg-line rounded-full mt-2"
                  role="progressbar"
                  aria-label="Fetching Reviews: not started"
                />
              </div>
            ) : fetchState === "complete" ? (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Fetched from Google
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {fetched} reviews fetched
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Fetching Reviews: 100%"
                >
                  <div className="h-full bg-yellow rounded-full transition-all" style={{ width: "100%" }} />
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Fetched from Google
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {hasDeterminate ? (
                    <>{fetched} of ~{total}</>
                  ) : (
                    <>{fetched} fetched</>
                  )}
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={hasDeterminate ? fetchPct : undefined}
                  aria-valuemin={0}
                  aria-valuemax={hasDeterminate ? 100 : undefined}
                  aria-label={
                    hasDeterminate
                      ? `Fetched from Google: ${fetchPct}%`
                      : `Fetching from Google: ${fetched} reviews so far`
                  }
                >
                  {hasDeterminate ? (
                    <div
                      className="h-full bg-yellow rounded-full transition-all"
                      style={{ width: `${fetchPct}%` }}
                    />
                  ) : (
                    /* Indeterminate bar for date-bounded syncs where the total is unknown */
                    <div className="h-full w-1/3 bg-yellow rounded-full animate-pulse" />
                  )}
                </div>
                {hasDeterminate && eta != null && (
                  <div className="text-[12px] text-muted mt-1">
                    About {eta} minute{eta === 1 ? "" : "s"} left
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Building Tag Vocabulary */}
            {vocabState === "pending" ? (
              <div className="opacity-60">
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Building Tag Vocabulary
                </label>
                <div className="text-[14px] text-muted mt-1">–</div>
                <div
                  className="w-full h-2 bg-line rounded-full mt-2"
                  role="progressbar"
                  aria-label="Building Tag Vocabulary: not started"
                />
              </div>
            ) : vocabState === "complete" ? (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Building Tag Vocabulary
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {vocabEnriched} reviews seeded
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Building Tag Vocabulary: 100%"
                >
                  <div className="h-full bg-green rounded-full transition-all" style={{ width: "100%" }} />
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Building Tag Vocabulary
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {vocabTotal != null
                    ? `Building vocabulary ${vocabEnriched}/${vocabTotal}`
                    : `Building vocabulary ${vocabEnriched}`}
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={vocabTotal != null ? vocabPct : undefined}
                  aria-valuemin={0}
                  aria-valuemax={vocabTotal != null ? 100 : undefined}
                  aria-label={
                    vocabTotal != null
                      ? `Building Tag Vocabulary: ${vocabPct}%`
                      : "Building Tag Vocabulary: in progress"
                  }
                >
                  {vocabTotal != null ? (
                    <div
                      className="h-full bg-green rounded-full transition-all"
                      style={{ width: `${vocabPct}%` }}
                    />
                  ) : (
                    <div className="h-full w-1/3 bg-green rounded-full animate-pulse" />
                  )}
                </div>
                {vocabEnriched === 0 && (
                  <div className="text-[12px] text-muted mt-1">Seeding vocabulary…</div>
                )}
              </div>
            )}

            {/* Step 3: AI Enrichment */}
            {enrichState === "pending" ? (
              <div className="opacity-60">
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Analysing with Review Bee AI Engine
                </label>
                <div className="text-[14px] text-muted mt-1">–</div>
                <div
                  className="w-full h-2 bg-line rounded-full mt-2"
                  role="progressbar"
                  aria-label="AI Enrichment: not started"
                />
              </div>
            ) : enrichState === "complete" ? (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Analysing with Review Bee AI Engine
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {snapshot?.enriched ?? 0} of {fetched} enriched
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="AI Enrichment: 100%"
                >
                  <div className="h-full bg-green rounded-full transition-all" style={{ width: "100%" }} />
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Analysing with Review Bee AI Engine
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {snapshot?.enriched ?? 0} of {fetched}
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={enrichPct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Review Bee AI Engine: ${enrichPct}%`}
                >
                  <div
                    className="h-full bg-green rounded-full transition-all"
                    style={{ width: `${enrichPct}%` }}
                  />
                </div>
                {(snapshot?.enriched ?? 0) === 0 && (
                  <div className="text-[12px] text-muted mt-1">
                    Starting AI analysis…
                  </div>
                )}
              </div>
            )}

            {/* Step 4: Finalising */}
            {finalisingState === "pending" ? (
              <div className="opacity-60">
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Finalising
                </label>
                <div className="text-[14px] text-muted mt-1">–</div>
                <div
                  className="w-full h-2 bg-line rounded-full mt-2"
                  role="progressbar"
                  aria-label="Finalising: not started"
                />
              </div>
            ) : finalisingState === "complete" ? (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Finalising
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">Done</div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Finalising: 100%"
                >
                  <div className="h-full bg-amber rounded-full transition-all" style={{ width: "100%" }} />
                </div>
              </div>
            ) : (
              <div>
                <label className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]">
                  Finalising
                </label>
                <div className="text-[14px] font-semibold text-ink mt-1">
                  {finalisingTotal != null
                    ? `Finalising ${finalisingProcessed}/${finalisingTotal}`
                    : `Finalising ${finalisingProcessed}`}
                </div>
                <div
                  className="w-full h-2 bg-line rounded-full overflow-hidden mt-2"
                  role="progressbar"
                  aria-valuenow={finalisingTotal != null ? finalisingPct : undefined}
                  aria-valuemin={0}
                  aria-valuemax={finalisingTotal != null ? 100 : undefined}
                  aria-label={
                    finalisingTotal != null
                      ? `Finalising: ${finalisingPct}%`
                      : "Finalising: in progress"
                  }
                >
                  {finalisingTotal != null ? (
                    <div
                      className="h-full bg-amber rounded-full transition-all"
                      style={{ width: `${finalisingPct}%` }}
                    />
                  ) : (
                    <div className="h-full w-1/3 bg-amber rounded-full animate-pulse" />
                  )}
                </div>
                {finalisingProcessed === 0 && (
                  <div className="text-[12px] text-muted mt-1">Deduplicating tags…</div>
                )}
              </div>
            )}

            <div className="text-[12px] text-muted">
              Last updated {secondsAgo} second{secondsAgo === 1 ? "" : "s"} ago
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
