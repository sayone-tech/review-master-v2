// Phase 25-03 — Three-dot actions menu for a canonical tag row.
// Opens a dropdown with Rename and Merge into… actions.

import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import type { OrgCanonicalTagRow } from "./types";

interface Props {
  row: OrgCanonicalTagRow;
  onRename: () => void;
  onMerge: () => void;
}

export function TagActionsMenu({ row: _row, onRename, onMerge }: Props) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        aria-label="Tag actions"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="w-8 h-8 flex items-center justify-center rounded-sm text-muted hover:bg-line-soft hover:text-ink"
      >
        <MoreHorizontal size={16} aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 min-w-[140px] bg-white border border-line rounded-menu shadow-[0_4px_16px_rgba(0,0,0,0.10)]">
          <button
            type="button"
            className="w-full text-left text-[14px] text-text px-3 py-2 hover:bg-line-soft cursor-pointer"
            onClick={() => {
              setOpen(false);
              onRename();
            }}
          >
            Rename
          </button>
          <button
            type="button"
            className="w-full text-left text-[14px] text-text px-3 py-2 hover:bg-line-soft cursor-pointer"
            onClick={() => {
              setOpen(false);
              onMerge();
            }}
          >
            Merge into…
          </button>
        </div>
      )}
    </div>
  );
}
