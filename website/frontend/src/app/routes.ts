/**
 * Single source of truth for the standalone app's routing — the transfer of
 * website/js/route-registry.js into real paths (docs/design/06 §3).
 *
 * Invariants, enforced by routes.test.ts against the legacy registry itself:
 *  - every legacy route key resolves to exactly one path here (records and
 *    hall-of-fame fold into record-book tabs — the key<->viewId duality dies);
 *  - every legacy hash shape a producer can emit maps through hashToPath()
 *    to a non-empty path this table can serve.
 *
 * The legacy registry stays untouched until switchover (app.js and
 * proximity.js import it); this file only ever *reads* the same URL grammar.
 */

export type NavSection = 'stats' | 'telemetry' | 'primary' | 'footer' | 'hidden';

export interface AppRoute {
  /** Legacy registry key (or a new-page name for routes the registry lacks). */
  key: string;
  /** react-router path pattern. */
  path: string;
  label: string;
  /** Which navigation surface owns the route (session-detail.dc.html nav). */
  nav: NavSection;
  /** Build phase from docs/design/08; shell renders a stub until then. */
  phase: number;
  /** True once the shell maps this route to a real page. Phases land page
   *  by page (phase 5 is six routes and six PRs), so the unit of "built"
   *  is the ROUTE — the phase number stays as planning provenance, but
   *  nothing derives whether a route is built from it anymore. routes.test.ts holds
   *  this flag, PAGES and the dev sweep in lockstep. */
  built?: boolean;
  /** Why this row exists, when that is not obvious from the row. */
  note?: string;
}

import routeData from './routes.data.json';

/**
 * The table itself lives in routes.data.json, not in this file.
 *
 * Not a style choice: the parity harness runs in plain Node (scripts/*.mjs,
 * which cannot import TypeScript), so as long as the table was TS, every
 * script that needed it kept its own copy — audit_website_browser.mjs carried
 * 29 hand-listed legacy routes while this table had 36, and nothing could
 * tell you they disagreed. JSON is the one format both worlds read, so there
 * is now one list and no generation step to forget. Each row's `note` carries
 * the reason that used to sit in a comment above it, which also means the
 * Node side can read the reason.
 */
export const APP_ROUTES: readonly AppRoute[] = Object.freeze(routeData as AppRoute[]);


const GREATSHOT_SECTIONS = new Set(['demos', 'highlights', 'clips', 'renders']);
const SESSION_DETAIL_TABS = new Set(['summary', 'players', 'teamplay', 'charts']);

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function enc(value: string): string {
  return encodeURIComponent(safeDecode(value));
}

/**
 * Map a legacy hash URL to a real path — the client-side shim's brain.
 *
 * Grammar transferred verbatim from route-registry.js parseHashRoute():
 * the eight producers (bot digest links, last_session cog, /share redirect)
 * plus the #/tonight, #/records and #/hall-of-fame aliases. The shim is
 * permanent: Discord messages never expire (06 §3).
 */
export function hashToPath(hash: string): string {
  const clean = String(hash || '').replace(/^#\/?/, '');
  if (!clean) return '/';

  const [routePath, query = ''] = clean.split('?');
  const q = query ? `?${query}` : '';
  const seg = routePath.split('/').filter(Boolean);
  if (seg.length === 0) return '/';

  switch (seg[0]) {
    case 'tonight':
      return `/live${q}`;
    case 'records':
      return withTab('/record-book', 'records', query);
    case 'hall-of-fame':
      // Legacy tab value is 'hof' (route-registry.js:286), not 'hall-of-fame'.
      return withTab('/record-book', 'hof', query);
    case 'greatshot': {
      if (seg[1] === 'demo' && seg[2]) return `/greatshot/demo/${enc(seg[2])}${q}`;
      const section = GREATSHOT_SECTIONS.has(seg[1]) ? seg[1] : 'demos';
      return `/greatshot/${section}${q}`;
    }
    case 'uploads':
      return seg[1] ? `/uploads/${enc(seg[1])}${q}` : `/uploads${q}`;
    case 'session-detail': {
      if (seg[1] === 'date' && seg[2]) {
        const tab = SESSION_DETAIL_TABS.has(seg[3]) && seg[3] !== 'summary' ? `/${seg[3]}` : '';
        return `/session-detail/date/${enc(seg[2])}${tab}${q}`;
      }
      if (seg[1]) {
        const tab = SESSION_DETAIL_TABS.has(seg[2]) && seg[2] !== 'summary' ? `/${seg[2]}` : '';
        return `/session-detail/${enc(seg[1])}${tab}${q}`;
      }
      return `/sessions2${q}`;
    }
    case 'story': {
      if (seg[1] === 'session' && seg[2]) return `/story/session/${enc(seg[2])}${q}`;
      if (seg[1] === 'date' && seg[2]) return `/story/date/${enc(seg[2])}${q}`;
      return `/story${q}`;
    }
    case 'proximity': {
      if (seg[1] === 'player' && seg[2]) return `/proximity/player/${enc(seg[2])}${q}`;
      if (seg[1] === 'round' && seg[2]) {
        return seg[3] === 'teams'
          ? `/proximity/round/${enc(seg[2])}/teams${q}`
          : `/proximity/round/${enc(seg[2])}${q}`;
      }
      return `/proximity${q}`;
    }
    case 'profile':
      return seg[1] ? `/profile/${enc(seg[1])}${q}` : `/profile${q}`;
    default:
      return `/${seg.map(enc).join('/')}${q}`;
  }
}

function withTab(path: string, tab: string, extraQuery: string): string {
  const params = new URLSearchParams(extraQuery);
  params.set('tab', tab);
  return `${path}?${params.toString()}`;
}
