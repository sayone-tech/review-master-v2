import { useState, type ReactNode } from "react";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import { Modal } from "./Modal";

export type ConfirmVariant = "amber" | "blue" | "red";

const ICON_BY_VARIANT = {
  amber: AlertTriangle,
  blue: Info,
  red: AlertCircle,
} as const;

const ICON_BG = {
  amber: "bg-amber-tint text-amber",
  blue: "bg-blue-tint text-blue",
  red: "bg-red-tint text-red",
} as const;

const CONFIRM_BTN_CLASS = {
  amber: "bg-red text-white border-transparent hover:bg-[#B91C1C]",
  blue: "bg-yellow text-black border-yellow-hover hover:bg-yellow-hover",
  red: "bg-red text-white border-transparent hover:bg-[#B91C1C]",
} as const;

export interface ConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  variant: ConfirmVariant;
  title: string;
  message: ReactNode;
  confirmLabel: string;
  /** If provided, confirm button is disabled until input matches this string exactly. */
  requireTypeToConfirm?: string;
}

export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  variant,
  title,
  message,
  confirmLabel,
  requireTypeToConfirm,
}: ConfirmModalProps) {
  const [typed, setTyped] = useState("");
  const Icon = ICON_BY_VARIANT[variant];
  const confirmDisabled = requireTypeToConfirm ? typed !== requireTypeToConfirm : false;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            data-testid="confirm-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={`inline-flex items-center px-3.5 py-2 border rounded-md text-[13.5px] font-medium ${CONFIRM_BTN_CLASS[variant]} ${confirmDisabled ? "opacity-50 cursor-not-allowed pointer-events-none" : ""}`}
            data-testid="confirm-confirm"
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <div className="flex gap-3.5">
        <div
          className={`w-11 h-11 shrink-0 rounded-confirm-icon flex items-center justify-center ${ICON_BG[variant]}`}
          aria-hidden="true"
        >
          <Icon size={22} />
        </div>
        <div>
          <h3 className="text-[18px] font-semibold text-ink mb-1.5">{title}</h3>
          <p className="text-[13.5px] text-muted leading-[1.5]">{message}</p>
          {requireTypeToConfirm && (
            <div className="mt-3">
              <div className="bg-line-soft px-3 py-2.5 rounded-md text-[12.5px] text-muted mb-2">
                Type{" "}
                <code className="bg-white px-1.5 py-[1px] rounded-sm font-mono text-[12px] text-ink border border-line">
                  {requireTypeToConfirm}
                </code>{" "}
                to confirm
              </div>
              <input
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="Organisation name"
                className="w-full px-3 py-[9px] text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink"
                data-testid="type-to-confirm-input"
              />
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
