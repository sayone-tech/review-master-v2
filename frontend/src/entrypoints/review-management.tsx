import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ReviewManagementWidget } from "../widgets/review-management/ReviewManagementWidget";

const root = document.getElementById("review-management-root");
if (root) {
  const userRole = root.dataset.currentUserRole ?? "";
  const openProgressShopId = root.dataset.openProgressShopId ?? "";
  createRoot(root).render(
    <StrictMode>
      <ReviewManagementWidget
        userRole={userRole}
        openProgressShopId={openProgressShopId ? Number(openProgressShopId) : null}
      />
    </StrictMode>,
  );
}
