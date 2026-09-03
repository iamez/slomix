import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';
// The legacy registry itself is the oracle — a route added there without a
// counterpart here must turn this suite red, not become a discovery at
// switchover (docs/design/06 §3: "izpuščena route postane rdeč test").
// @ts-expect-error plain-JS module, typed only where spider-web.d.ts covers it
import { listRouteDefinitions, getRouteHash } from '../../../js/route-registry.js';
import { APP_ROUTES, hashToPath, PARAM_REDIRECTS, REDIRECTS, SESSION_DETAIL_TABS } from './routes';

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
      // A retired route still resolves — through its redirect (stats 2.0
      // folded sessions2 into sessions), never into a stub or a 404.
      const redirected = REDIRECTS.find((r) => r.from === `/${target}`);
      const resolved = redirected ? matchesRegisteredRoute(redirected.to) : appByKey.has(target);
      expect(resolved, `no APP_ROUTES entry (or redirect) for '${target}'`).toBe(true);
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

describe('redirects', () => {
  it('every redirect target is a registered route and no source is', () => {
    for (const r of REDIRECTS) {
      expect(matchesRegisteredRoute(r.to), `${r.from} -> ${r.to} points at nothing`).toBe(true);
      expect(matchesRegisteredRoute(r.from), `${r.from} is both a route and a redirect`).toBe(false);
    }
    expect(REDIRECTS.length).toBeGreaterThan(0);
  });

  it('a parameterised redirect lands on a registered route once its params are filled', () => {
    // Substitute sample values so both ends are concrete paths: the source
    // must match no route (it is retired), the target must match one.
    const fill = (pattern: string) => pattern.replace(/:gsid/g, '150').replace(/:date/g, '2026-08-27');
    for (const r of PARAM_REDIRECTS) {
      expect(matchesRegisteredRoute(fill(r.to)), `${r.from} -> ${r.to} points at nothing`).toBe(true);
      expect(matchesRegisteredRoute(fill(r.from)), `${r.from} is both a route and a redirect`).toBe(false);
      // The target keeps every param the source captured — otherwise
      // generatePath throws at runtime for the visitor, not in a test.
      const params = [...r.from.matchAll(/:([a-z]+)/g)].map((m) => m[1]);
      for (const name of params) expect(r.to.includes(`:${name}`), `${r.to} drops :${name}`).toBe(true);
    }
    expect(PARAM_REDIRECTS.length).toBeGreaterThan(0);
  });

  it('the legacy story hashes land on the session page story tab', () => {
    expect(hashToPath('#/story/session/154')).toBe('/session-detail/154/story');
    expect(hashToPath('#/story/date/2026-08-27')).toBe('/session-detail/date/2026-08-27/story');
    expect(hashToPath('#/story')).toBe('/sessions');
    // The page's own tab list is the grammar: a rounds link keeps its tab.
    expect(hashToPath('#/session-detail/154/rounds')).toBe('/session-detail/154/rounds');
    expect(SESSION_DETAIL_TABS).toContain('rounds');
  });
});

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

  it('a route is wired exactly when the registry says it is built', () => {
    // The old invariant derived "built" from the PHASE number, which held
    // while phases landed whole — and broke the day phase 5 landed its
    // first page (six routes, six PRs, one wired). The unit of "built" is
    // the ROUTE, and the registry row says it; this test holds the flag
    // and PAGES in lockstep, in both directions, so a page that exists
    // with green tests but still stubs in the browser is caught by the
    // flag it forgot to set — the same failure the phase version existed
    // for.
    const wired = new Set(wiredKeys());
    const wrong = APP_ROUTES
      .filter((r) => wired.has(r.key) !== (r.built === true))
      .map((r) => `${r.key} (${wired.has(r.key) ? 'wired but not marked built' : 'marked built but stubbing'})`);
    expect(wrong, 'a page can exist, have green tests and still render the '
      + 'phase stub in a browser — nothing else in this repo notices')
      .toEqual([]);
  });

  it('the dev sweep reads the built flag, not a hand-raised constant', () => {
    // ⛔ THE FAILURE THE OLD CONSTANT HAD. `BUILT_THROUGH_PHASE` was raised
    // by hand and was left at 3 while phase 4 shipped, so the two newest
    // pages were exempt from the one check that proves a stub is gone. The
    // sweep now derives the expectation per route from the same registry
    // row the shell routes with; this test pins that it stays that way.
    const source = readFileSync(join(appDir, '..', '..', 'e2e', 'app-routes.spec.ts'), 'utf8');
    expect(source, 'the sweep grew a hand threshold again').not.toMatch(/BUILT_THROUGH_PHASE/);
    expect(source.includes('route.built'), 'the sweep no longer reads route.built').toBe(true);
  });

  it('the session-tabs sweep spells out the same tab grammar as routes.ts', () => {
    // e2e/session-tabs.spec.ts cannot import routes.ts (JSON import
    // attribute), so it carries its own copy of SESSION_DETAIL_TABS; a tab
    // added here and not there is a tab the sweep never visits.
    const source = readFileSync(join(appDir, '..', '..', 'e2e', 'session-tabs.spec.ts'), 'utf8');
    const m = source.match(/const SESSION_DETAIL_TABS = \[([^\]]*)\]/);
    expect(m, 'the sweep lost its tab list').not.toBeNull();
    const listed = [...(m as RegExpMatchArray)[1].matchAll(/'([a-z]+)'/g)].map((x) => x[1]);
    expect(listed).toEqual([...SESSION_DETAIL_TABS]);
  });

  it('the checks can fail', () => {
    // Without these, a regex that matched nothing would read as "all agree".
    expect(wiredKeys().length).toBeGreaterThan(20);
    expect(APP_ROUTES.filter((r) => r.built === true).length).toBeGreaterThan(20);
  });
});
