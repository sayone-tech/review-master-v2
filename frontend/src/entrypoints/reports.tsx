import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ReportsWidget } from "../widgets/reports";

function mount() {
  const el = document.getElementById("reports-root");
  if (!el || el.dataset.mounted) return;
  el.dataset.mounted = "1";
  createRoot(el).render(
    <StrictMode>
      <ReportsWidget />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
