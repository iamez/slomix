import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * The theme has to survive two journeys, and it failed both before this file
 * existed (measured 2026-08-28 on the live dev page):
 *
 *  1. NAME -> DECLARATION. `var(--color-ink-800)` was written at 21 call sites
 *     across 8 pages and declared nowhere. Every box and search field that
 *     asked for it rendered `rgba(0, 0, 0, 0)` — a background silently absent
 *     rather than wrong, which is why nobody saw it for two phases.
 *  2. DECLARATION -> BROWSER. Tailwind v4 only emits the theme variables that
 *     some CSS rule or generated utility references, and a `var(--x)` inside a
 *     React `style={{}}` is not such a reference. Nine tokens — including
 *     allies, axis and all four speed bands — never reached :root.
 *
 * This file guards (1) statically, in CI, with no browser. Guarding (2) needs
 * a real page, so it lives in the dev sweep (e2e/app-tokens.spec.ts); the
 * `@theme static` declaration in tokens.css is what makes it pass.
 */

const APP_DIR = join(__dirname);
const TOKENS_CSS = join(APP_DIR, 'tokens.css');

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      sourceFiles(full, out);
    } else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

const css = readFileSync(TOKENS_CSS, 'utf8');

/** Names the stylesheet declares, from `@theme` and from `:root` alike. */
const declared = new Set(
  [...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]),
);

/** Names the application reads, wherever it reads them. */
const usedIn = new Map<string, string[]>();
for (const file of sourceFiles(APP_DIR)) {
  const text = readFileSync(file, 'utf8');
  for (const m of text.matchAll(/var\((--[a-z0-9-]+)/g)) {
    const list = usedIn.get(m[1]) ?? [];
    list.push(file.slice(APP_DIR.length + 1));
    usedIn.set(m[1], list);
  }
}

describe('design tokens', () => {
  it('declares every custom property the app reads', () => {
    const missing = [...usedIn.entries()]
      .filter(([name]) => !declared.has(name))
      .map(([name, files]) => `${name} (used in ${[...new Set(files)].join(', ')})`);
    expect(missing).toEqual([]);
  });

  it('keeps the ground and rule ramps in the order the design gives them', () => {
    // A ramp whose steps are out of order is how --color-ink-800 came to mean
    // two different things in two files. Darkest first, no duplicates.
    const ramp = (prefix: string) =>
      [...css.matchAll(new RegExp(`^\\s*--color-${prefix}-(\\d+):\\s*(#[0-9a-f]{6});`, 'gm'))]
        .map((m) => ({ step: Number(m[1]), hex: m[2] }));
    for (const prefix of ['ink', 'rule', 'text']) {
      const steps = ramp(prefix);
      expect(steps.length, `${prefix} ramp is missing`).toBeGreaterThan(2);
      const hexes = steps.map((s) => s.hex);
      expect(new Set(hexes).size, `${prefix} ramp repeats a value`).toBe(hexes.length);
    }
  });

  it('emits the theme statically, so inline styles can read it', () => {
    // Without `static`, Tailwind drops every token no CSS rule mentions, and
    // the app styles almost exclusively from TSX.
    expect(css).toMatch(/@theme\s+static\s*\{/);
  });

  it('names one container width instead of the prototypes six', () => {
    expect(declared.has('--layout-max')).toBe(true);
  });

  it('carries a type and spacing scale, each monotonic', () => {
    // Layout and controls are going to be reworked repeatedly — that is the
    // owner's plan, not a risk. It stays cheap only while a size is a name.
    const scale = (prefix: string) =>
      [...css.matchAll(new RegExp(`^\\s*--${prefix}-([a-z0-9]+):\\s*(\\d+)px;`, 'gm'))].map(
        (m) => Number(m[2]),
      );
    for (const prefix of ['fs', 'space']) {
      const steps = scale(prefix);
      expect(steps.length, `${prefix} scale is missing`).toBeGreaterThan(5);
      expect(steps, `${prefix} scale is not ascending`).toEqual([...steps].sort((a, b) => a - b));
      expect(new Set(steps).size, `${prefix} scale repeats a step`).toBe(steps.length);
    }
    expect(declared.has('--track-label')).toBe(true);
  });

  it('does not grow the pile of hand-typed sizes', () => {
    /**
     * A ratchet, in the shape this repo already trusts (tests/data/
     * endpoint_gap.txt): a number that may fall and must never rise.
     *
     * 805 raw sizes live in inline styles today across 13 of 34 pages. Left
     * alone the count reaches ~2,000 by the last phase, and every one of them
     * is a value the next layout rework has to be read and re-decided by
     * hand — worse, 236 style blocks mix layout with look, so a find/replace
     * cannot separate what stays from what goes.
     *
     * This does not forbid them: the retrofit lowers the number page by page.
     * It forbids the pile getting deeper while that happens. When you lower
     * it, lower the budget with it.
     */
    const BUDGET = 805;
    const pattern =
      /\b(fontSize|gap|columnGap|rowGap|margin|marginTop|marginBottom|marginLeft|marginRight|padding|paddingTop|paddingBottom):\s*\d+\b/g;
    let count = 0;
    for (const file of sourceFiles(APP_DIR)) {
      count += [...readFileSync(file, 'utf8').matchAll(pattern)].length;
    }
    expect(
      count,
      count > BUDGET
        ? `raw inline sizes rose to ${count}; use the --fs-*/--space-* scale instead`
        : `raw inline sizes are down to ${count} — lower BUDGET to match`,
    ).toBeLessThanOrEqual(BUDGET);
  });
});
