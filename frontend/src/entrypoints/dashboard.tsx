import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DashboardWidget } from "../widgets/dashboard";

function mount() {
  const el = document.getElementById("dashboard-root");
  if (!el || el.dataset.mounted) return;
  el.dataset.mounted = "1";
  createRoot(el).render(
    <StrictMode>
      <DashboardWidget />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
