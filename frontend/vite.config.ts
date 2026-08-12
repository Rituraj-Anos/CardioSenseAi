import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The dev server proxies /api to the FastAPI backend so the browser makes
// same-origin requests and the httpOnly refresh cookie works without CORS
// juggling during development.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy vendors so the charting library doesn't bloat the main
        // bundle and can be cached independently.
        manualChunks: {
          charts: ["recharts"],
          vendor: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query", "axios"],
          motion: ["motion"],
        },
      },
    },
  },
});
