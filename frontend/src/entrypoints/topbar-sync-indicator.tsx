import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TopbarBell } from "../widgets/review-management/TopbarSyncIndicator";

const root = document.getElementById("topbar-bell-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <TopbarBell />
    </StrictMode>,
  );
}
