import { expect, test } from '@playwright/test';

/**
 * docs/design/19 §5, slice 1: the dataset register is published, typed and
 * reachable. The proof the design doc asks for is exactly this — the
 * endpoint answers with the sections the site renders, and a browser
 * session can reach it without signing in.
 */
test('the dataset register is public, typed and names the profile sections', async ({ request }) => {
  const res = await request.get('/api/datasets');
  expect(res.status()).toBe(200);
  const body = await res.json() as { registry_version: string; count: number; datasets: { key: string; default_visible_on: string[] }[] };
  expect(body.count).toBe(body.datasets.length);
  expect(body.count).toBeGreaterThanOrEqual(30);
  const keys = new Set(body.datasets.map((d) => d.key));
  for (const k of ['identity', 'weapons', 'maps', 'aim', 'advanced', 'session_basics', 'proximity_capture', 'kill_impact']) {
    expect(keys.has(k), `missing dataset ${k}`).toBe(true);
  }
  const onProfile = body.datasets.filter((d) => d.default_visible_on.includes('profile')).map((d) => d.key);
  expect(onProfile).toContain('weapons');
  expect(onProfile).not.toContain('aim');
});
