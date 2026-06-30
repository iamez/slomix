const BUILD_VERSION = '20260323-skill-rating-v1';
const MODERN_ENTRY_URL = `/static/modern/route-host.js?v=${BUILD_VERSION}`;
const MODERN_STYLESHEET_URL = `/static/modern/route-host.css?v=${BUILD_VERSION}`;

let runtimePromise = null;
let activeMount = null;

// Local HTML-escape for the failure panel (viewId / error text are interpolated
// into innerHTML; escape them so any user-influenced string can't inject markup).
function esc(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

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
            <div class="text-xs font-bold uppercase tracking-[0.3em] text-brand-amber">Couldn't load this view</div>
            <div class="mt-3 text-2xl font-black text-white">${esc(viewId)}</div>
            <p class="mt-3 text-sm text-slate-300">
                This view failed to load (it may be mid-deploy or a temporary network hiccup).
                Try reloading — if it persists it usually clears after the next deploy.
            </p>
            <button type="button" onclick="location.reload()"
                class="mt-4 px-4 py-2 rounded-lg text-sm font-bold bg-brand-cyan/20 text-brand-cyan hover:bg-brand-cyan/30">
                Reload
            </button>
            ${error ? `<pre class="mt-4 rounded-xl bg-slate-950/80 p-4 text-xs text-slate-400 overflow-auto">${esc(error.message || error)}</pre>` : ''}
        </div>
    `;
}

async function loadModernRuntime(forceFresh = false) {
    if (forceFresh) {
        // Drop the cached (failed) promise and bust any stale/poisoned cache entry
        // for a transient chunk/network failure (e.g. a 404 cached right after a
        // deploy). The runtime URL gets a one-shot cache-buster.
        runtimePromise = null;
    }
    if (!runtimePromise) {
        const url = forceFresh ? `${MODERN_ENTRY_URL}&_=${Date.now()}` : MODERN_ENTRY_URL;
        runtimePromise = import(url).catch((error) => {
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

    // Restore legacy children that were hidden by ensureHost()
    const viewElement = activeMount.host.parentElement;
    if (viewElement) {
        for (const child of Array.from(viewElement.querySelectorAll('[data-legacy-hidden="true"]'))) {
            child.style.display = '';
            child.removeAttribute('data-legacy-hidden');
        }
    }

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

    const attempt = async (forceFresh) => {
        const runtime = await loadModernRuntime(forceFresh);
        if (!runtime || typeof runtime.mountRoute !== 'function') {
            throw new Error('The modern route host did not export mountRoute().');
        }
        const mounted = await runtime.mountRoute(host, { viewId, params });
        activeMount = {
            viewId,
            host,
            unmount: mounted && typeof mounted.unmount === 'function' ? mounted.unmount : null,
        };
    };

    try {
        await attempt(false);
    } catch (firstError) {
        // One retry with a fresh, cache-busted import — handles a transient chunk/
        // network failure (common right after a deploy) before showing the panel.
        console.warn(`Modern route ${viewId} failed to mount, retrying once:`, firstError);
        try {
            await attempt(true);
        } catch (error) {
            console.error(`Failed to mount modern route ${viewId} (after retry):`, error);
            renderUnavailable(host, viewId, error);
        }
    }
}
