import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import FocusTrap from "focus-trap-react";
import { X } from "lucide-react";

export type ModalSize = "sm" | "default" | "lg";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  size?: ModalSize;
  dismissible?: boolean;
  children: ReactNode;
  footer?: ReactNode;
}

const SIZE_CLASS: Record<ModalSize, string> = {
  sm: "max-w-[420px]",
  default: "max-w-[520px]",
  lg: "max-w-[640px]",
};

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  size = "default",
  dismissible = true,
  children,
  footer,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dismissible) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, dismissible, onClose]);

  if (!open) return null;

  return createPortal(
    <FocusTrap
        focusTrapOptions={{
          escapeDeactivates: false,
          clickOutsideDeactivates: false,
          fallbackFocus: () => document.body,
        }}
      >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title || "Dialog"}
        className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-[rgba(24,24,27,0.45)] backdrop-blur-[3px]"
        data-testid="modal-backdrop"
        onClick={dismissible ? onClose : undefined}
      >
        <div
          className={`w-full ${SIZE_CLASS[size]} bg-white rounded-modal overflow-hidden shadow-[0_24px_64px_rgba(0,0,0,0.18),0_2px_8px_rgba(0,0,0,0.08)] max-h-[80vh] overflow-y-auto`}
          onClick={(e) => e.stopPropagation()}
          data-testid="modal-panel"
        >
          {title && (
            <div className="px-6 pt-[22px] flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[18px] font-semibold text-ink tracking-[-0.01em]">{title}</h2>
                {subtitle && <p className="text-[13.5px] text-muted mt-1">{subtitle}</p>}
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="w-[30px] h-[30px] rounded-md text-muted hover:bg-line-soft hover:text-ink flex items-center justify-center shrink-0"
                data-testid="modal-close"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
          )}
          <div className="px-6 py-5">{children}</div>
          {footer && (
            <div className="px-6 py-4 bg-[#FBFBFB] border-t border-line-soft flex justify-end gap-2">
              {footer}
            </div>
          )}
        </div>
      </div>
    </FocusTrap>,
    document.body,
  );
}
