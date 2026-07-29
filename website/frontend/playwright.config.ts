import { defineConfig, devices } from '@playwright/test';

// W7 (docs/TASKS_FOR_SONNET_2026-07-29.md): smoke tests over the routes a
// human clicks. Runs against the local dev backend, not production — start
// it first (`website/venv/bin/uvicorn backend.main:app --port 8000` from the
// repo root, or whatever port SMOKE_BASE_URL points at). No webServer
// auto-start here: the full site needs the FastAPI backend + Postgres +
// Redis, not just `vite dev`, so spinning that stack up from a test runner
// is out of scope for a first smoke pass.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.SMOKE_BASE_URL || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
