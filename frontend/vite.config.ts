import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";

export default defineConfig({
  base: "/static/dist/",
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  build: {
    manifest: "manifest.json",
    outDir: resolve(__dirname, "../static/dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "app-shell": resolve(__dirname, "src/entrypoints/app-shell.ts"),
        showcase: resolve(__dirname, "src/entrypoints/showcase.tsx"),
        "org-management": resolve(__dirname, "src/entrypoints/org-management.tsx"),
        "region-management": resolve(__dirname, "src/entrypoints/region-management.tsx"),
        "shop-management": resolve(__dirname, "src/entrypoints/shop-management.tsx"),
        "team-management": resolve(__dirname, "src/entrypoints/team-management.tsx"),
        "review-management": resolve(__dirname, "src/entrypoints/review-management.tsx"),
        "topbar-sync-indicator": resolve(__dirname, "src/entrypoints/topbar-sync-indicator.tsx"),
        "action-items-management": resolve(
          __dirname,
          "src/entrypoints/action-items-management.tsx",
        ),
        "notif-bell": resolve(__dirname, "src/entrypoints/notif-bell.tsx"),
        dashboard: resolve(__dirname, "src/entrypoints/dashboard.tsx"),
        "reply-templates": resolve(__dirname, "src/entrypoints/reply-templates.tsx"),
        "shop-targets": resolve(__dirname, "src/entrypoints/shop-targets.tsx"),
        reports: resolve(__dirname, "src/entrypoints/reports.tsx"),
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    origin: "http://localhost:5173",
  },
});
