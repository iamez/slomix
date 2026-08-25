import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { QueryClientProvider } from '@tanstack/react-query';
import './tokens.css';
import { applyHashShim } from './hashShim';
import { AppShell } from './components/AppShell';
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
import { makeQueryClient } from './lib/queries';
import { APP_ROUTES } from './routes';

// Must run before the router reads window.location (docs/design/06 §3).
applyHashShim('/app');

/**
 * Phase 0: every route renders a stub inside the real shell — the point is
 * that both sites are alive at once (/ legacy, /app/ this) and that routing,
 * tokens and navigation are load-bearing before any page content exists.
 * Phases 1+ replace stubs route by route (docs/design/08).
 */
function Stub({ label, phase }: { label: string; phase: number }) {
  return (
    <div style={{ paddingTop: 44 }}>
      <div className="lbl">phase {phase} · not built yet</div>
      <h1
        style={{
          fontSize: 40, letterSpacing: '0.04em', textTransform: 'uppercase',
          lineHeight: 1.05, margin: '12px 0 0', fontWeight: 500,
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
};

const router = createBrowserRouter(
  [
    {
      element: <AppShell />,
      children: [
        ...APP_ROUTES.map((r) => ({
          path: r.path,
          element: PAGES[r.key] ?? <Stub label={r.label} phase={r.phase} />,
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
