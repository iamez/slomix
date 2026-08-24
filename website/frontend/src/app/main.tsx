import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';
import './tokens.css';
import { applyHashShim } from './hashShim';
import { AppShell } from './components/AppShell';
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

const router = createBrowserRouter(
  [
    {
      element: <AppShell />,
      children: [
        ...APP_ROUTES.map((r) => ({
          path: r.path,
          element: <Stub label={r.label} phase={r.phase} />,
        })),
        { path: '*', element: <Stub label="Not found" phase={0} /> },
      ],
    },
  ],
  { basename: '/app' },
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
