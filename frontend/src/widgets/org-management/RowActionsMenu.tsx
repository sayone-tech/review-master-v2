import { useEffect, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import type { OrgRow } from "./types";

export interface RowAction {
  key: string;
  label: string;
  icon?: ReactNode;
  tone?: "default" | "amber" | "green" | "red";
  visible?: (row: OrgRow) => boolean;
  onSelect: (row: OrgRow) => void;
  separatorBefore?: boolean;
}

export function RowActionsMenu({
  row,
  actions,
}: {
  row: OrgRow;
  actions: RowAction[];
}) {
  const [open, setOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      )
        setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    // Close on any scroll so menu doesn't float away from its trigger
    const onScroll = () => setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);

  function handleOpen() {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setMenuPos({
        top: rect.bottom + 4,
        right: window.innerWidth - rect.right,
      });
    }
    setOpen((o) => !o);
  }

  const visible = actions.filter((a) => (a.visible ? a.visible(row) : true));

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Actions for ${row.name}`}
        onClick={handleOpen}
        className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:bg-line-soft hover:text-ink"
        data-testid={`row-actions-trigger-${row.id}`}
      >
        <MoreHorizontal size={16} aria-hidden="true" />
      </button>
      {open && (
        <div
          ref={menuRef}
          role="menu"
          style={{ position: "fixed", top: menuPos.top, right: menuPos.right }}
          className="w-44 bg-white border border-line rounded-menu shadow-[0_12px_32px_rgba(0,0,0,0.12)] py-1 z-[200]"
          data-testid={`row-actions-menu-${row.id}`}
        >
          {visible.map((a, i) => (
            <div key={a.key}>
              {a.separatorBefore && i > 0 && (
                <div className="h-px bg-line-soft my-1" aria-hidden="true" />
              )}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  a.onSelect(row);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-[13px] flex items-center gap-2 hover:bg-line-soft ${
                  a.tone === "red"
                    ? "text-red"
                    : a.tone === "amber"
                      ? "text-amber"
                      : a.tone === "green"
                        ? "text-green"
                        : "text-ink"
                }`}
                data-testid={`row-action-${a.key}-${row.id}`}
              >
                {a.icon}
                <span>{a.label}</span>
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
