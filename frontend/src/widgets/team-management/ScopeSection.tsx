import type { RegionOption, ShopOption } from "./types";

interface ScopeSectionProps {
  regions: RegionOption[];
  activeShops: ShopOption[];
  selectedRegionIds: Set<number>;
  selectedShopIds: Set<number>;
  onChangeRegions: (next: Set<number>) => void;
  onChangeShops: (next: Set<number>) => void;
  validationError?: string;
}

export function ScopeSection({
  regions,
  activeShops,
  selectedRegionIds,
  selectedShopIds,
  onChangeRegions,
  onChangeShops,
  validationError,
}: ScopeSectionProps) {
  const toggleRegion = (id: number) => {
    const next = new Set(selectedRegionIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChangeRegions(next);
  };

  const toggleShop = (id: number) => {
    const next = new Set(selectedShopIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChangeShops(next);
  };

  return (
    <div className="mt-4">
      <div className="text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-2">
        Access Scope
      </div>
      <p className="text-[12px] font-normal text-muted mb-3">
        Staff can only see the regions and stores you assign.
      </p>

      <div role="group" aria-label="Region access" className="mb-3">
        <div className="text-[12px] font-semibold text-subtle uppercase mb-1">Regions</div>
        {regions.length === 0 ? (
          <p className="text-[12px] text-muted">
            No regions to assign — create regions first.
          </p>
        ) : (
          <div className="max-h-[180px] overflow-y-auto border border-line rounded-md">
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

      <div role="group" aria-label="Store access">
        <div className="text-[12px] font-semibold text-subtle uppercase mb-1">Stores</div>
        {activeShops.length === 0 ? (
          <p className="text-[12px] text-muted">No active stores to assign.</p>
        ) : (
          <div className="max-h-[180px] overflow-y-auto border border-line rounded-md">
            {activeShops.map((s) => (
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
                <span className="text-[14px] text-ink">{s.name}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {validationError && (
        <p role="alert" className="text-[12px] text-red mt-2">
          {validationError}
        </p>
      )}
    </div>
  );
}
