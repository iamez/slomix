import { expect, test } from '@playwright/test';

/**
 * H3's second project: the same app, seen logged in. Until now every smoke
 * pass ran anonymous, so anything only a signed-in visitor sees was
 * unreviewed by construction (plan §2c). The assertions here are
 * deliberately about the AUTH SEAM, not any one page's content:
 * /auth/me must answer with the minted user, and the console must be free
 * of the 401/403 noise that the anon specs treat as the expected answer —
 * logged in, that noise would mean the cookie did not reach the backend.
 */

test('the session cookie reaches the backend and /auth/me answers with the user', async ({ page }) => {
  const me = await page.request.get('/auth/me');
  expect(me.status()).toBe(200);
  const body = await me.json();
  expect(body.username).toBe('e2e-owner');
});

test('a logged-in shell load emits no auth 401/403 console noise', async ({ page }) => {
  const authNoise: string[] = [];
  page.on('console', (msg) => {
    if (/\b(401|403)\b/.test(msg.text()) && msg.location().url.includes('/auth/')) {
      authNoise.push(msg.text());
    }
  });
  await page.goto('/app/', { waitUntil: 'networkidle' });
  expect(authNoise).toEqual([]);
});
