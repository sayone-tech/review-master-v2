import { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ApiError, mergeActionItems } from "./api";
import { emitToast } from "../../lib/toast";
import type { ActionItemListRow } from "./types";

function extractErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const data = err.data;
    if (Array.isArray(data) && typeof data[0] === "string") return data[0];
    if (data && typeof data === "object") {
      const obj = data as Record<string, unknown>;
      const candidate =
        (typeof obj.detail === "string" && obj.detail) ||
        (Array.isArray(obj.non_field_errors) &&
          typeof obj.non_field_errors[0] === "string" &&
          (obj.non_field_errors[0] as string)) ||
        (typeof obj.message === "string" && obj.message);
      if (candidate) return candidate;
    }
  }
  return "Could not merge items. Please try again.";
}

interface Props {
  open: boolean;
  selectedItems: ActionItemListRow[];
  onClose: () => void;
  onMerged: () => void;
}

export function MergeModal({ open, selectedItems, onClose, onMerged }: Props) {
  const [primaryId, setPrimaryId] = useState<number | null>(null);
  const [step, setStep] = useState<"pick" | "confirm">("pick");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset internal state whenever the modal transitions to open.
  useEffect(() => {
    if (open) {
      setPrimaryId(null);
      setStep("pick");
      setSaving(false);
      setError(null);
    }
  }, [open]);

  const primaryItem = selectedItems.find((i) => i.id === primaryId) ?? null;

  const handleMergeConfirm = async () => {
    if (primaryId === null) return;
    setSaving(true);
    setError(null);
    try {
      const duplicate_ids = selectedItems
        .filter((i) => i.id !== primaryId)
        .map((i) => i.id);
      await mergeActionItems({ primary_id: primaryId, duplicate_ids });
      emitToast({ kind: "success", title: "Items merged successfully" });
      onMerged();
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err));
      setSaving(false);
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
          onClick={() => setStep("confirm")}
          disabled={primaryId === null}
          className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Merge items
        </button>
      </>
    ) : (
      <>
        <button
          type="button"
          onClick={() => setStep("pick")}
          disabled={saving}
          className="px-4 py-2 text-[14px] bg-white text-ink border border-line rounded-md font-normal hover:bg-line-soft disabled:opacity-50"
        >
          Back
        </button>
        <button
          type="button"
          onClick={handleMergeConfirm}
          disabled={saving}
          aria-busy={saving}
          className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Merging…" : "Merge items"}
        </button>
      </>
    );

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="default"
      title="Merge action items"
      subtitle={`${selectedItems.length} items selected`}
      footer={footer}
      dismissible={!saving}
    >
      {error && (
        <div
          role="alert"
          data-testid="merge-error-banner"
          className="flex items-start gap-2 border-l-4 border-red bg-red-tint text-red rounded-md px-4 py-2 mb-4"
        >
          <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span className="text-[13px]">{error}</span>
        </div>
      )}
      {step === "pick" ? (
        <div className="space-y-4">
          <div>
            <h3
              id="merge-primary-section"
              className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted"
            >
              Pick the primary item
            </h3>
            <p className="text-[14px] text-muted mt-1">
              The primary item will remain active. All others will be merged into it.
            </p>
          </div>
          <div
            role="radiogroup"
            aria-labelledby="merge-primary-section"
            className="space-y-2"
          >
            {selectedItems.map((item) => {
              const selected = item.id === primaryId;
              return (
                <label
                  key={item.id}
                  className={`flex items-start gap-3 p-3 rounded-md border cursor-pointer hover:bg-line-soft ${
                    selected ? "border-yellow bg-yellow-tint" : "border-line"
                  }`}
                >
                  <input
                    type="radio"
                    name="merge-primary"
                    value={item.id}
                    checked={selected}
                    onChange={() => setPrimaryId(item.id)}
                    className="mt-1 w-4 h-4 accent-[#FACC15] cursor-pointer"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-semibold text-ink">
                      {item.title}
                    </div>
                    <div className="text-[12px] text-muted mt-1">
                      {item.scope === "BRAND"
                        ? "Brand"
                        : `Shop · ${item.shop_name ?? "—"}`}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-[12px] bg-amber-tint flex items-center justify-center shrink-0">
            <AlertTriangle size={22} className="text-amber" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-[18px] font-semibold text-ink mb-2">
              Confirm merge
            </h3>
            <p className="text-[14px] text-muted leading-[1.5]">
              Merge {selectedItems.length} items into &lsquo;
              {primaryItem?.title ?? ""}&rsquo;? This cannot be undone.
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
}
