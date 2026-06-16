// Phase 25-03 — Tag management entrypoint.
// Mounts the TagManagementWidget into #tag-management-root from templates/org_admin/tags.html.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TagManagementWidget } from "../widgets/tag-management/TagManagementWidget";

function mount() {
  const root = document.getElementById("tag-management-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  createRoot(root).render(
    <StrictMode>
      <TagManagementWidget />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
