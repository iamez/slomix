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
    const actual = have[hi];
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
