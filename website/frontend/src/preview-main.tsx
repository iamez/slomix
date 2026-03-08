import { createRoot } from 'react-dom/client';
import { routeCatalog } from './runtime/catalog';
import './styles/route-host.css';

function PreviewApp() {
  return (
    <main className="slmx-preview-shell">
      <div className="slmx-preview-header">
        <div className="slmx-modern-kicker">Slomix Website Upgrade</div>
        <h1>Modern route workspace preview</h1>
        <p className="slmx-modern-body">
          This Vite app is for isolated route work. The production website still runs through
          <code> website/index.html </code>
          and the legacy hash router.
        </p>
      </div>

      <section className="slmx-preview-grid">
        {routeCatalog.map((route) => (
          <article className="slmx-preview-card" key={route.viewId}>
            <div className="slmx-preview-card-top">
              <span>{route.label}</span>
              <span className={`slmx-chip slmx-chip-wave-${route.migrationWave.toLowerCase()}`}>
                Wave {route.migrationWave}
              </span>
            </div>
            <div className="slmx-preview-mode">{route.mode}</div>
            <p>{route.description}</p>
            <div className="slmx-preview-meta">{route.surfaceType}</div>
          </article>
        ))}
      </section>
    </main>
  );
}

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Missing preview root element');
}

createRoot(rootElement).render(<PreviewApp />);
