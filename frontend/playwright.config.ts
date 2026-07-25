import { defineConfig, devices } from "@playwright/test";

/**
 * Suite E2E full-stack: Playwright avvia il backend reale (migrazioni +
 * uvicorn su un database dedicato) e il frontend buildato. Esegue SOLO
 * contro l'ambiente locale/di test, mai contro produzione.
 */
const E2E_DATABASE_URL =
  process.env.E2E_DATABASE_URL ??
  "postgresql+psycopg://postgres:postgres@localhost:54329/hostpilot_e2e";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      // `--no-sync`: l'ambiente è già sincronizzato dal job CI (o in
      // locale da `uv sync`), qui non si reinstalla né si builda nulla.
      command:
        "uv run --no-sync --no-build alembic upgrade head && uv run --no-sync --no-build uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        HOSTPILOT_DATABASE_URL: E2E_DATABASE_URL,
        // Solo e2e locale/CI su http: in ogni ambiente reale resta true.
        HOSTPILOT_SESSION_COOKIE_SECURE: "false",
        HOSTPILOT_FRONTEND_ORIGIN: "http://localhost:3000",
      },
    },
    {
      command: "npm run build && npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
