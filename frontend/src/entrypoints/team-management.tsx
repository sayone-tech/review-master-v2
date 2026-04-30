import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { TeamMemberRow, RegionOption, ShopOption, TeamStats } from "../widgets/team-management/types";
import { TeamTableWidget } from "../widgets/team-management/TeamTable";
import { TeamModals } from "../widgets/team-management/TeamModals";

function parseJson<T>(id: string, fallback: T): T {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent ?? "") as T;
  } catch {
    return fallback;
  }
}

const initialRows = parseJson<TeamMemberRow[]>("team-data", []);
const initialRegions = parseJson<RegionOption[]>("team-regions-data", []);
const initialShops = parseJson<ShopOption[]>("team-active-shops-data", []);
const initialStats = parseJson<TeamStats>("team-stats-data", {
  total_members: 0,
  managers: 0,
  active_members: 0,
});

const tableRoot = document.getElementById("team-table-root");
if (tableRoot) {
  const currentUserId = Number(tableRoot.dataset.currentUserId ?? 0);
  createRoot(tableRoot).render(
    <StrictMode>
      <TeamTableWidget
        initial={{ rows: initialRows, stats: initialStats }}
        regions={initialRegions}
        activeShops={initialShops}
        currentUserId={currentUserId}
      />
    </StrictMode>,
  );
}

const modalsRoot = document.getElementById("team-modals-root");
if (modalsRoot) {
  const currentUserId = Number(modalsRoot.dataset.currentUserId ?? 0);
  const managerCount = Number(modalsRoot.dataset.managerCount ?? 0);
  createRoot(modalsRoot).render(
    <StrictMode>
      <TeamModals
        regions={initialRegions}
        activeShops={initialShops}
        currentUserId={currentUserId}
        managerCount={managerCount}
      />
    </StrictMode>,
  );
}
