import { defineConfig, devices } from '@playwright/test';

// W7 (docs/TASKS_FOR_SONNET_2026-07-29.md): smoke tests over the routes a
// human clicks. Runs against the local dev backend, not production — before
// running these, from the repo root:
//   1. npx --prefix website/frontend playwright install --with-deps chromium
//      `npm ci` installs the Playwright *runner* but not the browser binary
//      (the locked packages have no browser-download install hook), so without
//      this the suite dies before opening a single route with a
//      missing-executable error. `--with-deps` also pulls the shared libraries
//      Chromium needs — verified necessary here: without them the launch fails
//      with "libatk-1.0.so.0: cannot open shared object file" even once the
//      binary is present. That part needs root (it apt-installs), so on a box
//      where you can't sudo, expect to stop at this step.
//   2. npm --prefix website/frontend run build   (website/static/modern/ is
//      gitignored + generated; the skill-rating route imports
//      /static/modern/route-host.js and 404s without this)
//   3. cd website && ../venv/bin/uvicorn backend.main:app --port 8000
//      (must run from website/, not the repo root — there is no root-level
//      `backend` package, it's website/backend; the venv lives at the repo
//      root per docs/RUNBOOK_LOCAL_LINUX.md, hence ../)
// or point SMOKE_BASE_URL at wherever an already-running instance listens.
// No webServer auto-start here: the full site needs the FastAPI backend +
// Postgres + Redis, not just `vite dev`, so spinning that stack up from a
// test runner is out of scope for a first smoke pass.
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
