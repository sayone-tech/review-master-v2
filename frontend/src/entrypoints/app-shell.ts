import "@hotwired/turbo";
import Alpine from "alpinejs";
import { createIcons, icons } from "lucide";
import { refreshSummary, restoreFolds, syncActiveItem, toggleGroup } from "../shell/nav";

declare global {
  interface Window {
    Alpine: typeof Alpine;
  }
}

window.Alpine = Alpine;

Alpine.store("nav", {
  mobileOpen: false,
});

Alpine.start();

function initIcons() {
  createIcons({ icons });
}

function updateBreadcrumb() {
  const main = document.getElementById("main-content");
  const crumb = document.getElementById("topbar-breadcrumb");
  if (main && crumb) {
    const title = (main as HTMLElement).dataset.pageTitle;
    if (title) crumb.textContent = title;
  }
}

function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function syncSidebar() {
  const sidebar = document.getElementById("main-sidebar");
  if (!sidebar) return;
  syncActiveItem(sidebar, window.location.pathname);
  void refreshSummary(sidebar);
}

// Single owner of group fold state (delegated; the sidebar is turbo-permanent).
document.addEventListener("click", (e) => {
  const toggle = (e.target as Element | null)?.closest<HTMLElement>("[data-nav-group-toggle]");
  const sidebar = toggle?.closest<HTMLElement>("#main-sidebar");
  if (toggle && sidebar) toggleGroup(sidebar, toggle, safeStorage());
});

document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  updateBreadcrumb();
  const sidebar = document.getElementById("main-sidebar");
  if (sidebar) restoreFolds(sidebar, safeStorage());
  syncSidebar();
});

// Re-run after Alpine finishes rendering (handles x-if / x-show content)
document.addEventListener("alpine:initialized", initIcons);

// Re-run on every Turbo navigation (body has been swapped)
document.addEventListener("turbo:load", () => {
  initIcons();
  updateBreadcrumb();
  syncSidebar();
});
