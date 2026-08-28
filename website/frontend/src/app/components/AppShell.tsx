import { Link, NavLink, Outlet, useLocation } from 'react-router';
import { APP_ROUTES } from '../routes';

/**
 * The one navigation (docs/design/11 §A AppShell; layout and labels from
 * session-detail.dc.html — the most complete nav among the prototypes, O3).
 * Primary bar: 60-66px, logo, seven entries, server dot, Connect ID.
 * A secondary strip appears for sections that own sub-routes (stats,
 * telemetry). Footer: hairline + two mono lines.
 */

const PRIMARY: Array<{ label: string; to: string; section: 'stats' | 'telemetry' | null; prefix: string }> = [
  { label: 'Stats', to: '/sessions', section: 'stats', prefix: '/sessions' },
  { label: 'Live', to: '/live', section: null, prefix: '/live' },
  { label: 'Telemetry', to: '/proximity', section: 'telemetry', prefix: '/proximity' },
  { label: 'Greatshot', to: '/greatshot/demos', section: null, prefix: '/greatshot' },
  { label: 'Uploads', to: '/uploads', section: null, prefix: '/uploads' },
  { label: '#ETL', to: '/availability', section: null, prefix: '/availability' },
  { label: 'About', to: '/admin', section: null, prefix: '/admin' },
];

function sectionFor(pathname: string): 'stats' | 'telemetry' | null {
  const statsPrefixes = [
    '/sessions', '/sessions2', '/session-detail', '/leaderboards', '/maps',
    '/weapons', '/form', '/awards', '/record-book', '/retro-viz', '/profile',
    '/skill-rating', '/rivalries', '/story', '/replay', '/rounds',
  ];
  // ⛔ This list and `nav: 'stats'` in routes.ts are two halves of one fact,
  // and nothing joins them: a route tagged for the stats sub-nav but missing
  // here renders the sub-nav, then makes it vanish the moment you click into
  // the page. `routes.test.ts` now asserts the two agree.
  if (pathname.startsWith('/proximity') || pathname.startsWith('/spider-web')) return 'telemetry';
  if (statsPrefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return 'stats';
  return null;
}

function SubNav({ section }: { section: 'stats' | 'telemetry' }) {
  const items = APP_ROUTES.filter((r) => r.nav === section);
  return (
    <div style={{ borderBottom: '1px solid var(--color-rule-900)', background: 'var(--color-ink-900)' }}>
      <div
        style={{
          maxWidth: 'var(--layout-max)', margin: '0 auto', padding: '0 34px', display: 'flex',
          alignItems: 'center', gap: 18, height: 40, overflowX: 'auto',
        }}
      >
        <span className="lbl" style={{ fontSize: 9, flex: 'none' }}>{section}</span>
        {items.map((r) => (
          <NavLink
            key={r.key}
            to={r.path.split('/:')[0] || r.path}
            style={({ isActive }) => ({
              fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
              whiteSpace: 'nowrap', textDecoration: 'none',
              color: isActive ? 'var(--color-text-100)' : 'var(--color-text-400)',
            })}
          >
            {r.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const section = sectionFor(pathname);
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ borderBottom: '1px solid var(--color-rule-900)' }}>
        <div
          style={{
            maxWidth: 'var(--layout-max)', margin: '0 auto', padding: '8px 34px', display: 'flex',
            alignItems: 'center', minHeight: 60, gap: 26, flexWrap: 'wrap', rowGap: 8,
          }}
        >
          <Link
            to="/"
            style={{
              fontSize: 16, fontWeight: 600, letterSpacing: '0.32em',
              textTransform: 'uppercase', color: 'var(--color-text-100)', textDecoration: 'none',
            }}
          >
            slomix
          </Link>
          {/* Wraps on narrow viewports as an interim measure; the real
              responsive pass is phase-1 design work (docs/design/08). */}
          <nav style={{ display: 'flex', gap: 20, flexWrap: 'wrap', rowGap: 6 }}>
            {PRIMARY.map((item) => {
              // Sectioned entries light up for their whole sub-navigation;
              // unsectioned ones by their own prefix (a `section === null`
              // comparison would short-circuit to false on their own pages —
              // Codex review on #802).
              const active = item.section !== null
                ? section === item.section
                : pathname === item.prefix || pathname.startsWith(`${item.prefix}/`);
              return (
                <Link
                  key={item.label}
                  to={item.to}
                  style={{
                    fontSize: 14, letterSpacing: '0.12em', textTransform: 'uppercase',
                    textDecoration: 'none', paddingBottom: 3,
                    color: active ? 'var(--color-text-100)' : '#9b968e',
                    borderBottom: `1px solid ${active ? 'var(--color-accent)' : 'transparent'}`,
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 18 }}>
            <span className="m" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--color-text-500)' }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#454340' }} />
              DEV
            </span>
            {/* Known limitation until phase 6 (auth flows): the OAuth
                callback returns to the legacy site, not to /app — the login
                round-trip works, the return location does not yet. */}
            <a
              href="/auth/login"
              style={{
                fontSize: 13, letterSpacing: '0.14em', textTransform: 'uppercase',
                color: 'var(--color-text-200)', textDecoration: 'none',
                border: '1px solid #33322e', padding: '7px 12px',
              }}
            >
              Connect ID
            </a>
          </div>
        </div>
      </div>

      {section && <SubNav section={section} />}

      <main style={{ flex: 1, width: '100%', maxWidth: 'var(--layout-max)', margin: '0 auto', padding: '0 34px', boxSizing: 'border-box' }}>
        <Outlet />
      </main>

      <footer style={{ borderTop: '1px solid var(--color-rule-900)', marginTop: 48 }}>
        <div
          className="m"
          style={{
            maxWidth: 'var(--layout-max)', margin: '0 auto', padding: '14px 34px', display: 'flex',
            justifyContent: 'space-between', fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--color-text-600)',
          }}
        >
          <span>slomix · kept since january 2025</span>
          <span style={{ display: 'flex', gap: 18 }}>
            <Link to="/system" style={{ color: 'inherit', textDecoration: 'none' }}>system</Link>
            <Link to="/smart-stats-diag" style={{ color: 'inherit', textDecoration: 'none' }}>diag</Link>
            <span>et:legacy stopwatch</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
