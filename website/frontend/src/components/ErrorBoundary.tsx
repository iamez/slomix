import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isChunkLoadError, reportCaughtError } from '../app/lib/errorReporting';

interface Props {
  children: ReactNode;
  viewId?: string;
}

// The chunk-failure question now lives in app/lib/errorReporting, so both
// boundaries ask it the same way. What THIS boundary does with the answer is
// unchanged: a one-time, cache-busted reload, guarded so a genuinely-missing
// chunk cannot reload-loop (at most once per 15 s).
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
    // componentDidCatch handles render/lifecycle/lazy-chunk failures without
    // rethrowing as a window 'error' event, so without this call the global
    // listeners in errorReporting.ts never see the most common fatal-UI
    // failure class on modern pages (Codex P1 review on #578).
    reportCaughtError(error, `${this.props.viewId ?? 'unknown'}${errorInfo.componentStack ?? ''}`);
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
