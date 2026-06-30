import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  viewId?: string;
}

// A lazy page chunk that 404s (e.g. a stale index referencing the previous
// deploy's hashed chunks) surfaces here, NOT in modern-route-host's mount catch,
// because React.lazy fetches the chunk later under Suspense. Detect that and do
// a one-time, cache-busted full reload so the browser pulls the fresh
// route-host.js + current chunk hashes. Guarded so a genuinely-missing chunk
// can't reload-loop (at most once per 15s).
function isChunkLoadError(error: unknown): boolean {
  const e = error as { message?: unknown; name?: unknown } | null | undefined;
  const text = String((e && (e.message ?? e.name)) || '');
  return /loading (?:css )?chunk|chunkloaderror|dynamically imported module|failed to fetch dynamically imported/i.test(text);
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[ErrorBoundary] ${this.props.viewId ?? 'unknown'}:`, error, errorInfo);
    if (isChunkLoadError(error)) {
      try {
        const KEY = 'modern-chunk-reload-at';
        const now = Date.now();
        const last = Number(sessionStorage.getItem(KEY) || 0);
        if (now - last > 15000) {
          sessionStorage.setItem(KEY, String(now));
          window.location.reload();
        }
      } catch {
        /* sessionStorage unavailable — fall through to the error panel */
      }
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-panel rounded-2xl p-8 mt-6 text-center">
          <div className="text-2xl font-bold text-red-400 mb-2">Something went wrong</div>
          <p className="text-slate-400 mb-4">
            Route: <code className="text-slate-300">{this.props.viewId ?? 'unknown'}</code>
          </p>
          <pre className="text-xs text-slate-500 bg-slate-950/80 rounded-xl p-4 overflow-auto text-left max-h-40">
            {this.state.error?.message}
          </pre>
          <div className="mt-4 flex items-center justify-center gap-2">
            <button
              className="px-4 py-2 bg-brand-blue/20 text-brand-blue rounded-lg hover:bg-brand-blue/30 transition"
              onClick={() => { this.setState({ hasError: false, error: null }); }}
            >
              Try again
            </button>
            <button
              className="px-4 py-2 bg-white/10 text-slate-200 rounded-lg hover:bg-white/20 transition"
              onClick={() => { window.location.reload(); }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
