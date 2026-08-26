/// <reference types="vite/client" />
import { describe, expect, it } from 'vitest';

/**
 * H4 as a test (docs/design/09 §H4): every endpoint the app tree calls must
 * have a recorded fixture — pages are developed and tested against what the
 * backend really said, never against an invented shape. Until now this held
 * by convention; this makes it hold by assertion.
 *
 * Enumeration is Vite's `import.meta.glob` with literal patterns — the
 * bundler resolves the tree at build time, so there is no filesystem walk
 * and no dynamically constructed path anywhere (the first version used
 * node:fs and Codacy rightly asked why a test builds paths at runtime).
 *
 * Excluded: probes.ts (reachability pings, no data rendered — same reasoning
 * as its endpoint-ratchet exclusion in test_endpoint_gap.py) and templated
 * paths (no page calls one yet; when phase 3+ does, the fixture naming for
 * parameterised paths gets decided there, and this test will fail loudly to
 * force that decision).
 */

const SOURCES = import.meta.glob('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const FIXTURES = import.meta.glob('../pages/__fixtures__/*.json');

const CALL_RES = [
  /\bapiGet(?:<[^>]{0,200}>)?\(\s*'([^']+)'/g,
  /\bfetch\(\s*'(\/api\/[^'?]+)'/g,
];

function calledPaths(): string[] {
  const paths = new Set<string>();
  for (const [file, text] of Object.entries(SOURCES)) {
    if (file.includes('/__fixtures__/')) continue;
    if (file.endsWith('.test.ts') || file.endsWith('.test.tsx')) continue;
    if (file.endsWith('/probes.ts')) continue;
    for (const re of CALL_RES) {
      for (const match of text.matchAll(re)) {
        paths.add(match[1]);
      }
    }
  }
  return [...paths].sort();
}

/** '/api/voice-activity/current' -> 'api_voice_activity_current.json'.
 * Templated paths drop the braces, matching the corpus recorder's own
 * slugs: '/api/seasons/{season_id}/awards' ->
 * 'api_seasons_season_id_awards.json' — the naming decision phase 2's
 * first parameterised call forced (this test failed loudly until it was
 * made, exactly as designed). */
function fixtureNameFor(apiPath: string): string {
  return `${apiPath.replace(/^\//, '').replace(/[{}]/g, '').replace(/[/-]/g, '_')}.json`;
}

describe('H4 — fixture coverage', () => {
  it('every endpoint the app calls has a recorded fixture', () => {
    const paths = calledPaths();
    expect(paths.length).toBeGreaterThan(0);
    const missing = paths
      .filter((p) => !(`../pages/__fixtures__/${fixtureNameFor(p)}` in FIXTURES));
    expect(missing, `record these with scripts/record_api_corpus.py and copy into __fixtures__: ${missing.join(', ')}`).toEqual([]);
  });
});
