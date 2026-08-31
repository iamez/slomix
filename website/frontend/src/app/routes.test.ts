import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';
// The legacy registry itself is the oracle — a route added there without a
// counterpart here must turn this suite red, not become a discovery at
// switchover (docs/design/06 §3: "izpuščena route postane rdeč test").
// @ts-expect-error plain-JS module, typed only where spider-web.d.ts covers it
import { listRouteDefinitions, getRouteHash } from '../../../js/route-registry.js';
import { APP_ROUTES, hashToPath } from './routes';

/** Registry keys that deliberately fold into another app route. */
const FOLDED = new Map<string, string>([
  ['records', 'record-book'],
  ['hall-of-fame', 'record-book'],
]);

/** Sample params so buildHash() emits its non-empty shape per key. */
const SAMPLE_PARAMS = new Map<string, Record<string, unknown>>(Object.entries({
  profile: { id: 'E587CA5F' },
  'proximity-player': { guid: '1C747DF1' },
  'proximity-replay': { roundId: '11277' },
  'proximity-teams': { roundId: '11277' },
  'spider-web': { roundId: '11277' },
  greatshot: { section: 'demos' },
  'greatshot-demo': { demoId: 'abc123' },
  'upload-detail': { uploadId: 'de4f8d86' },
  story: { gsid: 150 },
  'session-detail': { sessionId: '150', tab: 'players' },
}));

const appByKey = new Map(APP_ROUTES.map((r) => [r.key, r]));

/**
 * Segment-wise route matcher: ':param' matches one segment, a trailing '?'
 * makes it optional. Translating a hash must land on a REGISTERED route —
 * '/leadeboards' is slash-prefixed and still a 404 (CodeRabbit on #802).
 * Written without RegExp on purpose: dynamic patterns trip three different
 * non-literal-RegExp scanners, and segments compare cleaner anyway.
 */
function matchesPattern(pathname: string, pattern: string): boolean {
  const want = pattern.split('/').filter(Boolean);
  const have = pathname.split('/').filter(Boolean);
  let hi = 0;
  for (const rawSeg of want) {
    const optional = rawSeg.endsWith('?');
    const seg = optional ? rawSeg.slice(0, -1) : rawSeg;
    // .at() types as string|undefined (bracket indexing doesn't under this
    // tsconfig) and sidesteps the object-injection-sink pattern scanners flag.
    const actual = have.at(hi);
    if (actual === undefined) {
      if (optional) continue;
      return false;
    }
    if (seg.startsWith(':') || seg === actual) {
      hi += 1;
      continue;
    }
    if (optional) continue;
    return false;
  }
  return hi === have.length;
}

function matchesRegisteredRoute(pathname: string): boolean {
  if (pathname === '/') return true;
  return APP_ROUTES.some((r) => matchesPattern(pathname, r.path));
}

describe('routes.ts covers the legacy registry', () => {
  const definitions = listRouteDefinitions() as Record<string, { label: string }>;

  for (const key of Object.keys(definitions)) {
    it(`legacy key '${key}' resolves to an app route`, () => {
      const target = FOLDED.get(key) ?? key;
      expect(appByKey.has(target), `no APP_ROUTES entry for '${target}'`).toBe(true);
    });

    it(`legacy hash for '${key}' maps to a REGISTERED route`, () => {
      const hash = getRouteHash(key, SAMPLE_PARAMS.get(key) ?? {});
      // home builds '' by design — the shim maps that to '/' via empty hash.
      const mapped = hashToPath(hash || '#/');
      expect(mapped, `hashToPath('${hash}') came back empty`).toBeTruthy();
      const pathname = mapped.split('?')[0];
      expect(
        matchesRegisteredRoute(pathname),
        `'${pathname}' (from '${hash}') matches no APP_ROUTES pattern — the router would render Not Found`,
      ).toBe(true);
    });
  }

  it('every app path is unique', () => {
    const paths = APP_ROUTES.map((r) => r.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('folded tabs carry the exact legacy tab values', () => {
    expect(hashToPath('#/records')).toBe('/record-book?tab=records');
    expect(hashToPath('#/hall-of-fame')).toBe('/record-book?tab=hof');
  });
});

// ---------------------------------------------------------------------------
// `nav` and the shell's own prefix list are two halves of one fact.
// ---------------------------------------------------------------------------

describe('routes and the shell agree on what is a stats page', () => {
  /** Read from source: the list lives in AppShell and nothing joins it to
   *  `nav: 'stats'`, so a route can be tagged and unrecognised — which renders
   *  the sub-nav on the way in, then makes the whole strip vanish on arrival
   *  and leaves the primary tab inactive. `/rounds` shipped that way. */
  function statsPrefixesFromShell(): string[] {
    const source = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), 'components', 'AppShell.tsx'),
      'utf8',
    );
    const block = source.match(/const statsPrefixes = \[([\s\S]*?)\];/);
    expect(block, 'statsPrefixes moved or was renamed').not.toBeNull();
    return [...(block as RegExpMatchArray)[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
  }

  it('every stats-tagged route is recognised as a stats path', () => {
    const prefixes = statsPrefixesFromShell();
    const unrecognised = APP_ROUTES.filter((r) => r.nav === 'stats')
      .map((r) => r.path)
      .filter((path) => !prefixes.some((p) => path === p || path.startsWith(`${p}/`)));
    expect(unrecognised, 'tagged for the stats sub-nav but the shell does not '
      + 'know them — the strip disappears on arrival').toEqual([]);
  });

  it('the check can fail', () => {
    // Without this, a regex that matched nothing would read as "all agree".
    expect(statsPrefixesFromShell().length).toBeGreaterThan(5);
  });
});

// ---------------------------------------------------------------------------
// `PAGES`, `phase` and the e2e stub threshold are three halves of one fact.
// ---------------------------------------------------------------------------

describe('the shell, the phases and the sweep agree on what is built', () => {
  const appDir = dirname(fileURLToPath(import.meta.url));

  /** Route keys the shell maps to a real component. Read from source because
   *  `main.tsx` cannot be imported: it calls `createRoot` and `applyHashShim`
   *  at module scope, so importing it would mount the app inside vitest. */
  function wiredKeys(): string[] {
    const source = readFileSync(join(appDir, 'main.tsx'), 'utf8');
    const start = source.indexOf('const PAGES');
    const end = source.indexOf('const router');
    expect(start, 'PAGES moved or was renamed').toBeGreaterThan(-1);
    expect(end, 'const router moved — the PAGES slice is unbounded')
      .toBeGreaterThan(start);
    return [...source.slice(start, end).matchAll(/^\s*'?([a-z0-9-]+)'?\s*:/gm)]
      .map((m) => m[1]);
  }

  /** The stub threshold the dev sweep enforces. */
  function sweepThreshold(): number {
    const source = readFileSync(join(appDir, '..', '..', 'e2e', 'app-routes.spec.ts'), 'utf8');
    const hit = source.match(/const BUILT_THROUGH_PHASE = (\d+)/);
    expect(hit, 'BUILT_THROUGH_PHASE moved or was renamed').not.toBeNull();
    return Number((hit as RegExpMatchArray)[1]);
  }

  it('a route is wired exactly when its phase is built', () => {
    const wired = new Set(wiredKeys());
    const built = Math.max(...APP_ROUTES.filter((r) => wired.has(r.key)).map((r) => r.phase));
    const wrong = APP_ROUTES
      .filter((r) => wired.has(r.key) !== (r.phase <= built))
      .map((r) => `${r.key} (phase ${r.phase}, ${wired.has(r.key) ? 'wired' : 'stub'})`);
    expect(wrong, 'a page can exist, have green tests and still render the '
      + 'phase stub in a browser — nothing else in this repo notices')
      .toEqual([]);
  });

  it('the dev sweep requires every built phase to have stopped stubbing', () => {
    // ⛔ THE FAILURE THIS EXISTS FOR. `BUILT_THROUGH_PHASE` is raised by hand,
    // and it was left at 3 while phase 4 shipped — so `session-detail` and
    // `session-detail-date`, the two newest pages, were the only routes exempt
    // from the one check that proves a stub is gone. A constant that must be
    // raised by hand is a constant that will stay too low; this is what makes
    // it self-checking instead.
    const wired = new Set(wiredKeys());
    const built = Math.max(...APP_ROUTES.filter((r) => wired.has(r.key)).map((r) => r.phase));
    expect(sweepThreshold(), `phase ${built} is wired in the shell but the dev `
      + `sweep still allows stubs up to phase ${sweepThreshold()} — raise `
      + 'BUILT_THROUGH_PHASE in e2e/app-routes.spec.ts').toBe(built);
  });

  it('the checks can fail', () => {
    // Without these, a regex that matched nothing would read as "all agree".
    expect(wiredKeys().length).toBeGreaterThan(20);
    expect(sweepThreshold()).toBeGreaterThan(0);
  });
});
