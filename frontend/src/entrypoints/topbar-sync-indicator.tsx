import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TopbarBell } from "../widgets/review-management/TopbarSyncIndicator";

const root = document.getElementById("topbar-bell-root");
if (root) {
  const notificationCount = parseInt(root.dataset.notificationCount ?? "0", 10);
  createRoot(root).render(
    <StrictMode>
      <TopbarBell notificationCount={notificationCount} />
    </StrictMode>,
  );
}
