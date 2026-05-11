import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { AllocationStatus, ShopRow } from "../widgets/shop-management/types";
import { ShopTableWidget } from "../widgets/shop-management/ShopTable";
import { ShopModals } from "../widgets/shop-management/ShopModals";

function readOpenProgressShopId(): number | null {
  try {
    const v = new URLSearchParams(window.location.search).get("open_progress");
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

function parseJson<T>(id: string, fallback: T): T {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

function mount() {
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
  if (tableRoot && !tableRoot.dataset.mounted) {
    tableRoot.dataset.mounted = "1";
    createRoot(tableRoot).render(
      <StrictMode>
        <ShopTableWidget
          initial={{
            rows: initialRows,
            allocation: initialAllocation,
            hasRegions: initialHasRegions,
          }}
          openProgressShopId={readOpenProgressShopId()}
        />
      </StrictMode>,
    );
  }

  const modalsRoot = document.getElementById("shop-modals-root");
  if (modalsRoot && !modalsRoot.dataset.mounted) {
    modalsRoot.dataset.mounted = "1";
    const initialPlaceIds = initialRows.map((r) => r.place_id).filter(Boolean);
    const isOrgAdmin = modalsRoot.dataset.isOrgAdmin === "true";
    createRoot(modalsRoot).render(
      <StrictMode>
        <ShopModals
          allocation={initialAllocation}
          regions={initialRegions}
          initialPlaceIds={initialPlaceIds}
          isOrgAdmin={isOrgAdmin}
        />
      </StrictMode>,
    );
  }
}

mount();
document.addEventListener("turbo:load", mount);
