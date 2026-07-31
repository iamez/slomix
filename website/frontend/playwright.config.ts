import { defineConfig, devices } from '@playwright/test';

// W7 (docs/TASKS_FOR_SONNET_2026-07-29.md): smoke tests over the routes a
// human clicks. Runs against the local dev backend, not production — before
// running these, from the repo root:
//   1. npm --prefix website/frontend ci
//      Nothing below works without it: step 2's `build` runs the `vite` binary,
//      which only exists in devDependencies, and starting from `npx` alone can
//      fetch an unpinned Playwright rather than the locked one (Codex review on
//      #582).
//   2. npx --prefix website/frontend playwright install --with-deps chromium
//      `npm ci` installs the Playwright *runner* but not the browser binary
//      (the locked packages have no browser-download install hook), so without
//      this the suite dies before opening a single route with a
//      missing-executable error. `--with-deps` also pulls the shared libraries
//      Chromium needs — verified necessary here: without them the launch fails
//      with "libatk-1.0.so.0: cannot open shared object file" even once the
//      binary is present. That part needs root (it apt-installs), so on a box
//      where you can't sudo, expect to stop at this step.
//   3. npm --prefix website/frontend run build   (website/static/modern/ is
//      gitignored + generated; the skill-rating route imports
//      /static/modern/route-host.js and 404s without this)
//   4. cd website && ../venv/bin/uvicorn backend.main:app --port 8000
//      (must run from website/, not the repo root — there is no root-level
//      `backend` package, it's website/backend; the venv lives at the repo
//      root per docs/RUNBOOK_LOCAL_LINUX.md, hence ../)
// Then run the suite with `npm --prefix website/frontend run test:e2e`, or point
// SMOKE_BASE_URL at wherever an already-running instance listens.
//
// NOT wired into CI, deliberately and as a known gap: the `react-frontend` job
// runs only `typecheck` + `test` (vitest), and these smoke checks need the full
// FastAPI backend plus Postgres and Redis, which that job doesn't provision.
// Standing one up there is a real piece of work, not a one-line addition — so
// for now this is a local/pre-deploy gate, and `test:e2e` exists so it's at
// least invocable by name rather than only via a remembered incantation
// (Codex review on #582).
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
