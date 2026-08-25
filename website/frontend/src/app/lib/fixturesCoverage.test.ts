import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * H4 as a test (docs/design/09 §H4): every endpoint the app tree calls must
 * have a recorded fixture — pages are developed and tested against what the
 * backend really said, never against an invented shape. Until now this held
 * by convention; this walks the sources and makes it hold by assertion.
 *
 * Excluded: probes.ts (reachability pings, no data rendered — same reasoning
 * as its endpoint-ratchet exclusion in test_endpoint_gap.py) and templated
 * paths (no page calls one yet; when phase 3+ does, the fixture naming for
 * parameterised paths gets decided there, and this test will fail loudly to
 * force that decision).
 */

// jsdom rewrites import.meta.url to an http: scheme, so anchor on vitest's
// cwd (the frontend package root) instead.
const APP_SRC = path.resolve(process.cwd(), 'src', 'app');
const FIXTURES_DIR = path.join(APP_SRC, 'pages', '__fixtures__');

const CALL_RES = [
  /\bapiGet(?:<[^>]{0,200}>)?\(\s*'([^']+)'/g,
  /\bfetch\(\s*'(\/api\/[^'?]+)'/g,
];

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return entry.name === '__fixtures__' ? [] : sourceFiles(full);
    }
    if (!/\.tsx?$/.test(entry.name)) return [];
    if (entry.name.endsWith('.test.ts') || entry.name.endsWith('.test.tsx')) return [];
    if (entry.name === 'probes.ts') return [];
    return [full];
  });
}

function calledPaths(): string[] {
  const paths = new Set<string>();
  for (const file of sourceFiles(APP_SRC)) {
    const text = fs.readFileSync(file, 'utf8');
    for (const re of CALL_RES) {
      for (const match of text.matchAll(re)) {
        paths.add(match[1]);
      }
    }
  }
  return [...paths].sort();
}

/** '/api/voice-activity/current' -> 'api_voice_activity_current.json' */
function fixtureNameFor(apiPath: string): string {
  return `${apiPath.replace(/^\//, '').replace(/[/-]/g, '_')}.json`;
}

describe('H4 — fixture coverage', () => {
  it('every endpoint the app calls has a recorded fixture', () => {
    const paths = calledPaths();
    expect(paths.length).toBeGreaterThan(0);
    const missing = paths
      .filter((p) => !p.includes('{'))
      .filter((p) => !fs.existsSync(path.join(FIXTURES_DIR, fixtureNameFor(p))));
    expect(missing, `record these with scripts/record_api_corpus.py and copy into __fixtures__: ${missing.join(', ')}`).toEqual([]);
  });

  it('templated paths are not silently exempt', () => {
    // The moment a page calls a parameterised path, decide the fixture
    // naming for it and extend fixtureNameFor — this failing test is the
    // reminder mechanism, not an error.
    const templated = calledPaths().filter((p) => p.includes('{'));
    expect(templated).toEqual([]);
  });
});
