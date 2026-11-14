import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { InsightsBook } from "../widgets/insights";

function mount() {
  const el = document.getElementById("insights-root");
  if (!el || el.dataset.mounted) return;
  el.dataset.mounted = "1";
  createRoot(el).render(
    <StrictMode>
      <InsightsBook />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
