import { useState, useEffect } from "react";
import { Modal, ConfirmModal } from "../modal";
import { updateOrg } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}

export function StoreAllocationModal({ org, onClose, onDone }: Props) {
  const [step, setStep] = useState<"input" | "confirm">("input");
  const [raw, setRaw] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Reset internal state when the org prop changes (modal opens for a different row).
  useEffect(() => {
    if (org) {
      setStep("input");
      setRaw(String(org.number_of_stores));
    } else {
      setStep("input");
      setRaw("");
      setSubmitting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [org?.id]);

  if (!org) return null;

  // Capture org in a const after the null guard so TypeScript narrows the type
  // correctly inside async closures (org prop could theoretically change).
  const currentOrg = org;

  const parsed = Number(raw);
  const isInt = Number.isInteger(parsed) && raw.trim() !== "";
  const tooLow = isInt && parsed < currentOrg.active_stores;
  const tooHigh = isInt && parsed > 1000;
  const invalid = !raw || !isInt || tooLow || tooHigh;
  const hasChanged = isInt && parsed !== currentOrg.number_of_stores;
  const updateDisabled = invalid || !hasChanged;

  function handleProceed() {
    if (updateDisabled) return;
    setStep("confirm");
  }

  async function handleConfirm() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await updateOrg(currentOrg.id, { number_of_stores: parsed });
      emitToast({ kind: "success", title: `Store allocation updated to ${parsed}.` });
      onClose();
      await onDone();
    } catch {
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Modal
        open={step === "input"}
        onClose={onClose}
        size="sm"
        title="Adjust Store Allocation"
        footer={
          <>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              data-testid="store-alloc-cancel"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={handleProceed}
              disabled={updateDisabled}
              className={`inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover ${
                updateDisabled ? "opacity-50 cursor-not-allowed pointer-events-none" : ""
              }`}
              data-testid="store-alloc-update"
            >
              Update
            </button>
          </>
        }
      >
        <p className="text-[13.5px] text-muted leading-[1.5] mb-4">
          Currently using <strong>{org.active_stores}</strong> of{" "}
          <strong>{org.number_of_stores}</strong> stores.
        </p>
        <label className="block">
          <span className="block text-[12px] font-semibold text-subtle mb-1.5">
            New allocation
          </span>
          <input
            type="number"
            min={org.active_stores}
            max={1000}
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder="e.g. 10"
            className="w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink"
            data-testid="store-alloc-input"
          />
        </label>
        {tooLow && (
          <p
            className="mt-2 bg-amber-tint text-[#92400E] px-3 py-2 rounded-md text-[12.5px]"
            data-testid="store-alloc-warning"
            role="alert"
          >
            Value cannot be lower than current usage ({org.active_stores} stores).
          </p>
        )}
        {tooHigh && (
          <p
            className="mt-2 bg-amber-tint text-[#92400E] px-3 py-2 rounded-md text-[12.5px]"
            role="alert"
          >
            Allocation must be 1000 or fewer.
          </p>
        )}
      </Modal>

      <ConfirmModal
        open={step === "confirm"}
        onClose={() => setStep("input")}
        onConfirm={handleConfirm}
        variant="blue"
        title="Confirm Store Allocation Change"
        message={
          <>
            Change store allocation for <strong>{org.name}</strong> from{" "}
            <strong>{org.number_of_stores}</strong> to <strong>{parsed}</strong>?
          </>
        }
        confirmLabel={submitting ? "Saving…" : "Confirm"}
      />
    </>
  );
}
