import { test, expect, type ConsoleMessage } from '@playwright/test';

// W7: five routes to start (not the full 30 from docs/ROUTE_MAP_2026-07.md),
// mixing legacy JS and React so both frontends are covered. Each page must
// load, render real content (not a blank error boundary), and produce zero
// console errors / zero failed network requests — that's the part that
// turns the F12 loop (W9) into something automated instead of anecdotal.
// The browser logs its OWN line for every failed request, so the 401 that
// /auth/me answers to an anonymous visitor arrives on the console as well as on
// the response handler. That handler exempts it deliberately — it is the API
// contract, not a fault (logging_middleware.py:40) — and without the same
// exemption here the suite can never pass a logged-out run. It never had been:
// the first real execution of this file failed all seven tests on that one line.
//
// Scoped by URL, not by message text, so a 401 from any non-/auth endpoint
// still fails. That is the case worth catching.
function isExpectedAuthConsoleError(msg: ConsoleMessage): boolean {
  const url = msg.location()?.url ?? '';
  return /\b(401|403)\b/.test(msg.text()) && url.includes('/auth/');
}

const ROUTES: Array<{ name: string; hash: string; expectSelector: string }> = [
  { name: 'home', hash: '#/', expectSelector: '#view-home' },
  { name: 'sessions (legacy)', hash: '#/sessions', expectSelector: '#view-sessions' },
  { name: 'leaderboards (legacy)', hash: '#/leaderboards', expectSelector: '#view-leaderboards' },
  { name: 'proximity (legacy)', hash: '#/proximity', expectSelector: '#view-proximity' },
  { name: 'skill-rating (React)', hash: '#/skill-rating', expectSelector: '#view-skill-rating' },
  { name: 'record-book (legacy)', hash: '#/record-book', expectSelector: '#view-record-book' },
];

for (const route of ROUTES) {
  test(`smoke: ${route.name} loads without console errors or failed requests`, async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      if (isExpectedAuthConsoleError(msg)) return;
      consoleErrors.push(msg.text());
    });
    // Uncaught exceptions surface here, not via console — a route that
    // throws without calling console.error (e.g. mid-loader, after the
    // legacy section's pre-rendered text is already visible) would
    // otherwise slip past the consoleErrors check entirely.
    page.on('pageerror', (error) => {
      consoleErrors.push(`pageerror: ${error.message}`);
    });
    page.on('requestfailed', (request) => {
      failedRequests.push(`${request.method()} ${request.url()} — ${request.failure()?.errorText}`);
    });
    page.on('response', (response) => {
      // Any 4xx/5xx is a failure, with ONE narrow exemption: 401/403 from an
      // /auth/* endpoint, which is the expected answer for a logged-out smoke
      // run (e.g. /auth/me during startup). Exempting those statuses for every
      // URL would hide the case where auth middleware is accidentally applied
      // to a public /api endpoint — the route can still render a nonempty
      // fallback with no console error, so the test would pass while the page
      // is actually broken (Codex review on #582). 404 is likewise not
      // exempt: loadScopedProximityData() swallows a 404 from
      // /api/proximity/summary into a fallback message without erroring.
      const status = response.status();
      if (status < 400) return;
      const isExpectedAuthChallenge =
        (status === 401 || status === 403) && new URL(response.url()).pathname.startsWith('/auth/');
      if (!isExpectedAuthChallenge) {
        failedRequests.push(`${response.request().method()} ${response.url()} -> ${status}`);
      }
    });

    // route.hash ("#/sessions") is a fragment only — page.goto() on a
    // fragment-only URL against a configured baseURL does a same-document
    // navigation (or an invalid-URL no-op), not a real document load, so
    // Playwright returns a null response and response?.ok() below always
    // fails regardless of whether the app actually works. Navigate to the
    // real path instead ("/#/sessions") so it resolves against baseURL.
    const response = await page.goto(`/${route.hash}`, { waitUntil: 'networkidle' });
    expect(response?.ok(), `initial page load for ${route.hash}`).toBeTruthy();

    // "renders something, not a blank error boundary": the route's own
    // view section must be present and hold visible content, not just
    // exist in the DOM while hidden/empty.
    const view = page.locator(route.expectSelector);
    await expect(view, `${route.expectSelector} should exist`).toBeAttached();
    await expect(view, `${route.expectSelector} should be visible`).toBeVisible();
    const text = await view.innerText();
    expect(text.trim().length, `${route.expectSelector} should hold real content, not be empty`).toBeGreaterThan(0);

    // "Nonempty" is not the same as "working". A route can render its own
    // error state and still pass every check above: e.g. /api/skill/leaderboard
    // returning HTTP 200 with an unparseable body (a proxy serving an HTML
    // error page) makes res.json() reject, React Query handles the rejection,
    // and SkillRating.tsx renders the "ET Rating" header plus "Failed to load
    // skill ratings." — no 5xx, no console error, nonempty text (Codex review
    // on #582). So assert the rendered text doesn't contain a failure message.
    const ERROR_TEXT = /failed to load|something went wrong|unable to load|error loading/i;
    expect(
      ERROR_TEXT.test(text),
      `${route.expectSelector} rendered an error state: ${text.trim().slice(0, 200)}`,
    ).toBe(false);

    // A stringified object reaching the DOM is always a bug, and it is the one
    // check none of the above catches: "[object Object]" is nonempty, is not an
    // error message and is not a loading placeholder, so the route passes every
    // other assertion while showing the user nothing meaningful.
    //
    // Found exactly this on #/record-book: /api/stats/maps returns objects, and
    // the map filter interpolated them straight into <option>, producing 18 of
    // these — with "[object Object]" as the option VALUE too, so the filter
    // matched nothing and had never worked.
    expect(
      text.includes('[object Object]'),
      `${route.expectSelector} rendered a stringified object`,
    ).toBe(false);

    // ...and not still sitting on its pre-rendered placeholder. The legacy
    // views ship static "Loading …" markup in index.html (e.g. line 1856 for
    // #view-sessions), so a loader that never ran — or returned without
    // touching its container — leaves the section visible, nonempty and
    // error-free, passing every check above while showing the user nothing
    // (Codex review on #582).
    await expect(
      view,
      `${route.expectSelector} still shows a loading placeholder — loader never resolved`,
    ).not.toHaveText(/loading[.\s]*$|loading\s+\w+\.\.\./i, { timeout: 15_000 });

    expect(consoleErrors, `console errors on ${route.hash}`).toEqual([]);
    expect(failedRequests, `failed/5xx requests on ${route.hash}`).toEqual([]);
  });
}

// Each ROUTES entry above gets its own fresh page, so none of them exercise
// an in-page transition away from the React route: resetModernRouteHost()
// unmounting the React root and restoring legacy children hidden via
// data-legacy-hidden. That's a distinct code path from an initial load and
// needs its own test.
test('smoke: navigating away from skill-rating (React) to sessions (legacy) unmounts cleanly', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    if (isExpectedAuthConsoleError(msg)) return;
    consoleErrors.push(msg.text());
  });
  page.on('pageerror', (error) => {
    consoleErrors.push(`pageerror: ${error.message}`);
  });

  await page.goto('/#/skill-rating', { waitUntil: 'networkidle' });
  const skillRatingRoot = page.locator('#view-skill-rating [data-modern-route-root]');
  await expect(skillRatingRoot, 'React root should be mounted under skill-rating').toBeAttached();
  await expect(async () => {
    expect((await skillRatingRoot.innerHTML()).length).toBeGreaterThan(0);
  }).toPass();

  // Start waiting for the route's own loader BEFORE triggering the transition —
  // set up afterwards, the wait can miss a response that already arrived.
  //
  // dispatchRoute() makes the view visible synchronously via setActiveView()
  // then awaits loadRoute(), but navigateTo() discards that promise, so the DOM
  // assertions below can all pass while the sessions request is still in flight
  // and a loader failing a moment later would go unseen.
  //
  // waitForLoadState('networkidle') does NOT cover this: the initial
  // page.goto() already reached networkidle, and Playwright resolves that call
  // immediately when the document is already in the requested state — the
  // previous version of this wait was a no-op on a hash-only transition (Codex
  // review on #582). Wait on the actual request instead.
  // /api/stats/sessions — NOT /api/sessions. loadSessions() builds
  // `${API_BASE}/stats/sessions?...` (website/js/sessions.js:1255); the wrong
  // path meant this never matched, so every run silently burned the full 15s
  // timeout and then asserted without having waited at all (Codex review on
  // #582).
  const sessionsLoaded = page
    .waitForResponse((r) => new URL(r.url()).pathname.startsWith('/api/stats/sessions'), {
      timeout: 15_000,
    })
    .catch(() => {
      // No new request (already-cached data) isn't a failure by itself — the
      // content assertions below still have to pass.
    });

  // In-page hash change — same mechanism a nav-link click uses — rather than
  // page.goto(), so this actually exercises dispatchRoute()'s client-side
  // transition instead of a fresh document load.
  await page.evaluate(() => {
    window.location.hash = '#/sessions';
  });

  await sessionsLoaded;

  const sessionsView = page.locator('#view-sessions');
  await expect(sessionsView, '#view-sessions should be visible after transition').toBeVisible();

  // Awaiting the response is NOT the same as awaiting the render, and asserting
  // on #view-sessions text does not distinguish the two. waitForResponse()
  // resolves on response HEADERS -- before fetchJSON() has read and parsed the
  // body and before loadSessions() has written anything to the DOM -- and the
  // .catch() above deliberately swallows the timeout, so "the loader never
  // fired the request at all" arrives here looking identical to success.
  //
  // Neither case is caught by the view's own text, because the static markup
  // already ships "Gaming Sessions" and "Loading sessions..."
  // (website/index.html:1856), so .trim().length > 0 is true before any data
  // exists. Poll the list itself until the placeholder is gone, which also
  // gives a failing loader time to render its error instead of letting the
  // console assertion below run first (Codex review on #582).
  const sessionsList = sessionsView.locator('#sessions-list');
  await expect(async () => {
    const listText = await sessionsList.innerText();
    expect(listText, 'sessions list should not still be showing its placeholder').not.toContain(
      'Loading sessions...',
    );
    expect(
      listText.trim().length,
      'sessions list should hold rendered content after the transition',
    ).toBeGreaterThan(0);
  }).toPass({ timeout: 15_000 });

  // resetModernRouteHost() clears the React root's children on unmount.
  await expect(skillRatingRoot, 'React root should be unmounted (emptied) after navigating away').toBeEmpty();

  expect(consoleErrors, 'console errors during the transition').toEqual([]);
});
