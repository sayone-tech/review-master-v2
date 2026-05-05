import { useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { Bell, Sparkles, Star, UserCheck } from "lucide-react";
import { useNotifications } from "./useNotifications";
import type { NotificationRow, NotificationType } from "./types";

const ICON: Record<NotificationType, LucideIcon> = {
  new_review: Star,
  new_action_item: Sparkles,
  action_item_assigned: UserCheck,
};

const ICON_COLOUR: Record<NotificationType, string> = {
  new_review: "text-yellow",
  new_action_item: "text-amber",
  action_item_assigned: "text-blue",
};

// Inlined per UI-SPEC §5: avoids coupling notif-bell to review-management.
// If a single source of truth is later wanted, lift to frontend/src/lib/time.ts.
function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function NotifBell() {
  const { count, items, markReadAndNavigate, markAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", escHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", escHandler);
    };
  }, [open]);

  const ariaLabel =
    count > 0
      ? `${count} unread notification${count === 1 ? "" : "s"}`
      : "Notifications";
  const displayCount = count > 99 ? "99+" : String(count);

  return (
    <div ref={containerRef} className="relative" aria-live="polite">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={ariaLabel}
        data-testid="notif-bell"
        className="relative w-9 h-9 rounded-md text-muted hover:bg-line-soft flex items-center justify-center"
      >
        <Bell size={18} aria-hidden="true" />
        {count >= 1 && (
          <span
            className="absolute top-0 right-0 translate-x-1/4 -translate-y-1/4 min-w-[18px] h-[18px] px-1 bg-red text-white text-[10px] font-semibold rounded-full flex items-center justify-center leading-none"
            aria-hidden="true"
          >
            {displayCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute top-full right-0 mt-2 w-[320px] bg-white border border-line rounded-menu shadow-lg z-50"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-line-soft">
            <span className="text-[14px] font-semibold text-ink">Notifications</span>
            {count > 0 && (
              <button
                type="button"
                onClick={() => void markAll()}
                className="text-[12px] text-muted underline hover:text-ink"
              >
                Mark all as read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <Bell size={24} className="text-muted mx-auto mb-2" aria-hidden="true" />
              <p className="text-[14px] text-muted">No new notifications</p>
            </div>
          ) : (
            <div className="divide-y divide-line-soft">
              {items.map((n) => (
                <NotificationListRow
                  key={n.id}
                  n={n}
                  onClick={() => void markReadAndNavigate(n)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface RowProps {
  n: NotificationRow;
  onClick: () => void;
}

function NotificationListRow({ n, onClick }: RowProps) {
  const Icon = ICON[n.notification_type];
  const colour = ICON_COLOUR[n.notification_type];
  const subline = n.shop_name
    ? `${n.shop_name} · ${relativeTime(n.created_at)}`
    : relativeTime(n.created_at);

  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={`flex items-start gap-3 px-4 py-3 cursor-pointer w-full text-left transition-colors ${
        n.is_read ? "hover:bg-line-soft" : "bg-amber-50/50 hover:bg-amber-50"
      }`}
    >
      <div className="relative shrink-0 mt-0.5">
        <Icon size={15} className={colour} aria-hidden="true" />
        {!n.is_read && (
          <span
            className="absolute -top-0.5 -right-0.5 w-[6px] h-[6px] rounded-full bg-yellow border border-white"
            aria-hidden="true"
          />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13.5px] font-semibold text-ink truncate leading-snug">{n.title}</p>
        <p className="text-[12px] text-muted mt-0.5">{subline}</p>
      </div>
    </button>
  );
}
