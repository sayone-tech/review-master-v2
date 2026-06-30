// Phase 25-03 — Banner showing merge job progress (HTTP-polled, 2s).
// States: in-progress, pending (queued), success (auto-dismissed + toast), failure (rollback).

import { useEffect, useRef } from "react";
import { AlertCircle, Loader2, X } from "lucide-react";
import { emitToast } from "../../lib/toast";
import type { TagMergeJobRow } from "./types";

interface Props {
  job: TagMergeJobRow;
  onDismiss: () => void;
  onComplete: () => void; // called on SUCCESS to trigger table refetch
}

export function MergeProgressBanner({ job, onDismiss, onComplete }: Props) {
  const completedRef = useRef(false);

  // On SUCCESS: emit toast and trigger table refetch (only once)
  useEffect(() => {
    if (job.status === "SUCCESS" && !completedRef.current) {
      completedRef.current = true;
      emitToast({
        kind: "success",
        title: "Merge complete",
        msg: `"${job.source_label}" merged into "${job.target_label}".`,
      });
      onComplete();
      onDismiss(); // auto-hide the banner
    }
  }, [job.status, job.source_label, job.target_label, onComplete, onDismiss]);

  if (job.status === "SUCCESS") {
    // Already handled via useEffect above; return null while dismissal propagates
    return null;
  }

  if (job.status === "FAILED") {
    return (
      <div
        role="alert"
        className="rounded-card border border-red bg-red-tint p-4 flex flex-col gap-3"
      >
        <div className="flex items-start gap-3">
          <AlertCircle size={16} className="text-red mt-1 shrink-0" aria-hidden="true" />
          <div className="flex-1 min-w-0">
            <span className="text-[14px] font-semibold text-red">
              Merge failed — changes rolled back
            </span>
            <p className="text-[12px] text-muted mt-1">
              {job.error_message ||
                "Something went wrong. The merge was rolled back. No reviews were affected."}
            </p>
          </div>
          <button
            type="button"
            aria-label="Dismiss error"
            onClick={onDismiss}
            className="w-7 h-7 rounded-sm text-red hover:bg-red/10 flex items-center justify-center shrink-0"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  }

  // PENDING or IN_PROGRESS
  const isPending = job.status === "PENDING";
  const pct =
    job.processed != null && job.total != null && job.total > 0
      ? Math.round((job.processed / job.total) * 100)
      : null;

  const subLabel = isPending
    ? "Queued — waiting to start"
    : pct != null
      ? `Re-mapping "${job.source_label}" → "${job.target_label}" · ${job.processed ?? 0}/${job.total ?? 0} reviews`
      : `Re-mapping "${job.source_label}" → "${job.target_label}" · starting…`;

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-card border border-line bg-white p-4 flex flex-col gap-3"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Loader2 size={16} className="animate-spin text-muted" aria-hidden="true" />
          <span className="text-[14px] font-semibold text-ink">Merging tags…</span>
        </div>
        <button
          type="button"
          aria-label="Dismiss merge progress"
          onClick={onDismiss}
          className="w-7 h-7 rounded-sm text-muted hover:bg-line-soft hover:text-ink flex items-center justify-center"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>

      <div>
        <div className="text-[12px] text-subtle mb-1">{subLabel}</div>
        {pct != null ? (
          <div
            className="w-full h-2 bg-line rounded-full overflow-hidden"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Merge progress: ${pct}%`}
          >
            <div
              className="h-full bg-yellow rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : (
          <div
            className="w-full h-2 bg-line rounded-full overflow-hidden"
            role="progressbar"
            aria-label="Merge progress: starting"
          >
            <div className="h-full w-1/3 bg-yellow rounded-full animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
