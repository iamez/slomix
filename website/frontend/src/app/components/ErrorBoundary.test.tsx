import { render, screen, fireEvent } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useParams } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary, RouteErrorBoundary } from './ErrorBoundary';
import { installErrorReporting } from '../lib/errorReporting';

/** A component that throws on demand, so a test can turn the failure off. */
function Boom({ throwing, message }: { throwing: boolean; message?: string }) {
  if (throwing) throw new Error(message ?? 'the page threw');
  return <div>the page rendered</div>;
}

function lastReport(): Record<string, unknown> | null {
  const mock = fetch as unknown as ReturnType<typeof vi.fn>;
  const call = [...mock.mock.calls].reverse().find(([url]) => String(url).includes('/api/client-error'));
  return call ? (JSON.parse((call[1] as { body: string }).body) as Record<string, unknown>) : null;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    window.__slomixErrorReportingInstalled = false;
    window.__slomixEarlyErrors = undefined;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
    // React logs the caught error; the noise is not the subject of the test.
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('shows the message and reports it, instead of leaving a blank page', () => {
    installErrorReporting();
    render(
      <ErrorBoundary viewId="story">
        <Boom throwing message="cannot read properties of undefined" />
      </ErrorBoundary>,
    );

    // The reader gets something to quote — the fastest bug report this
    // project gets is a person pasting the line they saw.
    expect(screen.getByText(/something in this page threw/)).toBeInTheDocument();
    expect(screen.getByText(/cannot read properties of undefined/)).toBeInTheDocument();

    // …and the server hears about it, with the route in the stack.
    const body = lastReport();
    expect(body).not.toBeNull();
    expect(body!.message).toBe('cannot read properties of undefined');
    expect(String(body!.stack)).toContain('story');
  });

  it('offers reload only, not retry, when a chunk is missing', () => {
    installErrorReporting();
    render(
      <ErrorBoundary viewId="proximity">
        <Boom throwing message="Failed to fetch dynamically imported module: /app/assets/x.js" />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/a piece of the site failed to load/)).toBeInTheDocument();
    // Retrying inside the same document re-renders against the same absent
    // file, so the button that promises it is not offered.
    expect(screen.queryByText(/try this page again/)).toBeNull();
    expect(screen.getByText(/reload the page/)).toBeInTheDocument();
  });

  it('lets a page bug be retried', () => {
    installErrorReporting();
    // Not a chunk failure: here retrying is meaningful, because the state
    // that produced the throw may be gone.
    render(
      <ErrorBoundary viewId="story">
        <Boom throwing />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/try this page again/)).toBeInTheDocument();
  });

  it('does not stay latched when the reader navigates to another session', () => {
    installErrorReporting();
    // The failure that motivates the key: /session-detail/145 throws,
    // /session-detail/154 is fine, and both match the SAME route pattern —
    // so without a per-pathname key React reuses the boundary element and
    // its hasError sticks, showing an error panel for a working page. The
    // navigation is a real one (a Link click), because MemoryRouter reads
    // initialEntries only at mount and a rerender would prove nothing.
    function Page() {
      const { id } = useParams();
      return (
        <>
          <Boom throwing={id === '145'} message={`session ${id} threw`} />
          <Link to="/session-detail/154">go to 154</Link>
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={['/session-detail/145']}>
        <Routes>
          <Route
            path="/session-detail/:id"
            element={<RouteErrorBoundary viewId="session-detail"><Page /></RouteErrorBoundary>}
          />
        </Routes>
        <Link to="/session-detail/154">escape hatch</Link>
      </MemoryRouter>,
    );
    expect(screen.getByText(/something in this page threw/)).toBeInTheDocument();

    // The link inside the page is gone with the page, so navigate from the
    // one outside the boundary — which is what a nav bar is.
    fireEvent.click(screen.getByText('escape hatch'));
    expect(screen.getByText('the page rendered')).toBeInTheDocument();
    expect(screen.queryByText(/something in this page threw/)).toBeNull();
  });

  it('recovers on retry when the cause is gone, and says so again when it is not', () => {
    installErrorReporting();
    // Retry re-renders the SAME element tree. That helps when the cause was
    // transient — a query that has since refetched — and it cannot help when
    // the render throws deterministically. Both are asserted, because a
    // button that silently does nothing is worse than no button.
    let failing = true;
    function Flaky() {
      if (failing) throw new Error('transient state threw');
      return <div>the page rendered</div>;
    }
    render(<ErrorBoundary viewId="story"><Flaky /></ErrorBoundary>);
    expect(screen.getByText(/something in this page threw/)).toBeInTheDocument();

    // Still broken: the panel comes back rather than a blank page.
    fireEvent.click(screen.getByText(/try this page again/));
    expect(screen.getByText(/something in this page threw/)).toBeInTheDocument();

    // Cause gone: the same click now recovers.
    failing = false;
    fireEvent.click(screen.getByText(/try this page again/));
    expect(screen.getByText('the page rendered')).toBeInTheDocument();
  });
});
