// Phase 25-03 — Two-step merge modal for canonical tags.
// Step 1 "pick": searchable target picker; Step 2 "confirm": irreversibility warning.
// Clones the MergeModal.tsx pick/confirm state machine pattern.

import { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ApiError, fetchTags, startMerge } from "./api";
import { PolarityBadge } from "./PolarityBadge";
import type { OrgCanonicalTagRow } from "./types";

function extractMergeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return "A merge is already in progress. Wait for it to complete before starting another.";
    }
    const data = err.data as Record<string, unknown> | null;
    if (data) {
      const detail = typeof data.detail === "string" && data.detail;
      if (detail) return detail;
    }
  }
  return "Could not start the merge. Please try again.";
}

interface Props {
  open: boolean;
  source: OrgCanonicalTagRow | null;
  onClose: () => void;
  onJobStarted: (jobId: number) => void;
}

export function TagMergeModal({ open, source, onClose, onJobStarted }: Props) {
  const [step, setStep] = useState<"pick" | "confirm">("pick");
  const [targetId, setTargetId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [allTags, setAllTags] = useState<OrgCanonicalTagRow[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset on open (mirrors MergeModal.tsx pattern)
  useEffect(() => {
    if (open) {
      setStep("pick");
      setTargetId(null);
      setSearchQuery("");
      setAllTags([]);
      setSubmitting(false);
      setError(null);
    }
  }, [open]);

  // Fetch tags when modal opens (step 1)
  useEffect(() => {
    if (!open || !source) return;
    setTagsLoading(true);
    fetchTags({ page_size: 200 })
      .then((data) => {
        // Exclude the source tag
        setAllTags(data.results.filter((t) => t.id !== source.id));
      })
      .catch(() => {
        setAllTags([]);
      })
      .finally(() => setTagsLoading(false));
  }, [open, source]);

  const filteredTags = searchQuery.trim()
    ? allTags.filter((t) =>
        t.label.toLowerCase().includes(searchQuery.trim().toLowerCase()),
      )
    : allTags;

  const targetTag = allTags.find((t) => t.id === targetId) ?? null;

  const handleConfirm = async () => {
    if (!source || targetId === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await startMerge(source.id, targetId);
      onJobStarted(result.job_id);
      onClose();
    } catch (err) {
      setError(extractMergeError(err));
      setSubmitting(false);
    }
  };

  const footer =
    step === "pick" ? (
      <>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-[14px] bg-white text-ink border border-line rounded-md font-normal hover:bg-line-soft"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={targetId === null}
          onClick={() => setStep("confirm")}
          className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {targetId === null
            ? "Select a target tag"
            : `Merge into "${targetTag?.label ?? ""}" →`}
        </button>
      </>
    ) : (
      <>
        <button
          type="button"
          disabled={submitting}
          onClick={() => setStep("pick")}
          className="px-4 py-2 text-[14px] bg-white text-ink border border-line rounded-md font-normal hover:bg-line-soft disabled:opacity-50"
        >
          ← Back
        </button>
        <button
          type="button"
          disabled={submitting}
          aria-busy={submitting}
          onClick={() => void handleConfirm()}
          className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Starting merge…" : "Confirm merge"}
        </button>
      </>
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Merge tag"
      subtitle={source ? `"${source.label}"` : undefined}
      footer={footer}
      dismissible={!submitting}
    >
      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 border-l-4 border-red bg-red-tint text-red rounded-md px-4 py-2 mb-4"
        >
          <AlertCircle size={16} className="mt-1 shrink-0" aria-hidden="true" />
          <span className="text-[12px]">{error}</span>
        </div>
      )}

      {step === "pick" ? (
        <div className="space-y-4">
          <div>
            <h3
              id="merge-target-section"
              className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted"
            >
              Merge into
            </h3>
            <p className="text-[14px] text-muted mt-1">
              All {source?.review_count ?? 0} reviews tagged &ldquo;{source?.label}&rdquo; will be
              re-tagged with the target. The source tag will be deleted. This cannot be undone.
            </p>
          </div>

          <input
            type="search"
            placeholder="Search tags…"
            aria-label="Search tags"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 px-3 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:border-yellow focus:ring-1 focus:ring-yellow/40"
          />

          <div
            role="radiogroup"
            aria-labelledby="merge-target-section"
            className="max-h-[240px] overflow-y-auto border border-line rounded-md divide-y divide-line-soft"
          >
            {tagsLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={`sk-${i}`}
                    className="flex items-center gap-3 px-3 py-2"
                  >
                    <span className="w-4 h-4 bg-line rounded-sm animate-sk-pulse inline-block" />
                    <div className="flex-1 space-y-1">
                      <span
                        className="inline-block bg-line rounded-sm animate-sk-pulse h-3"
                        style={{ width: "140px" }}
                      />
                      <span
                        className="inline-block bg-line rounded-sm animate-sk-pulse h-3"
                        style={{ width: "60px" }}
                      />
                    </div>
                  </div>
                ))
              : filteredTags.length === 0
                ? (
                    <p className="text-[14px] text-muted px-3 py-4">No tags match.</p>
                  )
                : filteredTags.map((tag) => {
                    const selected = tag.id === targetId;
                    return (
                      <label
                        key={tag.id}
                        className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-line-soft ${
                          selected ? "border-yellow bg-yellow-tint" : ""
                        }`}
                      >
                        <input
                          type="radio"
                          name="merge-target"
                          value={tag.id}
                          checked={selected}
                          onChange={() => setTargetId(tag.id)}
                          className="w-4 h-4 accent-[#FACC15] cursor-pointer"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-[14px] text-ink truncate">{tag.label}</div>
                          <div className="text-[12px] text-muted">{tag.review_count} reviews</div>
                        </div>
                        <PolarityBadge polarity={tag.polarity_type} />
                      </label>
                    );
                  })}
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-[12px] bg-red-tint flex items-center justify-center shrink-0">
            <AlertTriangle size={22} className="text-red" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-[18px] font-semibold text-ink mb-2">Confirm merge</h3>
            <p className="text-[14px] text-muted leading-[1.5]">
              Re-map {source?.review_count ?? 0} reviews from &ldquo;{source?.label}&rdquo; to
              &ldquo;{targetTag?.label}&rdquo;? The source tag will be permanently deleted. This
              cannot be undone.
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
}
