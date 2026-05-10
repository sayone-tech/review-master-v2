import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ActionItemManagementWidget } from "../widgets/action-items/ActionItemManagementWidget";
import type { ShopOption, TeamMember, UserRole } from "../widgets/action-items/types";

function mount() {
  const root = document.getElementById("action-items-management-root");
  if (!root) return;
  const userRole = (root.dataset.userRole ?? "STAFF_ADMIN") as UserRole;
  const userId = Number(root.dataset.userId ?? "0");
  const shops = JSON.parse(root.dataset.shops ?? "[]") as ShopOption[];
  const team = JSON.parse(root.dataset.team ?? "[]") as TeamMember[];
  createRoot(root).render(
    <StrictMode>
      <ActionItemManagementWidget
        userRole={userRole}
        userId={userId}
        shops={shops}
        teamMembers={team}
      />
    </StrictMode>,
  );
}

document.addEventListener("turbo:load", mount);
