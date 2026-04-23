import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";

export default defineConfig({
  base: "/static/dist/",
  plugins: [react(), tailwindcss()],
  build: {
    manifest: "manifest.json",
    outDir: resolve(__dirname, "../static/dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        tailwind: resolve(__dirname, "src/styles/tailwind.css"),
        "app-shell": resolve(__dirname, "src/entrypoints/app-shell.ts"),
        showcase: resolve(__dirname, "src/entrypoints/showcase.tsx"),
        "org-management": resolve(__dirname, "src/entrypoints/org-management.tsx"),
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
