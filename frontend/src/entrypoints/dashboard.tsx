import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DashboardWidget } from "../widgets/dashboard";

function mount() {
  const el = document.getElementById("dashboard-root");
  if (el) {
    createRoot(el).render(
      <StrictMode>
        <DashboardWidget />
      </StrictMode>,
    );
  }
}

document.addEventListener("turbo:load", mount);
