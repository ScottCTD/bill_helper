import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiProxyTarget = process.env.BILL_HELPER_API_PROXY_TARGET ?? "http://localhost:8000";

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
      "/api": apiProxyTarget
    }
  }
});
