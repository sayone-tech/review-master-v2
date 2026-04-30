import { useState, useMemo } from "react";
import type { RegionOption, ShopOption } from "./types";

type ScopeMode = "region" | "store";

interface ScopeSectionProps {
  regions: RegionOption[];
  activeShops: ShopOption[];
  selectedRegionIds: Set<number>;
  selectedShopIds: Set<number>;
  onChangeRegions: (next: Set<number>) => void;
  onChangeShops: (next: Set<number>) => void;
  validationError?: string;
  initialMode?: ScopeMode;
}

export function ScopeSection({
  regions,
  activeShops,
  selectedRegionIds,
  selectedShopIds,
  onChangeRegions,
  onChangeShops,
  validationError,
  initialMode = "region",
}: ScopeSectionProps) {
  const [mode, setMode] = useState<ScopeMode>(initialMode);
  const [storeSearch, setStoreSearch] = useState("");

  function switchMode(next: ScopeMode) {
    setMode(next);
    if (next === "region") {
      onChangeShops(new Set());
    } else {
      onChangeRegions(new Set());
    }
  }

  const filteredShops = useMemo(() => {
    const q = storeSearch.trim().toLowerCase();
    if (!q) return activeShops;
    return activeShops.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.region_name ?? "").toLowerCase().includes(q),
    );
  }, [activeShops, storeSearch]);

  function toggleRegion(id: number) {
    const next = new Set(selectedRegionIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChangeRegions(next);
  }

  function toggleShop(id: number) {
    const next = new Set(selectedShopIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChangeShops(next);
  }

  return (
    <div className="mt-4">
      <div className="text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1">
        Access Scope
      </div>
      <p className="text-[12px] text-muted mb-3">
        Staff can only see the regions and stores you assign.
      </p>

      {/* Mode toggle */}
      <div className="flex rounded-md border border-line overflow-hidden mb-3">
        <button
          type="button"
          onClick={() => switchMode("region")}
          className={`flex-1 py-2 text-[13px] font-medium transition-colors ${
            mode === "region"
              ? "bg-ink text-white"
              : "bg-white text-subtle hover:bg-line-soft"
          }`}
        >
          By Region
        </button>
        <button
          type="button"
          onClick={() => switchMode("store")}
          className={`flex-1 py-2 text-[13px] font-medium border-l border-line transition-colors ${
            mode === "store"
              ? "bg-ink text-white"
              : "bg-white text-subtle hover:bg-line-soft"
          }`}
        >
          By Store
        </button>
      </div>

      {/* Region mode */}
      {mode === "region" && (
        <div role="group" aria-label="Region access">
          <p className="text-[12px] text-muted mb-2">
            Staff will have access to all stores within the selected regions.
          </p>
          {regions.length === 0 ? (
            <p className="text-[12px] text-muted">
              No regions to assign — create regions first.
            </p>
          ) : (
            <div className="max-h-[200px] overflow-y-auto border border-line rounded-md">
              {regions.map((r) => (
                <label
                  key={r.id}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-line-soft cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="w-4 h-4 accent-yellow"
                    aria-label={r.name}
                    checked={selectedRegionIds.has(r.id)}
                    onChange={() => toggleRegion(r.id)}
                  />
                  <span className="text-[14px] text-ink">{r.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Store mode */}
      {mode === "store" && (
        <div role="group" aria-label="Store access">
          <p className="text-[12px] text-muted mb-2">
            Staff will have access only to the selected stores.
          </p>
          {activeShops.length === 0 ? (
            <p className="text-[12px] text-muted">No active stores to assign.</p>
          ) : (
            <>
              <input
                type="search"
                placeholder="Search stores…"
                value={storeSearch}
                onChange={(e) => setStoreSearch(e.target.value)}
                className="w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink mb-2"
              />
              {selectedShopIds.size > 0 && (
                <p className="text-[12px] text-muted mb-1">
                  {selectedShopIds.size} store{selectedShopIds.size !== 1 ? "s" : ""} selected
                </p>
              )}
              <div className="max-h-[200px] overflow-y-auto border border-line rounded-md">
                {filteredShops.length === 0 ? (
                  <p className="px-3 py-3 text-[13px] text-muted">
                    No stores match your search.
                  </p>
                ) : (
                  filteredShops.map((s) => (
                    <label
                      key={s.id}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-line-soft cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        className="w-4 h-4 accent-yellow"
                        aria-label={s.name}
                        checked={selectedShopIds.has(s.id)}
                        onChange={() => toggleShop(s.id)}
                      />
                      <div>
                        <div className="text-[14px] text-ink">{s.name}</div>
                        {s.region_name && (
                          <div className="text-[11px] text-muted">{s.region_name}</div>
                        )}
                      </div>
                    </label>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      )}

      {validationError && (
        <p role="alert" className="text-[12px] text-red mt-2">
          {validationError}
        </p>
      )}
    </div>
  );
}
