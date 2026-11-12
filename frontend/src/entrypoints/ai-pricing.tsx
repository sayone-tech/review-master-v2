// Phase 35 — AI Pricing page entrypoint (superadmin).
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AiPricingWidget } from "../widgets/ai-pricing/AiPricingWidget";

function mount() {
  const root = document.getElementById("ai-pricing-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  createRoot(root).render(
    <StrictMode>
      <AiPricingWidget />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
