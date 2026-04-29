import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { AllocationStatus, ShopRow } from "../widgets/shop-management/types";
import { ShopTableWidget } from "../widgets/shop-management/ShopTable";

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

// Plan 08-05 will mount the modals widget on #shop-modals-root.
// For now, leave that root empty so the page renders.
