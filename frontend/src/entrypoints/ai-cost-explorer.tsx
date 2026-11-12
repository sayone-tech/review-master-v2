// Phase 34 — AI Cost Explorer entrypoint (superadmin).
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AiCostWidget } from "../widgets/ai-cost/AiCostWidget";

function mount() {
  const root = document.getElementById("ai-cost-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const raw = root.dataset.orgId ?? "";
  const orgId = raw === "" ? null : Number(raw);
  const orgName = root.dataset.orgName || null;
  createRoot(root).render(
    <StrictMode>
      <AiCostWidget orgId={orgId} orgName={orgName} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
