import "@hotwired/turbo";
import Alpine from "alpinejs";
import { createIcons, icons } from "lucide";

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

// Keep the permanent sidebar's active nav item in sync with the current URL.
// Classes mirror what Django's {% is_active_route %} template tag injects.
const NAV_ACTIVE = [
  "border-yellow",
  "text-yellow",
  "bg-gradient-to-r",
  "from-yellow/[0.08]",
  "to-transparent",
  "pl-[17px]",
];
const NAV_INACTIVE = ["border-transparent", "text-[#D4D4D8]", "hover:text-yellow"];

function updateSidebarActiveState() {
  const sidebar = document.getElementById("main-sidebar");
  if (!sidebar) return;

  const path = window.location.pathname;
  sidebar.querySelectorAll<HTMLAnchorElement>("nav a[href]").forEach((a) => {
    const href = a.getAttribute("href") ?? "";
    const isActive = path.startsWith(href) && href !== "/";

    if (isActive) {
      a.classList.remove(...NAV_INACTIVE);
      a.classList.add(...NAV_ACTIVE);
      a.setAttribute("aria-current", "page");
    } else {
      a.classList.remove(...NAV_ACTIVE);
      a.classList.add(...NAV_INACTIVE);
      a.removeAttribute("aria-current");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  updateBreadcrumb();
});

// Re-run after Alpine finishes rendering (handles x-if / x-show content)
document.addEventListener("alpine:initialized", initIcons);

// Re-run on every Turbo navigation (body has been swapped)
document.addEventListener("turbo:load", () => {
  initIcons();
  updateBreadcrumb();
  updateSidebarActiveState();
});
