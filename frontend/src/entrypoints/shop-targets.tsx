import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ShopTargetsWidget } from "../widgets/shop-targets/ShopTargetsWidget";

function mount() {
  const root = document.getElementById("shop-targets-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const shopId = Number(root.dataset.shopId ?? "0");
  const shopName = root.dataset.shopName ?? "";
  const isOrgAdmin = root.dataset.isOrgAdmin === "true";
  createRoot(root).render(
    <StrictMode>
      <ShopTargetsWidget shopId={shopId} shopName={shopName} isOrgAdmin={isOrgAdmin} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
