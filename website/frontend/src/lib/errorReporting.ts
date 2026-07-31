/**
 * Client-side error reporting (W4, docs/TASKS_FOR_SONNET_2026-07-29.md).
 *
 * Mirrors website/js/error-reporting.js (the legacy site's copy) field-for-field
 * so both frontends land in the same logs/client_errors.log shape. Kept as a
 * separate TS file rather than importing the legacy .js directly: tsconfig.json
 * has allowJs: false and include: ["src"], so a cross-directory JS import would
 * fail type-checking. If you change one, change the other.
 */

declare global {
  interface Window {
    __slomixErrorReportingInstalled?: boolean;
    __slomixEarlyErrors?: Array<{ message: string; stack: string | null }>;
    __slomixTeardownEarlyErrorCapture?: () => void;
  }
}

const ENDPOINT = '/api/client-error';
const MAX_FIELD_LENGTH = 2000;
const MAX_REPORTS_PER_LOAD = 20; // client-side backstop; the server also rate-limits per IP
const TRUNCATION_MARKER = '…[truncated]';

let reportCount = 0;
const seenSignatures = new Set<string>();

function truncate(value: string | null | undefined, maxLength = MAX_FIELD_LENGTH): string | null {
  if (typeof value !== 'string') return null;
  // Slice to maxLength MINUS the marker's own length — see error-reporting.js
  // for the full explanation (Codex P1 review on #578: the backend caps
  // fields at exactly maxLength, so appending the marker after a full-length
  // slice produced an over-limit string that 422'd and silently dropped the
  // whole report).
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength - TRUNCATION_MARKER.length) + TRUNCATION_MARKER;
}

// Coerce non-strings to text before any string operation. TypeScript's types
// don't protect this: a rejection reason is `any` at runtime, so
// `Promise.reject({message: 'failed', stack: {}})` reaches here with a truthy
// non-string stack and threw on `.slice()` inside the global rejection handler,
// losing the original failure entirely (Codex review on #578).
function asText(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') return value;
  try {
    return typeof value === 'object' ? JSON.stringify(value) : String(value);
  } catch {
    return Object.prototype.toString.call(value);
  }
}

function sendReport(rawPayload: { message?: unknown; stack?: unknown }): void {
  if (reportCount >= MAX_REPORTS_PER_LOAD) return;

  const payload = { message: asText(rawPayload.message), stack: asText(rawPayload.stack) };

  const signature = `${payload.message}|${payload.stack ? payload.stack.slice(0, 200) : ''}`;
  if (seenSignatures.has(signature)) return;
  seenSignatures.add(signature);
  reportCount += 1;

  const body = JSON.stringify({
    message: truncate(payload.message) || 'Unknown error',
    stack: truncate(payload.stack ?? null),
    page_url: truncate(window.location.href, 500),
    user_agent: truncate(navigator.userAgent, 300),
    timestamp: new Date().toISOString(),
  });

  fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => {
    // Reporting failure is not itself reportable — would risk a loop.
  });
}

/**
 * Report an error caught outside the global window handlers — specifically
 * React's ErrorBoundary. componentDidCatch handles render/lifecycle/lazy-chunk
 * failures WITHOUT rethrowing them as a window 'error' event, so every modern
 * page's most common fatal-UI failure class was never reported even though
 * this module was installed (Codex P1 review on #578). Call from
 * componentDidCatch with the component stack appended for context.
 */
export function reportCaughtError(error: Error, componentStack?: string | null): void {
  sendReport({
    message: error.message || String(error),
    stack: componentStack ? `${error.stack ?? ''}\n\nComponent stack:${componentStack}` : error.stack ?? null,
  });
}

export function installErrorReporting(): void {
  // Shared window-level guard: the legacy site (error-reporting.js, via
  // app.js) always runs, and a modern route additionally loads this bundle,
  // which also calls installErrorReporting(). Without this guard both
  // install a full set of global listeners, so every uncaught error gets
  // POSTed and logged twice, burning the server's 20/minute budget after 10
  // distinct errors (Codex review on #578).
  if (window.__slomixErrorReportingInstalled) return;
  window.__slomixErrorReportingInstalled = true;

  // Drain the early bootstrap buffer (js/error-bootstrap.js) in case this
  // bundle is ever the first reporter to install.
  if (Array.isArray(window.__slomixEarlyErrors)) {
    window.__slomixEarlyErrors.forEach((entry) => sendReport(entry));
    window.__slomixEarlyErrors = [];
  }
  // Unregister the bootstrap's listeners so later errors aren't both reported
  // here and re-buffered there (that buffer has no dedup or per-session cap).
  if (typeof window.__slomixTeardownEarlyErrorCapture === 'function') {
    window.__slomixTeardownEarlyErrorCapture();
  }

  window.addEventListener('error', (event: ErrorEvent) => {
    if (!event.error && !event.message) return;
    sendReport({
      message: event.message,
      stack: event.error && event.error.stack ? event.error.stack : null,
    });
  });

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const reason = event.reason;
    const message = reason && reason.message ? reason.message : String(reason);
    const stack = reason && reason.stack ? reason.stack : null;
    sendReport({ message: `Unhandled rejection: ${message}`, stack });
  });
}
