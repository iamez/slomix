import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { QueryClientProvider } from '@tanstack/react-query';
import './tokens.css';
import { applyHashShim } from './hashShim';
import { AppShell } from './components/AppShell';
import { RouteErrorBoundary } from './components/ErrorBoundary';
import { installErrorReporting } from './lib/errorReporting';
import { Landing } from './pages/Landing';
import { About } from './pages/About';
import { SystemPage } from './pages/SystemPage';
import { SmartStatsDiag } from './pages/SmartStatsDiag';
import { Home } from './pages/Home';
import { SessionsList } from './pages/SessionsList';
import { Leaderboards } from './pages/Leaderboards';
import { RecordBook } from './pages/RecordBook';
import { Awards } from './pages/Awards';
import { MapsPage } from './pages/MapsPage';
import { WeaponsPage } from './pages/WeaponsPage';
import { FormPage } from './pages/FormPage';
import { RetroViz } from './pages/RetroViz';
import { PlayerProfilePage } from './pages/PlayerProfile';
import { DesignCatalog } from './pages/DesignCatalog';
import { Rivalries } from './pages/Rivalries';
import { SessionDetail } from './pages/SessionDetail';
import { Story } from './pages/Story';
import { Proximity } from './pages/Proximity';
import { ProximityPlayerPage } from './pages/ProximityPlayerPage';
import { ProximityTeamsPage } from './pages/ProximityTeamsPage';
import { ProximityReplayPage } from './pages/ProximityReplayPage';
import { SpiderWebPage } from './pages/SpiderWebPage';
import { AvailabilityPage } from './pages/AvailabilityPage';
import { SkillRating } from './pages/SkillRating';
import { RoundsPage } from './pages/RoundsPage';
import { makeQueryClient } from './lib/queries';
import { APP_ROUTES } from './routes';

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

/** Built pages replace their stubs route by route as phases land. */
const PAGES: Record<string, React.ReactElement> = {
  landing: <Landing />,
  admin: <About />,
  system: <SystemPage />,
  'smart-stats-diag': <SmartStatsDiag />,
  home: <Home />,
  sessions: <SessionsList box={false} />,
  sessions2: <SessionsList box />,
  leaderboards: <Leaderboards />,
  'record-book': <RecordBook />,
  awards: <Awards />,
  maps: <MapsPage />,
  weapons: <WeaponsPage />,
  form: <FormPage />,
  'retro-viz': <RetroViz />,
  profile: <PlayerProfilePage />,
  design: <DesignCatalog />,
  rivalries: <Rivalries />,
  'skill-rating': <SkillRating />,
  rounds: <RoundsPage />,
  story: <Story />,
  'story-session': <Story />,
  // All three story routes mount the same page — the date variant included,
  // which is the one that would otherwise render a stub while its tests pass
  // (they mount the component directly; only the registry decides what the
  // BROWSER gets). Found by the route sweep's own gap: a stub answers 200
  // and renders cleanly, so "the sweep is green" says nothing about whether
  // the right component is behind the route.
  'story-date': <Story />,
  proximity: <Proximity />,
  'proximity-player': <ProximityPlayerPage />,
  'proximity-replay': <ProximityReplayPage />,
  availability: <AvailabilityPage />,
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
              {PAGES[r.key] ?? <Stub label={r.label} phase={r.phase} />}
            </RouteErrorBoundary>
          ),
        })),
        { path: '*', element: <Stub label="Not found" phase={0} /> },
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
