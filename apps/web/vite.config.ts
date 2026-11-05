import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // No Docker com Windows, eventos de arquivo não chegam ao container.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
    proxy: {
      "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8010",
    },
  },
  test: {
    environment: "jsdom",
    css: false,
  },
});
