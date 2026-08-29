import { readFileSync } from 'node:fs';
import { test, expect, type ConsoleMessage, type Page } from '@playwright/test';

/** Read rather than imported: the runner's loader demands an import
 *  attribute for JSON, and a spec is not the place to argue with it. Same
 *  file the app routes with either way, which is the whole point. */
const routes = JSON.parse(
  readFileSync(new URL('../src/app/routes.data.json', import.meta.url), 'utf8'),
) as { key: string; path: string }[];

/**
 * Every route of the standalone app, loaded once (docs/design/09 §H3).
 *
 * smoke.spec.ts covers six routes of the LEGACY site, hand-listed. That was
 * the right size for a first pass and the wrong shape for a migration: the
 * list cannot grow when a page lands, so the newest page is always the least
 * covered one. This spec is driven by the same routes.data.json the app
 * routes with, so a route added to the table is a test the next run.
 *
 * Stubs are swept too, on purpose. A route whose page is not built yet still
 * has to render the shell without throwing — and a stub that throws is
 * exactly the failure that would otherwise be discovered by a person
 * clicking a nav item in a demo.
 *
 * NOT wired into CI, same standing reason as smoke.spec.ts: the `react-
 * frontend` job has no backend, and the `python` job has Postgres and Redis
 * but no served frontend. This is a dev sweep (scripts/parity_sweep.sh).
 */

/** Real rows on the dev database, so a parametrised route is exercised
 *  rather than bouncing off a guard. Shared with the sample table in
 *  scripts/audit_website_browser.mjs — the two sweeps should visit the same
 *  data, so a difference between them is a difference in the pages. */
const SAMPLES = new Map<string, string>([
  [':id?', 'D8423F90'],
  [':guid', 'D8423F90'],
  [':roundId', '11365'],
  [':sessionId', '154'],
  [':sessionDate', '2026-08-04'],
  [':gsid', '154'],
  [':date', '2026-08-27'],
  [':section?', 'demos'],
  [':demoId', '7dc01a5727344cd8afece44a1cc572e6'],
  [':uploadId', 'de4f8d8628c148e5a8756a522aeb43b0'],
  [':tab?', ''],
]);

function fill(path: string): string {
  const filled = path
    .split('/')
    .map((seg) => (seg.startsWith(':') ? SAMPLES.get(seg) ?? seg.replace(/[:?]/g, '') : seg))
    .filter((seg, i) => seg !== '' || i === 0)
    .join('/');
  return `/app${filled === '/' ? '' : filled}`;
}

/**
 * 401/403 from /auth/* is the API contract for a logged-out visitor, not a
 * fault (logging_middleware.py:40). Scoped by URL rather than message text,
 * so a 401 from any other endpoint still fails — that is the case worth
 * catching. Copied verbatim from smoke.spec.ts, whose reasoning stands.
 */
function isExpectedAuthConsoleError(msg: ConsoleMessage): boolean {
  return /\b(401|403)\b/.test(msg.text()) && msg.location().url.includes('/auth/');
}

function isExpectedAuthResponse(url: string, status: number): boolean {
  return (status === 401 || status === 403) && url.includes('/auth/');
}

interface Collected {
  consoleErrors: string[];
  badResponses: string[];
}

function collect(page: Page): Collected {
  const consoleErrors: string[] = [];
  const badResponses: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    if (isExpectedAuthConsoleError(msg)) return;
    consoleErrors.push(msg.text());
  });
  page.on('pageerror', (error) => {
    consoleErrors.push(`pageerror: ${error.message}`);
  });
  page.on('requestfailed', (request) => {
    badResponses.push(`${request.method()} ${request.url()} — ${request.failure()?.errorText}`);
  });
  page.on('response', (response) => {
    const status = response.status();
    if (status < 400) return;
    if (isExpectedAuthResponse(response.url(), status)) return;
    badResponses.push(`${status} ${response.url()}`);
  });
  return { consoleErrors, badResponses };
}

for (const route of routes) {
  const url = fill(route.path);
  test(`app route ${route.key} (${url}) renders without errors`, async ({ page }) => {
    const seen = collect(page);

    const response = await page.goto(url, { waitUntil: 'networkidle' });
    expect(response?.status(), `${url} did not answer 200`).toBe(200);

    // The shell always renders; what matters is that SOMETHING rendered
    // under it. An empty body is what a thrown render leaves behind, and it
    // is indistinguishable from a slow one without this assertion.
    const text = (await page.locator('body').innerText()).trim();
    expect(text.length, `${url} rendered an empty page`).toBeGreaterThan(120);

    // A rendered error boundary is a pass for "200 and non-empty" and a
    // failure for everything a reader wants.
    expect(text).not.toMatch(/Something went wrong|Unhandled error|TypeError:/);

    // Values the page failed to format leak as these three, and every one of
    // them has reached a screenshot in this project at least once.
    expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\[object Object\]/);

    expect(seen.consoleErrors, `${url} logged console errors`).toEqual([]);
    expect(seen.badResponses, `${url} made failing requests`).toEqual([]);
  });
}
