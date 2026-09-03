import { test, expect, type ConsoleMessage } from '@playwright/test';

/** The tab grammar, spelled out: the runner's loader cannot import
 *  routes.ts (its JSON import has no attribute), so routes.test.ts asserts
 *  this list and SESSION_DETAIL_TABS agree — the same lockstep the sweep
 *  keeps with `route.built`. */
const SESSION_DETAIL_TABS = ['summary', 'players', 'rounds', 'teamplay', 'story'] as const;

/**
 * Stats 2.0 R4: the session page's five tabs, on a full night and a thin one.
 *
 * app-routes.spec.ts sweeps every route once with `:tab?` empty, so it only
 * ever sees the summary — the four other tabs would be exempt from the one
 * check that catches a crash on real data. Same discipline as the sweep:
 * two samples (154 fills every field; 80 has counted rounds but no KIS, no
 * team attribution, no proximity for the trade table), no `undefined`/`NaN`
 * in the text, no console errors, and the tab's parity node present so a
 * tab that silently rendered nothing is a failure, not a pass.
 *
 * NOT wired into CI (no served frontend there); a dev sweep against :8056.
 */
const SESSIONS = [
  { id: 154, note: 'full night' },
  { id: 80, note: 'thin: no KIS, no teams, no proximity' },
];

/** 404s are answers on the thin sample (a panel's endpoint has nothing),
 *  not failures; anything else in the console is. */
const notFoundNoise = /\b404\b/;

function watch(page: import('@playwright/test').Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() === 'error' && !notFoundNoise.test(msg.text())) errors.push(msg.text());
  });
  page.on('pageerror', (error) => { errors.push(`pageerror: ${error.message}`); });
  return errors;
}

for (const s of SESSIONS) {
  for (const tab of SESSION_DETAIL_TABS) {
    const url = tab === 'summary' ? `/app/session-detail/${s.id}` : `/app/session-detail/${s.id}/${tab}`;
    test(`session ${s.id} (${s.note}) · ${tab} tab renders`, async ({ page }) => {
      const errors = watch(page);
      const response = await page.goto(url, { waitUntil: 'networkidle' });
      expect(response?.status()).toBe(200);
      await expect(page.locator(`[data-parity="session.${tab === 'summary' ? 'tabs' : tab}"]`)).toBeVisible();
      const text = await page.locator('body').innerText();
      expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\[object Object\]/);
      expect(errors, `${url} logged console errors`).toEqual([]);
    });
  }
}

test('the legacy story links land on the story tab', async ({ page }) => {
  await page.goto('/app/#/story/session/154', { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/\/app\/session-detail\/154\/story$/);
  await page.goto('/app/story/session/154', { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/\/app\/session-detail\/154\/story$/);
  await page.goto('/app/rounds', { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/\/app\/sessions$/);
});

test('the players tab carries the 21 legacy columns with their definitions', async ({ page }) => {
  await page.goto('/app/session-detail/154/players', { waitUntil: 'networkidle' });
  const table = page.locator('[data-parity="session.players"]');
  await expect(table).toBeVisible();
  const headers = table.locator('[role="region"] > div > .row').first().locator('> *');
  await expect(headers).toHaveCount(21);
  await expect(table.getByRole('button', { name: /^uk/ })).toHaveAttribute('title', /useful kills — the victim had at least half the spawn cycle/);
  await expect(table.getByRole('button', { name: /^alive %/ })).toHaveAttribute('title', /Alive%: time not dead/);
});

test('the story tab lists the objective escorts on the full night and says why the thin one has none', async ({ page }) => {
  await page.goto('/app/session-detail/154/story', { waitUntil: 'networkidle' });
  const panel = page.locator('[data-parity="story.escorts"]');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('escorted the truck on supply');
  await page.goto('/app/session-detail/80/story', { waitUntil: 'networkidle' });
  await expect(page.locator('[data-parity="story.escorts"]')).toContainText('no round in this session had a vehicle');
});

for (const s of SESSIONS) {
  test(`session ${s.id} (${s.note}) · the expanded player row opens with its five instruments`, async ({ page }) => {
    const errors = watch(page);
    await page.goto(`/app/session-detail/${s.id}/players`, { waitUntil: 'networkidle' });
    const first = page.locator('[data-parity="session.players"] button[aria-expanded]').first();
    await first.click();
    const row = page.locator('[data-parity="session.player"]');
    await expect(row).toBeVisible();
    for (const part of ['links', 'maps', 'life', 'form', 'kis', 'weapons']) {
      await expect(row.locator(`[data-parity="session.player.${part}"]`)).toBeVisible();
    }
    // Every instrument has answered — nothing is still pending.
    await expect(row.getByText(/…$/)).toHaveCount(0, { timeout: 15000 });
    const text = await row.innerText();
    expect(text).not.toMatch(/\bundefined\b|\bNaN\b|\bInfinity\b|\[object Object\]/);
    expect(errors, `session ${s.id} drilldown logged console errors`).toEqual([]);
  });
}
