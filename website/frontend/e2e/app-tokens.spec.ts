import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

/**
 * The browser half of the token guard (the static half is
 * src/app/tokens.test.ts, which runs in CI without a browser).
 *
 * Why a real page is needed: Tailwind v4 decides at BUILD time which theme
 * variables to emit, and it emits only the ones some CSS rule or generated
 * utility references. Everything this app styles from a React `style={{}}`
 * is invisible to that analysis. Measured on dev before `@theme static`:
 * ink-850, ink-800, rule-600, allies, axis and speed-1..4 were declared in
 * tokens.css and absent from getComputedStyle(:root) — and 22 boxes on
 * /app/maps had backgroundColor rgba(0, 0, 0, 0) as a result.
 *
 * No unit test can see that: the source says the token exists, the built
 * stylesheet says it does not. So this reads the names out of tokens.css and
 * asks the page itself for each one.
 *
 * Runs against a built /app served by the dev backend — the prerequisites of
 * smoke.spec.ts plus step 3b in playwright.config.ts (`npm run build:app`,
 * a bundle separate from `build`), and in that order: the backend decides
 * whether /app exists when it starts, so a build after startup still 404s.
 * Not wired into CI, for the same reason smoke.spec.ts is not.
 */

const here = dirname(fileURLToPath(import.meta.url));
const TOKENS_CSS = join(here, '../src/app/tokens.css');

const declaredNames = [
  ...readFileSync(TOKENS_CSS, 'utf8').matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm),
].map((m) => m[1]);

test('every declared token reaches the browser', async ({ page }) => {
  expect(declaredNames.length).toBeGreaterThan(20);
  await page.goto('/app/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('nav, header', { timeout: 15_000 });

  const empty = await page.evaluate((names: string[]) => {
    const cs = getComputedStyle(document.documentElement);
    return names.filter((n) => !cs.getPropertyValue(n).trim());
  }, declaredNames);

  expect(empty, `tokens declared but absent at runtime: ${empty.join(', ')}`).toEqual([]);
});

test('no element asks for a background it does not get', async ({ page }) => {
  // The consequence, not the cause: an inline background that resolves to an
  // undefined custom property paints nothing at all, and on a near-black page
  // that reads as "designed flat" rather than "broken".
  for (const path of ['/app/', '/app/maps', '/app/record-book']) {
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const transparent = await page.evaluate(() => {
      const out: string[] = [];
      // Array.from, not a spread: tsconfig.e2e.json omits DOM.Iterable, so a
      // NodeList is not iterable under that project even though it is at run
      // time (CI's second tsc pass caught this; the app pass did not).
      for (const el of Array.from(document.querySelectorAll<HTMLElement>('[style*="background"]'))) {
        const wanted = el.getAttribute('style') || '';
        if (!/background[^;]*var\(--/.test(wanted)) continue;
        const got = getComputedStyle(el).backgroundColor;
        if (got === 'rgba(0, 0, 0, 0)' || got === 'transparent') {
          out.push(wanted.slice(0, 80));
        }
      }
      return out;
    });
    expect(transparent, `${path} paints nothing where a token was asked for`).toEqual([]);
  }
});
