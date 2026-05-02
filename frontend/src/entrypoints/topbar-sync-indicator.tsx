import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TopbarSyncIndicator } from "../widgets/review-management/TopbarSyncIndicator";

const root = document.getElementById("sync-indicator-root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <TopbarSyncIndicator />
    </StrictMode>,
  );
}
