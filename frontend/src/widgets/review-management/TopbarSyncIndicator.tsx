import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { fetchSyncingShops } from "./api";

interface SyncingShop {
  shop_id: number;
  shop_name: string;
}

interface FailureEntry extends SyncingShop {
  error_code: string;
  error_message: string;
}

function buildWsUrl(shopId: number): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/sync-progress/${shopId}/`;
}

export function TopbarSyncIndicator() {
  const [active, setActive] = useState<SyncingShop[]>([]);
  const [failures, setFailures] = useState<FailureEntry[]>([]);
  const [open, setOpen] = useState(false);
  const sockets = useRef<Map<number, WebSocket>>(new Map());

  useEffect(() => {
    let cancelled = false;
    fetchSyncingShops()
      .then((data) => {
        if (cancelled) return;
        setActive(data.shops);
        for (const s of data.shops) connectToShop(s);
      })
      .catch(() => {
        // Ignore — initial fetch failure means no syncing shops to display.
      });
    return () => {
      cancelled = true;
      for (const ws of sockets.current.values()) ws.close();
      sockets.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connectToShop = (shop: SyncingShop) => {
    if (sockets.current.has(shop.shop_id)) return;
    const ws = new WebSocket(buildWsUrl(shop.shop_id));
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "sync.complete") {
          setActive((prev) => prev.filter((s) => s.shop_id !== shop.shop_id));
          setFailures((prev) => prev.filter((f) => f.shop_id !== shop.shop_id));
          ws.close();
          sockets.current.delete(shop.shop_id);
        } else if (data.type === "sync.error") {
          setActive((prev) => prev.filter((s) => s.shop_id !== shop.shop_id));
          setFailures((prev) => [
            ...prev.filter((f) => f.shop_id !== shop.shop_id),
            {
              shop_id: shop.shop_id,
              shop_name: shop.shop_name,
              error_code: data.error_code ?? "",
              error_message: data.error_message ?? "",
            },
          ]);
          ws.close();
          sockets.current.delete(shop.shop_id);
        }
      } catch {
        // ignore
      }
    };
    sockets.current.set(shop.shop_id, ws);
  };

  const totalCount = active.length + failures.length;
  if (totalCount === 0) return null;

  const hasFailures = failures.length > 0;

  return (
    <div className="relative" aria-live="polite">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={
          totalCount === 1
            ? "1 shop syncing reviews"
            : `${totalCount} shops syncing reviews`
        }
        title={
          totalCount === 1
            ? "1 shop syncing reviews"
            : `${totalCount} shops syncing reviews`
        }
        className={
          "inline-flex items-center gap-1 px-2 py-1 rounded-full " +
          (hasFailures ? "bg-red text-white" : "bg-yellow text-black")
        }
      >
        {hasFailures ? (
          <AlertTriangle size={14} aria-hidden="true" />
        ) : (
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        )}
        {totalCount > 1 && (
          <span className="text-[12px] font-semibold">{totalCount}</span>
        )}
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Syncing shops"
          className="absolute top-full right-0 mt-2 w-[280px] bg-white border border-line rounded-menu shadow-lg z-50 py-2"
        >
          {active.map((s) => (
            <div key={s.shop_id} className="px-4 py-2">
              <div className="text-[14px] font-semibold text-ink">{s.shop_name}</div>
              <a
                href={`/admin/org/shops/?open_progress=${s.shop_id}`}
                className="text-[12px] text-muted underline hover:text-ink"
              >
                View progress
              </a>
            </div>
          ))}
          {failures.map((f) => (
            <div key={f.shop_id} className="px-4 py-2">
              <div className="flex items-center gap-1">
                <AlertTriangle size={14} className="text-red" aria-hidden="true" />
                <div className="text-[14px] font-semibold text-ink">{f.shop_name}</div>
              </div>
              <a
                href={`/admin/org/shops/?open_progress=${f.shop_id}`}
                className="text-[12px] text-red underline hover:text-ink"
              >
                View error
              </a>
            </div>
          ))}
          {hasFailures && (
            <div className="px-4 pt-2 border-t border-line-soft">
              <button
                type="button"
                className="text-[12px] text-muted underline hover:text-ink"
                onClick={() => setFailures([])}
              >
                Mark all resolved
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
