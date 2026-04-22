import "../styles/tailwind.css";
import Alpine from "alpinejs";

// Expose Alpine on window for inline x-data directives to resolve
declare global {
  interface Window {
    Alpine: typeof Alpine;
  }
}

window.Alpine = Alpine;
Alpine.start();
