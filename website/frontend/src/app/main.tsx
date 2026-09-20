import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, generatePath, Navigate, RouterProvider, useParams } from 'react-router';
import { QueryClientProvider } from '@tanstack/react-query';
import './tokens.css';
import { applyHashShim } from './hashShim';
import { AppShell } from './components/AppShell';
import { Pending } from './components/ui';
import { RouteErrorBoundary } from './components/ErrorBoundary';
import { installErrorReporting } from './lib/errorReporting';

// Route-level code splitting (audit 2026-09-07 B3: one 990 KB chunk, no
// splitting): every page is its own chunk, fetched on first navigation to
// it. The PAGES map below still names each page component, so
// routes.test.ts keeps reading the wiring from source unchanged.
const Landing = React.lazy(() => import('./pages/Landing').then((m) => ({ default: m.Landing })));
const NotFound = React.lazy(() => import('./pages/NotFound').then((m) => ({ default: m.NotFound })));
const About = React.lazy(() => import('./pages/About').then((m) => ({ default: m.About })));
const SystemPage = React.lazy(() => import('./pages/SystemPage').then((m) => ({ default: m.SystemPage })));
const SmartStatsDiag = React.lazy(() => import('./pages/SmartStatsDiag').then((m) => ({ default: m.SmartStatsDiag })));
const Home = React.lazy(() => import('./pages/Home').then((m) => ({ default: m.Home })));
const SessionsList = React.lazy(() => import('./pages/SessionsList').then((m) => ({ default: m.SessionsList })));
const Leaderboards = React.lazy(() => import('./pages/Leaderboards').then((m) => ({ default: m.Leaderboards })));
const RecordBook = React.lazy(() => import('./pages/RecordBook').then((m) => ({ default: m.RecordBook })));
const Awards = React.lazy(() => import('./pages/Awards').then((m) => ({ default: m.Awards })));
const MapsPage = React.lazy(() => import('./pages/MapsPage').then((m) => ({ default: m.MapsPage })));
const WeaponsPage = React.lazy(() => import('./pages/WeaponsPage').then((m) => ({ default: m.WeaponsPage })));
const FormPage = React.lazy(() => import('./pages/FormPage').then((m) => ({ default: m.FormPage })));
const RetroViz = React.lazy(() => import('./pages/RetroViz').then((m) => ({ default: m.RetroViz })));
const PlayerProfilePage = React.lazy(() => import('./pages/PlayerProfile').then((m) => ({ default: m.PlayerProfilePage })));
const ComparePage = React.lazy(() => import('./pages/ComparePage').then((m) => ({ default: m.ComparePage })));
const WrappedPage = React.lazy(() => import('./pages/WrappedPage').then((m) => ({ default: m.WrappedPage })));
const DesignCatalog = React.lazy(() => import('./pages/DesignCatalog').then((m) => ({ default: m.DesignCatalog })));
const Rivalries = React.lazy(() => import('./pages/Rivalries').then((m) => ({ default: m.Rivalries })));
const SessionDetail = React.lazy(() => import('./pages/SessionDetail').then((m) => ({ default: m.SessionDetail })));
const Proximity = React.lazy(() => import('./pages/Proximity').then((m) => ({ default: m.Proximity })));
const ProximityPlayerPage = React.lazy(() => import('./pages/ProximityPlayerPage').then((m) => ({ default: m.ProximityPlayerPage })));
const ProximityTeamsPage = React.lazy(() => import('./pages/ProximityTeamsPage').then((m) => ({ default: m.ProximityTeamsPage })));
const ProximityReplayPage = React.lazy(() => import('./pages/ProximityReplayPage').then((m) => ({ default: m.ProximityReplayPage })));
const SpiderWebPage = React.lazy(() => import('./pages/SpiderWebPage').then((m) => ({ default: m.SpiderWebPage })));
const AvailabilityPage = React.lazy(() => import('./pages/AvailabilityPage').then((m) => ({ default: m.AvailabilityPage })));
const UploadsPage = React.lazy(() => import('./pages/UploadsPage').then((m) => ({ default: m.UploadsPage })));
const UploadDetailPage = React.lazy(() => import('./pages/UploadsPage').then((m) => ({ default: m.UploadDetailPage })));
const GreatshotPage = React.lazy(() => import('./pages/GreatshotPage').then((m) => ({ default: m.GreatshotPage })));
const GreatshotDemoPage = React.lazy(() => import('./pages/GreatshotPage').then((m) => ({ default: m.GreatshotDemoPage })));
const LivePage = React.lazy(() => import('./pages/LivePage').then((m) => ({ default: m.LivePage })));
const SkillRating = React.lazy(() => import('./pages/SkillRating').then((m) => ({ default: m.SkillRating })));
import { makeQueryClient } from './lib/queries';
import { APP_ROUTES, PARAM_REDIRECTS, REDIRECTS } from './routes';

// Must run before the router reads window.location (docs/design/06 §3).
applyHashShim('/app');

// Before the first render, so an error thrown while mounting is reported
// rather than lost. The install is idempotent and shares its window flag with
// the legacy site's copy, so a document that somehow loads both does not
// double-report and burn the server's per-IP budget twice as fast.
installErrorReporting();

/**
 * Phase 0: every route renders a stub inside the real shell — the point is
 * that both sites are alive at once (/ legacy, /app/ this) and that routing,
 * tokens and navigation are load-bearing before any page content exists.
 * Phases 1+ replace stubs route by route (docs/design/08).
 */
function Stub({ label, phase }: { label: string; phase: number }) {
  return (
    <div style={{ paddingTop: 'var(--space-7)' }}>
      <div className="lbl">phase {phase} · not built yet</div>
      <h1
        style={{
          fontSize: 'var(--fs-display)', letterSpacing: '0.04em', textTransform: 'uppercase',
          lineHeight: 1.05, margin: 'var(--space-3) 0 0', fontWeight: 500,
        }}
      >
        {label}
      </h1>
      <p style={{ color: 'var(--color-text-400)', maxWidth: '44em' }}>
        This route is registered and reachable — its content arrives in build
        phase {phase}. The legacy page at <a href="/" style={{ color: 'var(--color-accent)' }}>/</a> remains
        the source of truth until parity is proven.
      </p>
    </div>
  );
}

/** A retired path whose parameter travels to the new one: /story/session/154
 *  becomes /session-detail/154/story. `generatePath` substitutes the params
 *  the matched pattern captured; a literal Navigate could not. */
function ParamRedirect({ to }: { to: string }) {
  const params = useParams();
  return <Navigate to={generatePath(to, params)} replace />;
}

/** Built pages replace their stubs route by route as phases land. */
const PAGES: Record<string, React.ReactElement> = {
  landing: <Landing />,
  admin: <About />,
  system: <SystemPage />,
  'smart-stats-diag': <SmartStatsDiag />,
  home: <Home />,
  sessions: <SessionsList />,
  leaderboards: <Leaderboards />,
  'record-book': <RecordBook />,
  awards: <Awards />,
  maps: <MapsPage />,
  weapons: <WeaponsPage />,
  form: <FormPage />,
  'retro-viz': <RetroViz />,
  profile: <PlayerProfilePage />,
  compare: <ComparePage />,
  wrapped: <WrappedPage />,
  design: <DesignCatalog />,
  rivalries: <Rivalries />,
  'skill-rating': <SkillRating />,
  proximity: <Proximity />,
  'proximity-player': <ProximityPlayerPage />,
  'proximity-replay': <ProximityReplayPage />,
  availability: <AvailabilityPage />,
  greatshot: <GreatshotPage />,
  'greatshot-demo': <GreatshotDemoPage />,
  live: <LivePage />,
  uploads: <UploadsPage />,
  'upload-detail': <UploadDetailPage />,
  'spider-web': <SpiderWebPage />,
  'proximity-teams': <ProximityTeamsPage />,
  'session-detail': <SessionDetail />,
  'session-detail-date': <SessionDetail />,
};

const router = createBrowserRouter(
  [
    {
      element: <AppShell />,
      children: [
        // One boundary per route, and RouteErrorBoundary keys it by pathname
        // so it cannot stay latched across a navigation — a boundary is
        // state, and `hasError` does not clear itself. The route key travels
        // into the report too, which is the difference between "the app
        // threw" and "the story page threw".
        ...APP_ROUTES.map((r) => ({
          path: r.path,
          element: (
            <RouteErrorBoundary viewId={r.key}>
              <React.Suspense fallback={<Pending label={r.label.toLowerCase()} />}>
                {PAGES[r.key] ?? <Stub label={r.label} phase={r.phase} />}
              </React.Suspense>
            </RouteErrorBoundary>
          ),
        })),
        // Stats 2.0 (docs/design/18): the two archives became one. Old links
        // and bookmarks keep working — a redirect, not a 404 and not a stub.
        ...REDIRECTS.map((r) => ({ path: r.from, element: <Navigate to={r.to} replace /> })),
        ...PARAM_REDIRECTS.map((r) => ({ path: r.from, element: <ParamRedirect to={r.to} /> })),
        { path: '*', element: <NotFound /> },
      ],
    },
  ],
  { basename: '/app' },
);

const queryClient = makeQueryClient();

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('app.html is missing #root');
ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
