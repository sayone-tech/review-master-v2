import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { AllocationStatus, ShopRow } from "../widgets/shop-management/types";
import { ShopTableWidget } from "../widgets/shop-management/ShopTable";
import { ShopModals } from "../widgets/shop-management/ShopModals";

function parseJson<T>(id: string, fallback: T): T {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

const initialRows = parseJson<ShopRow[]>("shop-data", []);
const initialAllocation = parseJson<AllocationStatus>("shop-allocation", {
  current: 0,
  max: 0,
  at_limit: false,
});
const initialHasRegions = parseJson<boolean>("shop-has-regions", false);
const initialRegions = parseJson<{ id: number; region_id: string; name: string }[]>(
  "shop-regions-data",
  [],
);

const tableRoot = document.getElementById("shop-table-root");
if (tableRoot) {
  createRoot(tableRoot).render(
    <StrictMode>
      <ShopTableWidget
        initial={{
          rows: initialRows,
          allocation: initialAllocation,
          hasRegions: initialHasRegions,
        }}
      />
    </StrictMode>,
  );
}

const modalsRoot = document.getElementById("shop-modals-root");
if (modalsRoot) {
  const initialPlaceIds = initialRows.map((r) => r.place_id).filter(Boolean);
  createRoot(modalsRoot).render(
    <StrictMode>
      <ShopModals
        allocation={initialAllocation}
        regions={initialRegions}
        initialPlaceIds={initialPlaceIds}
      />
    </StrictMode>,
  );
}
