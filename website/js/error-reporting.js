/**
 * Client-side error reporting (W4, docs/TASKS_FOR_SONNET_2026-07-29.md).
 *
 * Catches uncaught JS errors and unhandled promise rejections and POSTs a
 * small report to /api/client-error so a browser exception is visible
 * server-side without the visitor needing to have F12 open and paste it in.
 *
 * This is the legacy site's copy, imported directly as an ES module (same
 * pattern as route-registry.js). The React build has its own, logically
 * identical copy at website/frontend/src/lib/errorReporting.ts — NOT a
 * shared import: tsconfig.json has allowJs:false and include:["src"], so a
 * cross-directory JS import from the React build would fail type-checking.
 * If you change one, change the other.
 */

const ENDPOINT = '/api/client-error';
const MAX_FIELD_LENGTH = 2000;
const MAX_REPORTS_PER_LOAD = 20; // client-side backstop; the server also rate-limits per IP
const TRUNCATION_MARKER = '…[truncated]';
const INSTALL_FLAG = '__slomixErrorReportingInstalled';

let reportCount = 0;
const seenSignatures = new Set();

// Coerce anything that isn't a string (or null/undefined) to text before it
// reaches the string operations below. JS lets you reject with arbitrary
// values — `Promise.reject({message: 'failed', stack: {}})` hands us a truthy
// non-string stack, which threw on `.slice()` *inside the global rejection
// handler*, so the original failure was never reported at all. And even if it
// survived, a non-string field fails the backend's pydantic validation with a
// 422 (Codex review on #578).
function asText(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === 'string') return value;
    try {
        return typeof value === 'object' ? JSON.stringify(value) : String(value);
    } catch {
        // Circular structure, or a throwing toString/toJSON.
        return Object.prototype.toString.call(value);
    }
}

function truncate(value, maxLength = MAX_FIELD_LENGTH) {
    if (typeof value !== 'string') return value;
    // Slice to maxLength MINUS the marker's own length: the backend caps
    // fields at exactly maxLength (pydantic Field(max_length=...)), so
    // appending the marker AFTER a full-length slice produced a string
    // longer than the limit — every long stack/message got a 422 and the
    // fire-and-forget caller silently lost the entire report (Codex P1
    // review on #578).
    if (value.length <= maxLength) return value;
    return value.slice(0, maxLength - TRUNCATION_MARKER.length) + TRUNCATION_MARKER;
}

function sendReport(rawPayload) {
    if (reportCount >= MAX_REPORTS_PER_LOAD) return;

    // Normalize BEFORE any string operation — see asText().
    const payload = {
        message: asText(rawPayload.message),
        stack: asText(rawPayload.stack),
    };

    // Dedupe identical errors within the same page load (e.g. an error
    // thrown on every re-render) so one bug doesn't burn the whole
    // per-load/per-IP budget on a single duplicated report.
    const signature = `${payload.message}|${payload.stack ? payload.stack.slice(0, 200) : ''}`;
    if (seenSignatures.has(signature)) return;
    seenSignatures.add(signature);
    reportCount += 1;

    const body = JSON.stringify({
        message: truncate(payload.message || 'Unknown error'),
        stack: truncate(payload.stack || null),
        page_url: truncate(window.location.href, 500),
        user_agent: truncate(navigator.userAgent, 300),
        timestamp: new Date().toISOString(),
    });

    // keepalive: the report should still go out if the error happens during
    // page unload/navigation. Fire-and-forget — a failed report must never
    // itself throw and re-trigger this handler.
    fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
    }).catch(() => {
        // Reporting failure is not itself reportable — would risk a loop.
    });
}

export function installErrorReporting() {
    // Shared window-level guard: the legacy site (this file) and the React
    // bundle (errorReporting.ts) can both load in the same page session —
    // the legacy app.js always runs, and a modern route additionally loads
    // route-host.tsx, which also calls its own installErrorReporting().
    // Without this guard both install a full set of global listeners, so
    // every uncaught error gets POSTed and logged twice, burning the
    // server's 20/minute budget after 10 distinct errors (Codex review on
    // #578).
    if (window[INSTALL_FLAG]) return;
    window[INSTALL_FLAG] = true;

    // Drain anything the early bootstrap buffer (js/error-bootstrap.js,
    // registered before any module script) caught before these real listeners
    // existed — e.g. a parse/init error from one of this module's own sibling
    // imports evaluating before this function ever ran.
    if (Array.isArray(window.__slomixEarlyErrors)) {
        window.__slomixEarlyErrors.forEach((entry) => sendReport(entry));
        window.__slomixEarlyErrors = [];
    }
    // Then unregister the bootstrap's listeners: leaving them attached means
    // every later error is both reported here AND re-buffered there, and that
    // buffer has no dedup or per-session cap of its own (Codex review on #578,
    // second round). The bootstrap also self-guards on INSTALL_FLAG, so this is
    // belt-and-braces for the case where it loaded but this teardown hook
    // didn't (older cached copy).
    if (typeof window.__slomixTeardownEarlyErrorCapture === 'function') {
        window.__slomixTeardownEarlyErrorCapture();
    }

    window.addEventListener('error', (event) => {
        // Ignore resource load errors (img/script/css 404s fire 'error' too
        // but have no .message/.error — not a JS exception worth reporting).
        if (!event.error && !event.message) return;
        sendReport({
            message: event.message,
            stack: event.error && event.error.stack ? event.error.stack : null,
        });
    });

    window.addEventListener('unhandledrejection', (event) => {
        const reason = event.reason;
        const message = reason && reason.message ? reason.message : String(reason);
        const stack = reason && reason.stack ? reason.stack : null;
        sendReport({ message: `Unhandled rejection: ${message}`, stack });
    });
}
