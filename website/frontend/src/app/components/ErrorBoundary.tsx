import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { isChunkLoadError, reportCaughtError } from '../lib/errorReporting';
import { Lbl } from './ui';
import { Cluster, Stack } from './layout';

/**
 * The last thing between a render error and a blank page.
 *
 * Until now the new SPA had neither this nor the global handlers: a component
 * that threw took the whole document down to an empty <div id="root">, the
 * reader saw nothing at all, and nothing reached the server log either. Every
 * page here already distinguishes "no data" from "unavailable" panel by
 * panel; a white page is the one state that says neither.
 *
 * Two failures, told apart, because the useful action differs:
 *
 *   a lazily-loaded chunk that is not there — a stale index pointing at the
 *   previous deploy's hashed filenames — is fixed by reloading, and no
 *   amount of "try again" inside the same document will find a missing file;
 *
 *   anything else is a bug in the page, where re-rendering the same broken
 *   state is exactly what "try again" should NOT do silently. The message is
 *   printed rather than hidden, because a reader who can quote the error is
 *   the fastest bug report this project gets.
 *
 * The chunk reload is guarded at one per 15 s (sessionStorage), so a chunk
 * that is genuinely gone cannot turn into a reload loop — the same guard the
 * older tree's boundary carries, and for the same measured reason.
 */

interface Props {
  children: ReactNode;
  /** Which route this boundary wraps; travels with the report. */
  viewId?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

const RELOAD_KEY = 'app-chunk-reload-at';
const RELOAD_GUARD_MS = 15000;

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // componentDidCatch handles render/lifecycle/lazy-chunk failures WITHOUT
    // rethrowing them as a window 'error' event, so the global listeners
    // never see this class at all — which is the most common fatal-UI
    // failure on a React page (Codex P1 on #578, learned on the older tree).
    reportCaughtError(error, `${this.props.viewId ?? 'app'}${errorInfo.componentStack ?? ''}`);

    if (isChunkLoadError(error)) {
      try {
        const now = Date.now();
        const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0);
        if (now - last > RELOAD_GUARD_MS) {
          sessionStorage.setItem(RELOAD_KEY, String(now));
          window.location.reload();
        }
      } catch {
        /* sessionStorage unavailable — fall through to the panel below */
      }
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const chunk = isChunkLoadError(this.state.error);
    return (
      <Stack gap={3} style={{ paddingTop: 'var(--space-7)', maxWidth: '62ch' }} data-parity="app.error">
        <Lbl>this page stopped</Lbl>
        <span style={{ fontSize: 'var(--fs-lead)' }}>
          {chunk
            ? 'a piece of the site failed to load'
            : 'something in this page threw'}
        </span>
        <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
          {chunk
            ? 'usually a page left open across a deploy, still asking for files that were replaced. Reloading picks up the current ones.'
            : 'the error was reported. Reloading gives a clean page; if it happens again, the message below is the useful half of a bug report.'}
        </span>
        {this.state.error?.message && (
          <pre
            className="m"
            style={{
              fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)',
              whiteSpace: 'pre-wrap', overflowX: 'auto', margin: 0,
            }}
          >
            {this.state.error.message}
          </pre>
        )}
        <Cluster gap={3}>
          <button type="button" className="chip" onClick={() => { window.location.reload(); }}>
            reload the page
          </button>
          {/* Only offered for a page bug: retrying a missing chunk in the
            * same document re-renders against the same absent file. */}
          {!chunk && (
            <button
              type="button"
              className="chip"
              onClick={() => { this.setState({ hasError: false, error: null }); }}
            >
              try this page again
            </button>
          )}
        </Cluster>
      </Stack>
    );
  }
}

/**
 * The boundary as the router should mount it: keyed by the URL.
 *
 * A boundary is a piece of STATE, and `hasError` does not clear itself. One
 * boundary per route pattern is not enough, because a pattern outlives its
 * parameters: throw on /session-detail/145, click through to
 * /session-detail/154, and React reuses the same element — the reader stays
 * on the error panel while looking at a page that works. Keying by pathname
 * remounts the boundary on every navigation, which is the only thing that
 * actually resets it.
 */
export function RouteErrorBoundary({ viewId, children }: { viewId: string; children: ReactNode }) {
  const { pathname } = useLocation();
  return <ErrorBoundary key={pathname} viewId={viewId}>{children}</ErrorBoundary>;
}
