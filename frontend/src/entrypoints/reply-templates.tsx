import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { TemplateModals } from "../widgets/reply-templates/TemplateModals";
import { TemplateTableWidget } from "../widgets/reply-templates/TemplateTable";

function parseInitialData() {
  const el = document.getElementById("template-data");
  if (!el) return [];
  try {
    return JSON.parse(el.textContent ?? "[]");
  } catch {
    return [];
  }
}

function mount() {
  const initialRows = parseInitialData();

  const modalsRoot = document.getElementById("template-modals-root");
  if (modalsRoot && !modalsRoot.dataset.mounted) {
    modalsRoot.dataset.mounted = "1";
    createRoot(modalsRoot).render(
      <StrictMode>
        <TemplateModals initialRows={initialRows} />
      </StrictMode>,
    );
  }

  const tableRoot = document.getElementById("template-table-root");
  if (tableRoot && !tableRoot.dataset.mounted) {
    tableRoot.dataset.mounted = "1";
    createRoot(tableRoot).render(
      <StrictMode>
        <TemplateTableWidget initialRows={initialRows} />
      </StrictMode>,
    );
  }
}

mount();
document.addEventListener("turbo:load", mount);
