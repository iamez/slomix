/// <reference types="vite/client" />
import { readFileSync } from 'node:fs';
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
 *
 * Enumeration is Vite's `import.meta.glob`, the same shape
 * lib/fixturesCoverage.test.ts settled on: the bundler resolves the tree at
 * build time, so there is no filesystem walk and no path built at runtime.
 * The stylesheet itself is read with one literal path — importing it with
 * `?raw` yields an empty string here, because the Tailwind Vite plugin owns
 * .css imports and hands the test environment processed (i.e. nothing)
 * output. The literal keeps the scanner's question answered and the
 * emptiness check below turns a wrong working directory into a failure
 * rather than a silently passing suite.
 */

const SOURCES = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const cssRaw = readFileSync('src/app/tokens.css', 'utf8');

/**
 * Every check below reads the stylesheet as CODE, never as prose. This file
 * is heavily commented — including comments that name tokens and quote the
 * `@theme static` line — and a guard that matches a comment is a guard that
 * a future paragraph can satisfy without a single declaration behind it
 * (the class that bit us in #798's source-matching guards). Stripping
 * comments once, here, is what keeps "declared" meaning declared.
 */
export function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 * The same rule for TS/TSX. It matters for exactly the reason the CSS one
 * does: a component that documents `var(--space-${step})` in a comment would
 * otherwise be recorded as READING a token named `--space-`, which nothing
 * declares — the guard would fail on prose while the code was correct, and
 * the tempting fix would be to reword the comment rather than to read code.
 *
 * Line comments are stripped only when the line begins with `//` or with a
 * `*` continuation, never mid-line: `'https://…'` inside a string must not
 * take the rest of its line with it.
 */
export function stripJsComments(text: string): string {
  return stripComments(text)
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\*)/.test(line))
    .join('\n');
}

const css = stripComments(cssRaw);

function appSources(): [string, string][] {
  return Object.entries(SOURCES)
    .filter(([file]) => !file.endsWith('.test.ts') && !file.endsWith('.test.tsx'))
    .map(([file, text]) => [file, stripJsComments(text)]);
}

/** Names the stylesheet declares, from `@theme` and from `:root` alike. */
const declared = new Set(
  [...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]),
);

/**
 * Names the application reads, wherever it reads them — and the stylesheet
 * reads them too. Its own utility classes (.act, .chip, .row …) resolve
 * var(--color-rule-500) and friends, so a typo there would be exactly as
 * invisible as the one in TSX was, and scanning only TSX would miss it
 * (Codex on #823).
 */
const usedIn = new Map<string, Set<string>>();
for (const [file, text] of [...appSources(), ['tokens.css', css] as [string, string]]) {
  for (const m of text.matchAll(/var\((--[a-z0-9-]+)/g)) {
    const seen = usedIn.get(m[1]) ?? new Set<string>();
    seen.add(file);
    usedIn.set(m[1], seen);
  }
}

/** Relative luminance — the ramps are ordered by lightness, not by name. */
function luminance(hex: string): number {
  const channel = (pair: string) => {
    const c = parseInt(pair, 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return (
    0.2126 * channel(hex.slice(1, 3)) +
    0.7152 * channel(hex.slice(3, 5)) +
    0.0722 * channel(hex.slice(5, 7))
  );
}

describe('design tokens', () => {
  it('reads the stylesheet it claims to check, as code and not as prose', () => {
    // An empty read would make every assertion below vacuously true.
    expect(cssRaw.length).toBeGreaterThan(500);
    expect(declared.size).toBeGreaterThan(20);
    // And a token that only a comment mentions is not declared. Without this
    // the whole file could be satisfied by paragraphs about tokens rather
    // than by tokens.
    expect(stripComments('/* --color-ghost: #fff; */\n  --color-real: #000;')).not.toContain(
      '--color-ghost',
    );
    expect(stripComments('/* @theme static { */\n@theme {')).not.toMatch(/@theme\s+static\s*\{/);
  });

  it('declares every custom property the app reads', () => {
    const missing = [...usedIn.entries()]
      .filter(([name]) => !declared.has(name))
      .map(([name, files]) => `${name} (used in ${[...files].join(', ')})`);
    expect(missing).toEqual([]);
  });

  it('keeps the ground and rule ramps in the order the design gives them', () => {
    // A ramp whose steps are out of order is how --color-ink-800 came to mean
    // two different things in two files. The invariant every ramp here obeys
    // is one sentence: A HIGHER STEP NUMBER IS DARKER. ink-950 is the page
    // and ink-800 the row hover; rule-900 is the hairline and rule-400 an
    // active chip border; text-100 is the brightest text and text-600 the
    // footer. Checking only that the values differ would let rule-900 and
    // rule-800 swap — turning every hairline in the app into a box border
    // while the test stayed green (Codex on #823).
    const ramps = new Map<string, { step: number; hex: string }[]>();
    for (const m of css.matchAll(/^\s*--color-(ink|rule|text)-(\d+):\s*(#[0-9a-f]{6});/gm)) {
      const list = ramps.get(m[1]) ?? [];
      list.push({ step: Number(m[2]), hex: m[3] });
      ramps.set(m[1], list);
    }

    expect([...ramps.keys()].sort()).toEqual(['ink', 'rule', 'text']);
    for (const [name, steps] of ramps) {
      expect(steps.length, `${name} ramp is missing`).toBeGreaterThan(2);
      const hexes = steps.map((s) => s.hex);
      expect(new Set(hexes).size, `${name} ramp repeats a value`).toBe(hexes.length);

      const wrong: string[] = [];
      let previous: { step: number; hex: string } | null = null;
      for (const current of [...steps].sort((a, b) => a.step - b.step)) {
        if (previous && luminance(current.hex) >= luminance(previous.hex)) {
          wrong.push(
            `${name}-${current.step} (${current.hex}) is not darker than ${name}-${previous.step} (${previous.hex})`,
          );
        }
        previous = current;
      }
      expect(wrong, `${name} ramp is out of order`).toEqual([]);
    }
  });

  it('emits the theme statically, so inline styles can read it', () => {
    // Without `static`, Tailwind drops every token no CSS rule mentions, and
    // the app styles almost exclusively from TSX.
    expect(css).toMatch(/@theme\s+static\s*\{/);
  });

  it('names one container width AND makes the shell use it', () => {
    // Declaring the token proves nothing on its own: the four shell widths
    // could drift back to numbers one at a time and the token would sit
    // there, declared and unread (Codex on #823). So assert the consumption,
    // not the declaration.
    expect(declared.has('--layout-max')).toBe(true);
    const shell = SOURCES['./components/AppShell.tsx'];
    expect(shell, 'AppShell.tsx not found by the glob').toBeTruthy();
    expect([...shell.matchAll(/maxWidth:\s*'var\(--layout-max\)'/g)].length).toBe(4);
    expect(
      [...shell.matchAll(/maxWidth:\s*(?:\d+|'[^']*\d+(?:px|em|rem|%)[^']*')/g)].map((m) => m[0]),
      'the shell hard-codes a width again',
    ).toEqual([]);
  });

  it('carries a type and spacing scale, each monotonic', () => {
    // Layout and controls are going to be reworked repeatedly — that is the
    // owner's plan, not a risk. It stays cheap only while a size is a name.
    const scales = new Map<string, number[]>();
    for (const m of css.matchAll(/^\s*--(fs|space)-[a-z0-9]+:\s*(\d+)px;/gm)) {
      const list = scales.get(m[1]) ?? [];
      list.push(Number(m[2]));
      scales.set(m[1], list);
    }

    expect([...scales.keys()].sort()).toEqual(['fs', 'space']);
    for (const [name, steps] of scales) {
      expect(steps.length, `${name} scale is missing`).toBeGreaterThan(5);
      expect(steps, `${name} scale is not ascending`).toEqual([...steps].sort((a, b) => a - b));
      expect(new Set(steps).size, `${name} scale repeats a step`).toBe(steps.length);
    }
    expect(declared.has('--track-label')).toBe(true);
  });

  it('holds the pile of hand-typed sizes at exactly the budget', () => {
    /**
     * A ratchet in the shape this repo already trusts (tests/data/
     * endpoint_gap.txt): the number may fall, must never rise, and — this is
     * the part a `<=` would lose — the budget must be lowered in the same
     * commit that lowers the count. An allowance nobody is forced to update
     * stops describing anything after the first retrofit (Codex on #823).
     *
     * 1,012 raw sizes live in inline styles today across 14 of 34 pages. Left
     * alone the count passes 2,000 by the last phase, and every one of them
     * is a value the next layout rework has to read and re-decide by hand —
     * worse, 236 style blocks mix layout with look, so a find/replace cannot
     * separate what stays from what goes.
     *
     * Both spellings count. `padding: 12` and `padding: '12px 8px'` are the
     * same decision typed two ways, and counting only the first would let the
     * pile grow in the form React code most often uses (Codex again).
     */
    // 917 when the theme branch was written; 1,022 once main gained the
    // player page (#822, 105 of them) — a merge from main is the one motion
    // that can legitimately raise this number, since that work predates the
    // guard rather than defying it. 1,012 here: the five copied Pill
    // functions this PR deletes take ten of them with it.
    const BUDGET = 1012;
    const SIZE_PROP =
      /\b(?:fontSize|gap|columnGap|rowGap|margin|marginTop|marginBottom|marginLeft|marginRight|padding|paddingTop|paddingBottom):\s*(?:\d+\b|'[^']*\d+(?:px|em|rem|%)[^']*')/g;
    let count = 0;
    for (const [, text] of appSources()) {
      count += [...text.matchAll(SIZE_PROP)].length;
    }
    expect(
      count,
      count > BUDGET
        ? `raw inline sizes rose to ${count}; use the --fs-*/--space-* scale instead`
        : `raw inline sizes are down to ${count} — lower BUDGET to ${count} in this commit`,
    ).toBe(BUDGET);
  });
});
