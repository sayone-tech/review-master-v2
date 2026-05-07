import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DashboardWidget } from "../widgets/dashboard";

const el = document.getElementById("dashboard-root");
if (el) {
  const root = createRoot(el);
  root.render(
    <StrictMode>
      <DashboardWidget />
    </StrictMode>,
  );
}
