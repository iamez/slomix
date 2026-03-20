const BUILD_VERSION = '20260315-session-tabs-v2';
const MODERN_ENTRY_URL = `/static/modern/route-host.js?v=${BUILD_VERSION}`;
const MODERN_STYLESHEET_URL = `/static/modern/route-host.css?v=${BUILD_VERSION}`;

let runtimePromise = null;
let activeMount = null;

function ensureHost(viewElement) {
    let host = viewElement.querySelector('[data-modern-route-root]');
    if (!host) {
        // Hide legacy template children so only the modern root is visible
        for (const child of Array.from(viewElement.children)) {
            child.setAttribute('data-legacy-hidden', 'true');
            child.style.display = 'none';
        }
        host = document.createElement('div');
        host.dataset.modernRouteRoot = 'true';
        host.className = 'modern-route-root';
        viewElement.appendChild(host);
    }
    return host;
}

function ensureStylesheet() {
    if (document.querySelector(`link[data-modern-route-css="${MODERN_STYLESHEET_URL}"]`)) {
        return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = MODERN_STYLESHEET_URL;
    link.dataset.modernRouteCss = MODERN_STYLESHEET_URL;
    document.head.appendChild(link);
}

function renderUnavailable(host, viewId, error = null) {
    host.innerHTML = `
        <div class="glass-panel border border-slate-700 rounded-2xl p-6 mt-6">
            <div class="text-xs font-bold uppercase tracking-[0.3em] text-brand-amber">Modern Route Offline</div>
            <div class="mt-3 text-2xl font-black text-white">${viewId}</div>
            <p class="mt-3 text-sm text-slate-300">
                The modern renderer is not built yet for this route. Switch the route back to
                <code class="text-slate-100">legacy</code> or run the Vite build into
                <code class="text-slate-100">/website/static/modern/</code>.
            </p>
            ${error ? `<pre class="mt-4 rounded-xl bg-slate-950/80 p-4 text-xs text-slate-400 overflow-auto">${String(error.message || error)}</pre>` : ''}
        </div>
    `;
}

async function loadModernRuntime() {
    if (!runtimePromise) {
        runtimePromise = import(MODERN_ENTRY_URL).catch((error) => {
            runtimePromise = null;
            throw error;
        });
    }
    return runtimePromise;
}

export function resetModernRouteHost(exceptViewId = null) {
    if (!activeMount) {
        return;
    }
    if (exceptViewId && activeMount.viewId === exceptViewId) {
        return;
    }
    if (typeof activeMount.unmount === 'function') {
        activeMount.unmount();
    }
    activeMount.host.replaceChildren();
    activeMount = null;
}

export async function mountModernRoute({ viewId, params = {}, viewElement }) {
    if (!viewElement) {
        return;
    }

    if (activeMount && typeof activeMount.unmount === 'function') {
        activeMount.unmount();
        activeMount = null;
    }

    ensureStylesheet();
    const host = ensureHost(viewElement);

    try {
        const runtime = await loadModernRuntime();
        if (!runtime || typeof runtime.mountRoute !== 'function') {
            throw new Error('The modern route host did not export mountRoute().');
        }
        const mounted = await runtime.mountRoute(host, { viewId, params });
        activeMount = {
            viewId,
            host,
            unmount: mounted && typeof mounted.unmount === 'function' ? mounted.unmount : null,
        };
    } catch (error) {
        console.error(`Failed to mount modern route ${viewId}:`, error);
        renderUnavailable(host, viewId, error);
    }
}
