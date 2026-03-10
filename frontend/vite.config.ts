import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Rebuild the optimized dependency cache on each dev-server start so
    // restart loops do not leave stale .vite chunk references behind.
    force: true
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000"
    }
  }
});
