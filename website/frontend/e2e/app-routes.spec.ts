import { test, expect, type ConsoleMessage, type Page } from '@playwright/test';
// The runner's loader requires the attribute; without it the import fails
// with "needs an import attribute of type json" and no tests are collected.
import routes from '../src/app/routes.data.json' with { type: 'json' };

/** Phases whose pages are built. A route at or below this renders a real
 *  page; above it, the shell's stub is the correct answer.
 *
 *  This number is the reason the constant exists rather than being inlined:
 *  raise it when a phase lands, and every route of that phase is required to
 *  stop showing the stub.
 *
 *  ⛔ IT WAS LEFT AT 3 WHILE PHASE 4 SHIPPED. `session-detail` and
 *  `session-detail-date` — the two newest pages, #839 and #840 — were the
 *  only routes exempt from the one check that proves a stub is gone, and a
 *  stub answers 200, renders cleanly and passes every other assertion in this
 *  spec. Raising it by hand is what failed, so `routes.test.ts` now compares
 *  this number against what `main.tsx` actually wires: leave it too low and
 *  a unit test says so, in CI, without a browser. */

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
  [':section?', 'demos'],
  [':demoId', '7dc01a5727344cd8afece44a1cc572e6'],
  [':uploadId', 'de4f8d8628c148e5a8756a522aeb43b0'],
  [':tab?', ''],
]);

/**
 * The SECOND sample set: the same routes against data that is thin, old or
 * absent rather than the healthy night everything was built against.
 *
 * This exists because one sample hid a crash. session-detail was written
 * against session 154, which fills every field; pointed at 151, 146 and 128
 * — sessions whose endpoints answer with a SHORT form — it threw
 * `Cannot read properties of undefined` on three of four. No unit test could
 * see it: they all ran against the same recording.
 *
 * The ids are chosen so the pass can FAIL for the original reason: 151 is a
 * session whose /detail answers 200 while its mvp, verdicts and good-night
 * answer the short form — pointing it at 145 instead (six orphan_r2 rounds,
 * /detail 404s) made the sweep green against the very crash it was written
 * for, because the panel that threw never rendered. Checked by mutation, not
 * assumed. 3C89435D is a player with a single round, 11306 a round the
 * position tracker never covered, and 2026-06-21 a date whose session is
 * likewise thin.
 */
// 2026-09-03 (stats 2.0 R3): the session sample moved from 151 to 80.
// Since #855's validity gate, 151 has ZERO counted rounds — /detail, /basics
// and /awards all 404 — so a pass against it renders no basics table and no
// awards block at all, the very blind spot the paragraph above names. 80
// has counted rounds (8 of 15), no KIS, no team attribution and engine
// awards on one round only: the sparse shapes the new panels must survive.
// 151's short-form mvp/verdicts/good-night stay pinned in the unit test.
const SAMPLES_THIN = new Map<string, string>([
  [':id?', '3C89435D'],
  [':guid', '3C89435D'],
  [':roundId', '11306'],
  [':sessionId', '80'],
  [':sessionDate', '2026-01-27'],
  [':section?', 'clips'],
  [':demoId', '7dc01a5727344cd8afece44a1cc572e6'],
  [':uploadId', 'de4f8d8628c148e5a8756a522aeb43b0'],
  [':tab?', ''],
]);

function fill(path: string, samples: Map<string, string> = SAMPLES): string {
  const filled = path
    .split('/')
    .map((seg) => (seg.startsWith(':') ? samples.get(seg) ?? seg.replace(/[:?]/g, '') : seg))
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

    // A stub answers 200 and renders cleanly, so every check above passes
    // for a route whose page was never wired into the registry. That is not
    // hypothetical: /story/date/:date rendered the stub while its unit tests
    // passed, because those mount the component directly and only the
    // registry decides what the browser gets.
    // Per-route, from the registry row itself: phases land page by page,
    // and a hand-raised threshold was exactly the thing that once exempted
    // the two newest pages (see routes.test.ts).
    if (route.built === true) {
      // Case-insensitive on purpose: the stub's label is a `.lbl`, and that
      // class uppercases through CSS, so innerText returns "NOT BUILT YET".
      // The first version of this assertion matched lowercase and passed on
      // a route that was showing the stub — the control run is what caught
      // it, not the green one.
      expect(text, `${url} still shows the phase stub`).not.toMatch(/not built yet/i);
    }

    expect(seen.consoleErrors, `${url} logged console errors`).toEqual([]);
    expect(seen.badResponses, `${url} made failing requests`).toEqual([]);
  });
}

/**
 * Second pass, parametrised routes only: the same assertions against thin
 * data. A route with no parameters cannot differ between the two sets, so
 * running it twice would only cost time.
 */
for (const route of routes.filter((r) => r.path.includes(':'))) {
  const url = fill(route.path, SAMPLES_THIN);
  test(`app route ${route.key} (${url}) survives thin data`, async ({ page }) => {
    const seen = collect(page);

    const response = await page.goto(url, { waitUntil: 'networkidle' });
    expect(response?.status(), `${url} did not answer 200`).toBe(200);

    const text = (await page.locator('body').innerText()).trim();
    expect(text.length, `${url} rendered an empty page`).toBeGreaterThan(120);
    expect(text).not.toMatch(/Something went wrong|Unhandled error|TypeError:/);
    expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\[object Object\]/);
    // 404s are EXPECTED here — a session with no counted rounds answers one,
    // and the page is required to SAY so rather than to break. The browser
    // logs its own line for each of those, so both channels exempt exactly
    // that status and nothing else: a 500, a failed request or any other
    // console error still fails this pass.
    const notFoundNoise = /Failed to load resource.*\b404\b/;
    expect(
      seen.consoleErrors.filter((line) => !notFoundNoise.test(line)),
      `${url} logged console errors`,
    ).toEqual([]);
    expect(
      seen.badResponses.filter((line) => !/^404 /.test(line)),
      `${url} made failing requests`,
    ).toEqual([]);
  });
}
