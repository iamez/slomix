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

test('the e2e owner is logged in but NOT an admin: no diagnostics panel, no request', async ({ page }) => {
  // Admin is an env allowlist of Discord ids (dependencies.py
  // _configured_admin_ids) and the e2e sentinel's id is -1, which no digits
  // filter admits — so the rig has no admin tier. The admin rendering is
  // pinned in About.test.tsx against a recording made as the real admin;
  // here the gate itself is proven: a signed-in non-admin sees no panel and
  // the page never asks.
  const asked: string[] = [];
  page.on('request', (r) => { if (/\/api\/diagnostics(\?|$)/.test(r.url())) asked.push(r.url()); });
  // The About page fires twelve probes and the availability access read;
  // wait for the panel, not for network idle.
  await page.goto('/app/admin', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-parity="admin.probes"]')).toBeVisible();
  const access = await page.request.get('/api/availability/access');
  expect((await access.json()).is_admin).toBe(false);
  await expect(page.locator('[data-parity="admin.diagnostics"]')).toHaveCount(0);
  expect(asked).toEqual([]);
});
