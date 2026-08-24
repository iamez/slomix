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
 * Convert a react-router path pattern to a matcher: ':param' matches one
 * segment, a trailing '?' makes it optional. Translating a hash must land on
 * a REGISTERED route — '/leadeboards' is slash-prefixed and still a 404
 * (CodeRabbit on #802).
 */
function patternToRegex(pattern: string): RegExp {
  const parts = pattern.split('/').filter(Boolean).map((seg) => {
    const optional = seg.endsWith('?');
    const core = optional ? seg.slice(0, -1) : seg;
    const piece = core.startsWith(':') ? '[^/]+' : core.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return optional ? `(?:/${piece})?` : `/${piece}`;
  });
  // Input is our own APP_ROUTES constant table, not user data (test-only).
  // eslint-disable-next-line security/detect-non-literal-regexp
  // nosemgrep
  return new RegExp(`^${parts.join('')}$`);
}

const ROUTE_MATCHERS = APP_ROUTES.map((r) => patternToRegex(r.path));

function matchesRegisteredRoute(pathname: string): boolean {
  if (pathname === '/') return true;
  return ROUTE_MATCHERS.some((rx) => rx.test(pathname));
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
