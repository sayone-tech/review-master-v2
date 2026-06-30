import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle, Loader2 } from "lucide-react";
import { fetchSyncingShops } from "./api";

interface SyncingShop {
  shop_id: number;
  shop_name: string;
  stage?: "fetching" | "vocab" | "enriching" | "finalising";
}

interface FailureEntry extends SyncingShop {
  error_code: string;
  error_message: string;
}

interface CompletedEntry extends SyncingShop {
  total_fetched: number;
}

function buildWsUrl(shopId: number): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/sync-progress/${shopId}/`;
}

export function TopbarBell() {
  const [active, setActive] = useState<SyncingShop[]>([]);
  const [failures, setFailures] = useState<FailureEntry[]>([]);
  const [completed, setCompleted] = useState<CompletedEntry[]>([]);
  const [open, setOpen] = useState(false);
  const sockets = useRef<Map<number, WebSocket>>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSyncingShops()
      .then((data) => {
        if (cancelled) return;
        setActive(data.shops);
        for (const s of data.shops) connectToShop(s);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      for (const ws of sockets.current.values()) ws.close();
      sockets.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (e: Event) => {
      const { shop_id, shop_name } = (e as CustomEvent<{ shop_id: number; shop_name: string }>).detail;
      const shop = { shop_id, shop_name };
      setActive((prev) => prev.some((s) => s.shop_id === shop_id) ? prev : [...prev, shop]);
      connectToShop(shop);
    };
    window.addEventListener("sync:shop-moved-to-background", handler);
    return () => window.removeEventListener("sync:shop-moved-to-background", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const connectToShop = (shop: SyncingShop) => {
    if (sockets.current.has(shop.shop_id)) return;
    const ws = new WebSocket(buildWsUrl(shop.shop_id));
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "sync.enrichment.progress") {
          setActive((prev) =>
            prev.map((s) =>
              s.shop_id === shop.shop_id ? { ...s, stage: "enriching" } : s,
            ),
          );
        } else if (data.type === "sync.vocab.progress") {
          setActive((prev) =>
            prev.map((s) =>
              s.shop_id === shop.shop_id ? { ...s, stage: "vocab" } : s,
            ),
          );
        } else if (data.type === "sync.finalising.progress") {
          setActive((prev) =>
            prev.map((s) =>
              s.shop_id === shop.shop_id ? { ...s, stage: "finalising" } : s,
            ),
          );
        } else if (data.type === "sync.fetch.progress") {
          // IN-02: extend the regression guard to cover all later stages, not just
          // "enriching". A stale sync.fetch.progress event must not regress a shop
          // that has already advanced to vocab/enriching/finalising.
          const STAGE_ORDER: Array<SyncingShop["stage"]> = ["fetching", "vocab", "enriching", "finalising"];
          setActive((prev) =>
            prev.map((s) => {
              const currentIdx = STAGE_ORDER.indexOf(s.stage ?? "fetching");
              const fetchingIdx = STAGE_ORDER.indexOf("fetching");
              return s.shop_id === shop.shop_id && currentIdx <= fetchingIdx
                ? { ...s, stage: "fetching" }
                : s;
            }),
          );
        } else if (data.type === "sync.complete") {
          setActive((prev) => prev.filter((s) => s.shop_id !== shop.shop_id));
          setFailures((prev) => prev.filter((f) => f.shop_id !== shop.shop_id));
          setCompleted((prev) => [
            ...prev.filter((c) => c.shop_id !== shop.shop_id),
            {
              shop_id: shop.shop_id,
              shop_name: shop.shop_name,
              total_fetched: data.total_fetched ?? 0,
            },
          ]);
          window.dispatchEvent(new CustomEvent("notifications:refresh"));
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

  const hasSyncActivity = active.length > 0 || failures.length > 0 || completed.length > 0;
  const hasFailures = failures.length > 0;
  const totalCount = active.length + failures.length + completed.length;

  if (!hasSyncActivity) return null;

  // State badge — only for non-active states (spinner communicates active state)
  let badge: React.ReactNode = null;
  if (active.length === 0 && hasFailures) {
    badge = (
      <span
        className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red border-2 border-white"
        aria-hidden="true"
      />
    );
  } else if (active.length === 0 && completed.length > 0) {
    badge = (
      <span
        className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-500 border-2 border-white"
        aria-hidden="true"
      />
    );
  }

  const isSyncing = active.length > 0;

  return (
    <div ref={containerRef} className="relative" aria-live="polite">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`${totalCount} sync notification${totalCount !== 1 ? "s" : ""}`}
        data-testid="topbar-bell"
        className={`relative w-[34px] h-[34px] rounded-md flex items-center justify-center transition-colors ${
          isSyncing
            ? "bg-yellow text-black hover:bg-yellow/90"
            : "text-muted hover:bg-line-soft"
        }`}
      >
        {isSyncing ? (
          <Loader2 size={17} className="animate-spin" aria-hidden="true" />
        ) : hasFailures ? (
          <AlertTriangle size={17} className="text-red" aria-hidden="true" />
        ) : (
          <CheckCircle size={17} className="text-green-500" aria-hidden="true" />
        )}
        {badge}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute top-full right-0 mt-2 w-[300px] bg-white border border-line rounded-menu shadow-lg z-50 py-2"
        >
          {active.map((s) => {
            const stageLabels: Record<string, string> = {
              fetching: "Fetching reviews from Google…",
              vocab: "Building tag vocabulary…",
              enriching: "Analysing reviews with AI…",
              finalising: "Finalising…",
            };
            const stageColors: Record<string, string> = {
              fetching: "text-yellow",
              vocab: "text-green",
              enriching: "text-green",
              finalising: "text-amber",
            };
            const subLabel = stageLabels[s.stage ?? "fetching"] ?? "Fetching reviews from Google…";
            const iconColorClass = stageColors[s.stage ?? "fetching"] ?? "text-yellow";
            return (
              <div key={s.shop_id} className="flex items-start gap-3 px-4 py-2.5">
                <Loader2
                  size={15}
                  className={`animate-spin ${iconColorClass} mt-0.5 shrink-0`}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-ink truncate">{s.shop_name}</div>
                  <div className="text-[12px] text-muted">{subLabel}</div>
                  <a
                    href={`/admin/org/shops/?open_progress=${s.shop_id}`}
                    className="text-[12px] text-yellow underline hover:opacity-80"
                  >
                    View progress
                  </a>
                </div>
              </div>
            );
          })}

          {failures.map((f) => (
            <div key={f.shop_id} className="flex items-start gap-3 px-4 py-2.5">
              <AlertTriangle
                size={15}
                className="text-red mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <div className="text-[13px] font-semibold text-ink truncate">{f.shop_name}</div>
                <div className="text-[12px] text-red">Sync failed</div>
                <a
                  href={`/admin/org/shops/?open_progress=${f.shop_id}`}
                  className="text-[12px] text-red underline hover:opacity-80"
                >
                  View error
                </a>
              </div>
            </div>
          ))}

          {completed.map((c) => (
            <div key={c.shop_id} className="flex items-start gap-3 px-4 py-2.5">
              <CheckCircle
                size={15}
                className="text-green-500 mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-ink truncate">{c.shop_name}</div>
                <div className="text-[12px] text-muted">
                  {c.total_fetched > 0
                    ? `${c.total_fetched} review${c.total_fetched !== 1 ? "s" : ""} synced`
                    : "Sync complete"}
                </div>
                <a
                  href="/admin/org/reviews/"
                  className="text-[12px] text-muted underline hover:text-ink"
                >
                  View reviews
                </a>
              </div>
              <button
                type="button"
                aria-label={`Dismiss ${c.shop_name} notification`}
                className="text-muted hover:text-ink text-[18px] leading-none mt-0.5 shrink-0"
                onClick={() =>
                  setCompleted((prev) => prev.filter((x) => x.shop_id !== c.shop_id))
                }
              >
                ×
              </button>
            </div>
          ))}

          {(hasFailures || completed.length > 0) && (
            <div className="px-4 pt-2 border-t border-line-soft flex gap-3">
              {completed.length > 0 && (
                <button
                  type="button"
                  className="text-[12px] text-muted underline hover:text-ink"
                  onClick={() => {
                    setCompleted([]);
                    setOpen(false);
                  }}
                >
                  Dismiss all
                </button>
              )}
              {hasFailures && (
                <button
                  type="button"
                  className="text-[12px] text-muted underline hover:text-ink"
                  onClick={() => {
                    setFailures([]);
                    if (!active.length && !completed.length) setOpen(false);
                  }}
                >
                  Clear errors
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** @deprecated use TopbarBell */
export const TopbarSyncIndicator = TopbarBell;
