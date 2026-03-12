import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, "..");
const host = process.env.PLAYWRIGHT_HOST ?? "127.0.0.1";
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? "4173");
const backendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT ?? "8010");
const frontendOrigin = `http://${host}:${frontendPort}`;
const backendOrigin = `http://${host}:${backendPort}`;
const backendScript = resolve(repoRoot, "scripts", "run_e2e_backend.py");
const backendPython = resolve(repoRoot, ".venv", "bin", "python");

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "../output/playwright/report" }],
  ],
  outputDir: "../output/playwright/test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: frontendOrigin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: `${JSON.stringify(backendPython)} ${JSON.stringify(backendScript)} --host ${host} --port ${backendPort} --frontend-origin ${frontendOrigin}`,
      cwd: repoRoot,
      url: `${backendOrigin}/healthz`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host ${host} --port ${frontendPort}`,
      cwd: frontendRoot,
      url: `${frontendOrigin}/login`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        VITE_API_BASE_URL: backendOrigin,
      },
    },
  ],
});
