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
    page.on('requestfailed', (request) => {
      failedRequests.push(`${request.method()} ${request.url()} — ${request.failure()?.errorText}`);
    });
    page.on('response', (response) => {
      // 401/403 on auth-dependent calls (e.g. /auth/me for a logged-out
      // smoke run) are expected, not a page failure — only flag 5xx, which
      // is what W1 (500 triage) and this test exist to catch together.
      if (response.status() >= 500) {
        failedRequests.push(`${response.request().method()} ${response.url()} -> ${response.status()}`);
      }
    });

    const response = await page.goto(route.hash, { waitUntil: 'networkidle' });
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
