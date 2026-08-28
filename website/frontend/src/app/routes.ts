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
}

export const APP_ROUTES: readonly AppRoute[] = Object.freeze([
  { key: 'home', path: '/', label: 'Home', nav: 'primary', phase: 2 },
  { key: 'landing', path: '/welcome', label: 'Welcome', nav: 'hidden', phase: 1 },

  // Stats sub-navigation (STATS_VIEWS in the legacy registry).
  { key: 'sessions', path: '/sessions', label: 'Sessions', nav: 'stats', phase: 2 },
  { key: 'sessions2', path: '/sessions2', label: 'Sessions 2.0', nav: 'stats', phase: 2 },
  { key: 'session-detail', path: '/session-detail/:sessionId/:tab?', label: 'Session Detail', nav: 'hidden', phase: 4 },
  { key: 'session-detail-date', path: '/session-detail/date/:sessionDate/:tab?', label: 'Session Detail', nav: 'hidden', phase: 4 },
  { key: 'leaderboards', path: '/leaderboards', label: 'Leaderboards', nav: 'stats', phase: 2 },
  { key: 'maps', path: '/maps', label: 'Maps', nav: 'stats', phase: 2 },
  { key: 'weapons', path: '/weapons', label: 'Weapons', nav: 'stats', phase: 2 },
  { key: 'form', path: '/form', label: 'Form', nav: 'stats', phase: 2 },
  { key: 'awards', path: '/awards', label: 'Awards', nav: 'stats', phase: 2 },
  // records + hall-of-fame are tabs of one route; their legacy hashes land on
  // ?tab= via hashToPath (grammar: route-registry.js parseHash for both keys).
  { key: 'record-book', path: '/record-book', label: 'Record Book', nav: 'stats', phase: 2 },
  { key: 'retro-viz', path: '/retro-viz', label: 'Retro Viz', nav: 'stats', phase: 2 },
  // Per-round stats the profile (phase 3) and session-detail (phase 4) will
  // eventually host; a route of its own so the data is reachable now
  // without colliding with those pages.
  { key: 'rounds', path: '/rounds', label: 'Rounds', nav: 'stats', phase: 2 },
  { key: 'profile', path: '/profile/:id?', label: 'Profile', nav: 'stats', phase: 3 },
  { key: 'skill-rating', path: '/skill-rating', label: 'ET Rating', nav: 'stats', phase: 3 },
  { key: 'rivalries', path: '/rivalries', label: 'Rivalries', nav: 'stats', phase: 3 },
  { key: 'story', path: '/story', label: 'Smart Stats', nav: 'stats', phase: 3 },
  { key: 'story-session', path: '/story/session/:gsid', label: 'Smart Stats', nav: 'hidden', phase: 3 },
  { key: 'story-date', path: '/story/date/:date', label: 'Smart Stats', nav: 'hidden', phase: 3 },
  { key: 'replay', path: '/replay', label: 'Replay', nav: 'stats', phase: 5 },
  { key: 'smart-stats-diag', path: '/smart-stats-diag', label: 'Smart Stats — Diag', nav: 'footer', phase: 1 },

  { key: 'live', path: '/live', label: 'Live', nav: 'primary', phase: 6 },

  // Telemetry sub-navigation.
  { key: 'proximity', path: '/proximity', label: 'Proximity', nav: 'telemetry', phase: 5 },
  { key: 'proximity-player', path: '/proximity/player/:guid', label: 'Player Profile', nav: 'hidden', phase: 5 },
  { key: 'proximity-replay', path: '/proximity/round/:roundId', label: 'Round Replay', nav: 'hidden', phase: 5 },
  { key: 'proximity-teams', path: '/proximity/round/:roundId/teams', label: 'Team Comparison', nav: 'hidden', phase: 5 },
  // New page owned by the spider-web workstream (PR #800); registered now so
  // the route exists the day that page needs a home (docs/design/17 §3.5).
  { key: 'spider-web', path: '/spider-web/round/:roundId', label: 'Spider Web', nav: 'hidden', phase: 5 },

  { key: 'greatshot', path: '/greatshot/:section?', label: 'Greatshot', nav: 'primary', phase: 6 },
  { key: 'greatshot-demo', path: '/greatshot/demo/:demoId', label: 'Greatshot Demo', nav: 'hidden', phase: 6 },
  { key: 'uploads', path: '/uploads', label: 'Uploads', nav: 'primary', phase: 6 },
  { key: 'upload-detail', path: '/uploads/:uploadId', label: 'Upload Detail', nav: 'hidden', phase: 6 },
  { key: 'availability', path: '/availability', label: '#ETL', nav: 'primary', phase: 6 },
  { key: 'admin', path: '/admin', label: 'About', nav: 'primary', phase: 1 },
  { key: 'system', path: '/system', label: 'System', nav: 'footer', phase: 1 },
  // The component workshop (docs/design/11, plan A3). Deliberately `hidden`:
  // it is a surface for whoever is reworking layout, not a page for readers,
  // and it calls no endpoint so it cannot break with the data.
  { key: 'design', path: '/design', label: 'Design', nav: 'hidden', phase: 1 },
]);

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
