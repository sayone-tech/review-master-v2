import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";

export interface MoreFiltersPanelProps<D> {
  applied: D;
  activeCount: number;
  onApply: (draft: D) => void;
  onReset: () => void;
  children: (draft: D, setDraft: (d: D) => void) => ReactNode;
}

export function MoreFiltersPanel<D>({ applied, activeCount, onApply, onReset, children }: MoreFiltersPanelProps<D>) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<D>(applied);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const panelId = useId();
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // The refocus timer outlives the open effect (it fires after close); clear it only on unmount.
  useEffect(() => () => clearTimeout(timerRef.current), []);

  function openPanel() {
    setDraft(applied);
    setOpen(true);
  }

  const closeAndRefocus = useCallback(() => {
    setOpen(false);
    buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      // Nested listboxes must handle Escape in a React onKeyDown (or capture phase) and call
      // preventDefault(); this document listener ignores events that are already defaultPrevented.
      if (e.key !== "Escape" || e.defaultPrevented) return;
      closeAndRefocus();
    }
    function onMouseDown(e: MouseEvent) {
      const target = e.target as Element | null;
      if (rootRef.current?.contains(target as Node)) return;
      if (target?.closest?.("[data-filter-popover]")) return;
      setOpen(false);
      // The browser moves focus after mousedown; only restore it if it landed nowhere, so we
      // never steal focus from the control the user clicked.
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        const a = document.activeElement;
        if (!a || a === document.body) buttonRef.current?.focus();
      }, 0);
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onMouseDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onMouseDown);
    };
  }, [open, closeAndRefocus]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => (open ? closeAndRefocus() : openPanel())}
        className="inline-flex items-center gap-[7px] h-[34px] px-[11px] text-[13px] text-white bg-black border border-black rounded-[8px] cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <SlidersHorizontal size={15} strokeWidth={1.8} />
        More filters
        {activeCount > 0 && (
          <span
            data-testid="more-filters-badge"
            className="bg-yellow text-black rounded-full text-[11px] font-semibold px-[6px]"
          >
            {activeCount}
          </span>
        )}
      </button>
      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label="More filters"
          className="absolute right-0 top-[calc(100%+8px)] w-[320px] max-w-[calc(100vw-32px)] bg-white border border-line rounded-[12px] shadow-[0_18px_40px_rgba(10,10,10,0.16)] p-[14px] z-30"
        >
          <h4 className="m-0 mb-[10px] text-[13px] font-semibold text-ink">More filters</h4>
          <div className="flex flex-col gap-[10px]">{children(draft, setDraft)}</div>
          <div className="flex items-center justify-between mt-[14px]">
            <button
              type="button"
              onClick={() => {
                onReset();
                closeAndRefocus();
              }}
              className="text-[12px] text-muted underline cursor-pointer focus-visible:outline-2 focus-visible:outline-ink rounded-sm"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => {
                onApply(draft);
                closeAndRefocus();
              }}
              className="bg-yellow hover:bg-yellow-hover text-black rounded-[8px] px-4 py-[7px] text-[13px] font-semibold cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
