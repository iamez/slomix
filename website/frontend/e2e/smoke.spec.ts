import { test, expect } from '@playwright/test';

// W7: five routes to start (not the full 30 from docs/ROUTE_MAP_2026-07.md),
// mixing legacy JS and React so both frontends are covered. Each page must
// load, render real content (not a blank error boundary), and produce zero
// console errors / zero failed network requests — that's the part that
// turns the F12 loop (W9) into something automated instead of anecdotal.
const ROUTES: Array<{ name: string; hash: string; expectSelector: string }> = [
  { name: 'home', hash: '#/', expectSelector: '#view-home' },
  { name: 'sessions (legacy)', hash: '#/sessions', expectSelector: '#view-sessions' },
  { name: 'leaderboards (legacy)', hash: '#/leaderboards', expectSelector: '#view-leaderboards' },
  { name: 'proximity (legacy)', hash: '#/proximity', expectSelector: '#view-proximity' },
  { name: 'skill-rating (React)', hash: '#/skill-rating', expectSelector: '#view-skill-rating' },
];

for (const route of ROUTES) {
  test(`smoke: ${route.name} loads without console errors or failed requests`, async ({ page }) => {
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
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
    if (msg.type() === 'error') consoleErrors.push(msg.text());
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

  // In-page hash change — same mechanism a nav-link click uses — rather than
  // page.goto(), so this actually exercises dispatchRoute()'s client-side
  // transition instead of a fresh document load.
  await page.evaluate(() => {
    window.location.hash = '#/sessions';
  });

  const sessionsView = page.locator('#view-sessions');
  await expect(sessionsView, '#view-sessions should be visible after transition').toBeVisible();
  const sessionsText = await sessionsView.innerText();
  expect(sessionsText.trim().length, 'sessions view should hold real content after transition').toBeGreaterThan(0);

  // resetModernRouteHost() clears the React root's children on unmount.
  await expect(skillRatingRoot, 'React root should be unmounted (emptied) after navigating away').toBeEmpty();

  // Wait for the route's own async loader before judging errors.
  // dispatchRoute() makes the view visible synchronously via setActiveView(),
  // then awaits loadRoute() — but navigateTo() discards that promise, so the
  // assertions above can all pass while the sessions request is still in
  // flight. Checking consoleErrors at that point would miss a loader that
  // fails a moment later, letting a real transition regression through
  // (Codex review on #582).
  await page.waitForLoadState('networkidle');

  expect(consoleErrors, 'console errors during the transition').toEqual([]);
});
