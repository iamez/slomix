// Early error buffer — MUST load before the ES module scripts in index.html.
//
// Why this exists: a `<script type="module">`'s static imports all evaluate
// before any of that module's own top-level code runs. So installErrorReporting()
// called from inside app.js cannot catch a parse/init error thrown while app.js's
// ~40 imports are themselves being evaluated — by the time the install call runs,
// the failure already happened. This script registers listeners first and buffers
// whatever it sees; error-reporting.js drains the buffer once its real listeners
// are installed (Codex review on #578).
//
// Why it's a separate file rather than an inline <script>: docker/nginx/default.conf
// sends `script-src 'self' <cdns>` with no 'unsafe-inline', nonce, or hash, so an
// inline block is blocked outright in the Docker deployment — the bootstrap would
// silently not exist exactly where it's needed (Codex review on #578, second round).
// An external same-origin file satisfies `'self'`.
(function () {
    'use strict';

    // Hard cap: unlike sendReport() in error-reporting.js, this buffer has no
    // dedup and no per-session report limit, so an error inside a rAF/interval
    // loop could otherwise grow it without bound before the drain runs.
    var MAX_BUFFERED = 20;

    window.__slomixEarlyErrors = [];

    function push(entry) {
        // Once error-reporting.js has installed its own listeners, it owns
        // reporting — keep buffering off so later errors aren't both reported
        // normally AND retained here (double-handling + unbounded growth).
        if (window.__slomixErrorReportingInstalled) return;
        if (window.__slomixEarlyErrors.length >= MAX_BUFFERED) return;
        window.__slomixEarlyErrors.push(entry);
        // Make sure a drain is scheduled. Without this, anything buffered
        // after the first self-flush would sit here until pagehide.
        armFlush();
    }

    function onError(event) {
        if (!event.error && !event.message) return;
        push({
            message: event.message,
            stack: event.error && event.error.stack ? event.error.stack : null,
        });
    }

    function onRejection(event) {
        var reason = event.reason;
        var message = reason && reason.message ? reason.message : String(reason);
        var stack = reason && reason.stack ? reason.stack : null;
        push({ message: 'Unhandled rejection: ' + message, stack: stack });
    }

    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);

    // Self-flush fallback. Buffering alone assumed error-reporting.js would
    // eventually drain us — but it is imported *by* app.js, so the one failure
    // this bootstrap exists to catch (a static dependency of app.js throwing
    // during evaluation) is exactly the case where installErrorReporting()
    // never runs and the buffered entries sit in memory forever, never sent
    // (Codex review on #578). So if nobody has claimed reporting shortly after
    // load, POST what we have ourselves.
    var FLUSH_DELAY_MS = 5000;
    // Re-entrancy guard, NOT a once-only latch. The previous `flushed = true`
    // meant every error arriving after the first self-flush was buffered and
    // then never sent: when app.js's module graph fails permanently the
    // listeners below stay registered (teardown only runs if
    // error-reporting.js takes over, which by definition it hasn't here), so
    // push() kept appending, while this function — including the pagehide
    // handler — returned at the latch every time (Codex review on #578).
    //
    // Re-running is safe because a successful drain sets buffered.length = 0,
    // so nothing already sent can be sent twice.
    var flushing = false;

    function selfFlush() {
        if (flushing) return;
        if (window.__slomixErrorReportingInstalled) return;   // the real reporter took over
        var buffered = window.__slomixEarlyErrors;
        if (!buffered || !buffered.length) return;
        flushing = true;

        for (var i = 0; i < buffered.length; i++) {
            var entry = buffered[i];
            var body = JSON.stringify({
                message: String(entry.message || 'Unknown error').slice(0, 2000),
                stack: entry.stack ? String(entry.stack).slice(0, 2000) : null,
                page_url: String(window.location.href).slice(0, 500),
                user_agent: String(navigator.userAgent || '').slice(0, 300),
                timestamp: new Date().toISOString(),
            });
            try {
                // sendBeacon with a typed Blob sets both Content-Type and
                // Content-Length (the endpoint requires the latter) and
                // survives an unload mid-flight.
                var sent = false;
                if (navigator.sendBeacon) {
                    sent = navigator.sendBeacon(
                        '/api/client-error',
                        new Blob([body], { type: 'application/json' })
                    );
                }
                if (!sent && window.fetch) {
                    window.fetch('/api/client-error', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: body,
                        keepalive: true,
                    }).catch(function () { /* fire-and-forget */ });
                }
            } catch {
                /* never let reporting failure become a second error */
            }
        }
        buffered.length = 0;
        flushing = false;
    }

    // Arming is event-driven rather than a repeating interval: a page that
    // never errors should not carry a timer for its whole life. push() arms it
    // whenever something new lands, so errors occurring AFTER a drain still go
    // out while the page is open, instead of waiting for a pagehide that a
    // crashed tab never fires.
    var flushTimer = null;

    function armFlush() {
        if (flushTimer !== null) return;
        if (window.__slomixErrorReportingInstalled) return;
        flushTimer = setTimeout(function () {
            flushTimer = null;
            selfFlush();
        }, FLUSH_DELAY_MS);
    }

    armFlush();
    // Also flush on the way out, in case the page is closed before the timer.
    window.addEventListener('pagehide', selfFlush);

    // Called by error-reporting.js right after it drains the buffer, so these
    // bootstrap listeners stop running entirely rather than staying registered
    // alongside the real ones for the rest of the page's life.
    window.__slomixTeardownEarlyErrorCapture = function () {
        window.removeEventListener('error', onError);
        window.removeEventListener('unhandledrejection', onRejection);
        delete window.__slomixTeardownEarlyErrorCapture;
    };
})();
