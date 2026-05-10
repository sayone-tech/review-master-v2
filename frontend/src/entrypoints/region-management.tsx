import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RegionModals } from "../widgets/region-management/RegionModals";
import { RegionTableWidget } from "../widgets/region-management/RegionTable";

function parseInitialData() {
  const el = document.getElementById("region-data");
  if (!el) return [];
  try {
    return JSON.parse(el.textContent ?? "[]");
  } catch {
    return [];
  }
}

function mount() {
  const initialRows = parseInitialData();

  const modalsRoot = document.getElementById("region-modals-root");
  if (modalsRoot) {
    createRoot(modalsRoot).render(
      <StrictMode>
        <RegionModals initialRows={initialRows} />
      </StrictMode>,
    );
  }

  const tableRoot = document.getElementById("region-table-root");
  if (tableRoot) {
    createRoot(tableRoot).render(
      <StrictMode>
        <RegionTableWidget initialRows={initialRows} />
      </StrictMode>,
    );
  }
}

document.addEventListener("turbo:load", mount);
