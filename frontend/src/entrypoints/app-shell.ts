import "../styles/tailwind.css";
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

document.addEventListener("DOMContentLoaded", () => {
  createIcons({ icons });
});

// Re-run after Alpine finishes rendering (handles x-if / x-show content)
document.addEventListener("alpine:initialized", () => {
  createIcons({ icons });
});
